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

class VideoReaderThread:
    """Thread 1: Hanya baca frame dari video"""
    
    def __init__(self, video_path, frame_queue):
        self.video_path = video_path
        self.frame_queue = frame_queue
        self.cap = None
        self.running = False
        self.paused = False
        self.frame_count = 0
        self.fps = 30
        
    def initialize(self):
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            print(f"[VIDEO] Error: Cannot open {self.video_path}")
            return False
        
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"[VIDEO] Initialized: {width}x{height} @ {self.fps} FPS")
        return True
    
    def run(self):
        if not self.initialize():
            return
        
        self.running = True
        print("[VIDEO] Reader thread started")
        
        while self.running:
            if not self.paused:
                ret, frame = self.cap.read()
                
                if not ret:
                    # Restart video
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                self.frame_count += 1
                
                # Masukkan frame ke queue
                if not self.frame_queue.full():
                    self.frame_queue.put((frame.copy(), self.frame_count), block=False)
            
            # Control frame rate
            time.sleep(1.0 / self.fps)
        
        if self.cap:
            self.cap.release()
        print("[VIDEO] Reader thread stopped")
    
    def stop(self):
        self.running = False

class DetectionThread:
    """Thread 2: Proses YOLO Detection"""
    
    def __init__(self, model, frame_queue, detection_queue):
        self.model = model
        self.frame_queue = frame_queue
        self.detection_queue = detection_queue
        self.running = False
        self.processed_frames = 0
        
    def detect_objects(self, frame):
        """Deteksi objek dalam frame"""
        results = self.model(frame)
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
                    class_name = self.model.names[int(class_id)]
                    
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
    
    def run(self):
        self.running = True
        print("[DETECT] Detection thread started")
        
        while self.running:
            try:
                # Ambil frame dari video reader
                frame, frame_number = self.frame_queue.get(timeout=1.0)
                
                # Proses detection
                persons, hardhats, safety_vests = self.detect_objects(frame)
                compliance_results = check_safety_compliance(persons, hardhats, safety_vests)
                
                # Kirim hasil ke drawing thread
                detection_data = {
                    'frame': frame,
                    'frame_number': frame_number,
                    'persons': persons,
                    'hardhats': hardhats,
                    'safety_vests': safety_vests,
                    'compliance_results': compliance_results
                }
                
                if not self.detection_queue.full():
                    self.detection_queue.put(detection_data, block=False)
                
                self.processed_frames += 1
                self.frame_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[DETECT] Error: {e}")
                continue
        
        print(f"[DETECT] Detection thread stopped. Processed: {self.processed_frames}")
    
    def stop(self):
        self.running = False

class DrawingThread:
    """Thread 3: Gambar Annotations"""
    
    def __init__(self, detection_queue, display_queue):
        self.detection_queue = detection_queue
        self.display_queue = display_queue
        self.running = False
        self.drawn_frames = 0
        
    def draw_annotations(self, frame, compliance_results, hardhats, safety_vests, frame_info=""):
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
    
    def run(self):
        self.running = True
        print("[DRAW] Drawing thread started")
        
        while self.running:
            try:
                # Ambil detection results
                detection_data = self.detection_queue.get(timeout=1.0)
                
                frame = detection_data['frame']
                frame_number = detection_data['frame_number']
                compliance_results = detection_data['compliance_results']
                hardhats = detection_data['hardhats']
                safety_vests = detection_data['safety_vests']
                persons = detection_data['persons']
                
                # Buat frame info
                violations = sum(1 for result in compliance_results if not result['compliant'])
                frame_info = f"[LIVE] F:{frame_number} | P:{len(persons)} | V:{violations}"
                
                # Gambar annotations
                annotated_frame, violation_count = self.draw_annotations(
                    frame, compliance_results, hardhats, safety_vests, frame_info
                )
                
                # Kirim ke display
                display_data = {
                    'annotated_frame': annotated_frame,
                    'original_frame': frame,
                    'frame_number': frame_number,
                    'violations': violation_count,
                    'compliance_results': compliance_results,
                    'persons': persons,
                    'hardhats': hardhats,
                    'safety_vests': safety_vests
                }
                
                if not self.display_queue.full():
                    self.display_queue.put(display_data, block=False)
                
                self.drawn_frames += 1
                self.detection_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[DRAW] Error: {e}")
                continue
        
        print(f"[DRAW] Drawing thread stopped. Drawn: {self.drawn_frames}")
    
    def stop(self):
        self.running = False

class ScreenshotThread:
    """Thread 4: Screenshot Handler"""
    
    def __init__(self, screenshot_dir="screenshots"):
        self.screenshot_dir = screenshot_dir
        self.screenshot_queue = queue.Queue()
        self.running = False
        self.screenshot_count = 0
        self.violation_screenshots = 0
        
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)
    
    def save_screenshot(self, frame, frame_number, violation_info="", is_violation=False):
        """Save screenshot"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        
        if is_violation:
            filename = f"{self.screenshot_dir}/violation_f{frame_number}_{timestamp}.jpg"
            self.violation_screenshots += 1
        else:
            filename = f"{self.screenshot_dir}/manual_f{frame_number}_{timestamp}.jpg"
        
        # Add info to frame
        if violation_info:
            cv2.putText(frame, violation_info, (10, frame.shape[0]-20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        cv2.imwrite(filename, frame)
        self.screenshot_count += 1
        
        screenshot_type = "VIOLATION" if is_violation else "MANUAL"
        print(f"[SCREENSHOT] {screenshot_type} saved: f{frame_number} -> {os.path.basename(filename)}")
        
        return filename
    
    def add_screenshot(self, frame, frame_number, violation_info="", is_violation=False):
        """Queue screenshot for processing"""
        try:
            self.screenshot_queue.put((frame.copy(), frame_number, violation_info, is_violation), block=False)
        except queue.Full:
            print("[SCREENSHOT] Queue full, skipping screenshot")
    
    def run(self):
        self.running = True
        print("[SCREENSHOT] Screenshot thread started")
        
        while self.running:
            try:
                frame, frame_number, violation_info, is_violation = self.screenshot_queue.get(timeout=1.0)
                self.save_screenshot(frame, frame_number, violation_info, is_violation)
                self.screenshot_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[SCREENSHOT] Error: {e}")
                continue
        
        print(f"[SCREENSHOT] Thread stopped. Total: {self.screenshot_count}, Violations: {self.violation_screenshots}")
    
    def stop(self):
        self.running = False

class MultiThreadSafetySystem:
    """Main coordinator untuk semua thread"""
    
    def __init__(self, model, video_path):
        self.model = model
        self.video_path = video_path
        
        # Queues untuk komunikasi antar thread
        self.frame_queue = queue.Queue(maxsize=5)       # Video -> Detection
        self.detection_queue = queue.Queue(maxsize=5)   # Detection -> Drawing  
        self.display_queue = queue.Queue(maxsize=5)     # Drawing -> Display
        
        # Threads
        self.video_thread = VideoReaderThread(video_path, self.frame_queue)
        self.detection_thread = DetectionThread(model, self.frame_queue, self.detection_queue)
        self.drawing_thread = DrawingThread(self.detection_queue, self.display_queue)
        self.screenshot_thread = ScreenshotThread()
        
        # Control
        self.running = False
        self.auto_screenshot = True
        self.manual_screenshot_requested = False
        
        # Stats
        self.displayed_frames = 0
        self.total_violations = 0
    
    def start_threads(self):
        """Start semua thread"""
        threading.Thread(target=self.video_thread.run, daemon=True).start()
        threading.Thread(target=self.detection_thread.run, daemon=True).start()
        threading.Thread(target=self.drawing_thread.run, daemon=True).start()
        threading.Thread(target=self.screenshot_thread.run, daemon=True).start()
        
        print("[SYSTEM] All threads started")
    
    def run(self):
        """Main display loop"""
        print("\n=== MULTI-THREAD SAFETY DETECTION SYSTEM ===")
        print("Thread 1: Video Reader")
        print("Thread 2: YOLO Detection") 
        print("Thread 3: Drawing Annotations")
        print("Thread 4: Screenshot Processor")
        print("Main: Display & Control")
        print("\nControls:")
        print("  'q' - Quit")
        print("  'p' - Pause/Resume video")
        print("  's' - Manual screenshot")
        print("  'a' - Toggle auto-screenshot")
        print("="*50)
        
        # Setup display
        cv2.namedWindow('Multi-Thread Safety Monitor', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Multi-Thread Safety Monitor', 1200, 800)
        
        # Start threads
        self.start_threads()
        self.running = True
        
        while self.running:
            try:
                # Ambil display data
                display_data = self.display_queue.get(timeout=0.1)
                
                annotated_frame = display_data['annotated_frame']
                original_frame = display_data['original_frame']
                frame_number = display_data['frame_number']
                violations = display_data['violations']
                compliance_results = display_data['compliance_results']
                
                self.displayed_frames += 1
                self.total_violations += violations
                
                # Add thread stats to display
                stats_y = 60
                thread_stats = [
                    f"Video Frames: {self.video_thread.frame_count} | Detection: {self.detection_thread.processed_frames}",
                    f"Drawing: {self.drawing_thread.drawn_frames} | Display: {self.displayed_frames}",
                    f"Screenshots: {self.screenshot_thread.screenshot_count} | Auto: {'ON' if self.auto_screenshot else 'OFF'}"
                ]
                
                for stat in thread_stats:
                    cv2.putText(annotated_frame, stat, (10, stats_y), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    stats_y += 20
                
                # Handle screenshots
                if self.auto_screenshot and violations > 0:
                    # Auto screenshot untuk violations
                    violation_details = []
                    for result in compliance_results:
                        if not result['compliant']:
                            missing = []
                            if not result['has_hardhat']:
                                missing.append("Helmet")
                            if not result['has_safety_vest']:
                                missing.append("Safety Vest")
                            violation_details.append(f"Missing: {', '.join(missing)}")
                    
                    violation_info = f"VIOLATIONS: {'; '.join(violation_details)}"
                    self.screenshot_thread.add_screenshot(annotated_frame, frame_number, violation_info, is_violation=True)
                
                if self.manual_screenshot_requested:
                    # Manual screenshot
                    self.screenshot_thread.add_screenshot(annotated_frame, frame_number, is_violation=False)
                    self.manual_screenshot_requested = False
                
                # Display frame
                cv2.imshow('Multi-Thread Safety Monitor', annotated_frame)
                self.display_queue.task_done()
                
            except queue.Empty:
                pass
            except Exception as e:
                print(f"[MAIN] Display error: {e}")
            
            # Controls
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                self.running = False
            elif key == ord('p'):
                self.video_thread.paused = not self.video_thread.paused
                status = "PAUSED" if self.video_thread.paused else "RESUMED"
                print(f"[MAIN] Video {status}")
            elif key == ord('s'):
                self.manual_screenshot_requested = True
                print("[MAIN] Manual screenshot requested")
            elif key == ord('a'):
                self.auto_screenshot = not self.auto_screenshot
                print(f"[MAIN] Auto-screenshot: {'ON' if self.auto_screenshot else 'OFF'}")
        
        self.cleanup()
    
    def cleanup(self):
        """Stop semua thread dan cleanup"""
        print("\n[MAIN] Stopping all threads...")
        
        self.video_thread.stop()
        self.detection_thread.stop()
        self.drawing_thread.stop()
        self.screenshot_thread.stop()
        
        time.sleep(1)  # Wait for threads to stop
        
        cv2.destroyAllWindows()
        
        print(f"\n=== SYSTEM SUMMARY ===")
        print(f"Video frames read: {self.video_thread.frame_count}")
        print(f"Frames detected: {self.detection_thread.processed_frames}")
        print(f"Frames drawn: {self.drawing_thread.drawn_frames}")
        print(f"Frames displayed: {self.displayed_frames}")
        print(f"Total violations: {self.total_violations}")
        print(f"Screenshots saved: {self.screenshot_thread.screenshot_count}")
        print(f"Violation screenshots: {self.screenshot_thread.violation_screenshots}")

def main():
    # Load YOLO model
    model = YOLO('best.pt')
    
    # Video path
    video_path = 'hse1.mp4'
    
    # Create and run system
    system = MultiThreadSafetySystem(model, video_path)
    
    try:
        system.run()
    except KeyboardInterrupt:
        print("\n[MAIN] Keyboard interrupt")
        system.running = False
        system.cleanup()

if __name__ == "__main__":
    main()