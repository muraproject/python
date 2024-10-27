import cv2
import numpy as np
import time
from ultralytics import YOLO
from collections import deque

# [Previous GPUProcessor and ObjectTracker classes remain the same]

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

class ObjectTracker:
    def __init__(self, max_trajectory_points=30):
        self.trajectories = {}
        self.max_points = max_trajectory_points
        self.colors = {}
        self.direction_status = {}

    def get_color(self, track_id):
        if track_id not in self.colors:
            self.colors[track_id] = tuple(np.random.randint(0, 255, 3).tolist())
        return self.colors[track_id]

    def update_trajectory(self, track_id, centroid):
        if track_id not in self.trajectories:
            self.trajectories[track_id] = deque(maxlen=self.max_points)
        self.trajectories[track_id].append(centroid)


def process_video_stream(video_source, skip_frames=2):
    model = YOLO('yolov8n.pt')
    gpu_processor = GPUProcessor()
    tracker = ObjectTracker()
    
    object_counts = {
        'car': {'up1': 0, 'up2': 0, 'up3': 0, 'up4': 0, 'up5': 0, 'up6': 0,
                'down1': 0, 'down2': 0, 'down3': 0, 'down4': 0, 'down5': 0, 'down6': 0},
        'motorcycle': {'up1': 0, 'up2': 0, 'up3': 0, 'up4': 0, 'up5': 0, 'up6': 0,
                      'down1': 0, 'down2': 0, 'down3': 0, 'down4': 0, 'down5': 0, 'down6': 0},
        'truck': {'up1': 0, 'up2': 0, 'up3': 0, 'up4': 0, 'up5': 0, 'up6': 0,
                  'down1': 0, 'down2': 0, 'down3': 0, 'down4': 0, 'down5': 0, 'down6': 0},
        'bus': {'up1': 0, 'up2': 0, 'up3': 0, 'up4': 0, 'up5': 0, 'up6': 0,
                'down1': 0, 'down2': 0, 'down3': 0, 'down4': 0, 'down5': 0, 'down6': 0},
        'person': {'up1': 0, 'up2': 0, 'up3': 0, 'up4': 0, 'up5': 0, 'up6': 0,
                  'down1': 0, 'down2': 0, 'down3': 0, 'down4': 0, 'down5': 0, 'down6': 0},
        'bicycle': {'up1': 0, 'up2': 0, 'up3': 0, 'up4': 0, 'up5': 0, 'up6': 0,
                   'down1': 0, 'down2': 0, 'down3': 0, 'down4': 0, 'down5': 0, 'down6': 0}
    }
    
    prev_centroids = {}
    tracking_id = 0
    crossed_ids = {
        'up1': set(), 'up2': set(), 'up3': set(), 'up4': set(), 'up5': set(), 'up6': set(),
        'down1': set(), 'down2': set(), 'down3': set(), 'down4': set(), 'down5': set(), 'down6': set()
    }

    video = cv2.VideoCapture(video_source, cv2.CAP_FFMPEG)
    video.set(cv2.CAP_PROP_BUFFERSIZE, 30)
    video.set(cv2.CAP_PROP_FPS, 30)
    
    if video_source.startswith(('rtsp://', 'http://', 'https://')):
        video.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
        video.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    frame_count = 0
    start_time = time.time()
    fps = 0
    process_this_frame = 0
    
    ret, first_frame = video.read()
    if not ret:
        return object_counts, 0
    
    height, width = first_frame.shape[:2]
    
    # Define six sets of detection lines
    up_lines_y = [
        int(height * 0.15),  # First up line
        int(height * 0.25),  # Second up line
        int(height * 0.35),  # Third up line
        int(height * 0.45),  # Fourth up line
        int(height * 0.55),  # Fifth up line
        int(height * 0.65)   # Sixth up line
    ]
    down_lines_y = [
        int(height * 0.20),  # First down line
        int(height * 0.30),  # Second down line
        int(height * 0.40),  # Third down line
        int(height * 0.50),  # Fourth down line
        int(height * 0.60),  # Fifth down line
        int(height * 0.70)   # Sixth down line
    ]
    
    last_frame_time = time.time()
    
    while True:
        for _ in range(skip_frames):
            ret = video.grab()
            if not ret:
                break

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
            overlay = cpu_frame.copy()
            
            # Draw all detection lines
            for i, y in enumerate(up_lines_y):
                cv2.line(overlay, (0, y), (width, y), (0, 255, 0), 2)
                cv2.putText(overlay, f"UP {i+1} DETECTION", (10, y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            for i, y in enumerate(down_lines_y):
                cv2.line(overlay, (0, y), (width, y), (0, 0, 255), 2)
                cv2.putText(overlay, f"DOWN {i+1} DETECTION", (10, y + 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = model.names[cls]
                    
                    if conf > 0.3 and class_name in ['car', 'person', 'truck', 'bus', 'bicycle', 'motorcycle']:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        centroid_x = (x1 + x2) // 2
                        centroid_y = (y1 + y2) // 2

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
                        
                        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
                        cv2.circle(overlay, (centroid_x, centroid_y), 4, color, -1)
                        
                        points = list(tracker.trajectories[matched_id])
                        for i in range(1, len(points)):
                            cv2.line(overlay, points[i-1], points[i], color, 2)

                        if matched_id in prev_centroids:
                            prev_y = prev_centroids[matched_id][1]
                            direction = ""
                            direction_color = color
                            
                            # Check crossings for all up lines
                            for i, up_y in enumerate(up_lines_y):
                                if prev_y > up_y and centroid_y <= up_y and matched_id not in crossed_ids[f'up{i+1}']:
                                    object_counts[class_name][f'up{i+1}'] += 1
                                    crossed_ids[f'up{i+1}'].add(matched_id)
                                    direction = f"↑ UP {i+1}"
                                    direction_color = (0, 255, 0)
                            
                            # Check crossings for all down lines
                            for i, down_y in enumerate(down_lines_y):
                                if prev_y < down_y and centroid_y >= down_y and matched_id not in crossed_ids[f'down{i+1}']:
                                    object_counts[class_name][f'down{i+1}'] += 1
                                    crossed_ids[f'down{i+1}'].add(matched_id)
                                    direction = f"↓ DOWN {i+1}"
                                    direction_color = (0, 0, 255)

                            label = f"ID:{matched_id} {class_name} {direction}"
                            cv2.putText(overlay, label, (x1, y1-10), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, direction_color, 2)
                        else:
                            label = f"ID:{matched_id} {class_name}"
                            cv2.putText(overlay, label, (x1, y1-10), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            prev_centroids = current_centroids
            
            # Update crossed_ids sets
            for direction in crossed_ids:
                crossed_ids[direction] = {id for id in crossed_ids[direction] if id in current_centroids}

            # Display counts with two rows for each object type
            y_position = 30
            for object_type, counts in object_counts.items():
                # Display first three UP counts
                up_text1 = f"{object_type.capitalize()} UP1: {counts['up1']} UP2: {counts['up2']} UP3: {counts['up3']}"
                cv2.putText(overlay, up_text1, (10, y_position), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                
                # Display first three DOWN counts
                down_text1 = f"DOWN1: {counts['down1']} DOWN2: {counts['down2']} DOWN3: {counts['down3']}"
                cv2.putText(overlay, down_text1, (350, y_position), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
                y_position += 20
                
                # Display next three UP counts
                up_text2 = f"UP4: {counts['up4']} UP5: {counts['up5']} UP6: {counts['up6']}"
                cv2.putText(overlay, up_text2, (10, y_position), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                
                # Display next three DOWN counts
                down_text2 = f"DOWN4: {counts['down4']} DOWN5: {counts['down5']} DOWN6: {counts['down6']}"
                cv2.putText(overlay, down_text2, (350, y_position), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
                y_position += 30

            elapsed_time = current_time - start_time
            if elapsed_time >= 1.0:
                fps = frame_count / elapsed_time
                frame_count = 0
                start_time = current_time

            cv2.putText(overlay, f"FPS: {fps:.2f}", (width - 150, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            cv2.putText(overlay, f"Objects: {len(current_centroids)}", (width - 150, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
            alpha = 0.7
            cv2.addWeighted(overlay, alpha, cpu_frame, 1 - alpha, 0, cpu_frame)
            
            cv2.imshow("Object Detection and Tracking", cpu_frame)

        process_this_frame = (process_this_frame + 1) % 1

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    video.release()
    cv2.destroyAllWindows()

    return object_counts, fps

def main():
    video_source = 'https://cctvjss.jogjakota.go.id/kotabaru/ANPR-Jl-Ahmad-Jazuli.stream/playlist.m3u8'
    skip_frames = 1
    object_counts, fps = process_video_stream(video_source, skip_frames)
    
    print("\nFinal Object Counts:")
    for object_type, counts in object_counts.items():
        print(f"\n{object_type.capitalize()}:")
        print(f"Up lines: 1:{counts['up1']}, 2:{counts['up2']}, 3:{counts['up3']}, 4:{counts['up4']}, 5:{counts['up5']}, 6:{counts['up6']}")
        print(f"Down lines: 1:{counts['down1']}, 2:{counts['down2']}, 3:{counts['down3']}, 4:{counts['down4']}, 5:{counts['down5']}, 6:{counts['down6']}")
    print(f"\nAverage FPS: {fps:.2f}")

if __name__ == "__main__":
    main()