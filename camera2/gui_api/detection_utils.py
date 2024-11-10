import cv2
import numpy as np
import os
from datetime import datetime
import csv
from queue import Queue
import time
from threading import Thread, Lock

class GPUProcessor:
    def __init__(self):
        self.use_gpu = self._init_gpu()
        if self.use_gpu:
            cv2.ocl.setUseOpenCL(True)
            print("OpenCL status:", cv2.ocl.useOpenCL())
            print("OpenCL device:", cv2.ocl.Device.getDefault().name())

    def _init_gpu(self):
        try:
            test_mat = cv2.UMat(np.zeros((100, 100), dtype=np.uint8))
            cv2.blur(test_mat, (3, 3))
            print("GPU acceleration is available using OpenCV UMat")
            return True
        except Exception as e:
            print(f"GPU acceleration not available: {e}")
            return False

    def to_gpu(self, frame):
        if not isinstance(frame, cv2.UMat) and self.use_gpu:
            return cv2.UMat(frame)
        return frame

    def to_cpu(self, frame):
        if isinstance(frame, cv2.UMat):
            return frame.get()
        return frame

class DetectionManager:
    def __init__(self):
        # GPU Processor
        self.gpu_processor = GPUProcessor()
        
        # Setup direktori
        self.data_dir = os.path.join(os.getcwd(), "data")
        self.screenshot_dir = os.path.join(self.data_dir, "screenshots")
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
        # Frame management
        self.current_frame = None
        self.frame_lock = Lock()
        self.process_this_frame = 0
        self.skip_frames = 2
        
        # Detection results management
        self.max_screenshots = 10
        self.current_screenshot_index = 0
        self.screenshot_files = []
        self.detection_results = []
        
        # Performance metrics
        self.frame_count = 0
        self.start_time = time.time()
        self.last_fps_time = self.start_time
        self.fps = 0
        
        # Detection status
        self.fire_detected = False
        self.smoke_detected = False
        self.current_overlay = None
        
        # Display rotation thread
        self.display_thread = Thread(target=self.rotate_display, daemon=True)
        self.stop_display = False
        self.display_thread.start()

    def create_red_overlay(self, frame):
        """Create a semi-transparent red overlay"""
        overlay = frame.copy()
        red_mask = np.zeros_like(frame)
        red_mask[:,:] = (0, 0, 255)  # BGR format - pure red
        cv2.addWeighted(red_mask, 0.3, overlay, 0.7, 0, overlay)
        return overlay

    def process_results(self, results, fire_threshold, smoke_threshold):
        """Process YOLO detection results"""
        try:
            if self.current_frame is None:
                return

            with self.frame_lock:
                frame = self.current_frame.copy()

            # Update FPS
            self.frame_count += 1
            current_time = time.time()
            if current_time - self.last_fps_time >= 1.0:
                self.fps = self.frame_count / (current_time - self.start_time)
                self.last_fps_time = current_time

            if self.process_this_frame == 0:
                # Process frame with GPU
                gpu_frame = self.gpu_processor.to_gpu(frame)
                if self.gpu_processor.use_gpu:
                    gpu_frame = cv2.GaussianBlur(gpu_frame, (3, 3), 0)
                
                cpu_frame = self.gpu_processor.to_cpu(gpu_frame)
                display_frame = cpu_frame.copy()
                
                self.fire_detected = False
                self.smoke_detected = False
                max_conf = 0.0
                detections = []

                # Process detections
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        cls = int(box.cls[0])
                        conf = float(box.conf[0])
                        
                        threshold = fire_threshold if cls == 0 else smoke_threshold
                        if conf > threshold:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            
                            # Update detection status
                            if cls == 0:  # Fire
                                self.fire_detected = True
                                color = (0, 0, 255)
                                label = f"Fire: {conf:.2f}"
                            else:  # Smoke
                                self.smoke_detected = True
                                color = (255, 0, 0)
                                label = f"Smoke: {conf:.2f}"
                            
                            # Draw detection box
                            cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                            cv2.putText(display_frame, label, (x1, y1-10),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                            
                            max_conf = max(max_conf, conf)
                            detections.append((cls, conf, (x1, y1, x2, y2)))

                # Apply overlay if fire detected
                if self.fire_detected:
                    display_frame = self.create_red_overlay(display_frame)
                    h, w = display_frame.shape[:2]
                    cv2.putText(display_frame, "FIRE DETECTED!", 
                              (w // 4, h // 2),
                              cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)

                # Add FPS counter
                cv2.putText(display_frame, f"FPS: {self.fps:.2f}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

                # Save screenshot if detection found
                if detections:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    screenshot_path = os.path.join(self.screenshot_dir, 
                                                 f"detection_{timestamp}.jpg")
                    cv2.imwrite(screenshot_path, display_frame)

                    # Update detection results with rotation
                    if len(self.detection_results) < self.max_screenshots:
                        self.detection_results.append((max_conf, screenshot_path, display_frame))
                        self.screenshot_files.append(screenshot_path)
                    else:
                        # Remove oldest screenshot
                        old_path = self.screenshot_files[self.current_screenshot_index]
                        if os.path.exists(old_path):
                            os.remove(old_path)
                        
                        self.screenshot_files[self.current_screenshot_index] = screenshot_path
                        self.detection_results[self.current_screenshot_index] = (max_conf, screenshot_path, display_frame)
                    
                    self.current_screenshot_index = (self.current_screenshot_index + 1) % self.max_screenshots

            self.process_this_frame = (self.process_this_frame + 1) % self.skip_frames

        except Exception as e:
            print(f"Error processing results: {e}")
            import traceback
            traceback.print_exc()

    def rotate_display(self):
        """Thread untuk merotasi tampilan screenshot"""
        while not self.stop_display:
            if self.detection_results:
                with self.frame_lock:
                    self.current_display_index = (
                        getattr(self, 'current_display_index', 0) + 1
                    ) % len(self.detection_results)
            time.sleep(0.1)

    def get_display_frame(self):
        """Get frame untuk display"""
        if not self.detection_results:
            return self.current_frame
            
        with self.frame_lock:
            current_result = self.detection_results[
                getattr(self, 'current_display_index', 0)
            ]
            # Return the processed frame directly from memory
            return current_result[2]

    def update_current_frame(self, frame):
        """Update frame saat ini"""
        with self.frame_lock:
            self.current_frame = frame.copy()

    def cleanup(self):
        """Cleanup resources"""
        self.stop_display = True
        if self.display_thread.is_alive():
            self.display_thread.join()
        
        # Clear screenshot directory
        for file_path in self.screenshot_files:
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Reset variables
        self.screenshot_files = []
        self.detection_results = []
        self.current_screenshot_index = 0