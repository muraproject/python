# utils/base_utils.py

import cv2
import numpy as np
import json
import os
from collections import deque
import requests
from urllib.parse import quote
from datetime import datetime


class GPUProcessor:
    """
    Class untuk mengelola penggunaan GPU dengan OpenCV
    """
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
            print("GPU acceleration tersedia menggunakan OpenCV UMat")
            return True
        except Exception as e:
            print(f"GPU acceleration tidak tersedia: {e}")
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
    """
    Class untuk tracking objek dan menyimpan trajectory
    """
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

    def clear_old_trajectories(self, active_ids):
        """
        Membersihkan trajectory yang sudah tidak aktif
        """
        current_ids = set(self.trajectories.keys())
        inactive_ids = current_ids - set(active_ids)
        for inactive_id in inactive_ids:
            del self.trajectories[inactive_id]
            if inactive_id in self.colors:
                del self.colors[inactive_id]

class DataManager:
    """
    Class untuk mengelola data perhitungan kendaraan
    """
    def __init__(self):
        self.current_counts = self.initialize_counts()
        self.api_manager = APIManager()

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

    def update_count(self, object_type, direction, count=1):
        """
        Update perhitungan untuk tipe objek dan arah tertentu
        """
        if object_type in self.current_counts and direction in self.current_counts[object_type]:
            self.current_counts[object_type][direction] += count

    def get_max_counts(self):
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

    def save_current_counts(self, camera_name, mode):
        """
        Menyimpan perhitungan saat ini ke API
        """
        max_counts = self.get_max_counts()
        success = self.api_manager.save_counts(max_counts, camera_name, mode)
        if success:
            self.reset_counts()
        return max_counts

    def reset_counts(self):
        """
        Reset semua perhitungan ke nol
        """
        self.current_counts = self.initialize_counts()

class SettingsManager:
    """
    Class untuk mengelola pengaturan aplikasi
    """
    def __init__(self):
        self.settings_file = "config/settings_mobil.json"
        self.api_manager = APIManager()
        self.gpu_processor = None
        self.tracker = None
        self.default_settings = {
            'interval': 300,
            'lines': {
                'up1': 0.15, 'up2': 0.25, 'up3': 0.35,
                'up4': 0.45, 'up5': 0.55, 'up6': 0.65,
                'down1': 0.20, 'down2': 0.30, 'down3': 0.40,
                'down4': 0.50, 'down5': 0.60, 'down6': 0.70
            },
            'video_source': None,
            'camera_row': 1,
            'camera_name': None,
            'camera_mode': None,
            'display': {
                'width': 640,
                'height': 480
            }
        }
        self.ensure_config_dir()
        self.settings = self.load_settings()

    def ensure_config_dir(self):
        """
        Memastikan direktori config ada
        """
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)


    def save_settings(self, settings):
        """
        Simpan settings ke file
        """
        with open(self.settings_file, 'w') as f:
            json.dump(settings, f, indent=4)
        self.settings = settings

    # Di base_utils.py, modifikasi SettingsManager:

# Di base_utils.py, perbaikan untuk SettingsManager:

# Modifikasi di base_utils.py

class SettingsManager:
    def __init__(self):
        self.settings_file = "config/settings_mobil.json"
        self.api_manager = APIManager()
        self.gpu_processor = None
        self.tracker = None
        
        # Default settings
        self.default_settings = {
            'interval': 300,
            'lines': {
                'up1': 0.15, 'up2': 0.25, 'up3': 0.35,
                'up4': 0.45, 'up5': 0.55, 'up6': 0.65,
                'down1': 0.20, 'down2': 0.30, 'down3': 0.40,
                'down4': 0.50, 'down5': 0.60, 'down6': 0.70
            },
            'video_source': None,
            'camera_name': None,
            'camera_mode': None,
            'display': {
                'width': 640,
                'height': 480
            }
        }
        
        self.ensure_config_dir()
        self.settings = {}
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
            print(f"Error loading settings: {e}")
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
        except Exception as e:
            print(f"Error saving settings: {e}")

    def update_video_source(self):
        try:
            cameras = self.api_manager.get_cameras()
            if not cameras:
                self.settings['video_source'] = None
                self.settings['camera_name'] = None
                self.settings['camera_mode'] = None
                self.save_settings(self.settings)
                return False

            # Gunakan data dari response API
            camera = cameras[1]  # Index tetap 0
            
            if camera:
                self.settings['video_source'] = camera['ip']
                self.settings['camera_name'] = camera['name']  # Menggunakan name dari API
                self.settings['camera_mode'] = camera['mode']
                
                self.save_settings(self.settings)
                print(f"Kamera diperbarui: {camera['name']} - {camera['ip']}")
                return True
            return False
                
        except Exception as e:
            print(f"Error memperbarui sumber video: {e}")
            return False
    def get_display_size(self):
        """
        Get current display size settings
        """
        return (
            self.settings['display']['width'],
            self.settings['display']['height']
        )

class APIManager:
    def __init__(self, base_url="http://103.139.192.236:5000"):
        self.base_url = base_url
        self.current_camera = None
        self.cameras = []
        self.last_update = None
        
    def get_cameras(self, mode="Counting Kendaraan"):
        """
        Mengambil daftar kamera dari API
        """
        try:
            response = requests.get(f"{self.base_url}/api/processor?mode={quote(mode)}")
            if response.status_code == 200:
                data = response.json()
                self.cameras = data.get("cameras", [])
                self.last_update = datetime.now()
                if self.cameras:
                    self.current_camera = self.cameras[1]  # Always use first camera
                return self.cameras
            return []
        except Exception as e:
            print(f"Error getting cameras: {e}")
            return []
            
    def save_counts(self, counts, camera_name, mode):
        """
        Mengirim data perhitungan ke API
        """
        try:
            result = json.dumps(counts)
            url = f"{self.base_url}/api/save"
            params = {
                "camera_name": camera_name,
                "mode": mode,
                "result": result
            }
            response = requests.get(url, params=params)
            return response.status_code == 200
        except Exception as e:
            print(f"Error saving counts: {e}")
            return False