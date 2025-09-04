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

class OptimizedVideoReader:
    """Optimized RTSP reader - minimal CPU usage"""
    
    def __init__(self, rtsp_url):
        self.rtsp_url = rtsp_url
        self.cap = None
        self.running = False
        self.paused = False
        
        # Latest frame cache - shared across threads
        self.latest_frame = None
        self.latest_frame_number = 0
        self.frame_lock = threading.Lock()
        
        # Connection management
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.connection_stable = False
        
        # Performance stats
        self.frames_read = 0
        self.dropped_frames = 0
        
    def initialize(self):
        """Initialize RTSP with minimal overhead"""
        print(f"[VIDEO] Connecting to RTSP: {self.rtsp_url}")
        
        self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        
        # Aggressive optimization for minimal CPU
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffer
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        if not self.cap.isOpened():
            print(f"[VIDEO] Error: Cannot connect to RTSP")
            return False
        
        # Test frame
        ret, test_frame = self.cap.read()
        if not ret:
            print("[VIDEO] Error: Cannot read from stream")
            return False
        
        print("[VIDEO] RTSP connected - Low CPU mode activated")
        self.connection_stable = True
        return True
    
    def get_latest_frame(self):
        """Thread-safe access ke latest frame"""
        with self.frame_lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy(), self.latest_frame_number
            return None, 0
    
    def run(self):
        """Lightweight frame reader"""
        if not self.initialize():
            return
        
        self.running = True
        print("[VIDEO] Optimized reader started - 1 FPS processing mode")
        
        consecutive_failures = 0
        
        while self.running:
            if not self.paused:
                ret, frame = self.cap.read()
                
                if not ret:
                    consecutive_failures += 1
                    if consecutive_failures > 10:
                        print("[VIDEO] Connection lost, attempting reconnect...")
                        if not self.reconnect():
                            break
                        consecutive_failures = 0
                    continue
                
                consecutive_failures = 0
                self.frames_read += 1
                
                # Update latest frame (thread-safe)
                with self.frame_lock:
                    self.latest_frame = frame
                    self.latest_frame_number = self.frames_read
                
            # Minimal sleep untuk reduce CPU
            time.sleep(0.01)  # 100 FPS max, tapi detection hanya 1 FPS
        
        if self.cap:
            self.cap.release()
        print(f"[VIDEO] Reader stopped. Read: {self.frames_read}, Dropped: {self.dropped_frames}")
    
    def reconnect(self):
        """Quick reconnect"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            return False
        
        self.reconnect_attempts += 1
        if self.cap:
            self.cap.release()
        
        time.sleep(1)
        return self.initialize()
    
    def stop(self):
        self.running = False

class LowCPUDetectionProcessor:
    """Detection processor - 1 frame per second only"""
    
    def __init__(self, model, video_reader):
        self.model = model
        self.video_reader = video_reader
        self.running = False
        
        # Detection cache - reuse hasil untuk frame lain
        self.last_detection_results = {
            'persons': [],
            'hardhats': [],
            'safety_vests': [],
            'compliance_results': [],
            'timestamp': 0,
            'frame_number': 0
        }
        self.detection_lock = threading.Lock()
        
        # Performance tracking
        self.detections_processed = 0
        
    def detect_objects_optimized(self, frame):
        """Optimized YOLO detection"""
        # Resize frame untuk speed (optional)
        # height, width = frame.shape[:2]
        # if width > 640:  # Resize jika terlalu besar
        #     scale = 640 / width
        #     new_width = int(width * scale)
        #     new_height = int(height * scale)
        #     frame = cv2.resize(frame, (new_width, new_height))
        
        results = self.model(frame, verbose=False)  # Disable verbose untuk speed
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
    
    def get_detection_results(self):
        """Thread-safe access ke detection results"""
        with self.detection_lock:
            return self.last_detection_results.copy()
    
    def run(self):
        """Process 1 frame per second only"""
        self.running = True
        print("[DETECT] Low-CPU detector started - 1 FPS processing")
        
        last_detection_time = 0
        
        while self.running:
            current_time = time.time()
            
            # Process hanya 1 frame per detik
            if current_time - last_detection_time >= 1.0:
                # Ambil latest frame
                frame, frame_number = self.video_reader.get_latest_frame()
                
                if frame is not None:
                    try:
                        # Proses detection
                        persons, hardhats, safety_vests = self.detect_objects_optimized(frame)
                        compliance_results = check_safety_compliance(persons, hardhats, safety_vests)
                        
                        # Update cache (thread-safe)
                        with self.detection_lock:
                            self.last_detection_results = {
                                'persons': persons,
                                'hardhats': hardhats,
                                'safety_vests': safety_vests,
                                'compliance_results': compliance_results,
                                'timestamp': current_time,
                                'frame_number': frame_number
                            }
                        
                        self.detections_processed += 1
                        last_detection_time = current_time
                        
                        # Console output untuk violations
                        violations = sum(1 for result in compliance_results if not result['compliant'])
                        if violations > 0:
                            print(f"[DETECT] Frame {frame_number}: {violations} violations detected")
                        
                    except Exception as e:
                        print(f"[DETECT] Error processing frame: {e}")
            
            # Sleep to reduce CPU usage
            time.sleep(0.1)
        
        print(f"[DETECT] Processor stopped. Processed: {self.detections_processed} frames")
    
    def stop(self):
        self.running = False

class FastDisplayRenderer:
    """Fast display renderer - menggunakan cached detection results"""
    
    def __init__(self, video_reader, detection_processor):
        self.video_reader = video_reader
        self.detection_processor = detection_processor
        self.running = False
        
        # Display stats
        self.frames_displayed = 0
        self.screenshots_taken = 0
        
        # Screenshot management
        self.screenshot_dir = "screenshots_optimized"
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)
    
    def draw_annotations_fast(self, frame, detection_results, frame_number):
        """Fast annotation drawing"""
        annotated_frame = frame.copy()
        
        compliance_results = detection_results['compliance_results']
        hardhats = detection_results['hardhats']
        safety_vests = detection_results['safety_vests']
        persons = detection_results['persons']
        detection_age = time.time() - detection_results['timestamp']
        
        # Draw safety equipment (simplified)
        for hardhat in hardhats:
            x1, y1, x2, y2 = hardhat['bbox']
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (128, 128, 128), 1)
        
        for vest in safety_vests:
            x1, y1, x2, y2 = vest['bbox']
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (128, 128, 128), 1)
        
        # Draw persons with compliance
        violations = 0
        for result in compliance_results:
            person = result['person']
            x1, y1, x2, y2 = person['bbox']
            
            if result['compliant']:
                color = (0, 255, 0)
                status = "OK"
            else:
                color = (0, 0, 255)
                status = "VIOLATION"
                violations += 1
            
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(annotated_frame, status, (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        # Status info
        status_lines = [
            f"[OPTIMIZED] Frame:{frame_number} | P:{len(persons)} | V:{violations}",
            f"Detection Age: {detection_age:.1f}s | CPU Mode: LOW",
            f"Processed: {self.detection_processor.detections_processed} | Displayed: {self.frames_displayed}"
        ]
        
        y_pos = 30
        for line in status_lines:
            cv2.putText(annotated_frame, line, (10, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            y_pos += 25
        
        return annotated_frame, violations
    
    def save_screenshot(self, frame, frame_number, violations):
        """Quick screenshot save"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.screenshot_dir}/optimized_f{frame_number}_{timestamp}.jpg"
        cv2.imwrite(filename, frame)
        self.screenshots_taken += 1
        print(f"[DISPLAY] Screenshot saved: {os.path.basename(filename)} ({violations} violations)")
    
    def run(self):
        """Main display loop - high FPS display with 1 FPS detection"""
        self.running = True
        print("[DISPLAY] Fast renderer started")
        
        cv2.namedWindow('Optimized Safety Monitor', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Optimized Safety Monitor', 1200, 800)
        
        auto_screenshot = True
        
        # FPS tracking
        fps_counter = 0
        last_fps_time = time.time()
        current_fps = 0
        
        while self.running:
            # Ambil latest frame
            frame, frame_number = self.video_reader.get_latest_frame()
            
            if frame is not None:
                # Ambil detection results (cached)
                detection_results = self.detection_processor.get_detection_results()
                
                # Draw annotations
                annotated_frame, violations = self.draw_annotations_fast(
                    frame, detection_results, frame_number
                )
                
                # FPS calculation
                fps_counter += 1
                if time.time() - last_fps_time >= 1.0:
                    current_fps = fps_counter
                    fps_counter = 0
                    last_fps_time = time.time()
                
                # Add FPS info
                cv2.putText(annotated_frame, f"Display FPS: {current_fps}", 
                           (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # Auto screenshot pada violations
                if auto_screenshot and violations > 0:
                    self.save_screenshot(annotated_frame, frame_number, violations)
                
                # Display
                cv2.imshow('Optimized Safety Monitor', annotated_frame)
                self.frames_displayed += 1
            else:
                # No frame available
                blank = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(blank, "WAITING FOR RTSP STREAM...", (50, 240), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.imshow('Optimized Safety Monitor', blank)
            
            # Controls
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                self.running = False
            elif key == ord('p'):
                self.video_reader.paused = not self.video_reader.paused
                print(f"[DISPLAY] Stream {'PAUSED' if self.video_reader.paused else 'RESUMED'}")
            elif key == ord('s'):
                if frame is not None:
                    self.save_screenshot(annotated_frame, frame_number, 0)
            elif key == ord('a'):
                auto_screenshot = not auto_screenshot
                print(f"[DISPLAY] Auto-screenshot: {'ON' if auto_screenshot else 'OFF'}")
            elif key == ord('r'):
                print("[DISPLAY] Force reconnect requested")
                self.video_reader.reconnect_attempts = 0
        
        cv2.destroyAllWindows()
        print(f"[DISPLAY] Renderer stopped. Displayed: {self.frames_displayed}, Screenshots: {self.screenshots_taken}")
    
    def stop(self):
        self.running = False

class OptimizedSafetySystem:
    """Main system coordinator - optimized for low CPU usage"""
    
    def __init__(self, model, rtsp_url):
        self.model = model
        self.rtsp_url = rtsp_url
        
        # Components
        self.video_reader = OptimizedVideoReader(rtsp_url)
        self.detection_processor = LowCPUDetectionProcessor(model, self.video_reader)
        self.display_renderer = FastDisplayRenderer(self.video_reader, self.detection_processor)
        
        # Control
        self.running = False
        self.start_time = None
    
    def start_threads(self):
        """Start all optimized threads"""
        threading.Thread(target=self.video_reader.run, daemon=True).start()
        threading.Thread(target=self.detection_processor.run, daemon=True).start()
        threading.Thread(target=self.display_renderer.run, daemon=True).start()
        
        print("[SYSTEM] All optimized threads started")
    
    def run(self):
        """Main coordinator"""
        print("\n🚀 === OPTIMIZED LOW-CPU SAFETY DETECTION SYSTEM ===")
        print(f"📡 RTSP Stream: {self.rtsp_url}")
        print("⚡ CPU Optimization: MAXIMUM")
        print("🎯 Detection Rate: 1 FPS (low CPU)")
        print("📺 Display Rate: 30 FPS (smooth)")
        print("💾 Memory: Optimized caching")
        print("\nOptimizations Applied:")
        print("  • 1 frame per second detection only")
        print("  • Shared memory for frames")
        print("  • Cached detection results")
        print("  • Minimal buffer sizes")
        print("  • Fast display rendering")
        print("\nControls:")
        print("  'q' - Quit")
        print("  'p' - Pause/Resume")
        print("  's' - Manual screenshot")
        print("  'a' - Toggle auto-screenshot")
        print("  'r' - Force reconnect")
        print("=" * 60)
        
        self.start_time = time.time()
        self.start_threads()
        self.running = True
        
        try:
            # Run display renderer in main thread
            self.display_renderer.run()
        except KeyboardInterrupt:
            print("\n[MAIN] Keyboard interrupt")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup all components"""
        print("\n[MAIN] Shutting down optimized system...")
        
        self.video_reader.stop()
        self.detection_processor.stop()
        self.display_renderer.stop()
        
        time.sleep(1)
        
        if self.start_time:
            runtime = time.time() - self.start_time
            avg_display_fps = self.display_renderer.frames_displayed / runtime if runtime > 0 else 0
            detection_rate = self.detection_processor.detections_processed / runtime if runtime > 0 else 0
            
            print(f"\n🎯 === OPTIMIZED SYSTEM SUMMARY ===")
            print(f"⏱️  Runtime: {runtime:.1f} seconds")
            print(f"📺 Display FPS: {avg_display_fps:.1f}")
            print(f"🔍 Detection Rate: {detection_rate:.2f} per second")
            print(f"📡 RTSP Frames Read: {self.video_reader.frames_read}")
            print(f"🧠 Detections Processed: {self.detection_processor.detections_processed}")
            print(f"🎬 Frames Displayed: {self.display_renderer.frames_displayed}")
            print(f"📸 Screenshots Saved: {self.display_renderer.screenshots_taken}")
            print(f"🔄 Reconnect Attempts: {self.video_reader.reconnect_attempts}")
            print("💚 CPU Usage: OPTIMIZED (1 FPS detection)")

def main():
    print("🔥 Loading YOLO model...")
    model = YOLO('best.pt')
    print("✅ YOLO model loaded!")
    
    rtsp_url = 'rtsp://192.168.1.30:554/live/ch00_1'
    
    print(f"\n📡 Connecting to optimized RTSP stream: {rtsp_url}")
    print("🎯 This version optimized for LOW CPU usage!")
    print("⚡ Detection: 1 FPS only (CPU friendly)")
    print("📺 Display: Full FPS (smooth viewing)")
    
    system = OptimizedSafetySystem(model, rtsp_url)
    
    try:
        system.run()
    except Exception as e:
        print(f"\n❌ [MAIN] System error: {e}")
        if hasattr(system, 'cleanup'):
            system.cleanup()

if __name__ == "__main__":
    main()