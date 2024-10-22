import cv2
import numpy as np
import time
import threading
from queue import Queue
from ultralytics import YOLO
import multiprocessing

class GPUProcessor:
    def __init__(self):
        self.use_gpu = self._init_gpu()
        if self.use_gpu:
            cv2.ocl.setUseOpenCL(True)
            print("OpenCL status:", cv2.ocl.useOpenCL())
            print("OpenCL device:", cv2.ocl.Device.getDefault().name())
        
        # Pre-create CLAHE object
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    def _init_gpu(self):
        try:
            test_mat = cv2.UMat(np.zeros((100, 100), dtype=np.uint8))
            cv2.blur(test_mat, (3, 3))
            print("GPU acceleration is available using OpenCV UMat")
            return True
        except Exception as e:
            print(f"GPU acceleration not available: {e}")
            return False

    def get_dimensions(self, frame):
        """Safely get dimensions whether frame is UMat or numpy array"""
        if isinstance(frame, cv2.UMat):
            return frame.get().shape
        return frame.shape

    def to_gpu(self, frame):
        """Convert numpy array to UMat if not already"""
        if not isinstance(frame, cv2.UMat) and self.use_gpu:
            return cv2.UMat(frame)
        return frame

    def to_cpu(self, frame):
        """Convert UMat to numpy array if needed"""
        if isinstance(frame, cv2.UMat):
            return frame.get()
        return frame

    def process_frame(self, frame):
        """Lightweight GPU-accelerated processing"""
        if not self.use_gpu:
            return frame

        gpu_frame = self.to_gpu(frame)
        
        # Basic enhancement only
        # Gaussian blur untuk mengurangi noise
        gpu_frame = cv2.GaussianBlur(gpu_frame, (3, 3), 0)
        
        # Simple contrast enhancement
        gpu_frame = cv2.convertScaleAbs(gpu_frame, alpha=1.1, beta=0)

        return gpu_frame

def process_video_stream(video_source):
    # Initialize
    model = YOLO('yolov8n.pt')
    gpu_processor = GPUProcessor()
    
    vehicle_counts = {
        'car': {'up': 0, 'down': 0},
        'motorcycle': {'up': 0, 'down': 0},
        'truck': {'up': 0, 'down': 0},
        'bus': {'up': 0, 'down': 0}
    }
    
    prev_centroids = {}
    tracking_id = 0
    crossed_ids = set()

    video = cv2.VideoCapture(video_source, cv2.CAP_FFMPEG)
    video.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    frame_count = 0
    start_time = time.time()
    last_fps_time = start_time
    fps = 0
    
    # Get initial frame dimensions
    ret, first_frame = video.read()
    if not ret:
        return vehicle_counts, 0
    
    height, width = first_frame.shape[:2]
    horizontal_line_y = int(height * 0.5)
    
    while True:
        ret, frame = video.read()
        if not ret:
            break
            
        frame_count += 1
        
        # Process frame on GPU (lightweight processing)
        gpu_frame = gpu_processor.to_gpu(frame)
        processed_frame = gpu_processor.process_frame(gpu_frame)
        
        # Convert to CPU only once for YOLO
        cpu_frame = gpu_processor.to_cpu(processed_frame)
        results = model(cpu_frame)
        
        current_centroids = {}
        
        # Process detections
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                class_name = model.names[cls]
                
                if conf > 0.3 and class_name in ['car', 'motorcycle', 'truck', 'bus']:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    centroid_x = (x1 + x2) // 2
                    centroid_y = (y1 + y2) // 2

                    # Tracking
                    min_distance = float('inf')
                    matched_id = None
                    for id, (prev_x, prev_y, prev_class) in prev_centroids.items():
                        distance = np.sqrt((centroid_x - prev_x)**2 + (centroid_y - prev_y)**2)
                        if distance < min_distance:
                            min_distance = distance
                            matched_id = id

                    if matched_id is None or min_distance > 50:
                        matched_id = tracking_id
                        tracking_id += 1

                    current_centroids[matched_id] = (centroid_x, centroid_y, class_name)

                    # Line crossing
                    if matched_id in prev_centroids and matched_id not in crossed_ids:
                        prev_y = prev_centroids[matched_id][1]
                        if prev_y < horizontal_line_y and centroid_y >= horizontal_line_y:
                            vehicle_counts[class_name]['down'] += 1
                            crossed_ids.add(matched_id)
                        elif prev_y > horizontal_line_y and centroid_y <= horizontal_line_y:
                            vehicle_counts[class_name]['up'] += 1
                            crossed_ids.add(matched_id)

                    # Draw bounding box
                    cv2.rectangle(cpu_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Update tracking
        prev_centroids = current_centroids
        crossed_ids = {id for id in crossed_ids if id in current_centroids}
        
        # Draw line
        cv2.line(cpu_frame, (0, horizontal_line_y), (width, horizontal_line_y), 
                 (0, 0, 255), 2)
        
        # Update FPS setiap detik
        current_time = time.time()
        if current_time - last_fps_time >= 1.0:
            fps = frame_count / (current_time - start_time)
            last_fps_time = current_time
        
        # Display counts and FPS
        y_position = 30
        for vehicle_type, counts in vehicle_counts.items():
            text = f"{vehicle_type.capitalize()}: Up {counts['up']} Down {counts['down']}"
            cv2.putText(cpu_frame, text, (10, y_position), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            y_position += 30
        
        cv2.putText(cpu_frame, f"FPS: {fps:.2f}", (width - 150, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        cv2.imshow("Vehicle Detection and Counting", cpu_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    video.release()
    cv2.destroyAllWindows()

    return vehicle_counts, fps

def main():
    video_source = 'https://cctvjss.jogjakota.go.id/kotabaru/ANPR-Jl-Ahmad-Jazuli.stream/playlist.m3u8'
    vehicle_counts, fps = process_video_stream(video_source)
    
    print("\nFinal Vehicle Counts:")
    for vehicle_type, counts in vehicle_counts.items():
        print(f"{vehicle_type.capitalize()}: Up {counts['up']}, Down {counts['down']}")
    print(f"\nAverage FPS: {fps:.2f}")

if __name__ == "__main__":
    main()