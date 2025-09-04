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

def detect_input_type(input_path):
    """Deteksi apakah input RTSP atau video file"""
    if input_path.startswith('rtsp://') or input_path.startswith('http://') or input_path.startswith('https://'):
        return 'rtsp'
    elif os.path.isfile(input_path):
        return 'video'
    else:
        return 'unknown'

class LiveReaderThread:
    """Thread 1: Live Reader - Support RTSP dan Video File"""
    
    def __init__(self, input_source, frame_capture_queue):
        self.input_source = input_source
        self.frame_capture_queue = frame_capture_queue
        self.input_type = detect_input_type(input_source)
        
        self.cap = None
        self.running = False
        self.paused = False
        self.loop_video = True  # Auto-loop untuk video file
        
        # Stats
        self.frames_read = 0
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
        # Video specific
        self.total_frames = 0
        self.fps = 30
        
        print(f"[LIVE] Input detected as: {self.input_type.upper()}")
        
    def initialize(self):
        """Initialize berdasarkan input type"""
        if self.input_type == 'rtsp':
            return self.initialize_rtsp()
        elif self.input_type == 'video':
            return self.initialize_video()
        else:
            print(f"[LIVE] Error: Unsupported input - {self.input_source}")
            return False
    
    def initialize_rtsp(self):
        """Initialize RTSP stream"""
        print(f"[LIVE] Connecting to RTSP: {self.input_source}")
        
        self.cap = cv2.VideoCapture(self.input_source, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Low latency
        
        if not self.cap.isOpened():
            print("[LIVE] Error: Cannot connect to RTSP")
            return False
        
        ret, test_frame = self.cap.read()
        if not ret:
            print("[LIVE] Error: Cannot read from RTSP stream")
            return False
        
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS)) or 30
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"[LIVE] RTSP Connected: {width}x{height} @ {self.fps} FPS")
        return True
    
    def initialize_video(self):
        """Initialize video file"""
        print(f"[LIVE] Opening video file: {self.input_source}")
        
        self.cap = cv2.VideoCapture(self.input_source)
        
        if not self.cap.isOpened():
            print("[LIVE] Error: Cannot open video file")
            return False
        
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        duration = self.total_frames / self.fps if self.fps > 0 else 0
        
        print(f"[LIVE] Video Loaded: {width}x{height} @ {self.fps} FPS")
        print(f"[LIVE] Duration: {duration:.1f}s ({self.total_frames} frames)")
        print(f"[LIVE] Auto-loop: {'ON' if self.loop_video else 'OFF'}")
        
        return True
    
    def reconnect_rtsp(self):
        """Reconnect RTSP stream"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            print(f"[LIVE] Max reconnect attempts reached")
            return False
        
        self.reconnect_attempts += 1
        print(f"[LIVE] Reconnecting RTSP... (attempt {self.reconnect_attempts})")
        
        if self.cap:
            self.cap.release()
        
        time.sleep(2)
        return self.initialize_rtsp()
    
    def restart_video(self):
        """Restart video dari awal"""
        if self.cap:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            print("[LIVE] Video restarted from beginning")
        
    def run(self):
        """Main reader loop"""
        if not self.initialize():
            return
        
        self.running = True
        print(f"[LIVE] {self.input_type.upper()} reader thread started")
        
        consecutive_failures = 0
        frame_delay = 1.0 / self.fps if self.input_type == 'video' else 0.01
        
        while self.running:
            if not self.paused:
                ret, frame = self.cap.read()
                
                if not ret:
                    if self.input_type == 'rtsp':
                        consecutive_failures += 1
                        if consecutive_failures > 10:
                            print("[LIVE] RTSP connection lost, attempting reconnect...")
                            if not self.reconnect_rtsp():
                                break
                            consecutive_failures = 0
                        continue
                    
                    elif self.input_type == 'video':
                        if self.loop_video:
                            self.restart_video()
                            continue
                        else:
                            print("[LIVE] Video finished")
                            break
                
                consecutive_failures = 0
                self.frames_read += 1
                
                # Kirim frame ke capture thread
                try:
                    current_frame_pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) if self.input_type == 'video' else self.frames_read
                    
                    frame_data = {
                        'frame': frame,
                        'frame_number': self.frames_read,
                        'timestamp': time.time(),
                        'frame_pos': current_frame_pos,
                        'total_frames': self.total_frames,
                        'input_type': self.input_type
                    }
                    
                    self.frame_capture_queue.put(frame_data, block=False)
                    
                except queue.Full:
                    # Skip frame jika queue penuh
                    pass
            
            # Frame rate control
            time.sleep(frame_delay)
        
        if self.cap:
            self.cap.release()
        print(f"[LIVE] Reader stopped. Read: {self.frames_read} frames")
    
    def stop(self):
        self.running = False

class FrameCaptureThread:
    """Thread 2: Frame Capture - Manage frame untuk detection"""
    
    def __init__(self, frame_capture_queue, detection_queue):
        self.frame_capture_queue = frame_capture_queue
        self.detection_queue = detection_queue
        self.running = False
        
        # Latest frame cache untuk display
        self.latest_frame_data = None
        self.frame_lock = threading.Lock()
        
        # Stats
        self.frames_captured = 0
        self.frames_sent_detection = 0
        
    def get_latest_frame(self):
        """Thread-safe access ke latest frame"""
        with self.frame_lock:
            return self.latest_frame_data.copy() if self.latest_frame_data else None
    
    def run(self):
        """Capture dan distribute frames"""
        self.running = True
        print("[CAPTURE] Frame capture thread started")
        
        detection_interval = 1.0  # 1 detik interval untuk detection
        last_detection_time = 0
        
        while self.running:
            try:
                frame_data = self.frame_capture_queue.get(timeout=1.0)
                
                self.frames_captured += 1
                current_time = time.time()
                
                # Update latest frame (thread-safe)
                with self.frame_lock:
                    self.latest_frame_data = frame_data
                
                # Kirim ke detection hanya 1 FPS
                if current_time - last_detection_time >= detection_interval:
                    try:
                        detection_data = frame_data.copy()
                        detection_data['detection_timestamp'] = current_time
                        
                        self.detection_queue.put(detection_data, block=False)
                        self.frames_sent_detection += 1
                        last_detection_time = current_time
                        
                    except queue.Full:
                        pass  # Skip jika detection busy
                
                self.frame_capture_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[CAPTURE] Error: {e}")
        
        print(f"[CAPTURE] Capture stopped. Captured: {self.frames_captured}, Sent to detection: {self.frames_sent_detection}")
    
    def stop(self):
        self.running = False

class DetectionThread:
    """Thread 3: Detection Processing - 1 FPS YOLO detection"""
    
    def __init__(self, model, detection_queue, draw_queue):
        self.model = model
        self.detection_queue = detection_queue
        self.draw_queue = draw_queue
        self.running = False
        
        # Detection cache
        self.latest_detection_results = None
        self.detection_lock = threading.Lock()
        
        # Stats
        self.detections_processed = 0
    
    def detect_objects_optimized(self, frame):
        """Optimized YOLO detection"""
        results = self.model(frame, verbose=False)
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
    
    def get_latest_detection(self):
        """Thread-safe access ke detection results"""
        with self.detection_lock:
            return self.latest_detection_results.copy() if self.latest_detection_results else None
    
    def run(self):
        """Detection processing loop"""
        self.running = True
        print("[DETECT] Detection thread started - 1 FPS processing")
        
        while self.running:
            try:
                detection_data = self.detection_queue.get(timeout=1.0)
                
                frame = detection_data['frame']
                frame_number = detection_data['frame_number']
                
                # Process YOLO detection
                persons, hardhats, safety_vests = self.detect_objects_optimized(frame)
                compliance_results = check_safety_compliance(persons, hardhats, safety_vests)
                
                # Create detection results
                detection_results = {
                    'persons': persons,
                    'hardhats': hardhats,
                    'safety_vests': safety_vests,
                    'compliance_results': compliance_results,
                    'frame_number': frame_number,
                    'detection_time': time.time(),
                    'input_type': detection_data['input_type']
                }
                
                # Update cache (thread-safe)
                with self.detection_lock:
                    self.latest_detection_results = detection_results
                
                # Send ke draw thread
                try:
                    draw_data = {
                        'detection_results': detection_results,
                        'original_frame_data': detection_data
                    }
                    self.draw_queue.put(draw_data, block=False)
                    
                except queue.Full:
                    pass  # Skip jika draw thread busy
                
                self.detections_processed += 1
                
                # Console output untuk violations
                violations = sum(1 for result in compliance_results if not result['compliant'])
                if violations > 0:
                    print(f"[DETECT] Frame {frame_number}: {violations} violations detected")
                
                self.detection_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[DETECT] Error: {e}")
        
        print(f"[DETECT] Detection stopped. Processed: {self.detections_processed}")
    
    def stop(self):
        self.running = False

class DrawThread:
    """Thread 4: Drawing - Render annotations dan display"""
    
    def __init__(self, draw_queue, frame_capture_thread, detection_thread):
        self.draw_queue = draw_queue
        self.frame_capture_thread = frame_capture_thread
        self.detection_thread = detection_thread
        self.running = False
        
        # Display stats
        self.frames_displayed = 0
        self.screenshots_taken = 0
        
        # Screenshot management
        self.screenshot_dir = "screenshots_multi_input"
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)
    
    def draw_annotations(self, frame, detection_results, frame_info):
        """Draw annotations dengan detection results"""
        annotated_frame = frame.copy()
        
        if detection_results:
            compliance_results = detection_results['compliance_results']
            hardhats = detection_results['hardhats']
            safety_vests = detection_results['safety_vests']
            persons = detection_results['persons']
            detection_age = time.time() - detection_results['detection_time']
            
            # Draw safety equipment
            for hardhat in hardhats:
                x1, y1, x2, y2 = hardhat['bbox']
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (128, 128, 128), 1)
                cv2.putText(annotated_frame, f"H {hardhat['confidence']:.2f}", 
                           (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 128), 1)
            
            for vest in safety_vests:
                x1, y1, x2, y2 = vest['bbox']
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (128, 128, 128), 1)
                cv2.putText(annotated_frame, f"V {vest['confidence']:.2f}", 
                           (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 128), 1)
            
            # Draw persons dengan compliance
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
                cv2.putText(annotated_frame, f"{status} {person['confidence']:.2f}", 
                           (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            frame_info += f" | P:{len(persons)} | V:{violations} | Age:{detection_age:.1f}s"
        else:
            frame_info += " | No detection data"
        
        # Add frame info
        cv2.putText(annotated_frame, frame_info, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return annotated_frame
    
    def save_screenshot(self, frame, frame_number, input_type, violations=0):
        """Save screenshot"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "violation" if violations > 0 else "manual"
        filename = f"{self.screenshot_dir}/{prefix}_{input_type}_f{frame_number}_{timestamp}.jpg"
        
        cv2.imwrite(filename, frame)
        self.screenshots_taken += 1
        print(f"[DRAW] Screenshot saved: {os.path.basename(filename)}")
        return filename
    
    def run(self):
        """Main display loop"""
        self.running = True
        print("[DRAW] Draw thread started")
        
        cv2.namedWindow('Multi-Input Safety Monitor', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Multi-Input Safety Monitor', 1200, 800)
        
        auto_screenshot = True
        last_screenshot_time = 0
        screenshot_cooldown = 2.0  # 2 detik cooldown antar screenshot
        
        # FPS tracking
        fps_counter = 0
        last_fps_time = time.time()
        current_fps = 0
        
        while self.running:
            # Ambil latest frame
            latest_frame_data = self.frame_capture_thread.get_latest_frame()
            
            if latest_frame_data:
                frame = latest_frame_data['frame']
                frame_number = latest_frame_data['frame_number']
                input_type = latest_frame_data['input_type']
                
                # Progress info untuk video
                progress_info = ""
                if input_type == 'video':
                    frame_pos = latest_frame_data.get('frame_pos', 0)
                    total_frames = latest_frame_data.get('total_frames', 0)
                    if total_frames > 0:
                        progress = (frame_pos / total_frames) * 100
                        progress_info = f" | Progress:{progress:.1f}%"
                
                # Frame info
                frame_info = f"[{input_type.upper()}] F:{frame_number}{progress_info}"
                
                # Get latest detection results
                detection_results = self.detection_thread.get_latest_detection()
                
                # Draw annotations
                annotated_frame = self.draw_annotations(frame, detection_results, frame_info)
                
                # Add thread stats
                stats = [
                    f"Captured: {self.frame_capture_thread.frames_captured} | Detection: {self.detection_thread.detections_processed}",
                    f"Displayed: {self.frames_displayed} | Screenshots: {self.screenshots_taken}",
                    f"Display FPS: {current_fps} | Auto-Screenshot: {'ON' if auto_screenshot else 'OFF'}"
                ]
                
                y_pos = 60
                for stat in stats:
                    cv2.putText(annotated_frame, stat, (10, y_pos), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    y_pos += 20
                
                # Auto screenshot untuk violations
                current_time = time.time()
                if (auto_screenshot and detection_results and 
                    current_time - last_screenshot_time > screenshot_cooldown):
                    
                    violations = sum(1 for result in detection_results['compliance_results'] 
                                   if not result['compliant'])
                    if violations > 0:
                        self.save_screenshot(annotated_frame, frame_number, input_type, violations)
                        last_screenshot_time = current_time
                
                # Display frame
                cv2.imshow('Multi-Input Safety Monitor', annotated_frame)
                self.frames_displayed += 1
                
                # FPS calculation
                fps_counter += 1
                if time.time() - last_fps_time >= 1.0:
                    current_fps = fps_counter
                    fps_counter = 0
                    last_fps_time = time.time()
            
            else:
                # No frame available
                blank = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(blank, "WAITING FOR INPUT...", (150, 240), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.imshow('Multi-Input Safety Monitor', blank)
            
            # Controls
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                self.running = False
            elif key == ord('p'):
                # Pause/Resume based on input type
                print("[DRAW] Pause/Resume toggled")
            elif key == ord('s'):
                if latest_frame_data:
                    self.save_screenshot(annotated_frame if 'annotated_frame' in locals() else frame, 
                                       frame_number, input_type, 0)
            elif key == ord('a'):
                auto_screenshot = not auto_screenshot
                print(f"[DRAW] Auto-screenshot: {'ON' if auto_screenshot else 'OFF'}")
            elif key == ord('l'):
                # Toggle loop untuk video
                print("[DRAW] Loop toggle requested")
        
        cv2.destroyAllWindows()
        print(f"[DRAW] Draw stopped. Displayed: {self.frames_displayed}, Screenshots: {self.screenshots_taken}")
    
    def stop(self):
        self.running = False

class MultiInputSafetySystem:
    """Main system coordinator - Support RTSP dan Video"""
    
    def __init__(self, model, input_source):
        self.model = model
        self.input_source = input_source
        self.input_type = detect_input_type(input_source)
        
        # Queues
        self.frame_capture_queue = queue.Queue(maxsize=5)
        self.detection_queue = queue.Queue(maxsize=3)
        self.draw_queue = queue.Queue(maxsize=3)
        
        # Threads
        self.live_reader = LiveReaderThread(input_source, self.frame_capture_queue)
        self.frame_capture = FrameCaptureThread(self.frame_capture_queue, self.detection_queue)
        self.detection = DetectionThread(model, self.detection_queue, self.draw_queue)
        self.draw = DrawThread(self.draw_queue, self.frame_capture, self.detection)
        
        # System control
        self.running = False
        self.start_time = None
    
    def start_threads(self):
        """Start all threads"""
        threading.Thread(target=self.live_reader.run, daemon=True).start()
        threading.Thread(target=self.frame_capture.run, daemon=True).start()
        threading.Thread(target=self.detection.run, daemon=True).start()
        threading.Thread(target=self.draw.run, daemon=True).start()
        
        print("[SYSTEM] All threads started")
    
    def run(self):
        """Main system coordinator"""
        print("\n🎬 === MULTI-INPUT SAFETY DETECTION SYSTEM ===")
        print(f"📹 Input: {self.input_source}")
        print(f"🎯 Type: {self.input_type.upper()}")
        print("🔧 Architecture:")
        print("  Thread 1: Live Reader (RTSP/Video)")
        print("  Thread 2: Frame Capture")
        print("  Thread 3: Detection (1 FPS)")
        print("  Thread 4: Draw & Display")
        print("\n⚡ Optimizations:")
        print("  • CPU friendly (1 FPS detection)")
        print("  • Smooth display (30 FPS)")
        print("  • Auto-loop video files")
        print("  • Auto-reconnect RTSP")
        print("\nControls:")
        print("  'q' - Quit")
        print("  'p' - Pause/Resume")
        print("  's' - Manual screenshot")
        print("  'a' - Toggle auto-screenshot")
        print("  'l' - Toggle video loop")
        print("=" * 60)
        
        self.start_time = time.time()
        self.start_threads()
        self.running = True
        
        try:
            # Run draw thread in main
            self.draw.run()
        except KeyboardInterrupt:
            print("\n[MAIN] Keyboard interrupt")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Stop all threads"""
        print("\n[MAIN] Shutting down system...")
        
        self.live_reader.stop()
        self.frame_capture.stop()
        self.detection.stop()
        self.draw.stop()
        
        time.sleep(1)
        
        if self.start_time:
            runtime = time.time() - self.start_time
            
            print(f"\n🎯 === MULTI-INPUT SYSTEM SUMMARY ===")
            print(f"⏱️  Runtime: {runtime:.1f} seconds")
            print(f"📡 Input Type: {self.input_type.upper()}")
            print(f"📹 Frames Read: {self.live_reader.frames_read}")
            print(f"📦 Frames Captured: {self.frame_capture.frames_captured}")
            print(f"🧠 Detections: {self.detection.detections_processed}")
            print(f"🎬 Frames Displayed: {self.draw.frames_displayed}")
            print(f"📸 Screenshots: {self.draw.screenshots_taken}")
            if self.input_type == 'rtsp':
                print(f"🔄 Reconnect Attempts: {self.live_reader.reconnect_attempts}")

def main():
    print("🔥 Loading YOLO model...")
    model = YOLO('best.pt')
    print("✅ YOLO model loaded!")
    
    # Input source - bisa RTSP atau video file
    input_sources = [
        # 'rtsp://localhost:8554/stream',  # RTSP stream
        'hse2.mp4',                      # Video file
        'hse2.mp4',
        # Tambah input lain sesuai kebutuhan
    ]
    
    print("\n📹 Available input sources:")
    for i, source in enumerate(input_sources):
        input_type = detect_input_type(source)
        print(f"  {i+1}. {source} ({input_type.upper()})")
    
    # Auto-select first available input
    selected_input = None
    for source in input_sources:
        if detect_input_type(source) == 'rtsp':
            # Untuk RTSP, langsung coba
            selected_input = source
            break
        elif detect_input_type(source) == 'video' and os.path.exists(source):
            # Untuk video, cek file exists
            selected_input = source
            break
    
    if not selected_input:
        print("❌ No valid input source found!")
        print("Make sure:")
        print("  • RTSP server is running, or")
        print("  • Video file exists")
        return
    
    print(f"\n🎯 Selected input: {selected_input}")
    
    system = MultiInputSafetySystem(model, selected_input)
    
    try:
        system.run()
    except Exception as e:
        print(f"\n❌ System error: {e}")
        if hasattr(system, 'cleanup'):
            system.cleanup()

if __name__ == "__main__":
    main()