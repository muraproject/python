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
    def __init__(self, video_source, resize_factor=1.0, target_fps=None):
        self.video_source = video_source
        self.resize_factor = resize_factor
        
        # Inisialisasi video capture
        print(f"Connecting to video source: {video_source}")
        self.cap = cv2.VideoCapture(video_source)
        
        # Set options khusus untuk stream RTSP/HTTP
        if video_source.startswith(('rtsp://', 'http://', 'https://')):
            print("Setting stream parameters for RTSP/HTTP connection")
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
            
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
            
        # Resize jika diperlukan, tetapi pertahankan aspect ratio
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
                        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
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

def create_sidebar(frame, width, padding=10):
    """Buat sidebar untuk GUI dengan background transparansi"""
    height = frame.shape[0]
    # Buat background semi-transparan
    sidebar = np.zeros((height, width, 3), dtype=np.uint8)
    sidebar_alpha = np.ones((height, width)) * 0.8  # 80% opaque
    
    # Return sidebar dan alpha channel
    return sidebar, sidebar_alpha

def overlay_sidebar(frame, sidebar, sidebar_alpha, x_offset=0):
    """Overlay sidebar ke frame dengan alpha blending"""
    height, width = frame.shape[:2]
    sidebar_width = sidebar.shape[1]
    
    # Pastikan sidebar tidak melebihi frame
    if x_offset + sidebar_width > width:
        sidebar_width = width - x_offset
        sidebar = sidebar[:, :sidebar_width]
        sidebar_alpha = sidebar_alpha[:, :sidebar_width]
    
    # Get region for overlay
    roi = frame[:, x_offset:x_offset+sidebar_width].copy()
    
    # Blend sidebar dengan frame
    for c in range(3):  # RGB channels
        roi[:, :, c] = roi[:, :, c] * (1 - sidebar_alpha) + sidebar[:, :, c] * sidebar_alpha
    
    # Copy blended region back to frame
    frame[:, x_offset:x_offset+sidebar_width] = roi
    
    return frame

def run_tracker(
    video_source,
    output_dir='output',
    resize_factor=1.0,
    confidence_threshold=0.4,
    screenshot_interval=5.0,
    yolo_model='yolov8n.pt',
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
    
    # Load YOLO model
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
        resize_factor=resize_factor
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
    
    # Setup windows
    window_name = "Traffic Analytics"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, int(width * 1.2), height)  # Allow space for sidebar
    
    # Inisialisasi sidebar
    sidebar_width = 250
    
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
    
    # Font settings for clean UI
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale_small = 0.5
    font_scale_medium = 0.6
    font_scale_large = 0.7
    
    try:
        while not video_capture.stopped:
            current_time = time.time()
            
            # Get latest frame
            frame = video_capture.read()
            if frame is None:
                print("Null frame received, waiting...")
                time.sleep(0.1)
                continue
            
            # Create a clean copy for UI
            display_frame = frame.copy()
            
            # Create sidebar with clean UI
            sidebar, sidebar_alpha = create_sidebar(display_frame, sidebar_width)
            
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
                                            direction = f"↑ {line_num}"
                                            direction_color = (0, 255, 0)
                                    
                                    # Check all down lines
                                    for i, down_y in enumerate(down_lines_y):
                                        line_num = i + 1
                                        if prev_y < down_y and centroid_y >= down_y and matched_id not in crossed_ids[f'down{line_num}']:
                                            analytics.update_count(class_name, 'down', line_num)
                                            crossed_ids[f'down{line_num}'].add(matched_id)
                                            direction = f"↓ {line_num}"
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
            
            # Draw detection lines dengan desain yang lebih bersih
            for i, y in enumerate(up_lines_y):
                line_num = i + 1
                # Basic line
                line_color = (0, 230, 0)  # Sedikit kurang terang
                text_color = (0, 230, 0)
                
                # Check if hotspot
                is_hotspot = False
                hotspot_text = ""
                for obj_type, data in analytics.get_hotspots().items():
                    if data['line'] == line_num:
                        is_hotspot = True
                        hotspot_text += f"{obj_type} "
                        line_color = (0, 255, 255)  # Highlight color
                        text_color = (0, 255, 255)
                
                # Draw main line
                cv2.line(display_frame, (0, y), (width-sidebar_width, y), line_color, 2)
                
                # Draw minimal label
                label = f"U{line_num}"
                if is_hotspot:
                    label = f"U{line_num}★"  # Gunakan simbol bintang untuk hotspot
                
                cv2.putText(display_frame, label, (5, y - 5),
                           font, font_scale_small, text_color, 2)
            
            for i, y in enumerate(down_lines_y):
                line_num = i + 1
                # Basic line
                line_color = (0, 0, 230)  # Sedikit kurang terang
                text_color = (0, 0, 230)
                
                # Check if hotspot
                is_hotspot = False
                hotspot_text = ""
                for obj_type, data in analytics.get_hotspots().items():
                    if data['line'] == line_num:
                        is_hotspot = True
                        hotspot_text += f"{obj_type} "
                        line_color = (0, 255, 255)  # Highlight color
                        text_color = (0, 255, 255)
                
                # Draw main line
                cv2.line(display_frame, (0, y), (width-sidebar_width, y), line_color, 2)
                
                # Draw minimal label
                label = f"D{line_num}"
                if is_hotspot:
                    label = f"D{line_num}★"  # Gunakan simbol bintang untuk hotspot
                
                cv2.putText(display_frame, label, (5, y + 15),
                           font, font_scale_small, text_color, 2)
            
            # Draw detected objects if available
            if detected_objects:
                for obj in detected_objects:
                    x1, y1, x2, y2 = obj['box']
                    centroid_x, centroid_y = obj['centroid']
                    color = obj['color']
                    
                    # Draw bounding box dengan style minimal
                    cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                    
                    # Draw centroid with smaller circle
                    cv2.circle(display_frame, (centroid_x, centroid_y), 3, color, -1)
                    
                    # Draw trajectory dengan garis tipis
                    if obj['id'] in tracker.trajectories:
                        points = list(tracker.trajectories[obj['id']])
                        for i in range(1, len(points)):
                            cv2.line(display_frame, points[i-1], points[i], color, 1)
                    
                    # Draw label dengan label minimal
                    direction = obj.get('direction', '')
                    direction_color = obj.get('direction_color', color)
                    
                    # Lebih compact dan bersih
                    cls_name = obj['class'][:3]  # Hanya 3 karakter pertama
                    label = f"{cls_name}"
                    if direction:
                        label = f"{cls_name} {direction}"
                    
                    # Text dengan outline tipis untuk keterbacaan
                    cv2.putText(display_frame, label, (x1, y1-5), 
                               font, font_scale_small, (0, 0, 0), 3)  # Outline
                    cv2.putText(display_frame, label, (x1, y1-5), 
                               font, font_scale_small, direction_color, 1)  # Text
            
            # Create clean sidebar content
            cv2.putText(sidebar, "TRAFFIC ANALYTICS", (10, 30), 
                       font, font_scale_large, (255, 255, 255), 2)
            
            # Progress bar for interval
            progress = analytics.get_interval_progress()
            bar_width = 230
            bar_height = 10
            filled_width = int(bar_width * progress / 100)
            
            y_pos = 50
            cv2.putText(sidebar, f"Analytics ({analytics_interval}min):", (10, y_pos), 
                       font, font_scale_small, (200, 200, 200), 1)
            y_pos += 20
            
            # Draw clean progress bar
            cv2.rectangle(sidebar, (10, y_pos), (10 + bar_width, y_pos + bar_height), (50, 50, 50), -1)
            cv2.rectangle(sidebar, (10, y_pos), (10 + filled_width, y_pos + bar_height), (0, 255, 0), -1)
            cv2.putText(sidebar, f"{progress:.0f}%", (10 + bar_width + 5, y_pos + 8), 
                       font, 0.4, (200, 200, 200), 1)
            
            # Hotspots section
            y_pos += 30
            cv2.putText(sidebar, "Traffic Hotspots:", (10, y_pos), 
                       font, font_scale_small, (255, 255, 255), 1)
            y_pos += 25
            
            hotspots = analytics.get_hotspots()
            if hotspots:
                for obj_type, data in hotspots.items():
                    line = data['line']
                    count = data['count']
                    text = f"{obj_type.capitalize()}: Line {line} ({count})"
                    cv2.putText(sidebar, text, (15, y_pos), 
                               font, font_scale_small, (0, 255, 255), 1)
                    y_pos += 20
            else:
                cv2.putText(sidebar, "No hotspots detected yet", (15, y_pos), 
                          font, font_scale_small, (150, 150, 150), 1)
                y_pos += 20
            
            # Total counts section
            y_pos += 15
            cv2.putText(sidebar, "Total Counts:", (10, y_pos), 
                       font, font_scale_small, (255, 255, 255), 1)
            y_pos += 25
            
            # Calculate total for each object type
            total_counts = {}
            for obj_type, counts in analytics.get_counts().items():
                total_counts[obj_type] = sum(counts.values())
            
            # Show all object types with counts > 0
            sorted_counts = sorted(total_counts.items(), key=lambda x: x[1], reverse=True)
            
            for obj_type, count in sorted_counts:
                if count > 0:  # Only show types with counts
                    text = f"{obj_type.capitalize()}: {count}"
                    cv2.putText(sidebar, text, (15, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 20
            
            # System info at bottom of sidebar
            y_pos = height - 80
            cv2.putText(sidebar, "System Info:", (10, y_pos), 
                       font, font_scale_small, (255, 255, 255), 1)
            y_pos += 20
            
            cv2.putText(sidebar, f"Video: {video_capture.get_fps():.1f} FPS", 
                        (15, y_pos), font, font_scale_small, (200, 200, 200), 1)
            y_pos += 20
            
            cv2.putText(sidebar, f"Detection: {detection_fps:.1f} FPS", 
                        (15, y_pos), font, font_scale_small, (200, 200, 200), 1)
            y_pos += 20
            
            # Add timestamp
            current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(sidebar, current_datetime, 
                        (15, y_pos), font, font_scale_small, (200, 200, 200), 1)
            
            # Overlay sidebar to main frame
            display_frame = overlay_sidebar(display_frame, sidebar, sidebar_alpha, width - sidebar_width)
            
            # Take screenshot if needed
            screenshot_mgr.maybe_save(display_frame, current_time)
            
            # Display final frame
            cv2.imshow(window_name, display_frame)
            
            # Check for exit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
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
                        default='http://103.130.16.22:8880', 
                        help='Video source')
    parser.add_argument('--output', type=str, default='output', help='Output directory')
    parser.add_argument('--resize', type=float, default=0.9, help='Resize factor for input frames')
    parser.add_argument('--confidence', type=float, default=0.2, help='Detection confidence threshold')
    parser.add_argument('--screenshot', type=float, default=0.0, 
                        help='Screenshot interval in seconds (0 to disable)')
    parser.add_argument('--model', type=str, default='yolov8n.pt', help='YOLO model to use')
    parser.add_argument('--detection-fps', type=float, default=20.0,
                        help='Target FPS for object detection (default is 5 FPS)')
    parser.add_argument('--analytics-interval', type=int, default=1,
                        help='Interval for traffic analytics in minutes (default: 1)')
    
    args = parser.parse_args()
    
    print(f"Starting Traffic Analytics with settings:")
    print(f"- Video source: {args.source}")
    print(f"- Resize factor: {args.resize}x")
    print(f"- Detection FPS: {args.detection_fps}")
    print(f"- Screenshot interval: {args.screenshot}s")
    print(f"- Analytics interval: {args.analytics_interval} minutes")
    
    run_tracker(
        video_source=args.source,
        output_dir=args.output,
        resize_factor=args.resize,
        confidence_threshold=args.confidence,
        screenshot_interval=args.screenshot,
        yolo_model=args.model,
        detection_fps=args.detection_fps,
        analytics_interval=args.analytics_interval
    )

if __name__ == "__main__":
    main()