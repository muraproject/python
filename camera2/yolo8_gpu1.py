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
        self.trajectories = {}  # Store centroid history for each tracked object
        self.max_points = max_trajectory_points
        self.colors = {}  # Store unique color for each tracked object

    def get_color(self, track_id):
        if track_id not in self.colors:
            # Generate random color for new tracked object
            self.colors[track_id] = tuple(np.random.randint(0, 255, 3).tolist())
        return self.colors[track_id]

    def update_trajectory(self, track_id, centroid):
        if track_id not in self.trajectories:
            self.trajectories[track_id] = deque(maxlen=self.max_points)
        self.trajectories[track_id].append(centroid)

def process_video_stream(video_source, skip_frames=2):
    model = YOLO('yolov8n.pt')
    gpu_processor = GPUProcessor()
    tracker = VehicleTracker()
    
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
    horizontal_line_y = int(height * 0.3)
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
            gpu_frame = gpu_processor.to_gpu(frame)
            
            if gpu_processor.use_gpu:
                gpu_frame = cv2.GaussianBlur(gpu_frame, (3, 3), 0)
            
            cpu_frame = gpu_processor.to_cpu(gpu_frame)
            results = model(cpu_frame)
            
            current_centroids = {}
            
            # Create visualization overlay
            overlay = cpu_frame.copy()
            
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

                        # Centroid tracking
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
                        
                        # Update trajectory
                        tracker.update_trajectory(matched_id, (centroid_x, centroid_y))
                        
                        # Draw centroid and trajectory
                        color = tracker.get_color(matched_id)
                        
                        # Draw bounding box
                        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
                        
                        # Draw centroid point
                        cv2.circle(overlay, (centroid_x, centroid_y), 4, color, -1)
                        
                        # Draw ID and class
                        label = f"ID:{matched_id} {class_name}"
                        cv2.putText(overlay, label, (x1, y1-10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                        
                        # Draw trajectory
                        points = list(tracker.trajectories[matched_id])
                        for i in range(1, len(points)):
                            cv2.line(overlay, points[i-1], points[i], color, 2)

                        # Line crossing detection
                        if matched_id in prev_centroids and matched_id not in crossed_ids:
                            prev_y = prev_centroids[matched_id][1]
                            if prev_y < horizontal_line_y and centroid_y >= horizontal_line_y:
                                vehicle_counts[class_name]['down'] += 1
                                crossed_ids.add(matched_id)
                            elif prev_y > horizontal_line_y and centroid_y <= horizontal_line_y:
                                vehicle_counts[class_name]['up'] += 1
                                crossed_ids.add(matched_id)

            # Update tracking
            prev_centroids = current_centroids
            crossed_ids = {id for id in crossed_ids if id in current_centroids}

            # Draw counting line
            cv2.line(overlay, (0, horizontal_line_y), (width, horizontal_line_y), 
                     (0, 0, 255), 2)

            # Update FPS calculation
            if current_time - last_fps_time >= 1.0:
                fps = frame_count / (current_time - start_time)
                last_fps_time = current_time

            # Display information
            y_position = 30
            for vehicle_type, counts in vehicle_counts.items():
                text = f"{vehicle_type.capitalize()}: Up {counts['up']} Down {counts['down']}"
                cv2.putText(overlay, text, (10, y_position), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                y_position += 30

            cv2.putText(overlay, f"FPS: {fps:.2f}", (width - 150, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.putText(overlay, f"Tracked Objects: {len(current_centroids)}", (width - 150, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Blend the overlay with the original frame
            alpha = 0.7
            cv2.addWeighted(overlay, alpha, cpu_frame, 1 - alpha, 0, cpu_frame)
            
            cv2.imshow("Vehicle Tracking with Centroids", cpu_frame)

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