
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

# Setup logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Kelas untuk manajemen pengaturan
class SettingsManager:
    def __init__(self, settings_file="config/settings_opencv.json"):
        self.settings_file = settings_file
        
        # Default settings
        self.default_settings = {
            'interval': 300,  # Interval kirim ke server (detik)
            'api_url': "http://17.12.89.3:5000",  # URL server API
            'api_check_interval': 5,  # Interval cek API (detik)
            'reset_interval': 20,  # Interval reset dan akumulasi (detik)
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
                'target_fps': 30,  # Target FPS untuk pemrosesan
                'confidence_threshold': 0.3,  # Threshold deteksi
                'tracking_points': 30  # Jumlah titik tracking
            },
            'display': {
                'resize_factor': 0.8,  # Faktor resize untuk tampilan
                'show_sidebar': True,  # Tampilkan sidebar
                'screenshot_interval': 0  # Interval screenshot (0=disabled)
            }
        }
        
        self.ensure_config_dir()
        self.settings = self.load_settings()

    def ensure_config_dir(self):
        """
        Memastikan direktori config ada
        """
        config_dir = os.path.dirname(self.settings_file)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

    def load_settings(self):
        """
        Load settings dari file, update dengan nilai default jika diperlukan
        """
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    
                    # Deep merge with default settings
                    merged_settings = self.default_settings.copy()
                    
                    for key, value in settings.items():
                        if isinstance(value, dict) and key in merged_settings:
                            merged_settings[key].update(value)
                        else:
                            merged_settings[key] = value
                    
                    return merged_settings
            else:
                # Jika file tidak ada, gunakan default settings
                self.save_settings(self.default_settings)
                return self.default_settings.copy()
                
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            # Jika terjadi error, gunakan default settings
            return self.default_settings.copy()

    def save_settings(self, settings):
        """
        Simpan settings ke file
        """
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
            self.settings = settings
            logger.info("Settings saved successfully")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

# Kelas untuk tracking objek
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
        
    def clear_old_trajectories(self, active_ids):
        """
        Membersihkan trajectory yang sudah tidak aktif
        """
        current_ids = set(self.trajectories.keys())
        inactive_ids = current_ids - set(active_ids)
        for inactive_id in inactive_ids:
            if inactive_id in self.trajectories:
                del self.trajectories[inactive_id]
            if inactive_id in self.colors:
                del self.colors[inactive_id]

# Kelas untuk manajemen data dan API
class DataManager:
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.current_counts = self.initialize_counts()
        self.accumulated_counts = self.initialize_accumulated_counts()  # Untuk mengakumulasi nilai maksimum
        self.last_save_time = time.time()
        self.last_reset_time = time.time()  # Untuk reset setiap 20 detik
        self.base_url = settings_manager.settings['api_url']
        self.reset_interval = settings_manager.settings.get('reset_interval', 20)  # Interval reset 20 detik
        
    def initialize_counts(self):
        """
        Inisialisasi struktur data untuk perhitungan
        """
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
        """
        Inisialisasi struktur data untuk nilai akumulasi
        """
        return {
            'car_up': 0,
            'car_down': 0, 
            'bus_up': 0,
            'bus_down': 0,
            'truck_up': 0,
            'truck_down': 0,
            'person_motor_up': 0,
            'person_motor_down': 0
        }

    def update_count(self, object_type, direction, count=1):
        """
        Update perhitungan untuk tipe objek dan arah tertentu
        """
        if object_type in self.current_counts and direction in self.current_counts[object_type]:
            self.current_counts[object_type][direction] += count

    def get_summary_counts(self):
        """
        Mendapatkan nilai maksimum untuk setiap tipe kendaraan
        """
        counts = self.current_counts
        
        # Mendapatkan hitungan maksimum untuk setiap arah
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
        
        # Membandingkan hitungan orang dan motor/sepeda dan mengambil nilai maksimum
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
            'car_up': car_up,
            'car_down': car_down,
            'bus_up': bus_up,
            'bus_down': bus_down,
            'truck_up': truck_up,
            'truck_down': truck_down,
            'person_motor_up': person_motor_up,
            'person_motor_down': person_motor_down
        }
        
    def check_and_reset_if_needed(self):
        """
        Periksa apakah sudah waktunya untuk reset penghitungan dan akumulasi nilai maksimum
        """
        current_time = time.time()
        
        # Jika interval reset (20 detik) telah berlalu
        if current_time - self.last_reset_time >= self.reset_interval:
            # Dapatkan nilai maksimum saat ini
            current_summary = self.get_summary_counts()
            
            # Akumulasi nilai maksimum (tambahkan ke nilai yang ada)
            for key in self.accumulated_counts:
                self.accumulated_counts[key] += current_summary[key]
                
            # Log informasi akumulasi
            logger.info(f"Accumulated max counts after {self.reset_interval}s interval: {current_summary}")
            logger.info(f"Total accumulated counts: {self.accumulated_counts}")
            
            # Reset penghitungan untuk interval berikutnya
            self.current_counts = self.initialize_counts()
            
            # Update waktu reset terakhir
            self.last_reset_time = current_time
            
            return True
        
        return False

    def save_current_counts(self):
        """
        Menyimpan perhitungan nilai akumulasi ke API
        """
        try:
            camera_name = self.settings_manager.settings['camera_name']
            camera_mode = self.settings_manager.settings['camera_mode']
            
            if not camera_name or not camera_mode:
                logger.warning("Cannot save counts: camera name or mode not configured")
                return False
                
            # Kirim nilai akumulasi
            result = json.dumps(self.accumulated_counts)
            
            url = f"{self.base_url}/api/save"
            params = {
                "camera_name": camera_name,
                "mode": camera_mode,
                "result": result
            }
            
            response = requests.get(url, params=params)
            success = response.status_code == 200
            
            if success:
                logger.info(f"Successfully saved accumulated counts to server: {self.accumulated_counts}")
                # Reset nilai akumulasi setelah berhasil mengirim
                self.accumulated_counts = self.initialize_accumulated_counts()
            else:
                logger.error(f"Failed to save counts: HTTP {response.status_code}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error saving counts: {e}")
            return False
            
    def check_and_save_if_needed(self):
        """Check if it's time to save counts and do so if needed"""
        current_time = time.time()
        interval = self.settings_manager.settings['interval']
        
        if current_time - self.last_save_time >= interval:
            if self.save_current_counts():
                self.last_save_time = current_time
                return True
                
        return False
        
    def get_cameras(self):
        """
        Mengambil daftar kamera dari API
        """
        try:
            mode = "Counting Kendaraan"
            response = requests.get(f"{self.base_url}/api/processor?mode={quote(mode)}")
            
            if response.status_code == 200:
                data = response.json()
                cameras = data.get("cameras", [])
                return cameras
            else:
                logger.error(f"Failed to get cameras: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting cameras: {e}")
            return []
            
    def update_camera_source(self):
        """
        Update video source berdasarkan data API
        """
        try:
            # Force refresh camera list
            cameras = self.get_cameras()
            if not cameras:
                self.settings_manager.settings['video_source'] = None
                self.settings_manager.settings['camera_name'] = None
                self.settings_manager.settings['camera_mode'] = None
                self.settings_manager.save_settings(self.settings_manager.settings)
                logger.warning("No cameras available from API")
                return False

            # Get first available camera
            camera = cameras[0]
            
            if camera:
                # Store previous settings
                previous_settings = {
                    'video_source': self.settings_manager.settings.get('video_source'),
                    'camera_name': self.settings_manager.settings.get('camera_name'),
                    'camera_mode': self.settings_manager.settings.get('camera_mode')
                }
                
                # Update settings
                self.settings_manager.settings['video_source'] = camera['ip']
                self.settings_manager.settings['camera_name'] = camera['name']
                self.settings_manager.settings['camera_mode'] = camera['mode']
                
                # Save settings
                self.settings_manager.save_settings(self.settings_manager.settings)
                
                # Check if anything changed
                changed = any(
                    previous_settings[key] != self.settings_manager.settings[key]
                    for key in previous_settings
                )
                
                logger.info(f"Camera updated: {camera['name']} - {camera['ip']}")
                return True
                
            return False
                
        except Exception as e:
            logger.error(f"Error updating camera source: {e}")
            return False

# Thread untuk mengambil frame dari video source dengan kontrol framerate
class FramerateControlledCapture:
    def __init__(self, video_source, resize_factor=1.0, target_fps=None):
        self.video_source = video_source
        self.resize_factor = resize_factor
        self.restart_required = False  # Flag untuk menandakan perlu restart aplikasi

        # Inisialisasi video capture
        logger.info(f"Connecting to video source: {video_source}")
        self.cap = cv2.VideoCapture(video_source, cv2.CAP_FFMPEG)
        
        # Set options khusus untuk stream RTSP/HTTP
        if isinstance(video_source, str) and video_source.startswith(('rtsp://', 'http://', 'https://')):
            logger.info("Setting stream parameters for RTSP/HTTP connection")
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
            
        # Cek koneksi    
        if not self.cap.isOpened():
            logger.error("Failed to open video source")
            self.grabbed = False
            self.frame = None
            return
        
        # Dapatkan framerate asli video
        self.original_fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.original_fps <= 0 or self.original_fps > 60:
            logger.warning(f"Unusual FPS detected ({self.original_fps}), setting to 25 FPS")
            self.original_fps = 25.0
        else:
            logger.info(f"Video original FPS: {self.original_fps}")
        
        # Set target framerate (gunakan original jika tidak ditentukan)
        self.target_fps = target_fps if target_fps is not None else self.original_fps
        
        # Baca frame pertama
        logger.info("Reading first frame...")
        retry_count = 0
        max_retries = 5
        while retry_count < max_retries:
            self.grabbed, frame = self.cap.read()
            if self.grabbed:
                break
            retry_count += 1
            logger.warning(f"Failed to grab first frame, retrying ({retry_count}/{max_retries})...")
            time.sleep(1)
            
        if not self.grabbed:
            logger.error("Could not grab first frame after multiple attempts")
            self.frame = None
            return
            
        # Get original dimensions
        self.original_width = frame.shape[1]
        self.original_height = frame.shape[0]
        
        # Calculate resized dimensions
        self.width = int(self.original_width * self.resize_factor)
        self.height = int(self.original_height * self.resize_factor)
            
        # Resize jika diperlukan, tetapi pertahankan aspect ratio
        if self.grabbed and self.resize_factor != 1.0:
            frame = cv2.resize(frame, (self.width, self.height))
        
        self.frame = frame
        self.last_frame_time = time.time()
        self.stopped = False
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()
        
        # Thread lock
        self.lock = threading.Lock()
        
        # Frame buffer for dropout protection
        self.frame_buffer = deque(maxlen=5)
        
        # Variabel untuk kontrol framerate
        self.frame_interval = 1.0 / self.target_fps
        
        logger.info(f"Video capture initialized successfully")
        logger.info(f"Original dimensions: {self.original_width}x{self.original_height}")
        logger.info(f"Resized dimensions: {self.width}x{self.height}")
        
    def start(self):
        if not self.grabbed:
            logger.error("Cannot start video capture thread (initialization failed)")
            return self
            
        threading.Thread(target=self.update, daemon=True).start()
        return self
        
    def update(self):
        """Threading function untuk mengambil frame dengan kontrol framerate"""
        frame_error_count = 0
        consecutive_errors = 0
        max_consecutive_errors = 10
        max_reconnection_attempts = 3
        reconnection_attempts = 0

        while not self.stopped:
            if not self.grabbed:
                frame_error_count += 1
                consecutive_errors += 1
                logger.warning(f"Frame grab error #{frame_error_count}, consecutive: {consecutive_errors}")

                if consecutive_errors > max_consecutive_errors:
                    reconnection_attempts += 1
                    logger.error(f"Too many consecutive frame errors, attempting reconnection (attempt {reconnection_attempts}/{max_reconnection_attempts})")

                    if reconnection_attempts >= max_reconnection_attempts:
                        logger.error("Maximum reconnection attempts reached. Requesting application restart...")
                        self.restart_required = True
                        self.stopped = True
                        break

                    try:
                        self.cap.release()
                        time.sleep(2)
                        self.cap = cv2.VideoCapture(self.video_source, cv2.CAP_FFMPEG)
                        if isinstance(self.video_source, str) and self.video_source.startswith(('rtsp://', 'http://', 'https://')):
                            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
                            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
                        consecutive_errors = 0
                    except Exception as e:
                        logger.error(f"Reconnection error: {e}")

                time.sleep(0.1)
                continue
            
            # Waktu yang dibutuhkan untuk setiap frame berdasarkan target FPS
            current_time = time.time()
            elapsed = current_time - self.last_frame_time
            
            # Hanya ambil frame baru jika sudah waktunya
            if elapsed >= self.frame_interval:
                self.grabbed, frame = self.cap.read()
                
                if not self.grabbed:
                    consecutive_errors += 1
                    logger.warning(f"Failed to grab frame, consecutive errors: {consecutive_errors}")
                    time.sleep(0.1)
                    continue

                # Reset error counters on successful grab
                consecutive_errors = 0
                reconnection_attempts = 0
                
                # Apply resize
                if self.resize_factor != 1.0:
                    frame = cv2.resize(frame, (self.width, self.height))
                    
                with self.lock:
                    self.frame = frame.copy()
                    self.frame_buffer.append(frame.copy())
                
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
        """Thread-safe frame reading with dropout prevention"""
        with self.lock:
            if self.frame is None:
                # Try to use buffer if available
                if self.frame_buffer:
                    return self.frame_buffer[-1].copy()
                return None
            return self.frame.copy()
    
    def get_fps(self):
        return self.fps
    
    def get_dimensions(self):
        return (self.width, self.height)
        
    def get_original_dimensions(self):
        return (self.original_width, self.original_height)
        
    def update_resize_factor(self, new_factor):
        """Update resize factor and recalculate dimensions"""
        with self.lock:
            self.resize_factor = new_factor
            self.width = int(self.original_width * self.resize_factor)
            self.height = int(self.original_height * self.resize_factor)
            logger.info(f"Updated resize factor to {new_factor}, new dimensions: {self.width}x{self.height}")
        
    def stop(self):
        self.stopped = True
        if hasattr(self, 'cap') and self.cap is not None:
            self.cap.release()
        logger.info("Video capture released")

    def is_opened(self):
        return hasattr(self, 'cap') and self.cap is not None and self.cap.isOpened()

    def is_restart_required(self):
        """Check if application restart is required due to persistent errors"""
        return self.restart_required

# Screenshot Manager
class ScreenshotManager:
    def __init__(self, save_dir="screenshots", interval=0, prefix="tracking"):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        self.interval = interval  # Interval in seconds (0 = disabled)
        self.prefix = prefix
        self.last_save_time = 0
        
    def maybe_save(self, frame, current_time):
        """Ambil screenshot saat interval waktu tercapai"""
        if self.interval <= 0:
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
            logger.info(f"Screenshot saved to {filename}")
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

def run_vehicle_counter(
    settings_manager,
    output_dir='output',
    yolo_model='yolov8s.pt'
):
    """Main function to run the vehicle counter application"""
    
    # Buat directory output jika belum ada
    os.makedirs(output_dir, exist_ok=True)
    
    # Inisialisasi data manager
    data_manager = DataManager(settings_manager)
    tracker = ObjectTracker(max_trajectory_points=settings_manager.settings['processing']['tracking_points'])
    
    # Inisialisasi screenshot manager
    screenshot_mgr = ScreenshotManager(
        save_dir=output_dir, 
        interval=settings_manager.settings['display']['screenshot_interval']
    )
    
    # Load YOLO model
    try:
        logger.info(f"Loading {yolo_model}...")
        model = YOLO(yolo_model)
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return

    # Configuration variables
    confidence_threshold = settings_manager.settings['processing']['confidence_threshold']
    target_fps = settings_manager.settings['processing']['target_fps']
    resize_factor = settings_manager.settings['display']['resize_factor']
    show_sidebar = settings_manager.settings['display']['show_sidebar']
    api_check_interval = settings_manager.settings['api_check_interval']
    
    # Inisialisasi variabel tracking
    prev_centroids = {}
    tracking_id = 0
    crossed_ids = {
        f'up{i+1}': set() for i in range(6)
    } | {
        f'down{i+1}': set() for i in range(6)
    }
    
    # Flags for operation
    running = True
    restart_required = False
    last_api_check = time.time()
    video_source = settings_manager.settings.get('video_source')
    
    # Font settings for clean UI
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale_small = 0.5
    font_scale_medium = 0.6
    font_scale_large = 0.7
    
    # Initialize keyboard handler - key mapping
    key_actions = {
        ord('q'): 'quit',          # Quit
        ord('s'): 'screenshot',    # Take screenshot
        ord('h'): 'toggle_sidebar',# Hide/show sidebar
        ord('+'): 'increase_size', # Increase size
        ord('-'): 'decrease_size', # Decrease size
        ord('r'): 'restart',       # Restart
        27: 'quit'                 # ESC = quit
    }
    
    # Main processing loop
    while running:
        # Check API for camera updates periodically
        current_time = time.time()
        if current_time - last_api_check >= api_check_interval:
            last_api_check = current_time
            if data_manager.update_camera_source():
                # Check if source changed
                new_source = settings_manager.settings.get('video_source')
                if new_source != video_source:
                    logger.info(f"Video source changed from {video_source} to {new_source}")
                    video_source = new_source
                    restart_required = True
                    break
        
        # Check if we have a video source
        if not video_source:
            logger.warning("No video source available. Checking API...")
            if data_manager.update_camera_source():
                video_source = settings_manager.settings.get('video_source')
                if not video_source:
                    logger.error("Still no video source after API check. Waiting...")
                    # Show a message on a black frame
                    message_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(message_frame, "No video source available", (50, 240), font, 1, (255, 255, 255), 2)
                    cv2.putText(message_frame, "Checking for camera...", (50, 280), font, 0.7, (200, 200, 200), 2)
                    cv2.putText(message_frame, "Press 'q' to quit", (50, 320), font, 0.7, (200, 200, 200), 2)
                    
                    cv2.imshow("Vehicle Counter", message_frame)
                    key = cv2.waitKey(1000) & 0xFF
                    if key == ord('q') or key == 27:  # q or ESC
                        running = False
                    continue
            else:
                # Show message and wait for next API check
                logger.error("Failed to get video source from API. Waiting...")
                message_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(message_frame, "Waiting for camera connection...", (50, 240), font, 1, (255, 255, 255), 2)
                cv2.putText(message_frame, "Press 'q' to quit", (50, 280), font, 0.7, (200, 200, 200), 2)
                
                cv2.imshow("Vehicle Counter", message_frame)
                key = cv2.waitKey(1000) & 0xFF
                if key == ord('q') or key == 27:  # q or ESC
                    running = False
                continue

        # Start video capture
        logger.info(f"Starting video capture from: {video_source}")
        video_capture = FramerateControlledCapture(
            video_source=video_source,
            resize_factor=resize_factor,
            target_fps=target_fps
        ).start()
        
        # Make sure we have a valid video source
        if not video_capture.is_opened():
            logger.error(f"Failed to open video source: {video_source}")
            message_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(message_frame, f"Failed to open video source", (50, 240), font, 1, (255, 255, 255), 2)
            cv2.putText(message_frame, "Checking for camera...", (50, 280), font, 0.7, (200, 200, 200), 2)
            
            cv2.imshow("Vehicle Counter", message_frame)
            key = cv2.waitKey(3000) & 0xFF
            if key == ord('q') or key == 27:  # q or ESC
                running = False
            continue

        # Get frame dimensions
        width, height = video_capture.get_dimensions()
        
        # Define detection lines
        line_spacing = height / 7  # Jarak antar garis
        
        # Calculate line positions based on settings (or use default spacing)
        line_settings = settings_manager.settings['lines']
        up_lines_y = [int(height * line_settings[f'up{i+1}']) for i in range(6)]
        down_lines_y = [int(height * line_settings[f'down{i+1}']) for i in range(6)]
        
        # Setup window
        window_name = "Vehicle Counter"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        
        # Calculate display size with sidebar if needed
        display_width = width + (250 if show_sidebar else 0)
        cv2.resizeWindow(window_name, display_width, height)
        
        # Inisialisasi sidebar
        sidebar_width = 250
        
        # Main camera loop (processing each frame)
        frame_count = 0
        start_time = time.time()
        processing_fps = 0
        tracking_fps = video_capture.get_fps()
        
        # Variable for last detection time for FPS control
        last_detection_time = 0
        detection_interval = 1.0 / 10  # Process detections at 10 FPS maximum
        
        # For tracking last detected objects
        last_detected_objects = []

        # For tracking null frames
        null_frame_count = 0
        max_null_frames = 50  # Restart after 50 consecutive null frames

        logger.info("Starting main processing loop")

        try:
            while not video_capture.stopped and running:
                current_time = time.time()

                # Check if video capture requires restart due to persistent errors
                if video_capture.is_restart_required():
                    logger.warning("Video capture encountered persistent errors. Triggering restart...")
                    restart_required = True
                    break

                # Check for API updates
                if current_time - last_api_check >= api_check_interval:
                    last_api_check = current_time
                    if data_manager.update_camera_source():
                        new_source = settings_manager.settings.get('video_source')
                        if new_source != video_source:
                            logger.info(f"Video source changed from {video_source} to {new_source}")
                            video_source = new_source
                            restart_required = True
                            break

                # Check if it's time to save counts to server
                data_manager.check_and_save_if_needed()

                # Check if it's time to reset counts and accumulate maximums
                data_manager.check_and_reset_if_needed()

                # Get latest frame
                frame = video_capture.read()
                if frame is None:
                    null_frame_count += 1
                    logger.warning(f"Null frame received, waiting... (consecutive: {null_frame_count})")

                    if null_frame_count >= max_null_frames:
                        logger.error(f"Too many consecutive null frames ({null_frame_count}). Triggering restart...")
                        restart_required = True
                        break

                    time.sleep(0.1)
                    continue
                else:
                    # Reset null frame counter on successful read
                    null_frame_count = 0
                
                # Create a clean copy for UI
                display_frame = frame.copy()
                
                # Create sidebar with clean UI if enabled
                if show_sidebar:
                    sidebar, sidebar_alpha = create_sidebar(display_frame, sidebar_width)
                
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
                                
                                if conf > confidence_threshold and class_name in ['car', 'motorcycle', 'truck', 'bus', 'bicycle', 'person']:
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
                                                data_manager.update_count(class_name, f'up{line_num}')
                                                crossed_ids[f'up{line_num}'].add(matched_id)
                                                direction = f"↑ {line_num}"
                                                direction_color = (0, 255, 0)
                                        
                                        # Check all down lines
                                        for i, down_y in enumerate(down_lines_y):
                                            line_num = i + 1
                                            if prev_y < down_y and centroid_y >= down_y and matched_id not in crossed_ids[f'down{line_num}']:
                                                data_manager.update_count(class_name, f'down{line_num}')
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
                        frame_count += 1
                        elapsed_time = time.time() - start_time
                        if elapsed_time >= 1.0:
                            processing_fps = frame_count / elapsed_time
                            frame_count = 0
                            start_time = time.time()
                            tracking_fps = video_capture.get_fps()
                        
                        # Hitung waktu proses
                        process_time = time.time() - process_start
                        
                        # Simpan object untuk visualisasi
                        last_detected_objects = detected_objects
                        
                    except Exception as e:
                        logger.error(f"Detection error: {e}")
                        continue
                else:
                    # Gunakan hasil deteksi sebelumnya
                    detected_objects = last_detected_objects
                    process_time = 0
                
                # Draw detection lines dengan desain yang lebih bersih
                for i, y in enumerate(up_lines_y):
                    line_num = i + 1
                    # Basic line - warna standar hijau
                    line_color = (0, 230, 0)
                    text_color = (0, 230, 0)
                    
                    # Draw main line
                    cv2.line(display_frame, (0, y), (width, y), line_color, 2)
                    
                    # Draw minimal label
                    label = f"U{line_num}"
                    cv2.putText(display_frame, label, (5, y - 5),
                               font, font_scale_small, text_color, 2)
                
                for i, y in enumerate(down_lines_y):
                    line_num = i + 1
                    # Basic line - warna standar biru
                    line_color = (0, 0, 230)
                    text_color = (0, 0, 230)
                    
                    # Draw main line
                    cv2.line(display_frame, (0, y), (width, y), line_color, 2)
                    
                    # Draw minimal label
                    label = f"D{line_num}"
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
                
                # If sidebar is enabled, create and overlay it
                if show_sidebar:
                    # Create clean sidebar content
                    cv2.putText(sidebar, "TRAFFIC ANALYTICS", (10, 30), 
                               font, font_scale_large, (255, 255, 255), 2)
                    
                    # Camera info
                    y_pos = 60
                    camera_name = settings_manager.settings.get('camera_name', 'Unknown')
                    camera_mode = settings_manager.settings.get('camera_mode', 'Unknown')
                    cv2.putText(sidebar, f"Camera: {camera_name}", (10, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 20
                    cv2.putText(sidebar, f"Mode: {camera_mode}", (10, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 30
                    
                    # Reset interval info
                    reset_progress = min(100, ((current_time - data_manager.last_reset_time) / data_manager.reset_interval) * 100)
                    cv2.putText(sidebar, f"Reset Interval ({data_manager.reset_interval}s):", (10, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 20
                    
                    # Draw reset interval progress bar
                    bar_width = 230
                    bar_height = 10
                    filled_width = int(bar_width * reset_progress / 100)
                    cv2.rectangle(sidebar, (10, y_pos), (10 + bar_width, y_pos + bar_height), (50, 50, 50), -1)
                    cv2.rectangle(sidebar, (10, y_pos), (10 + filled_width, y_pos + bar_height), (0, 255, 0), -1)
                    cv2.putText(sidebar, f"{reset_progress:.0f}%", (10 + bar_width + 5, y_pos + 8), 
                               font, 0.4, (200, 200, 200), 1)
                    y_pos += 20
                    
                    # Save interval info
                    save_progress = min(100, ((current_time - data_manager.last_save_time) / settings_manager.settings['interval']) * 100)
                    cv2.putText(sidebar, f"Save Interval ({settings_manager.settings['interval']}s):", (10, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 20
                    
                    # Draw save interval progress bar
                    bar_width = 230
                    bar_height = 10
                    filled_width = int(bar_width * save_progress / 100)
                    cv2.rectangle(sidebar, (10, y_pos), (10 + bar_width, y_pos + bar_height), (50, 50, 50), -1)
                    cv2.rectangle(sidebar, (10, y_pos), (10 + filled_width, y_pos + bar_height), (0, 255, 0), -1)
                    cv2.putText(sidebar, f"{save_progress:.0f}%", (10 + bar_width + 5, y_pos + 8), 
                               font, 0.4, (200, 200, 200), 1)
                    
                    # Current accumulated counts
                    y_pos += 30
                    cv2.putText(sidebar, "Accumulated Maximums:", (10, y_pos), 
                               font, font_scale_small, (255, 255, 255), 1)
                    y_pos += 25
                    
                    # Display accumulated counts
                    counts = data_manager.accumulated_counts
                    cv2.putText(sidebar, f"Car: {counts['car_up']}↑ {counts['car_down']}↓", (15, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 20
                    cv2.putText(sidebar, f"Bus: {counts['bus_up']}↑ {counts['bus_down']}↓", (15, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 20
                    cv2.putText(sidebar, f"Truck: {counts['truck_up']}↑ {counts['truck_down']}↓", (15, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 20
                    cv2.putText(sidebar, f"Person/Motor: {counts['person_motor_up']}↑ {counts['person_motor_down']}↓", (15, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 30
                    
                    # Current interval counts (will be reset every 20s)
                    cv2.putText(sidebar, "Current 20s Interval:", (10, y_pos), 
                               font, font_scale_small, (255, 255, 255), 1)
                    y_pos += 25
                    
                    # Display current counts
                    current = data_manager.get_summary_counts()
                    cv2.putText(sidebar, f"Car: {current['car_up']}↑ {current['car_down']}↓", (15, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 20
                    cv2.putText(sidebar, f"Bus: {current['bus_up']}↑ {current['bus_down']}↓", (15, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 20
                    cv2.putText(sidebar, f"Truck: {current['truck_up']}↑ {current['truck_down']}↓", (15, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 20
                    cv2.putText(sidebar, f"Person/Motor: {current['person_motor_up']}↑ {current['person_motor_down']}↓", (15, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    
                    # System info at bottom of sidebar
                    y_pos = height - 80
                    cv2.putText(sidebar, "System Info:", (10, y_pos), 
                               font, font_scale_small, (255, 255, 255), 1)
                    y_pos += 20
                    
                    cv2.putText(sidebar, f"Camera: {tracking_fps:.1f} FPS", 
                                (15, y_pos), font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 20
                    
                    cv2.putText(sidebar, f"Processing: {processing_fps:.1f} FPS", 
                                (15, y_pos), font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 20
                    
                    # Add timestamp
                    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cv2.putText(sidebar, current_datetime, 
                                (15, y_pos), font, font_scale_small, (200, 200, 200), 1)
                    
                    # Add controls help
                    y_pos = height - 140
                    cv2.putText(sidebar, "Controls:", (10, y_pos), 
                              font, font_scale_small, (255, 255, 255), 1)
                    y_pos += 20
                    cv2.putText(sidebar, "Q/ESC: Quit", (15, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 20
                    cv2.putText(sidebar, "S: Screenshot", (15, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    y_pos += 20
                    cv2.putText(sidebar, "H: Hide/Show sidebar", (15, y_pos), 
                               font, font_scale_small, (200, 200, 200), 1)
                    
                    # Overlay sidebar to main frame
                    display_frame = overlay_sidebar(display_frame, sidebar, sidebar_alpha, width - sidebar_width)
                
                else:
                    # If sidebar is disabled, just show minimal info on main screen
                    cv2.putText(display_frame, f"FPS: {processing_fps:.1f}", (10, 30), 
                               font, font_scale_medium, (255, 255, 255), 2)
                    cv2.putText(display_frame, f"Objects: {len(detected_objects)}", (10, 60), 
                               font, font_scale_medium, (255, 255, 255), 2)
                    cv2.putText(display_frame, f"Camera: {camera_name}", (10, 90), 
                               font, font_scale_medium, (255, 255, 255), 2)
                    
                    # Bottom-right timestamp
                    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    text_size = cv2.getTextSize(current_datetime, font, font_scale_small, 1)[0]
                    cv2.putText(display_frame, current_datetime, 
                              (width - text_size[0] - 10, height - 10), 
                              font, font_scale_small, (255, 255, 255), 1)
                
                # Take screenshot if needed
                screenshot_mgr.maybe_save(display_frame, current_time)
                
                # Display final frame
                cv2.imshow(window_name, display_frame)
                
                # Check for user input with short wait
                key = cv2.waitKey(1) & 0xFF
                
                # Handle key presses
                if key in key_actions:
                    action = key_actions[key]
                    
                    if action == 'quit':
                        logger.info("Quit requested by user")
                        running = False
                        break
                    elif action == 'screenshot':
                        screenshot_mgr.maybe_save(display_frame, 0)  # Force screenshot
                        logger.info("Screenshot taken")
                    elif action == 'toggle_sidebar':
                        show_sidebar = not show_sidebar
                        settings_manager.settings['display']['show_sidebar'] = show_sidebar
                        settings_manager.save_settings(settings_manager.settings)
                        # Update window size
                        display_width = width + (250 if show_sidebar else 0)
                        cv2.resizeWindow(window_name, display_width, height)
                        logger.info(f"Sidebar {'shown' if show_sidebar else 'hidden'}")
                    elif action == 'increase_size':
                        new_factor = min(resize_factor + 0.1, 1.5)
                        if new_factor != resize_factor:
                            resize_factor = new_factor
                            video_capture.update_resize_factor(resize_factor)
                            settings_manager.settings['display']['resize_factor'] = resize_factor
                            settings_manager.save_settings(settings_manager.settings)
                            logger.info(f"Resize factor increased to {resize_factor:.1f}")
                    elif action == 'decrease_size':
                        new_factor = max(resize_factor - 0.1, 0.3)
                        if new_factor != resize_factor:
                            resize_factor = new_factor
                            video_capture.update_resize_factor(resize_factor)
                            settings_manager.settings['display']['resize_factor'] = resize_factor
                            settings_manager.save_settings(settings_manager.settings)
                            logger.info(f"Resize factor decreased to {resize_factor:.1f}")
                    elif action == 'restart':
                        logger.info("Restart requested by user")
                        restart_required = True
                        break
                        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            running = False
        except Exception as e:
            logger.error(f"Critical error in main loop: {e}")
            import traceback
            traceback.print_exc()
            logger.warning("Triggering restart due to critical error...")
            restart_required = True
        finally:
            # Clean up
            if 'video_capture' in locals():
                video_capture.stop()
            cv2.destroyAllWindows()
    
    # Final cleanup
    cv2.destroyAllWindows()
    
    # Return restart flag
    return restart_required
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Vehicle Counter with OpenCV UI')
    parser.add_argument('--model', type=str, default='yolov8n.pt', help='YOLO model to use')
    parser.add_argument('--output', type=str, default='output', help='Output directory')
    args = parser.parse_args()
    
    # Initialize settings
    settings_manager = SettingsManager()
    
    # Show startup message
    logger.info("Starting Vehicle Counter Application")
    logger.info(f"Use keyboard shortcuts:")
    logger.info(f"  - Q/ESC: Quit")
    logger.info(f"  - S: Take screenshot")
    logger.info(f"  - H: Toggle sidebar")
    logger.info(f"  - +/-: Increase/decrease size")
    logger.info(f"  - R: Restart")
    
    # Main application loop with restart support
    restart = True
    restart_count = 0
    max_restarts = 10  # Maximum number of restarts before giving up
    restart_window_start = time.time()

    while restart:
        if restart_count > 0:
            logger.info(f"Restarting application (restart #{restart_count}/{max_restarts})...")

            # Check if we've restarted too many times
            if restart_count >= max_restarts:
                logger.error(f"Maximum restart limit ({max_restarts}) reached. Stopping application.")
                logger.error("Please check your camera connection and configuration.")
                break

            logger.info("Waiting 5 seconds before restart...")
            time.sleep(5)  # Wait before restarting to allow system cleanup

        restart = run_vehicle_counter(
            settings_manager=settings_manager,
            output_dir=args.output,
            yolo_model=args.model
        )

        restart_count += 1

        # Reset restart counter if we've been running successfully for a while (e.g., 5 minutes)
        if time.time() - restart_window_start > 300:  # 5 minutes
            logger.info("Application has been stable for 5 minutes. Resetting restart counter.")
            restart_count = 0
            restart_window_start = time.time()

        if restart:
            logger.info("Application will restart due to:")
            logger.info("  - Video source change, or")
            logger.info("  - Persistent connection errors, or")
            logger.info("  - User requested restart")

    logger.info("Application shutdown complete.")
