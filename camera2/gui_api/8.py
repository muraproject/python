import tkinter as tk
from tkinter import ttk
import cv2
import PIL.Image, PIL.ImageTk
import time
from datetime import datetime
import numpy as np
from ultralytics import YOLO
import threading
from queue import Queue
import json
import os
import requests

# Part 1: API Handler and Data Management
class APIHandler:
    def __init__(self, base_url="http://192.168.0.4:5000"):
        self.base_url = base_url
        self.last_check = 0
        self.check_interval = 5  # 5 seconds between checks
        self.cameras = []
        self.current_mode = "Api dan Asap"

    def get_cameras(self):
        """Fetch camera information from the API"""
        current_time = time.time()
        if current_time - self.last_check >= self.check_interval:
            try:
                response = requests.get(
                    f"{self.base_url}/api/processor",
                    params={"mode": self.current_mode}
                )
                response.raise_for_status()
                data = response.json()
                self.cameras = data.get("cameras", [])
                self.last_check = current_time
                return True
            except Exception as e:
                print(f"API Error: {e}")
                return False
        return True

    def get_camera_source(self, index):
        """Get video source for selected camera"""
        if 0 <= index < len(self.cameras):
            return self.cameras[index]['ip']
        return None

    def get_camera_names(self):
        """Get formatted camera names for display"""
        return [f"Camera {cam['id']}: {cam['name']}" for cam in self.cameras]

# Part 2: Detection Engine
class DetectionEngine:
    def __init__(self, model_path='api3.pt'):
        self.model = YOLO(model_path)
        self.fire_detected = False
        self.smoke_detected = False
        
    def process_frame(self, frame, fire_conf_threshold, smoke_conf_threshold):
        """Process a single frame for detection"""
        results = self.model(frame)
        detections = {
            'fire': {'detected': False, 'confidence': 0.0, 'box': None},
            'smoke': {'detected': False, 'confidence': 0.0, 'box': None}
        }
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                class_name = self.model.names[cls]
                
                if class_name == 'Fire' and conf > fire_conf_threshold:
                    if conf > detections['fire']['confidence']:
                        detections['fire'] = {
                            'detected': True,
                            'confidence': conf,
                            'box': box.xyxy[0]
                        }
                        
                elif class_name == 'Smoke' and conf > smoke_conf_threshold:
                    if conf > detections['smoke']['confidence']:
                        detections['smoke'] = {
                            'detected': True,
                            'confidence': conf,
                            'box': box.xyxy[0]
                        }
        
        return detections

    def draw_detections(self, frame, detections):
        """Draw detection boxes and labels on frame"""
        if detections['fire']['detected']:
            box = detections['fire']['box']
            conf = detections['fire']['confidence']
            x1, y1, x2, y2 = map(int, box)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(frame, f"Fire: {conf:.2f}", (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
        if detections['smoke']['detected']:
            box = detections['smoke']['box']
            conf = detections['smoke']['confidence']
            x1, y1, x2, y2 = map(int, box)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (128, 128, 128), 2)
            cv2.putText(frame, f"Smoke: {conf:.2f}", (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 2)
            
        return frame

# Part 3: GUI and Main Application
class FireSmokeDetectionGUI:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        self.window.state('zoomed')
        
        # Initialize components
        self.api_handler = APIHandler()
        self.detection_engine = DetectionEngine()
        
        # Configuration
        self.config_file = 'detection_config.json'
        self.load_config()
        
        # Video handling
        self.vid = None
        self.selected_camera_index = 0
        self.current_video_source = None
        
        # Detection variables
        self.is_running = True  # Auto-start when camera is available
        self.interval = tk.DoubleVar(value=self.config['interval'])
        self.fire_confidence = tk.DoubleVar(value=self.config['fire_confidence'])
        self.smoke_confidence = tk.DoubleVar(value=self.config['smoke_confidence'])
        self.last_detection_time = time.time()
        
        # Create GUI
        self.create_main_frames()
        self.create_widgets()
        
        # Start main loops
        self.check_api()
        self.update()
        
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_config(self):
        """Load configuration from JSON file"""
        default_config = {
            'interval': 2.0,
            'fire_confidence': 0.5,
            'smoke_confidence': 0.5
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f"Error loading configuration: {e}")
                self.config = default_config
        else:
            self.config = default_config
            self.save_config()

    def save_config(self):
        """Save current configuration"""
        try:
            config_to_save = {
                'interval': self.interval.get(),
                'fire_confidence': self.fire_confidence.get(),
                'smoke_confidence': self.smoke_confidence.get()
            }
            with open(self.config_file, 'w') as f:
                json.dump(config_to_save, f, indent=4)
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def check_api(self):
        """Check API for camera updates"""
        if self.api_handler.get_cameras():
            camera_list = self.api_handler.get_camera_names()
            if camera_list:
                self.camera_selector['values'] = camera_list
                if not self.current_video_source:
                    self.on_camera_select(None)  # Auto-select first camera
        
        self.window.after(1000, self.check_api)

    def create_main_frames(self):
        """Create main layout frames"""
        self.left_frame = ttk.Frame(self.window)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        
        self.right_frame = ttk.Frame(self.window)
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        
        self.window.grid_columnconfigure(0, weight=3)
        self.window.grid_columnconfigure(1, weight=1)
        self.window.grid_rowconfigure(0, weight=1)

    def create_widgets(self):
        """Create all GUI widgets"""
        # Camera selector
        selector_frame = ttk.Frame(self.right_frame)
        selector_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        ttk.Label(selector_frame, text="Select Camera:").grid(row=0, column=0, sticky="w")
        self.camera_selector = ttk.Combobox(selector_frame, state="readonly")
        self.camera_selector.grid(row=0, column=1, sticky="ew", padx=5)
        self.camera_selector.bind('<<ComboboxSelected>>', self.on_camera_select)
        
        # Video displays
        video_container = ttk.Frame(self.left_frame, padding="10")
        video_container.grid(row=0, column=0, sticky="nsew")
        
        # Original video canvas
        self.canvas1 = tk.Canvas(video_container, width=800, height=600, bg='black')
        self.canvas1.grid(row=0, column=0, padx=5)
        ttk.Label(video_container, text="Live Feed", font=('Arial', 12, 'bold')).grid(row=1, column=0)
        
        # Detection video canvas
        self.canvas2 = tk.Canvas(video_container, width=800, height=600, bg='black')
        self.canvas2.grid(row=2, column=0, padx=5, pady=10)
        ttk.Label(video_container, text="Detection Feed", font=('Arial', 12, 'bold')).grid(row=3, column=0)
        
        # Status labels
        status_frame = ttk.LabelFrame(self.right_frame, text="Status", padding="10")
        status_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        self.fire_status = ttk.Label(status_frame, text="Fire: Not Detected", font=('Arial', 10, 'bold'))
        self.fire_status.grid(row=0, column=0, sticky="w")
        
        self.smoke_status = ttk.Label(status_frame, text="Smoke: Not Detected", font=('Arial', 10, 'bold'))
        self.smoke_status.grid(row=1, column=0, sticky="w")

    def on_camera_select(self, event):
        """Handle camera selection change"""
        if event is None:  # Auto-select first camera
            self.selected_camera_index = 0
            self.camera_selector.current(0)
        else:
            self.selected_camera_index = self.camera_selector.current()
        
        new_source = self.api_handler.get_camera_source(self.selected_camera_index)
        if new_source and new_source != self.current_video_source:
            self.load_video(new_source)

    def load_video(self, video_source):
        """Load new video source"""
        if self.vid is not None:
            self.vid.release()
        
        try:
            self.vid = cv2.VideoCapture(video_source)
            if not self.vid.isOpened():
                raise Exception("Could not open video file")
            
            self.current_video_source = video_source
            print(f"Loaded video: {video_source}")
            
        except Exception as e:
            print(f"Error loading video: {e}")
            self.current_video_source = None

    def update(self):
        """Update video frames and perform detection"""
        if self.vid and self.vid.isOpened():
            ret, frame = self.vid.read()
            
            if ret:
                if frame is None:
                    self.vid.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = self.vid.read()
                
                # Resize frame
                frame = cv2.resize(frame, (800, 600))
                
                # Update original video
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.photo1 = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame_rgb))
                self.canvas1.create_image(400, 300, image=self.photo1)
                
                # Perform detection if interval has passed
                current_time = time.time()
                if self.is_running and current_time - self.last_detection_time >= self.interval.get():
                    detections = self.detection_engine.process_frame(
                        frame,
                        self.fire_confidence.get(),
                        self.smoke_confidence.get()
                    )
                    
                    # Draw detections
                    detection_frame = frame.copy()
                    detection_frame = self.detection_engine.draw_detections(detection_frame, detections)
                    
                    # Update detection video
                    detection_rgb = cv2.cvtColor(detection_frame, cv2.COLOR_BGR2RGB)
                    self.photo2 = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(detection_rgb))
                    self.canvas2.create_image(400, 300, image=self.photo2)
                    
                    # Update status labels
                    if detections['fire']['detected']:
                        self.fire_status.configure(
                            text=f"Fire: Detected ({detections['fire']['confidence']:.2f})",
                            foreground='red')
                    else:
                        self.fire_status.configure(
                            text="Fire: Not Detected",
                            foreground='black')
                    
                    if detections['smoke']['detected']:
                        self.smoke_status.configure(
                            text=f"Smoke: Detected ({detections['smoke']['confidence']:.2f})",
                            foreground='red')
                    else:
                        self.smoke_status.configure(
                            text="Smoke: Not Detected",
                            foreground='black')
                    
                    self.last_detection_time = current_time
        
        self.window.after(10, self.update)

    def on_closing(self):
        """Clean up on window close"""
        self.save_config()
        self.is_running = False
        if self.vid and self.vid.isOpened():
            self.vid.release()
        self.window.destroy()

def main():
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('Accent.TButton', font=('Arial', 10, 'bold'))
    app = FireSmokeDetectionGUI(root, "Fire & Smoke Detection System")
    root.mainloop()

if __name__ == "__main__":
    main()