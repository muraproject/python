import cv2
import numpy as np
import time
from ultralytics import YOLO
from collections import deque

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

class VehicleTracker:
    def __init__(self, max_trajectory_points=30):
        self.trajectories = {}
        self.max_points = max_trajectory_points
        self.colors = {}
        self.direction_status = {}  # Track movement direction for each object

    def get_color(self, track_id):
        if track_id not in self.colors:
            self.colors[track_id] = tuple(np.random.randint(0, 255, 3).tolist())
        return self.colors[track_id]

    def update_trajectory(self, track_id, centroid):
        if track_id not in self.trajectories:
            self.trajectories[track_id] = deque(maxlen=self.max_points)
        self.trajectories[track_id].append(centroid)

def process_video_stream(video_source, skip_frames=2):
    # Initialize YOLOv11s instead of YOLOv8
    model = YOLO('yolo11s.pt')
    gpu_processor = GPUProcessor()
    tracker = VehicleTracker()
    
    # Extended vehicle classes for YOLOv11
    vehicle_counts = {
        'car': {'up': 0, 'down': 0},
        'motorcycle': {'up': 0, 'down': 0},
        'truck': {'up': 0, 'down': 0},
        'bus': {'up': 0, 'down': 0},
        'bicycle': {'up': 0, 'down': 0}  # Additional class for YOLOv11
    }
    
    prev_centroids = {}
    tracking_id = 0
    crossed_ids = set()

    video = cv2.VideoCapture(video_source, cv2.CAP_FFMPEG)
    video.set(cv2.CAP_PROP_BUFFERSIZE, 30)
    video.set(cv2.CAP_PROP_FPS, 30)
    
    if video_source.startswith(('rtsp://', 'http://', 'https://')):
        video.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
        video.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    frame_count = 0
    start_time = time.time()
    last_fps_time = start_time
    fps = 0
    process_this_frame = 0
    
    ret, first_frame = video.read()
    if not ret:
        return vehicle_counts, 0
    
    height, width = first_frame.shape[:2]
    
    # Define two detection lines
    line_spacing = 50
    up_line_y = int(height * 0.3)
    down_line_y = int(height * 0.45)
    
    dropped_frames = 0
    last_frame_time = time.time()
    
    while True:
        for _ in range(skip_frames):
            ret = video.grab()
            if not ret:
                break
            dropped_frames += 1

        ret, frame = video.read()
        if not ret:
            break
            
        frame_count += 1
        current_time = time.time()
        frame_time = current_time - last_frame_time
        last_frame_time = current_time

        if process_this_frame == 0:
            # Resize frame for YOLOv11s optimal input
            frame = cv2.resize(frame, (640, 640))
            
            gpu_frame = gpu_processor.to_gpu(frame)
            
            if gpu_processor.use_gpu:
                # Enhanced preprocessing for YOLOv11s
                gpu_frame = cv2.GaussianBlur(gpu_frame, (3, 3), 0)
                gpu_frame = cv2.convertScaleAbs(gpu_frame, alpha=1.2, beta=5)
            
            cpu_frame = gpu_processor.to_cpu(gpu_frame)
            results = model(cpu_frame, verbose=False)  # Reduced verbosity
            
            current_centroids = {}
            overlay = cpu_frame.copy()
            
            # Draw detection lines with labels
            cv2.line(overlay, (0, up_line_y), (width, up_line_y), (0, 255, 0), 2)
            cv2.putText(overlay, "UP DETECTION", (10, up_line_y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.line(overlay, (0, down_line_y), (width, down_line_y), (0, 0, 255), 4)
            cv2.putText(overlay, "DOWN DETECTION", (10, down_line_y + 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = model.names[cls]
                    
                    # Adjusted confidence threshold for YOLOv11s
                    if conf > 0.4 and class_name in vehicle_counts.keys():
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        centroid_x = (x1 + x2) // 2
                        centroid_y = (y1 + y2) // 2

                        # Enhanced tracking for YOLOv11s
                        if prev_centroids:
                            prev_points = np.array([[p[0], p[1]] for p in prev_centroids.values()])
                            curr_point = np.array([centroid_x, centroid_y])
                            distances = np.linalg.norm(prev_points - curr_point, axis=1)
                            min_distance_idx = np.argmin(distances)
                            min_distance = distances[min_distance_idx]
                            matched_id = list(prev_centroids.keys())[min_distance_idx] if min_distance <= 50 else None
                        else:
                            matched_id = None

                        if matched_id is None:
                            matched_id = tracking_id
                            tracking_id += 1

                        current_centroids[matched_id] = (centroid_x, centroid_y, class_name)
                        tracker.update_trajectory(matched_id, (centroid_x, centroid_y))
                        color = tracker.get_color(matched_id)
                        
                        # Enhanced visualization for YOLOv11s
                        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
                        cv2.circle(overlay, (centroid_x, centroid_y), 4, color, -1)
                        
                        # Draw enhanced trajectory
                        points = list(tracker.trajectories[matched_id])
                        for i in range(1, len(points)):
                            thickness = int(np.sqrt(float(i + 1))) + 1
                            cv2.line(overlay, points[i-1], points[i], color, thickness)

                        # Dual line crossing detection
                        if matched_id in prev_centroids and matched_id not in crossed_ids:
                            prev_y = prev_centroids[matched_id][1]
                            
                            if prev_y > up_line_y and centroid_y <= up_line_y:
                                vehicle_counts[class_name]['up'] += 1
                                crossed_ids.add(matched_id)
                                direction = "↑ UP"
                                direction_color = (0, 255, 0)
                            
                            elif prev_y < down_line_y and centroid_y >= down_line_y:
                                vehicle_counts[class_name]['down'] += 1
                                crossed_ids.add(matched_id)
                                direction = "↓ DOWN"
                                direction_color = (0, 0, 255)
                            else:
                                direction = ""
                                direction_color = color

                            # Enhanced label with confidence
                            label = f"ID:{matched_id} {class_name} {conf:.2f} {direction}"
                            cv2.putText(overlay, label, (x1, y1-10), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, direction_color, 2)
                        else:
                            label = f"ID:{matched_id} {class_name} {conf:.2f}"
                            cv2.putText(overlay, label, (x1, y1-10), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # Update tracking
            prev_centroids = current_centroids
            crossed_ids = {id for id in crossed_ids if id in current_centroids}

            # Enhanced display with more detailed counts
            y_position = 30
            for vehicle_type, counts in vehicle_counts.items():
                up_text = f"{vehicle_type.capitalize()} UP: {counts['up']}"
                down_text = f"DOWN: {counts['down']}"
                cv2.putText(overlay, up_text, (10, y_position), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                cv2.putText(overlay, down_text, (200, y_position), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                y_position += 30

            # Enhanced statistics display
            cv2.putText(overlay, f"FPS: {fps:.2f}", (width - 150, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            cv2.putText(overlay, f"Objects: {len(current_centroids)}", (width - 150, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
            # Blend overlay with adjustable transparency
            alpha = 0.7
            cv2.addWeighted(overlay, alpha, cpu_frame, 1 - alpha, 0, cpu_frame)
            
            cv2.imshow("YOLOv11s Vehicle Tracking", cpu_frame)

        process_this_frame = (process_this_frame + 1) % 1

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    video.release()
    cv2.destroyAllWindows()

    return vehicle_counts, fps

def main():
    video_source = 'https://cctvjss.jogjakota.go.id/kotabaru/ANPR-Jl-Ahmad-Jazuli.stream/playlist.m3u8'
    skip_frames = 2
    vehicle_counts, fps = process_video_stream(video_source, skip_frames)
    
    print("\nFinal Vehicle Counts:")
    for vehicle_type, counts in vehicle_counts.items():
        print(f"{vehicle_type.capitalize()}: Up {counts['up']}, Down {counts['down']}")
    print(f"\nAverage FPS: {fps:.2f}")

if __name__ == "__main__":
    main()