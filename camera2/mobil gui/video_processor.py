import cv2
import numpy as np
from ultralytics import YOLO
from collections import deque

class VideoProcessor:
    def get_processed_frame(self, line_positions):
        ret, frame = self.cap.read()
        if not ret:
            self.cap.release()
            self.cap = cv2.VideoCapture(self.video_source)
            return None

        # Resize frame
        frame = cv2.resize(frame, (800, 600))
        height, width = frame.shape[:2]
        
        # Create overlay
        overlay = frame.copy()
        
        # Tampilkan FPS dan jumlah objek terdeteksi
        self.frame_count += 1
        current_time = time.time()
        if current_time - self.fps_time >= 1.0:
            self.fps = self.frame_count / (current_time - self.fps_time)
            self.frame_count = 0
            self.fps_time = current_time

        # Draw monitoring info
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(overlay, f'FPS: {self.fps:.1f}', (width-150, 30), font, 0.6, (0,255,0), 2)
        
        # Draw lines with absolute positions
        try:
            for i in range(1, 7):
                # UP lines
                y_pos = int(height * (i * 0.1))  # 10%, 20%, 30%, etc of height
                cv2.line(overlay, (0, y_pos), (width, y_pos), (0, 255, 0), 2)
                cv2.putText(overlay, f"UP {i}", (10, y_pos - 10), font, 0.5, (0, 255, 0), 2)
                
                # DOWN lines
                y_pos_down = int(height * (i * 0.1 + 0.05))  # 15%, 25%, 35%, etc
                cv2.line(overlay, (0, y_pos_down), (width, y_pos_down), (0, 0, 255), 2)
                cv2.putText(overlay, f"DOWN {i}", (10, y_pos_down + 20), font, 0.5, (0, 0, 255), 2)

        except Exception as e:
            print(f"Error drawing lines: {e}")

        # Detect and track objects
        results = self.model(frame)
        current_centroids = {}
        
        # Real-time monitoring panel
        monitor_y = 60
        vehicle_counts = {
            'car': {'up': 0, 'down': 0},
            'bus': {'up': 0, 'down': 0},
            'truck': {'up': 0, 'down': 0},
            'person': {'up': 0, 'down': 0},
            'motorcycle': {'up': 0, 'down': 0}
        }
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                class_name = self.model.names[cls]
                
                if conf > 0.3 and class_name in ['car', 'person', 'truck', 'bus', 'motorcycle']:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    centroid_x = (x1 + x2) // 2
                    centroid_y = (y1 + y2) // 2

                    # Update vehicle counts
                    if centroid_y < height/2:
                        vehicle_counts[class_name]['up'] += 1
                    else:
                        vehicle_counts[class_name]['down'] += 1

                    # Draw detection box and label
                    color = self.get_color(class_name)
                    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(overlay, f"{class_name} {conf:.2f}", (x1, y1-10), font, 0.5, color, 2)

        # Draw real-time monitoring panel
        panel_x = width - 200
        panel_y = 60
        cv2.rectangle(overlay, (panel_x-10, panel_y-30), (panel_x+190, panel_y+150), (0,0,0), -1)
        cv2.putText(overlay, "REAL-TIME MONITORING", (panel_x, panel_y-10), font, 0.6, (255,255,255), 2)
        
        y_offset = panel_y + 20
        for vehicle in vehicle_counts:
            counts = vehicle_counts[vehicle]
            text = f"{vehicle.upper()}: UP={counts['up']} DOWN={counts['down']}"
            cv2.putText(overlay, text, (panel_x, y_offset), font, 0.5, (255,255,255), 1)
            y_offset += 25

        # Draw total counts for current interval
        total_panel_y = y_offset + 20
        cv2.rectangle(overlay, (panel_x-10, total_panel_y-10), (panel_x+190, total_panel_y+150), (0,0,0), -1)
        cv2.putText(overlay, "TOTAL COUNTS", (panel_x, total_panel_y+10), font, 0.6, (255,255,255), 2)
        
        y_offset = total_panel_y + 40
        for vehicle in self.counts:
            up_total = sum(self.counts[vehicle][f'up{i}'] for i in range(1, 7))
            down_total = sum(self.counts[vehicle][f'down{i}'] for i in range(1, 7))
            text = f"{vehicle.upper()}: UP={up_total} DOWN={down_total}"
            cv2.putText(overlay, text, (panel_x, y_offset), font, 0.5, (255,255,255), 1)
            y_offset += 25

        # Blend overlay with original frame
        result = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
        return result

    def __init__(self):
        super().__init__()
        self.frame_count = 0
        self.fps = 0
        self.fps_time = time.time()
    def __init__(self):
        # Initialize YOLO model
        self.model = YOLO('yolov8n.pt')
        
        # Initialize video capture
        self.video_source = 'https://cctvjss.jogjakota.go.id/kotabaru/ANPR-Jl-Ahmad-Jazuli.stream/playlist.m3u8'
        self.cap = cv2.VideoCapture(self.video_source)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Initialize tracking variables
        self.trajectories = {}
        self.prev_centroids = {}
        self.tracking_id = 0
        self.colors = {}
        self.max_trajectory_points = 30
        
        # Initialize counters
        self.init_counters()
        
        # Initialize crossed IDs sets
        self.crossed_ids = {
            'up1': set(), 'up2': set(), 'up3': set(), 'up4': set(), 'up5': set(), 'up6': set(),
            'down1': set(), 'down2': set(), 'down3': set(), 'down4': set(), 'down5': set(), 'down6': set()
        }

    def init_counters(self):
        self.counts = {
            'car': {'up1': 0, 'up2': 0, 'up3': 0, 'up4': 0, 'up5': 0, 'up6': 0,
                   'down1': 0, 'down2': 0, 'down3': 0, 'down4': 0, 'down5': 0, 'down6': 0},
            'motorcycle': {'up1': 0, 'up2': 0, 'up3': 0, 'up4': 0, 'up5': 0, 'up6': 0,
                         'down1': 0, 'down2': 0, 'down3': 0, 'down4': 0, 'down5': 0, 'down6': 0},
            'truck': {'up1': 0, 'up2': 0, 'up3': 0, 'up4': 0, 'up5': 0, 'up6': 0,
                     'down1': 0, 'down2': 0, 'down3': 0, 'down4': 0, 'down5': 0, 'down6': 0},
            'bus': {'up1': 0, 'up2': 0, 'up3': 0, 'up4': 0, 'up5': 0, 'up6': 0,
                   'down1': 0, 'down2': 0, 'down3': 0, 'down4': 0, 'down5': 0, 'down6': 0},
            'person': {'up1': 0, 'up2': 0, 'up3': 0, 'up4': 0, 'up5': 0, 'up6': 0,
                      'down1': 0, 'down2': 0, 'down3': 0, 'down4': 0, 'down5': 0, 'down6': 0}
        }

    def get_color(self, track_id):
        if track_id not in self.colors:
            self.colors[track_id] = tuple(np.random.randint(0, 255, 3).tolist())
        return self.colors[track_id]

    def update_trajectory(self, track_id, centroid):
        if track_id not in self.trajectories:
            self.trajectories[track_id] = deque(maxlen=self.max_trajectory_points)
        self.trajectories[track_id].append(centroid)

    def get_processed_frame(self, line_positions):
        ret, frame = self.cap.read()
        if not ret:
            # Try to reconnect if stream is lost
            self.cap.release()
            self.cap = cv2.VideoCapture(self.video_source)
            return None

        # Resize frame to smaller size
        # Ubah ukuran sesuai kebutuhan, misal 640x480 atau 800x600
        frame = cv2.resize(frame, (800, 600))
        height, width = frame.shape[:2]
        
        # Sesuaikan posisi garis dengan ukuran baru
        scale_y = height / 1080  # asumsi ukuran asli 1080p
        
        current_centroids = {}
        overlay = frame.copy()
        
        try:
            # Draw detection lines dengan posisi yang disesuaikan
            for i in range(1, 7):
                # Draw UP lines (green)
                up_y = int(float(line_positions[f'up{i}']) * scale_y)
                cv2.line(overlay, (0, up_y), (width, up_y), (0, 255, 0), 2)
                cv2.putText(overlay, f"UP {i}", (10, up_y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # Draw DOWN lines (red)
                down_y = int(float(line_positions[f'down{i}']) * scale_y)
                cv2.line(overlay, (0, down_y), (width, down_y), (0, 0, 255), 2)
                cv2.putText(overlay, f"DOWN {i}", (10, down_y + 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        except Exception as e:
            print(f"Error drawing lines: {e}")
            return frame

        # Run YOLO detection on the resized frame
        results = self.model(frame)
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                class_name = self.model.names[cls]
                
                if conf > 0.3 and class_name in ['car', 'person', 'truck', 'bus', 'motorcycle']:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    centroid_x = (x1 + x2) // 2
                    centroid_y = (y1 + y2) // 2

                    # Track object
                    if self.prev_centroids:
                        prev_points = np.array([[p[0], p[1]] for p in self.prev_centroids.values()])
                        curr_point = np.array([centroid_x, centroid_y])
                        distances = np.linalg.norm(prev_points - curr_point, axis=1)
                        min_distance_idx = np.argmin(distances)
                        min_distance = distances[min_distance_idx]
                        matched_id = list(self.prev_centroids.keys())[min_distance_idx] if min_distance <= 50 else None
                    else:
                        matched_id = None

                    if matched_id is None:
                        matched_id = self.tracking_id
                        self.tracking_id += 1

                    current_centroids[matched_id] = (centroid_x, centroid_y, class_name)
                    self.update_trajectory(matched_id, (centroid_x, centroid_y))
                    color = self.get_color(matched_id)
                    
                    # Draw bounding box and trajectory
                    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
                    cv2.circle(overlay, (centroid_x, centroid_y), 4, color, -1)
                    
                    # Draw trajectory
                    points = list(self.trajectories[matched_id])
                    for i in range(1, len(points)):
                        cv2.line(overlay, points[i-1], points[i], color, 2)

                    # Check line crossings
                    if matched_id in self.prev_centroids:
                        prev_y = self.prev_centroids[matched_id][1]
                        
                        try:
                            # Check all UP lines
                            for i in range(1, 7):
                                up_y = int(float(line_positions[f'up{i}']))
                                if prev_y > up_y and centroid_y <= up_y and matched_id not in self.crossed_ids[f'up{i}']:
                                    self.counts[class_name][f'up{i}'] += 1
                                    self.crossed_ids[f'up{i}'].add(matched_id)
                                    direction = f"↑ UP {i}"
                                    cv2.putText(overlay, f"{class_name} {direction}", (x1, y1-10),
                                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                            
                            # Check all DOWN lines
                            for i in range(1, 7):
                                down_y = int(float(line_positions[f'down{i}']))
                                if prev_y < down_y and centroid_y >= down_y and matched_id not in self.crossed_ids[f'down{i}']:
                                    self.counts[class_name][f'down{i}'] += 1
                                    self.crossed_ids[f'down{i}'].add(matched_id)
                                    direction = f"↓ DOWN {i}"
                                    cv2.putText(overlay, f"{class_name} {direction}", (x1, y1-10),
                                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                        except Exception as e:
                            print(f"Error checking line crossings: {e}")

        # Update previous centroids
        self.prev_centroids = {k: (v[0], v[1]) for k, v in current_centroids.items()}
        
        # Clean up crossed_ids sets
        for direction in self.crossed_ids:
            self.crossed_ids[direction] = {id for id in self.crossed_ids[direction] if id in current_centroids}

        # Add count display
        y_position = 30
        for object_type in ['car', 'bus', 'truck', 'motorcycle', 'person']:
            counts = self.counts[object_type]
            cv2.putText(overlay, f"{object_type.capitalize()}: "
                       f"UP: {sum(counts[f'up{i}'] for i in range(1, 7))} "
                       f"DOWN: {sum(counts[f'down{i}'] for i in range(1, 7))}", 
                       (10, y_position), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            y_position += 20

        # Blend overlay with original frame
        alpha = 0.7
        frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
        
        return frame

    def get_current_counts(self):
        return self.counts.copy()

    def __del__(self):
        self.cap.release()