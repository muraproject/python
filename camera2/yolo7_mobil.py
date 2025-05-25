import cv2
import numpy as np
import time
from ultralytics import YOLO
from collections import deque, defaultdict, Counter
import os
from datetime import datetime, timedelta
import threading
import argparse

# Kelas untuk tracking objek
class ObjectTracker:
    def __init__(self, max_trajectory_points=10):
        self.trajectories = {}
        self.max_points = max_trajectory_points
        self.colors = {}

    def get_color(self, track_id):
        if track_id not in self.colors:
            self.colors[track_id] = tuple(np.random.randint(0, 255, 3).tolist())
        return self.colors[track_id]

    def update_trajectory(self, track_id, centroid):
        if track_id not in self.trajectories:
            self.trajectories[track_id] = deque(maxlen=self.max_points)
        self.trajectories[track_id].append(centroid)

# Thread untuk mengambil frame dari video source dengan kontrol framerate
class FramerateControlledCapture:
    def __init__(self, video_source, resize_factor=0.5, target_fps=None):
        self.video_source = video_source
        self.resize_factor = resize_factor
        
        # Inisialisasi video capture
        print(f"Connecting to video source: {video_source}")
        self.cap = cv2.VideoCapture(video_source)
        
        # Set options khusus untuk stream RTSP/HTTP
        if video_source.startswith(('rtsp://', 'http://', 'https://')):
            print("Setting stream parameters for RTSP/HTTP connection")
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
        # Cek koneksi    
        if not self.cap.isOpened():
            print("Error: Failed to open video source")
            self.grabbed = False
            self.frame = None
            return
        
        # Dapatkan framerate asli video
        self.original_fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.original_fps <= 0 or self.original_fps > 60:
            print(f"Warning: Unusual FPS detected ({self.original_fps}), setting to 25 FPS")
            self.original_fps = 25.0
        else:
            print(f"Video original FPS: {self.original_fps}")
        
        # Set target framerate (gunakan original jika tidak ditentukan)
        self.target_fps = target_fps if target_fps is not None else self.original_fps
        
        # Baca frame pertama
        print("Reading first frame...")
        retry_count = 0
        max_retries = 5
        while retry_count < max_retries:
            self.grabbed, frame = self.cap.read()
            if self.grabbed:
                break
            retry_count += 1
            print(f"Failed to grab first frame, retrying ({retry_count}/{max_retries})...")
            time.sleep(1)
            
        if not self.grabbed:
            print("Error: Could not grab first frame after multiple attempts")
            self.frame = None
            return
            
        if self.grabbed and self.resize_factor != 1.0:
            frame = cv2.resize(frame, (0, 0), fx=self.resize_factor, fy=self.resize_factor)
        
        self.frame = frame
        self.last_frame_time = time.time()
        self.stopped = False
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()
        self.height, self.width = frame.shape[:2] if self.grabbed else (0, 0)
        
        # Variabel untuk kontrol framerate
        self.frame_interval = 1.0 / self.target_fps
        
        print(f"Video capture initialized successfully")
        print(f"Frame dimensions: {self.width}x{self.height}")
        
    def start(self):
        if not self.grabbed:
            print("Error: Cannot start video capture thread (initialization failed)")
            return self
            
        threading.Thread(target=self.update, daemon=True).start()
        return self
        
    def update(self):
        """Threading function untuk mengambil frame dengan kontrol framerate"""
        frame_error_count = 0
        
        while not self.stopped:
            if not self.grabbed:
                frame_error_count += 1
                print(f"Frame grab error #{frame_error_count}")
                
                if frame_error_count > 10:
                    print("Too many frame errors, stopping capture")
                    self.stop()
                    break
                    
                # Coba reset koneksi untuk stream
                if self.video_source.startswith(('rtsp://', 'http://', 'https://')):
                    try:
                        print("Attempting to reconnect to stream...")
                        self.cap.release()
                        time.sleep(2)
                        self.cap = cv2.VideoCapture(self.video_source)
                        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
                        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    except Exception as e:
                        print(f"Reconnection error: {e}")
                
                time.sleep(1)
                continue
            
            # Waktu yang dibutuhkan untuk setiap frame berdasarkan target FPS
            current_time = time.time()
            elapsed = current_time - self.last_frame_time
            
            # Hanya ambil frame baru jika sudah waktunya
            if elapsed >= self.frame_interval:
                self.grabbed, frame = self.cap.read()
                
                if not self.grabbed:
                    print("Error: Failed to grab frame")
                    frame_error_count += 1
                    time.sleep(0.1)
                    continue
                    
                frame_error_count = 0  # Reset error counter on successful grab
                
                if self.resize_factor != 1.0:
                    frame = cv2.resize(frame, (0, 0), fx=self.resize_factor, fy=self.resize_factor)
                    
                self.frame = frame
                self.last_frame_time = current_time
                
                # Calculate actual FPS
                self.frame_count += 1
                total_elapsed = current_time - self.start_time
                if total_elapsed >= 1.0:
                    self.fps = self.frame_count / total_elapsed
                    self.frame_count = 0
                    self.start_time = current_time
            else:
                # Sleep untuk mengurangi penggunaan CPU 
                sleep_time = max(0, self.frame_interval - elapsed) * 0.8  # 80% dari waktu yang tersisa
                if sleep_time > 0:
                    time.sleep(sleep_time)
    
    def read(self):
        return self.frame
    
    def get_fps(self):
        return self.fps
    
    def get_dimensions(self):
        return (self.width, self.height)
        
    def stop(self):
        self.stopped = True
        if self.cap is not None:
            self.cap.release()

# Kelas untuk manajemen statistik traffic
class TrafficAnalytics:
    def __init__(self, num_lines=6, interval_minutes=1):
        self.num_lines = num_lines
        self.object_types = ['car', 'motorcycle', 'truck', 'bus', 'bicycle', 'person']
        
        # Inisialisasi counter
        self.counts = {
            obj_type: {
                f'up{i+1}': 0 for i in range(num_lines)
            } | {
                f'down{i+1}': 0 for i in range(num_lines)
            } for obj_type in self.object_types
        }
        
        # Untuk statistik per interval
        self.interval_minutes = interval_minutes
        self.interval_seconds = interval_minutes * 60
        self.interval_start_time = time.time()
        self.interval_counts = self._init_interval_counts()
        
        # Untuk menyimpan history interval
        self.history = []
        
        # Untuk hotspot analytics
        self.current_hotspots = {}
    
    def _init_interval_counts(self):
        return {
            obj_type: {
                f'up{i+1}': 0 for i in range(self.num_lines)
            } | {
                f'down{i+1}': 0 for i in range(self.num_lines)
            } for obj_type in self.object_types
        }
    
    def update_count(self, object_type, direction, line_num):
        """Update count untuk objek dan garis tertentu"""
        if object_type in self.counts and f"{direction}{line_num}" in self.counts[object_type]:
            self.counts[object_type][f"{direction}{line_num}"] += 1
            self.interval_counts[object_type][f"{direction}{line_num}"] += 1
    
    def check_interval(self):
        """Periksa apakah interval sudah selesai, jika ya update hotspots"""
        current_time = time.time()
        if current_time - self.interval_start_time >= self.interval_seconds:
            # Simpan data interval saat ini ke history
            timestamp = datetime.now()
            self.history.append({
                'timestamp': timestamp,
                'counts': self.interval_counts.copy()
            })
            
            # Hitung hotspots
            self._calculate_hotspots()
            
            # Reset interval
            self.interval_start_time = current_time
            self.interval_counts = self._init_interval_counts()
            
            return True
        return False
    
    def _calculate_hotspots(self):
        """Hitung garis mana yang memiliki jumlah objek terbanyak untuk setiap jenis"""
        hotspots = {}
        
        for obj_type in self.object_types:
            # Gabungkan up dan down untuk setiap line
            line_totals = {}
            for i in range(self.num_lines):
                line_num = i + 1
                up_key = f'up{line_num}'
                down_key = f'down{line_num}'
                total = self.interval_counts[obj_type][up_key] + self.interval_counts[obj_type][down_key]
                line_totals[line_num] = total
            
            # Temukan line dengan nilai tertinggi
            max_line = max(line_totals.items(), key=lambda x: x[1], default=(0, 0))
            if max_line[1] > 0:  # Only if there's actually some count
                hotspots[obj_type] = {
                    'line': max_line[0],
                    'count': max_line[1]
                }
        
        self.current_hotspots = hotspots
        return hotspots
    
    def get_hotspots(self):
        """Dapatkan informasi hotspot terkini"""
        return self.current_hotspots
    
    def get_counts(self):
        """Dapatkan total counts"""
        return self.counts
    
    def get_interval_counts(self):
        """Dapatkan counts untuk interval saat ini"""
        return self.interval_counts
    
    def get_interval_progress(self):
        """Dapatkan progress interval saat ini dalam persen"""
        current_time = time.time()
        elapsed = current_time - self.interval_start_time
        progress = (elapsed / self.interval_seconds) * 100
        return min(progress, 100)  # Cap at 100%

# Screenshot Manager
class ScreenshotManager:
    def __init__(self, save_dir, interval=5.0, prefix="tracking"):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        self.interval = interval
        self.prefix = prefix
        self.last_save_time = 0
        self.enabled = True
        
    def maybe_save(self, frame, current_time):
        """Ambil screenshot saat interval waktu tercapai"""
        if not self.enabled or self.interval <= 0:
            return False

        if current_time - self.last_save_time >= self.interval:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.save_dir}/{self.prefix}_{timestamp}.jpg"
            
            # Spawn thread khusus untuk I/O operasi 
            # agar tidak menghambat thread utama
            threading.Thread(
                target=lambda f, fn: cv2.imwrite(fn, f), 
                args=(frame.copy(), filename),
                daemon=True
            ).start()
            
            self.last_save_time = current_time
            return True
        return False

def run_tracker(
    video_source,
    output_dir='output',
    display_mode='single',
    resize_factor=0.5,
    confidence_threshold=0.4,
    screenshot_interval=5.0,
    yolo_model='yolov8n.pt',
    show_ui=True,
    target_fps=None,
    detection_fps=5.0,
    analytics_interval=1  # interval dalam menit
):
    # Buat directory output jika belum ada
    os.makedirs(output_dir, exist_ok=True)
    
    # Inisialisasi screenshot manager
    screenshot_mgr = ScreenshotManager(
        save_dir=output_dir, 
        interval=screenshot_interval
    )
    
    # Load YOLO model di thread utama untuk menghindari masalah
    try:
        print(f"Loading {yolo_model}...")
        model = YOLO(yolo_model)
        print("Model loaded successfully")
    except Exception as e:
        print(f"Failed to load model: {e}")
        return
    
    # Inisialisasi tracker dan analytics
    tracker = ObjectTracker(max_trajectory_points=10)
    analytics = TrafficAnalytics(num_lines=6, interval_minutes=analytics_interval)

    # Inisialisasi variabel tracking
    prev_centroids = {}
    tracking_id = 0
    crossed_ids = {
        f'up{i+1}': set() for i in range(6)
    } | {
        f'down{i+1}': set() for i in range(6)
    }
    
    # Start video capture in threaded mode with framerate control
    print(f"Connecting to video source: {video_source}")
    video_capture = FramerateControlledCapture(
        video_source=video_source,
        resize_factor=resize_factor,
        target_fps=target_fps
    ).start()
    
    if not video_capture.grabbed:
        print("Failed to open video source")
        return
    
    # Get frame dimensions
    width, height = video_capture.get_dimensions()
    
    # Define detection lines
    line_spacing = height / 7  # Jarak antar garis
    
    up_lines_y = [int(line_spacing * (i + 1)) for i in range(6)]
    down_lines_y = [int(line_spacing * (i + 1.5)) for i in range(6)]
    
    # Display setup
    if show_ui:
        if display_mode == 'dual':
            cv2.namedWindow("Live View", cv2.WINDOW_NORMAL)
        cv2.namedWindow("Tracking", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Tracking", 1280, 720)
        
    print(f"Starting video processing...")
    print(f"Video playback FPS: {video_capture.target_fps:.1f}")
    print(f"Detection FPS: {detection_fps}")
    print(f"Analytics interval: {analytics_interval} minutes")
    
    # Untuk pengukuran FPS
    tracking_fps = 0
    tracking_frame_count = 0
    tracking_start_time = time.time()
    
    # Variabel untuk last detection time
    last_detection_time = 0
    detection_interval = 1.0 / detection_fps  # Interval untuk 5 FPS (0.2 detik)
    
    # Untuk tracking hasil terakhir
    last_detected_objects = []
    
    try:
        while not video_capture.stopped:
            current_time = time.time()
            
            # Get latest frame
            frame = video_capture.read()
            if frame is None:
                print("Null frame received, waiting...")
                time.sleep(0.1)
                continue
                
            # Show original frame if in dual mode
            if show_ui and display_mode == 'dual':
                live_frame = frame.copy()
                cv2.putText(live_frame, "LIVE VIEW", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                cv2.putText(live_frame, f"FPS: {video_capture.get_fps():.1f}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                cv2.imshow("Live View", live_frame)
            
            # Buat copy dari frame untuk tracking view
            if show_ui or screenshot_interval > 0:
                tracking_frame = frame.copy()
            else:
                tracking_frame = None
                
            # Periksa apakah interval analitik sudah selesai
            interval_completed = analytics.check_interval()
            if interval_completed:
                print("\n--- Analytics Update ---")
                hotspots = analytics.get_hotspots()
                print(f"Hotspots for the last {analytics_interval} minutes:")
                for obj_type, data in hotspots.items():
                    print(f"{obj_type.capitalize()}: Line {data['line']} with {data['count']} objects")
                print("------------------------\n")
                
            # Hanya lakukan deteksi setiap interval (sesuai detection_fps)
            do_detection = current_time - last_detection_time >= detection_interval
                
            if do_detection:
                # Catat waktu mulai proses
                process_start = time.time()
                last_detection_time = current_time
                
                # Detect objects with YOLO
                try:
                    results = model(frame, verbose=False)
                    
                    # Process detection results
                    current_centroids = {}
                    detected_objects = []  # Lista untuk menyimpan data tracking
                    
                    for r in results:
                        boxes = r.boxes
                        for box in boxes:
                            cls = int(box.cls[0])
                            conf = float(box.conf[0])
                            class_name = model.names[cls]
                            
                            if conf > confidence_threshold and class_name in analytics.object_types:
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                centroid_x = (x1 + x2) // 2
                                centroid_y = (y1 + y2) // 2
                                
                                # Tracking with simple algorithm
                                matched_id = None
                                min_distance = float('inf')
                                
                                for prev_id, prev_data in prev_centroids.items():
                                    prev_x, prev_y, _ = prev_data
                                    distance = ((prev_x - centroid_x) ** 2 + (prev_y - centroid_y) ** 2) ** 0.5
                                    if distance < min_distance and distance <= 50:
                                        min_distance = distance
                                        matched_id = prev_id
                                        
                                if matched_id is None:
                                    matched_id = tracking_id
                                    tracking_id += 1
                                    
                                current_centroids[matched_id] = (centroid_x, centroid_y, class_name)
                                tracker.update_trajectory(matched_id, (centroid_x, centroid_y))
                                color = tracker.get_color(matched_id)
                                
                                # Check line crossing for all lines
                                direction = ""
                                direction_color = color
                                
                                if matched_id in prev_centroids:
                                    prev_y = prev_centroids[matched_id][1]
                                    
                                    # Check all up lines
                                    for i, up_y in enumerate(up_lines_y):
                                        line_num = i + 1
                                        if prev_y > up_y and centroid_y <= up_y and matched_id not in crossed_ids[f'up{line_num}']:
                                            analytics.update_count(class_name, 'up', line_num)
                                            crossed_ids[f'up{line_num}'].add(matched_id)
                                            direction = f"↑ UP{line_num}"
                                            direction_color = (0, 255, 0)
                                    
                                    # Check all down lines
                                    for i, down_y in enumerate(down_lines_y):
                                        line_num = i + 1
                                        if prev_y < down_y and centroid_y >= down_y and matched_id not in crossed_ids[f'down{line_num}']:
                                            analytics.update_count(class_name, 'down', line_num)
                                            crossed_ids[f'down{line_num}'].add(matched_id)
                                            direction = f"↓ DN{line_num}"
                                            direction_color = (0, 0, 255)
                                
                                # Save object data for visualization
                                detected_objects.append({
                                    'id': matched_id,
                                    'class': class_name,
                                    'box': (x1, y1, x2, y2),
                                    'centroid': (centroid_x, centroid_y),
                                    'color': color,
                                    'direction': direction,
                                    'direction_color': direction_color
                                })
                    
                    # Update tracking data
                    prev_centroids = current_centroids
                    
                    # Update crossed IDs - remove IDs no longer being tracked
                    for key in crossed_ids:
                        crossed_ids[key] = {id for id in crossed_ids[key] if id in current_centroids}
                    
                    # Calculate tracking FPS
                    tracking_frame_count += 1
                    elapsed_time = time.time() - tracking_start_time
                    if elapsed_time >= 1.0:
                        tracking_fps = tracking_frame_count / elapsed_time
                        tracking_frame_count = 0
                        tracking_start_time = time.time()
                    
                    # Hitung waktu proses
                    process_time = time.time() - process_start
                    
                    # Simpan object untuk visualisasi
                    last_detected_objects = detected_objects
                    
                except Exception as e:
                    print(f"Detection error: {e}")
                    continue
            else:
                # Gunakan hasil deteksi sebelumnya
                detected_objects = last_detected_objects
                process_time = 0
            
            # Only render visualization if UI is enabled or screenshot is needed
            if (show_ui or screenshot_mgr.maybe_save(tracking_frame, current_time)) and tracking_frame is not None:
                # Draw all detection lines
                for i, y in enumerate(up_lines_y):
                    line_num = i + 1
                    cv2.line(tracking_frame, (0, y), (width, y), (0, 255, 0), 2)
                    # Highlight hotspot lines
                    is_hotspot = False
                    hotspot_text = ""
                    for obj_type, data in analytics.get_hotspots().items():
                        if data['line'] == line_num:
                            is_hotspot = True
                            hotspot_text += f"{obj_type.upper()} "
                    
                    if is_hotspot:
                        # Outline text for better visibility
                        text = f"UP{line_num} HOTSPOT: {hotspot_text}"
                        cv2.putText(tracking_frame, text, (width//2 - 100, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
                        cv2.putText(tracking_frame, text, (width//2 - 100, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    else:
                        cv2.putText(tracking_frame, f"UP{line_num}", (10, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                for i, y in enumerate(down_lines_y):
                    line_num = i + 1
                    cv2.line(tracking_frame, (0, y), (width, y), (0, 0, 255), 2)
                    # Highlight hotspot lines
                    is_hotspot = False
                    hotspot_text = ""
                    for obj_type, data in analytics.get_hotspots().items():
                        if data['line'] == line_num:
                            is_hotspot = True
                            hotspot_text += f"{obj_type.upper()} "
                    
                    if is_hotspot:
                        # Outline text for better visibility
                        text = f"DN{line_num} HOTSPOT: {hotspot_text}"
                        cv2.putText(tracking_frame, text, (width//2 - 100, y + 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
                        cv2.putText(tracking_frame, text, (width//2 - 100, y + 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    else:
                        cv2.putText(tracking_frame, f"DN{line_num}", (10, y + 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
                # Draw detected objects if available
                if detected_objects:
                    for obj in detected_objects:
                        x1, y1, x2, y2 = obj['box']
                        centroid_x, centroid_y = obj['centroid']
                        color = obj['color']
                        
                        # Draw bounding box and centroid
                        cv2.rectangle(tracking_frame, (x1, y1), (x2, y2), color, 2)
                        cv2.circle(tracking_frame, (centroid_x, centroid_y), 4, color, -1)
                        
                        # Draw trajectory
                        if obj['id'] in tracker.trajectories:
                            points = list(tracker.trajectories[obj['id']])
                            for i in range(1, len(points)):
                                cv2.line(tracking_frame, points[i-1], points[i], color, 2)
                        
                        # Draw label with direction
                        direction = obj.get('direction', '')
                        direction_color = obj.get('direction_color', color)
                        label = f"{obj['class']} {direction}"
                        cv2.putText(tracking_frame, label, (x1, y1-10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, direction_color, 2)
                
                # Display analytics
                # Progress bar for interval
                progress = analytics.get_interval_progress()
                bar_width = 200
                bar_height = 20
                filled_width = int(bar_width * progress / 100)
                
                cv2.rectangle(tracking_frame, (width - 220, 80), (width - 220 + bar_width, 80 + bar_height), (0, 0, 0), -1)
                cv2.rectangle(tracking_frame, (width - 220, 80), (width - 220 + filled_width, 80 + bar_height), (0, 255, 0), -1)
                cv2.putText(tracking_frame, f"Analytics: {progress:.1f}%", (width - 220, 70), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                
                # Display counts - show only top 3 object types
                y_pos = 120
                
                # Hotspots for this interval
                cv2.putText(tracking_frame, f"Traffic Hotspots:", (width - 220, y_pos), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                y_pos += 25
                
                for obj_type, data in analytics.get_hotspots().items():
                    line = data['line']
                    count = data['count']
                    text = f"{obj_type.capitalize()}: Line {line} ({count})"
                    cv2.putText(tracking_frame, text, (width - 220, y_pos), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                    y_pos += 20
                
                # Total counts for top object types (sorted)
                y_pos += 20
                cv2.putText(tracking_frame, f"Total Counts:", (width - 220, y_pos), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                y_pos += 25
                
                # Calculate total for each object type
                total_counts = {}
                for obj_type, counts in analytics.get_counts().items():
                    total_counts[obj_type] = sum(counts.values())
                
                # Sort and show top 3
                sorted_counts = sorted(total_counts.items(), key=lambda x: x[1], reverse=True)
                for obj_type, count in sorted_counts[:3]:
                    text = f"{obj_type.capitalize()}: {count}"
                    cv2.putText(tracking_frame, text, (width - 220, y_pos), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                    y_pos += 20
                
                # Display FPS info
                cv2.putText(tracking_frame, f"Video: {video_capture.get_fps():.1f} FPS", 
                            (10, height - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                cv2.putText(tracking_frame, f"Detection: {detection_fps:.1f} FPS", 
                            (10, height - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                
                detection_status = "Active" if do_detection else "Waiting"
                cv2.putText(tracking_frame, f"Detection: {detection_status}", 
                            (10, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                            (0, 255, 0) if do_detection else (0, 165, 255), 2)
                
                # Take screenshot if needed
                screenshot_mgr.maybe_save(tracking_frame, current_time)
                
                # Display tracking view
                if show_ui:
                    cv2.putText(tracking_frame, "TRAFFIC ANALYTICS", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                    cv2.imshow("Tracking", tracking_frame)
            
            # Check for exit key
            if show_ui and cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        video_capture.stop()
        if show_ui:
            cv2.destroyAllWindows()
        
        # Print results
        print("\nFinal Traffic Analytics:")
        for obj_type, counts in analytics.get_counts().items():
            total = sum(counts.values())
            if total > 0:
                print(f"\n{obj_type.capitalize()} (Total: {total}):")
                # Print up counts
                up_counts = [f"{i+1}:{counts[f'up{i+1}']}" for i in range(6)]
                print(f"  Up lines: {', '.join(up_counts)}")
                # Print down counts
                down_counts = [f"{i+1}:{counts[f'down{i+1}']}" for i in range(6)]
                print(f"  Down lines: {', '.join(down_counts)}")

def main():
    parser = argparse.ArgumentParser(description='Traffic Analytics with YOLO')
    parser.add_argument('--source', type=str, 
                        default='https://cctvjss.jogjakota.go.id/balaikota/Balaikota_Gerbang_Masuk_Utara_View_Timur-Luar.stream/playlist.m3u8', 
                        help='Video source')
    parser.add_argument('--output', type=str, default='output', help='Output directory')
    parser.add_argument('--display', type=str, default='single', choices=['single', 'dual', 'none'], 
                        help='Display mode: single (tracking only), dual (live + tracking), none (headless)')
    parser.add_argument('--resize', type=float, default=0.5, help='Resize factor for input frames')
    parser.add_argument('--confidence', type=float, default=0.4, help='Detection confidence threshold')
    parser.add_argument('--screenshot', type=float, default=5.0, 
                        help='Screenshot interval in seconds (0 to disable)')
    parser.add_argument('--model', type=str, default='yolov8n.pt', help='YOLO model to use')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode (no UI)')
    parser.add_argument('--fps', type=float, default=None, 
                        help='Target FPS (default is original video FPS)')
    parser.add_argument('--detection-fps', type=float, default=5.0,
                        help='Target FPS for object detection (default is 5 FPS)')
    parser.add_argument('--analytics-interval', type=int, default=1,
                        help='Interval for traffic analytics in minutes (default: 1)')
    
    args = parser.parse_args()
    
    # Determine display mode
    show_ui = not args.headless
    display_mode = 'none' if args.headless else args.display
    
    print(f"Starting Traffic Analytics with settings:")
    print(f"- Video source: {args.source}")
    print(f"- Display mode: {display_mode}")
    print(f"- Resize factor: {args.resize}x")
    print(f"- Detection FPS: {args.detection_fps}")
    print(f"- Screenshot interval: {args.screenshot}s")
    print(f"- Analytics interval: {args.analytics_interval} minutes")
    print(f"- Target Video FPS: {args.fps if args.fps else 'Original video FPS'}")
    
    run_tracker(
        video_source=args.source,
        output_dir=args.output,
        display_mode=display_mode,
        resize_factor=args.resize,
        confidence_threshold=args.confidence,
        screenshot_interval=args.screenshot,
        yolo_model=args.model,
        show_ui=show_ui,
        target_fps=args.fps,
        detection_fps=args.detection_fps,
        analytics_interval=args.analytics_interval
    )

if __name__ == "__main__":
    main()