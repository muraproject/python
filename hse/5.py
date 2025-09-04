import cv2
from ultralytics import YOLO
import numpy as np
import math
import threading
import time
import os
from datetime import datetime
import queue
from collections import deque

def calculate_distance(box1, box2):
    """Hitung jarak antara center point dua bounding box"""
    center1 = ((box1[0] + box1[2]) / 2, (box1[1] + box1[3]) / 2)
    center2 = ((box2[0] + box2[2]) / 2, (box2[1] + box2[3]) / 2)
    return math.sqrt((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)

def calculate_iou(box1, box2):
    """Hitung Intersection over Union (IoU) antara dua bounding box"""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    if x2 <= x1 or y2 <= y1:
        return 0
    
    intersection = (x2 - x1) * (y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection
    
    return intersection / union if union > 0 else 0

def is_overlap_or_nearby(person_box, safety_box, distance_threshold=100, iou_threshold=0.1):
    """Cek apakah safety equipment berada dekat atau overlap dengan person"""
    iou = calculate_iou(person_box, safety_box)
    if iou > iou_threshold:
        return True
    
    distance = calculate_distance(person_box, safety_box)
    if distance < distance_threshold:
        return True
    
    person_center_x = (person_box[0] + person_box[2]) / 2
    person_top = person_box[1]
    safety_center_x = (safety_box[0] + safety_box[2]) / 2
    safety_bottom = safety_box[3]
    
    if abs(person_center_x - safety_center_x) < 50 and safety_bottom <= person_top + 80:
        return True
    
    return False

def check_safety_compliance(persons, hardhats, safety_vests):
    """Cek compliance safety untuk setiap person"""
    compliance_results = []
    
    for person in persons:
        person_box = person['bbox']
        has_hardhat = False
        has_safety_vest = False
        
        for hardhat in hardhats:
            if is_overlap_or_nearby(person_box, hardhat['bbox']):
                has_hardhat = True
                break
        
        for vest in safety_vests:
            if is_overlap_or_nearby(person_box, vest['bbox'], distance_threshold=80):
                has_safety_vest = True
                break
        
        compliance_results.append({
            'person': person,
            'has_hardhat': has_hardhat,
            'has_safety_vest': has_safety_vest,
            'compliant': has_hardhat and has_safety_vest
        })
    
    return compliance_results

def detect_objects(model, frame):
    """Deteksi objek dalam frame"""
    results = model(frame)
    persons = []
    hardhats = []
    safety_vests = []
    
    for r in results:
        boxes = r.boxes
        if boxes is not None:
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0]
                confidence = box.conf[0]
                class_id = box.cls[0]
                class_name = model.names[int(class_id)]
                
                if confidence < 0.5:
                    continue
                
                detection = {
                    'bbox': (int(x1), int(y1), int(x2), int(y2)),
                    'confidence': float(confidence),
                    'class_name': class_name
                }
                
                if class_name == 'Person':
                    persons.append(detection)
                elif class_name == 'Hardhat':
                    hardhats.append(detection)
                elif class_name == 'Safety Vest':
                    safety_vests.append(detection)
    
    return persons, hardhats, safety_vests

def draw_annotations(frame, compliance_results, hardhats, safety_vests, frame_info=""):
    """Gambar annotations pada frame"""
    annotated_frame = frame.copy()
    
    # Gambar safety equipment
    for hardhat in hardhats:
        x1, y1, x2, y2 = hardhat['bbox']
        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (128, 128, 128), 1)
        cv2.putText(annotated_frame, f"Helmet {hardhat['confidence']:.2f}", 
                   (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 128), 1)
    
    for vest in safety_vests:
        x1, y1, x2, y2 = vest['bbox']
        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (128, 128, 128), 1)
        cv2.putText(annotated_frame, f"Vest {vest['confidence']:.2f}", 
                   (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 128), 1)
    
    # Gambar person dengan compliance status
    violations = 0
    for result in compliance_results:
        person = result['person']
        x1, y1, x2, y2 = person['bbox']
        
        if result['compliant']:
            color = (0, 255, 0)  # Hijau
            status = "COMPLIANT"
        else:
            color = (0, 0, 255)  # Merah
            status = "VIOLATION"
            violations += 1
        
        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 3)
        
        missing_items = []
        if not result['has_hardhat']:
            missing_items.append("HELM")
        if not result['has_safety_vest']:
            missing_items.append("VEST")
        
        detail = f"Missing: {', '.join(missing_items)}" if missing_items else "Complete Safety"
        
        cv2.putText(annotated_frame, f"{status} {person['confidence']:.2f}", 
                   (x1, y1-25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        cv2.putText(annotated_frame, detail, 
                   (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    # Info header
    cv2.putText(annotated_frame, frame_info, 
               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    return annotated_frame, violations

class ScreenshotProcessor:
    """Background thread untuk processing screenshot"""
    
    def __init__(self, model, screenshot_dir="screenshots"):
        self.model = model
        self.screenshot_dir = screenshot_dir
        self.frame_queue = queue.Queue(maxsize=10)  # Buffer untuk frame yang akan diproses
        self.running = False
        self.processed_count = 0
        self.violation_count = 0
        
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)
            
        print(f"Screenshot processor initialized. Saving to: {self.screenshot_dir}")
    
    def add_frame(self, frame, frame_number):
        """Tambahkan frame ke queue untuk diproses"""
        try:
            # Hanya tambahkan jika queue tidak penuh
            if not self.frame_queue.full():
                self.frame_queue.put((frame.copy(), frame_number), block=False)
            else:
                # Skip frame jika queue penuh untuk menghindari delay pada live video
                pass
        except queue.Full:
            pass
    
    def process_frame_detailed(self, frame, frame_number):
        """Process frame dengan detail analysis untuk screenshot"""
        try:
            # Deteksi objek
            persons, hardhats, safety_vests = detect_objects(self.model, frame)
            compliance_results = check_safety_compliance(persons, hardhats, safety_vests)
            
            # Hitung violations
            violations = sum(1 for result in compliance_results if not result['compliant'])
            
            if violations > 0:
                # Ada violations, save screenshot
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
                
                # Buat detailed annotation
                frame_info = f"[SCREENSHOT] Frame:{frame_number} | Violations:{violations} | {timestamp}"
                annotated_frame, _ = draw_annotations(frame, compliance_results, hardhats, safety_vests, frame_info)
                
                # Tambahkan violation details di bawah
                y_pos = annotated_frame.shape[0] - 80
                violation_details = []
                
                for i, result in enumerate(compliance_results):
                    if not result['compliant']:
                        missing = []
                        if not result['has_hardhat']:
                            missing.append("Helmet")
                        if not result['has_safety_vest']:
                            missing.append("Safety Vest")
                        violation_details.append(f"Person {i+1}: Missing {', '.join(missing)}")
                
                # Tulis violation details
                for detail in violation_details:
                    cv2.putText(annotated_frame, detail, (10, y_pos), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    y_pos += 25
                
                # Save screenshot
                filename = f"{self.screenshot_dir}/violation_f{frame_number}_{timestamp}.jpg"
                cv2.imwrite(filename, annotated_frame)
                
                self.violation_count += 1
                print(f"[SCREENSHOT] Violation saved: {filename} ({violations} violations)")
                
                return True
            
            return False
            
        except Exception as e:
            print(f"[SCREENSHOT ERROR] Frame {frame_number}: {e}")
            return False
    
    def run(self):
        """Main processing loop untuk screenshot thread"""
        self.running = True
        print("[SCREENSHOT] Background processor started...")
        
        while self.running:
            try:
                # Ambil frame dari queue dengan timeout
                frame, frame_number = self.frame_queue.get(timeout=1.0)
                
                # Process frame
                self.process_frame_detailed(frame, frame_number)
                self.processed_count += 1
                
                # Mark task as done
                self.frame_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[SCREENSHOT ERROR] Processing error: {e}")
                continue
        
        print(f"[SCREENSHOT] Processor stopped. Processed: {self.processed_count}, Violations: {self.violation_count}")
    
    def stop(self):
        """Stop screenshot processor"""
        self.running = False

class LiveVideoSystem:
    """Main live video system"""
    
    def __init__(self, model, video_path):
        self.model = model
        self.video_path = video_path
        self.cap = None
        self.running = False
        self.paused = False
        
        # Statistics
        self.frame_count = 0
        self.total_violations = 0
        
        # Screenshot processor
        self.screenshot_processor = ScreenshotProcessor(model)
        self.screenshot_thread = None
        
        # Control settings
        self.auto_screenshot = True  # Auto screenshot pada violations
        self.manual_screenshot_requested = False
    
    def initialize(self):
        """Initialize video capture"""
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            print(f"Error: Tidak dapat membuka video {self.video_path}")
            return False
        
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"Live Video: {self.width}x{self.height} @ {self.fps} FPS")
        print(f"Video file: {self.video_path}")
        
        # Start screenshot processor thread
        self.screenshot_thread = threading.Thread(target=self.screenshot_processor.run, daemon=True)
        self.screenshot_thread.start()
        
        return True
    
    def process_frame_live(self, frame):
        """Process frame untuk live display (optimized)"""
        self.frame_count += 1
        
        # Live detection - bisa dikurangi frekuensinya untuk performa
        persons, hardhats, safety_vests = detect_objects(self.model, frame)
        compliance_results = check_safety_compliance(persons, hardhats, safety_vests)
        
        # Hitung violations
        violations_this_frame = sum(1 for result in compliance_results if not result['compliant'])
        self.total_violations += violations_this_frame
        
        # Prepare frame info
        screenshot_queue_size = self.screenshot_processor.frame_queue.qsize()
        frame_info = f"[LIVE] F:{self.frame_count} | P:{len(persons)} | V:{violations_this_frame} | Queue:{screenshot_queue_size}"
        
        # Draw annotations
        annotated_frame, _ = draw_annotations(frame, compliance_results, hardhats, safety_vests, frame_info)
        
        # Add screenshot processor stats
        cv2.putText(annotated_frame, f"Screenshots: {self.screenshot_processor.violation_count} violations saved", 
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Koordinasi dengan screenshot processor
        if self.auto_screenshot and violations_this_frame > 0:
            # Kirim frame ke screenshot processor untuk detailed analysis
            self.screenshot_processor.add_frame(frame, self.frame_count)
        
        if self.manual_screenshot_requested:
            # Manual screenshot request
            self.screenshot_processor.add_frame(frame, self.frame_count)
            self.manual_screenshot_requested = False
            print(f"[LIVE] Manual screenshot queued for frame {self.frame_count}")
        
        return annotated_frame, violations_this_frame
    
    def run(self):
        """Main live video loop"""
        if not self.initialize():
            return
        
        self.running = True
        print("\n=== LIVE VIDEO WITH BACKGROUND SCREENSHOT SYSTEM ===")
        print("Controls:")
        print("  'q' - Quit")
        print("  'p' - Pause/Resume")
        print("  's' - Manual screenshot")
        print("  'a' - Toggle auto-screenshot")
        print("  'r' - Reset statistics")
        print("="*60)
        
        # Setup window
        cv2.namedWindow('Live Safety Monitor', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Live Safety Monitor', 1200, 800)
        
        while self.running:
            if not self.paused:
                ret, frame = self.cap.read()
                
                if not ret:
                    print("[LIVE] Video ended, restarting...")
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Restart video
                    continue
                
                # Process frame untuk live display
                annotated_frame, violations_this_frame = self.process_frame_live(frame)
                
                # Display frame
                cv2.imshow('Live Safety Monitor', annotated_frame)
                
                # Console output untuk violations
                if violations_this_frame > 0:
                    print(f"[LIVE] Frame {self.frame_count}: {violations_this_frame} violations detected")
            
            # Control dengan delay minimal
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                self.running = False
                print("[LIVE] Stopping system...")
            elif key == ord('p'):
                self.paused = not self.paused
                print(f"[LIVE] {'Paused' if self.paused else 'Resumed'}")
            elif key == ord('s'):
                self.manual_screenshot_requested = True
            elif key == ord('a'):
                self.auto_screenshot = not self.auto_screenshot
                print(f"[LIVE] Auto-screenshot: {'ON' if self.auto_screenshot else 'OFF'}")
            elif key == ord('r'):
                self.total_violations = 0
                self.frame_count = 0
                print("[LIVE] Statistics reset")
        
        self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        print("[LIVE] Shutting down...")
        
        # Stop screenshot processor
        self.screenshot_processor.stop()
        if self.screenshot_thread and self.screenshot_thread.is_alive():
            self.screenshot_thread.join(timeout=2)
        
        # Release video
        if self.cap:
            self.cap.release()
        
        cv2.destroyAllWindows()
        
        print(f"\n=== LIVE VIDEO SUMMARY ===")
        print(f"Total frames processed: {self.frame_count}")
        print(f"Total violations detected: {self.total_violations}")
        print(f"Screenshots saved: {self.screenshot_processor.violation_count}")
        print(f"Screenshot folder: {self.screenshot_processor.screenshot_dir}")

def main():
    # Load YOLO model
    model = YOLO('best.pt')
    
    # Video path
    video_path = 'hse1.mp4'
    
    # Create and run live system
    live_system = LiveVideoSystem(model, video_path)
    
    try:
        live_system.run()
    except KeyboardInterrupt:
        print("\n[MAIN] Keyboard interrupt received")
        live_system.running = False
        live_system.cleanup()

if __name__ == "__main__":
    main()