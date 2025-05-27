import cv2
import numpy as np
import time
from ultralytics import YOLO
from collections import deque, defaultdict, Counter
import os
import json
import threading
import argparse
import requests
from urllib.parse import quote
from datetime import datetime, timedelta
import logging
from queue import Queue, Empty

# Setup logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Kelas untuk manajemen pengaturan
class SettingsManager:
    def __init__(self, settings_file="config/settings_opencv.json"):
        self.settings_file = settings_file
        self.default_settings = {
            'interval': 300,
            'api_url': "http://localhost:5000",
            'api_check_interval': 5,
            'reset_interval': 20,
            'lines': {
                'up1': 0.15, 'up2': 0.25, 'up3': 0.35,
                'up4': 0.45, 'up5': 0.55, 'up6': 0.65,
                'down1': 0.20, 'down2': 0.30, 'down3': 0.40,
                'down4': 0.50, 'down5': 0.60, 'down6': 0.70
            },
            'video_source': None,
            'camera_name': None,
            'camera_mode': None,
            'processing': {
                'target_fps': 30,
                'confidence_threshold': 0.3,
                'tracking_points': 30
            },
            'display': {
                'resize_factor': 0.8,
                'show_sidebar': True,
                'screenshot_interval': 0
            }
        }
        self.ensure_config_dir()
        self.settings = self.load_settings()

    def ensure_config_dir(self):
        config_dir = os.path.dirname(self.settings_file)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    merged_settings = self.default_settings.copy()
                    for key, value in settings.items():
                        if isinstance(value, dict) and key in merged_settings:
                            merged_settings[key].update(value)
                        else:
                            merged_settings[key] = value
                    return merged_settings
            else:
                self.save_settings(self.default_settings)
                return self.default_settings.copy()
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            return self.default_settings.copy()

    def save_settings(self, settings):
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
            self.settings = settings
            logger.info("Settings saved successfully")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

class ObjectTracker:
    def __init__(self, max_trajectory_points=30):
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

# KELAS BARU: DataManager dengan API calls di thread terpisah
class NonBlockingDataManager:
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.current_counts = self.initialize_counts()
        self.accumulated_counts = self.initialize_accumulated_counts()
        self.last_save_time = time.time()
        self.last_reset_time = time.time()
        self.base_url = settings_manager.settings['api_url']
        self.reset_interval = settings_manager.settings.get('reset_interval', 20)
        
        # Thread untuk API calls agar tidak blocking main loop
        self.api_thread_running = True
        self.restart_required = False
        self.api_thread = threading.Thread(target=self._api_worker, daemon=True)
        self.api_thread.start()
        
    def initialize_counts(self):
        base_counts = {f'{direction}{i}': 0 for direction in ['up', 'down'] for i in range(1, 7)}
        return {
            'car': base_counts.copy(),
            'motorcycle': base_counts.copy(),
            'truck': base_counts.copy(),
            'bus': base_counts.copy(),
            'person': base_counts.copy(),
            'bicycle': base_counts.copy()
        }
        
    def initialize_accumulated_counts(self):
        return {
            'car_up': 0, 'car_down': 0, 'bus_up': 0, 'bus_down': 0,
            'truck_up': 0, 'truck_down': 0, 'person_motor_up': 0, 'person_motor_down': 0
        }

    def _api_worker(self):
        """Thread worker untuk API calls tanpa memblokir video loop"""
        last_api_check = time.time()
        api_check_interval = self.settings_manager.settings['api_check_interval']
        
        while self.api_thread_running:
            try:
                current_time = time.time()
                
                # Check API untuk camera updates
                if current_time - last_api_check >= api_check_interval:
                    last_api_check = current_time
                    
                    # Lakukan API call di background thread
                    previous_source = self.settings_manager.settings.get('video_source')
                    
                    if self._update_camera_source_async():
                        new_source = self.settings_manager.settings.get('video_source')
                        if new_source != previous_source:
                            logger.info(f"Video source changed from {previous_source} to {new_source}")
                            self.restart_required = True
                
                # Check untuk save data
                if self._should_save_data():
                    self._save_data_async()
                    
                # Sleep untuk mengurangi CPU usage
                time.sleep(1)  # Check setiap 1 detik
                
            except Exception as e:
                logger.error(f"Error in API worker: {e}")
                time.sleep(5)  # Wait longer on error

    def _update_camera_source_async(self):
        """Update camera source secara asynchronous"""
        try:
            cameras = self._get_cameras_async()
            if not cameras:
                return False

            camera = cameras[0]
            if camera:
                previous_settings = {
                    'video_source': self.settings_manager.settings.get('video_source'),
                    'camera_name': self.settings_manager.settings.get('camera_name'),
                    'camera_mode': self.settings_manager.settings.get('camera_mode')
                }
                
                self.settings_manager.settings['video_source'] = camera['ip']
                self.settings_manager.settings['camera_name'] = camera['name']
                self.settings_manager.settings['camera_mode'] = camera['mode']
                
                self.settings_manager.save_settings(self.settings_manager.settings)
                
                changed = any(
                    previous_settings[key] != self.settings_manager.settings[key]
                    for key in previous_settings
                )
                
                if changed:
                    logger.info(f"Camera updated: {camera['name']} - {camera['ip']}")
                return changed
                
        except Exception as e:
            logger.error(f"Error updating camera source: {e}")
        return False

    def _get_cameras_async(self):
        """Get cameras list dengan timeout untuk mencegah hanging"""
        try:
            mode = "Counting Kendaraan"
            response = requests.get(
                f"{self.base_url}/api/processor?mode={quote(mode)}", 
                timeout=3  # Timeout 3 detik
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("cameras", [])
        except requests.exceptions.Timeout:
            logger.warning("API request timeout")
        except Exception as e:
            logger.error(f"Error getting cameras: {e}")
        return []

    def _should_save_data(self):
        """Check if data should be saved"""
        current_time = time.time()
        interval = self.settings_manager.settings['interval']
        return current_time - self.last_save_time >= interval

    def _save_data_async(self):
        """Save data secara asynchronous"""
        try:
            camera_name = self.settings_manager.settings['camera_name']
            camera_mode = self.settings_manager.settings['camera_mode']
            
            if not camera_name or not camera_mode:
                return False
                
            result = json.dumps(self.accumulated_counts)
            url = f"{self.base_url}/api/save"
            params = {
                "camera_name": camera_name,
                "mode": camera_mode,
                "result": result
            }
            
            response = requests.get(url, params=params, timeout=5)
            success = response.status_code == 200
            
            if success:
                logger.info(f"Data saved successfully: {self.accumulated_counts}")
                self.accumulated_counts = self.initialize_accumulated_counts()
                self.last_save_time = time.time()
            
            return success
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            return False

    def update_count(self, object_type, direction, count=1):
        if object_type in self.current_counts and direction in self.current_counts[object_type]:
            self.current_counts[object_type][direction] += count

    def get_summary_counts(self):
        counts = self.current_counts
        car_up = max(counts['car']['up1'], counts['car']['up2'], counts['car']['up3'],
                    counts['car']['up4'], counts['car']['up5'], counts['car']['up6'])
        car_down = max(counts['car']['down1'], counts['car']['down2'], counts['car']['down3'],
                      counts['car']['down4'], counts['car']['down5'], counts['car']['down6'])
        bus_up = max(counts['bus']['up1'], counts['bus']['up2'], counts['bus']['up3'],
                    counts['bus']['up4'], counts['bus']['up5'], counts['bus']['up6'])
        bus_down = max(counts['bus']['down1'], counts['bus']['down2'], counts['bus']['down3'],
                      counts['bus']['down4'], counts['bus']['down5'], counts['bus']['down6'])
        truck_up = max(counts['truck']['up1'], counts['truck']['up2'], counts['truck']['up3'],
                      counts['truck']['up4'], counts['truck']['up5'], counts['truck']['up6'])
        truck_down = max(counts['truck']['down1'], counts['truck']['down2'], counts['truck']['down3'],
                        counts['truck']['down4'], counts['truck']['down5'], counts['truck']['down6'])
        person_up = max(counts['person']['up1'], counts['person']['up2'], counts['person']['up3'],
                       counts['person']['up4'], counts['person']['up5'], counts['person']['up6'])
        motor_up = max(counts['motorcycle']['up1'], counts['motorcycle']['up2'], counts['motorcycle']['up3'],
                      counts['motorcycle']['up4'], counts['motorcycle']['up5'], counts['motorcycle']['up6'])
        bicycle_up = max(counts['bicycle']['up1'], counts['bicycle']['up2'], counts['bicycle']['up3'],
                        counts['bicycle']['up4'], counts['bicycle']['up5'], counts['bicycle']['up6'])
        person_motor_up = max(person_up, motor_up, bicycle_up)
        person_down = max(counts['person']['down1'], counts['person']['down2'], counts['person']['down3'],
                         counts['person']['down4'], counts['person']['down5'], counts['person']['down6'])
        motor_down = max(counts['motorcycle']['down1'], counts['motorcycle']['down2'], counts['motorcycle']['down3'],
                        counts['motorcycle']['down4'], counts['motorcycle']['down5'], counts['motorcycle']['down6'])
        bicycle_down = max(counts['bicycle']['down1'], counts['bicycle']['down2'], counts['bicycle']['down3'],
                          counts['bicycle']['down4'], counts['bicycle']['down5'], counts['bicycle']['down6'])
        person_motor_down = max(person_down, motor_down, bicycle_down)
        
        return {
            'car_up': car_up, 'car_down': car_down, 'bus_up': bus_up, 'bus_down': bus_down,
            'truck_up': truck_up, 'truck_down': truck_down, 
            'person_motor_up': person_motor_up, 'person_motor_down': person_motor_down
        }
        
    def check_and_reset_if_needed(self):
        current_time = time.time()
        if current_time - self.last_reset_time >= self.reset_interval:
            current_summary = self.get_summary_counts()
            for key in self.accumulated_counts:
                self.accumulated_counts[key] += current_summary[key]
            self.current_counts = self.initialize_counts()
            self.last_reset_time = current_time
            return True
        return False

    def is_restart_required(self):
        """Check if restart is required due to source change"""
        return self.restart_required

    def stop(self):
        """Stop API worker thread"""
        self.api_thread_running = False

# Video capture yang sudah diperbaiki
class SmoothVideoCapture:
    def __init__(self, video_source, resize_factor=1.0):
        self.video_source = video_source
        self.resize_factor = resize_factor
        self.stopped = False
        
        logger.info(f"Opening video source: {video_source}")
        self.cap = cv2.VideoCapture(video_source)
        
        if not self.cap.isOpened():
            logger.error("Failed to open video source")
            self.frame = None
            return
            
        # Baca frame pertama
        ret, frame = self.cap.read()
        if not ret:
            logger.error("Cannot read first frame")
            self.frame = None
            return
            
        self.original_height, self.original_width = frame.shape[:2]
        self.width = int(self.original_width * resize_factor)
        self.height = int(self.original_height * resize_factor)
        
        if resize_factor != 1.0:
            frame = cv2.resize(frame, (self.width, self.height))
            
        self.frame = frame
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.frame_time = 1.0 / self.fps
        
        logger.info(f"Video initialized - Size: {self.width}x{self.height}, FPS: {self.fps}")
        
    def start(self):
        if self.frame is None:
            return self
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()
        return self
        
    def _update(self):
        frame_count = 0
        start_time = time.time()
        
        while not self.stopped:
            ret, frame = self.cap.read()
            
            if not ret:
                # Loop video jika sampai akhir
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if not ret:
                    break
                    
            if self.resize_factor != 1.0:
                frame = cv2.resize(frame, (self.width, self.height))
            
            self.frame = frame.copy()
            frame_count += 1
            
            # Frame timing control
            elapsed = time.time() - start_time
            expected_time = frame_count * self.frame_time
            sleep_time = expected_time - elapsed
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            elif sleep_time < -0.1:
                start_time = time.time()
                frame_count = 0
                
    def read(self):
        if self.frame is None:
            return None
        return self.frame.copy()
        
    def get_fps(self):
        return self.fps
        
    def get_dimensions(self):
        return (self.width, self.height)
        
    def stop(self):
        self.stopped = True
        if hasattr(self, 'thread'):
            self.thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
            
    def is_opened(self):
        return self.cap is not None and self.cap.isOpened()

def create_sidebar(frame, width):
    height = frame.shape[0]
    sidebar = np.zeros((height, width, 3), dtype=np.uint8)
    return sidebar

def overlay_sidebar(frame, sidebar, x_offset=0):
    height, width = frame.shape[:2]
    sidebar_width = sidebar.shape[1]
    if x_offset + sidebar_width <= width:
        frame[:, x_offset:x_offset+sidebar_width] = sidebar
    return frame

def run_vehicle_counter(settings_manager, output_dir='output', yolo_model='yolov8s.pt'):
    """Main function dengan API calls non-blocking"""
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Inisialisasi dengan NonBlockingDataManager
    data_manager = NonBlockingDataManager(settings_manager)
    tracker = ObjectTracker(max_trajectory_points=30)
    
    # Load YOLO model
    try:
        logger.info(f"Loading {yolo_model}...")
        model = YOLO(yolo_model)
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return False

    # Configuration
    confidence_threshold = settings_manager.settings['processing']['confidence_threshold']
    resize_factor = settings_manager.settings['display']['resize_factor']
    show_sidebar = settings_manager.settings['display']['show_sidebar']
    
    # Video source
    video_source = settings_manager.settings.get('video_source')
    if not video_source:
        logger.error("No video source configured")
        return False
    
    # Video capture
    video_capture = SmoothVideoCapture(video_source, resize_factor).start()
    
    if not video_capture.is_opened():
        logger.error("Failed to open video source")
        return False

    # Setup window
    width, height = video_capture.get_dimensions()
    window_name = "Vehicle Counter - Non-Blocking"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    display_width = width + (250 if show_sidebar else 0)
    cv2.resizeWindow(window_name, display_width, height)
    
    # Initialize tracking variables
    prev_centroids = {}
    tracking_id = 0
    crossed_ids = {f'up{i+1}': set() for i in range(6)} | {f'down{i+1}': set() for i in range(6)}
    
    running = True
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # Detection control
    detection_counter = 0
    detection_interval = 3
    last_detected_objects = []
    
    # FPS tracking
    fps_counter = 0
    fps_start_time = time.time()
    current_fps = 0
    
    # Line positions
    line_settings = settings_manager.settings['lines']
    up_lines_y = [int(height * line_settings[f'up{i+1}']) for i in range(6)]
    down_lines_y = [int(height * line_settings[f'down{i+1}']) for i in range(6)]
    
    logger.info("Starting main loop - API calls are now non-blocking...")
    
    try:
        while running:
            loop_start = time.time()
            
            # Check jika restart diperlukan dari API thread
            if data_manager.is_restart_required():
                logger.info("Restart required due to source change")
                break
            
            # Baca frame
            frame = video_capture.read()
            if frame is None:
                time.sleep(0.01)
                continue
            
            display_frame = frame.copy()
            
            # Data management (non-blocking sekarang)
            data_manager.check_and_reset_if_needed()
            
            # Detection
            detection_counter += 1
            do_detection = detection_counter >= detection_interval
            
            if do_detection:
                detection_counter = 0
                
                try:
                    results = model(frame, verbose=False)
                    
                    current_centroids = {}
                    detected_objects = []
                    
                    for r in results:
                        boxes = r.boxes
                        if boxes is not None:
                            for box in boxes:
                                cls = int(box.cls[0])
                                conf = float(box.conf[0])
                                class_name = model.names[cls]
                                
                                if conf > confidence_threshold and class_name in ['car', 'motorcycle', 'truck', 'bus', 'bicycle', 'person']:
                                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                                    centroid_x = (x1 + x2) // 2
                                    centroid_y = (y1 + y2) // 2
                                    
                                    # Simple tracking
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
                                    
                                    # Line crossing detection
                                    direction = ""
                                    direction_color = color
                                    
                                    if matched_id in prev_centroids:
                                        prev_y = prev_centroids[matched_id][1]
                                        
                                        # Check up lines
                                        for i, up_y in enumerate(up_lines_y):
                                            line_num = i + 1
                                            if prev_y > up_y and centroid_y <= up_y and matched_id not in crossed_ids[f'up{line_num}']:
                                                data_manager.update_count(class_name, f'up{line_num}')
                                                crossed_ids[f'up{line_num}'].add(matched_id)
                                                direction = f"↑ {line_num}"
                                                direction_color = (0, 255, 0)
                                        
                                        # Check down lines
                                        for i, down_y in enumerate(down_lines_y):
                                            line_num = i + 1
                                            if prev_y < down_y and centroid_y >= down_y and matched_id not in crossed_ids[f'down{line_num}']:
                                                data_manager.update_count(class_name, f'down{line_num}')
                                                crossed_ids[f'down{line_num}'].add(matched_id)
                                                direction = f"↓ {line_num}"
                                                direction_color = (0, 0, 255)
                                    
                                    detected_objects.append({
                                        'id': matched_id,
                                        'class': class_name,
                                        'box': (x1, y1, x2, y2),
                                        'centroid': (centroid_x, centroid_y),
                                        'color': color,
                                        'direction': direction,
                                        'direction_color': direction_color
                                    })
                    
                    prev_centroids = current_centroids
                    
                    # Clean up crossed IDs
                    for key in crossed_ids:
                        crossed_ids[key] = {id for id in crossed_ids[key] if id in current_centroids}
                    
                    last_detected_objects = detected_objects
                    
                except Exception as e:
                    logger.error(f"Detection error: {e}")
                    detected_objects = last_detected_objects
            else:
                detected_objects = last_detected_objects
            
            # Draw detection lines
            for i, y in enumerate(up_lines_y):
                cv2.line(display_frame, (0, y), (width, y), (0, 230, 0), 2)
                cv2.putText(display_frame, f"U{i+1}", (5, y-5), font, 0.5, (0, 230, 0), 2)
            
            for i, y in enumerate(down_lines_y):
                cv2.line(display_frame, (0, y), (width, y), (0, 0, 230), 2)
                cv2.putText(display_frame, f"D{i+1}", (5, y+15), font, 0.5, (0, 0, 230), 2)
            
            # Draw detected objects
            for obj in detected_objects:
                x1, y1, x2, y2 = obj['box']
                centroid_x, centroid_y = obj['centroid']
                color = obj['color']
                
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                cv2.circle(display_frame, (centroid_x, centroid_y), 3, color, -1)
                
                # Draw trajectory
                if obj['id'] in tracker.trajectories:
                    points = list(tracker.trajectories[obj['id']])
                    for i in range(1, len(points)):
                        cv2.line(display_frame, points[i-1], points[i], color, 1)
                
                # Draw label
                direction = obj.get('direction', '')
                direction_color = obj.get('direction_color', color)
                cls_name = obj['class'][:3]
                label = f"{cls_name} {direction}".strip()
                
                cv2.putText(display_frame, label, (x1, y1-5), font, 0.5, (0, 0, 0), 3)
                cv2.putText(display_frame, label, (x1, y1-5), font, 0.5, direction_color, 1)
            
            # Sidebar
            if show_sidebar:
                sidebar = create_sidebar(display_frame, 250)
                
                cv2.putText(sidebar, "TRAFFIC ANALYTICS", (10, 30), font, 0.7, (255, 255, 255), 2)
                
                y_pos = 70
                counts = data_manager.get_summary_counts()
                cv2.putText(sidebar, "Current Counts:", (10, y_pos), font, 0.5, (255, 255, 255), 1)
                y_pos += 25
                cv2.putText(sidebar, f"Car: {counts['car_up']}↑ {counts['car_down']}↓", (15, y_pos), font, 0.5, (200, 200, 200), 1)
                y_pos += 20
                cv2.putText(sidebar, f"Bus: {counts['bus_up']}↑ {counts['bus_down']}↓", (15, y_pos), font, 0.5, (200, 200, 200), 1)
                y_pos += 20
                cv2.putText(sidebar, f"Truck: {counts['truck_up']}↑ {counts['truck_down']}↓", (15, y_pos), font, 0.5, (200, 200, 200), 1)
                y_pos += 20
                cv2.putText(sidebar, f"Person/Motor: {counts['person_motor_up']}↑ {counts['person_motor_down']}↓", (15, y_pos), font, 0.5, (200, 200, 200), 1)
                
                # System info
                y_pos = height - 80
                cv2.putText(sidebar, f"FPS: {current_fps:.1f}", (15, y_pos), font, 0.5, (200, 200, 200), 1)
                y_pos += 20
                cv2.putText(sidebar, f"Objects: {len(detected_objects)}", (15, y_pos), font, 0.5, (200, 200, 200), 1)
                y_pos += 20
                cv2.putText(sidebar, "API: Non-blocking", (15, y_pos), font, 0.4, (0, 255, 0), 1)
                y_pos += 20
                cv2.putText(sidebar, "Q: Quit, H: Hide sidebar", (15, y_pos), font, 0.4, (150, 150, 150), 1)
                
                display_frame = overlay_sidebar(display_frame, sidebar, width)
            else:
                cv2.putText(display_frame, f"FPS: {current_fps:.1f}", (10, 30), font, 0.6, (255, 255, 255), 2)
                cv2.putText(display_frame, f"Objects: {len(detected_objects)}", (10, 60), font, 0.6, (255, 255, 255), 2)
                cv2.putText(display_frame, "API: Non-blocking", (10, 90), font, 0.5, (0, 255, 0), 2)
            
            # Calculate FPS
            fps_counter += 1
            if fps_counter >= 30:
                elapsed = time.time() - fps_start_time
                current_fps = fps_counter / elapsed
                fps_counter = 0
                fps_start_time = time.time()
            
            # Display
            cv2.imshow(window_name, display_frame)
            
            # Key handling
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                logger.info("Quit requested")
                running = False
            elif key == ord('h'):
                show_sidebar = not show_sidebar
                display_width = width + (250 if show_sidebar else 0)
                cv2.resizeWindow(window_name, display_width, height)
                logger.info(f"Sidebar {'shown' if show_sidebar else 'hidden'}")
            
            # Frame rate control - target 30 FPS
            loop_time = time.time() - loop_start
            target_time = 1.0 / 30.0
            if loop_time < target_time:
                time.sleep(target_time - loop_time)
                
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Stop API thread
        data_manager.stop()
        video_capture.stop()
        cv2.destroyAllWindows()
    
    return data_manager.is_restart_required()

if __name__ == "__main__":
   parser = argparse.ArgumentParser(description='Non-Blocking Vehicle Counter')
   parser.add_argument('--model', type=str, default='yolov8n.pt', help='YOLO model')
   parser.add_argument('--video', type=str, help='Video file path (optional, will use API if not provided)')
   parser.add_argument('--output', type=str, default='output', help='Output directory')
   args = parser.parse_args()
   
   # Initialize settings
   settings_manager = SettingsManager()
   
   # Set video source jika diberikan via argument
   if args.video:
       settings_manager.settings['video_source'] = args.video
       settings_manager.settings['camera_name'] = f"Local Video: {os.path.basename(args.video)}"
       settings_manager.settings['camera_mode'] = "Counting Kendaraan"
       settings_manager.save_settings(settings_manager.settings)
   
   logger.info("Starting Non-Blocking Vehicle Counter")
   logger.info("API calls now run in background thread - no more video freezing!")
   logger.info("Controls: Q/ESC=Quit, H=Toggle sidebar")
   
   # Main application loop with restart support
   restart = True
   while restart:
       restart = run_vehicle_counter(
           settings_manager=settings_manager,
           output_dir=args.output,
           yolo_model=args.model
       )
       
       if restart:
           logger.info("Restarting application due to source change...")
           time.sleep(1)  # Brief pause before restart