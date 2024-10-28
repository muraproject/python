# vehicle_counter_utils.py

import cv2
import numpy as np
import time
from ultralytics import YOLO
from collections import deque
import json
import csv
from datetime import datetime
import os

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

class SettingsManager:
    def __init__(self):
        self.settings_file = "settings_mobil.json"
        self.default_settings = {
            'interval': 300,  # 5 minutes in seconds
            'lines': {
                'up1': 0.15, 'up2': 0.25, 'up3': 0.35,
                'up4': 0.45, 'up5': 0.55, 'up6': 0.65,
                'down1': 0.20, 'down2': 0.30, 'down3': 0.40,
                'down4': 0.50, 'down5': 0.60, 'down6': 0.70
            },
            'video_source': 'https://cctvjss.jogjakota.go.id/kotabaru/ANPR-Jl-Ahmad-Jazuli.stream/playlist.m3u8'
        }
        self.settings = self.load_settings()

    def load_settings(self):
        try:
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
                # Update with any missing default settings
                for key, value in self.default_settings.items():
                    if key not in settings:
                        settings[key] = value
                return settings
        except FileNotFoundError:
            self.save_settings(self.default_settings)
            return self.default_settings

    def save_settings(self, settings):
        with open(self.settings_file, 'w') as f:
            json.dump(settings, f, indent=4)

class DataManager:
    def __init__(self):
        self.csv_file = "counter_mobil.csv"
        self.ensure_csv_exists()
        self.current_counts = self.initialize_counts()

    def ensure_csv_exists(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'car_up', 'car_down', 'bus_up', 'bus_down', 
                               'truck_up', 'truck_down', 'person_motor_up', 'person_motor_down'])

    def initialize_counts(self):
        return {
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

    def reset_counts(self):
        self.current_counts = self.initialize_counts()

    def update_count(self, object_type, direction, count=1):
        if object_type in self.current_counts and direction in self.current_counts[object_type]:
            self.current_counts[object_type][direction] += count

    def get_max_counts(self):
        counts = self.current_counts
        
        # Get maximum counts for each direction
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
        
        # Compare person and motorcycle counts and take the maximum
        person_up = max(counts['person']['up1'], counts['person']['up2'], counts['person']['up3'],
                       counts['person']['up4'], counts['person']['up5'], counts['person']['up6'])
        motor_up = max(counts['motorcycle']['up1'], counts['motorcycle']['up2'], counts['motorcycle']['up3'],
                      counts['motorcycle']['up4'], counts['motorcycle']['up5'], counts['motorcycle']['up6'])
        person_motor_up = max(person_up, motor_up)
        
        person_down = max(counts['person']['down1'], counts['person']['down2'], counts['person']['down3'],
                         counts['person']['down4'], counts['person']['down5'], counts['person']['down6'])
        motor_down = max(counts['motorcycle']['down1'], counts['motorcycle']['down2'], counts['motorcycle']['down3'],
                        counts['motorcycle']['down4'], counts['motorcycle']['down5'], counts['motorcycle']['down6'])
        person_motor_down = max(person_down, motor_down)
        
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

    def save_current_counts(self):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        max_counts = self.get_max_counts()
        
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                max_counts['car_up'],
                max_counts['car_down'],
                max_counts['bus_up'],
                max_counts['bus_down'],
                max_counts['truck_up'],
                max_counts['truck_down'],
                max_counts['person_motor_up'],
                max_counts['person_motor_down']
            ])
        
        # Reset counts after saving
        self.reset_counts()
        return max_counts

class VideoProcessor:
    def __init__(self, settings_manager, data_manager):
        self.settings_manager = settings_manager
        self.data_manager = data_manager
        self.model = YOLO('yolov8n.pt')
        self.gpu_processor = GPUProcessor()
        self.tracker = ObjectTracker()
        self.prev_centroids = {}
        self.tracking_id = 0
        self.crossed_ids = {
            'up1': set(), 'up2': set(), 'up3': set(), 'up4': set(), 'up5': set(), 'up6': set(),
            'down1': set(), 'down2': set(), 'down3': set(), 'down4': set(), 'down5': set(), 'down6': set()
        }

    def initialize_video_capture(self):
        video_source = self.settings_manager.settings['video_source']
        cap = cv2.VideoCapture(video_source, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 30)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        if video_source.startswith(('rtsp://', 'http://', 'https://')):
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        return cap

    def calculate_line_positions(self, frame_height):
        settings = self.settings_manager.settings['lines']
        return {
            'up_lines': [int(frame_height * settings[f'up{i}']) for i in range(1, 7)],
            'down_lines': [int(frame_height * settings[f'down{i}']) for i in range(1, 7)]
        }

    def process_frame(self, frame, line_positions):
        # This will be implemented in part 2
        pass