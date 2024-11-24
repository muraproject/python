import tkinter as tk
from tkinter import ttk, messagebox
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

class APIHandler:
    def __init__(self, base_url="http://192.168.0.4:5000"):
        self.base_url = base_url
        self.last_check = 0
        self.check_interval = 2
        self.cameras = []
        self.current_mode = "Api dan Asap"
        self.last_camera_hash = None
        self.camera_index = 1  # Ubah angka ini untuk memilih kamera dari JSON (0,1,dst)
        print(f"APIHandler initialized with base URL: {base_url}")

    def get_cameras(self):
        """Fetch camera information from the API and check for changes"""
        current_time = time.time()
        if current_time - self.last_check >= self.check_interval:
            try:
                print("Fetching cameras from API...")
                response = requests.get(
                    f"{self.base_url}/api/processor",
                    params={"mode": self.current_mode}
                )
                response.raise_for_status()
                data = response.json()
                
                new_cameras = data.get("cameras", [])
                new_hash = hash(str(new_cameras))
                has_changed = new_hash != self.last_camera_hash
                
                self.cameras = new_cameras
                self.last_camera_hash = new_hash
                self.last_check = current_time
                
                if has_changed:
                    print("Camera data has changed")
                    
                return has_changed
                
            except Exception as e:
                print(f"API Error: {e}")
                self.cameras = []
                return True  # Return True to update UI with no camera status
        return False

    def get_current_camera(self):
        """Get the selected camera from the list"""
        if self.cameras and len(self.cameras) > self.camera_index:
            return self.cameras[self.camera_index]
        return None

    def send_detection_result(self, camera_name, mode, result):
        """Send detection results back to API"""
        try:
            print(f"Sending detection result: {result} for camera {camera_name}")
            response = requests.get(
                f"{self.base_url}/api/save",
                params={
                    "camera_name": camera_name,
                    "mode": mode,
                    "result": result
                }
            )
            response.raise_for_status()
            print(f"Detection result sent successfully for {camera_name}")
            return True
        except Exception as e:
            print(f"Error sending detection result: {e}")
            return False

class DetectionEngine:
    def __init__(self, model_path='api3.pt'):
        try:
            print(f"Loading YOLO model from {model_path}")
            self.model = YOLO(model_path)
            print("Model loaded successfully")
        except Exception as e:
            print(f"Error loading model: {e}")
            raise

    def process_frame(self, frame, fire_conf_threshold, smoke_conf_threshold):
        """Process a single frame for detection"""
        try:
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
        except Exception as e:
            print(f"Error processing frame: {e}")
            return None

    def draw_detections(self, frame, detections):
        """Draw detection boxes and labels on frame"""
        try:
            frame_with_detections = frame.copy()
            
            if detections['fire']['detected']:
                box = detections['fire']['box']
                conf = detections['fire']['confidence']
                x1, y1, x2, y2 = map(int, box)
                cv2.rectangle(frame_with_detections, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame_with_detections, f"Fire: {conf:.2f}", (x1, y1-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
            if detections['smoke']['detected']:
                box = detections['smoke']['box']
                conf = detections['smoke']['confidence']
                x1, y1, x2, y2 = map(int, box)
                cv2.rectangle(frame_with_detections, (x1, y1), (x2, y2), (128, 128, 128), 2)
                cv2.putText(frame_with_detections, f"Smoke: {conf:.2f}", (x1, y1-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 2)
                
            return frame_with_detections
        except Exception as e:
            print(f"Error drawing detections: {e}")
            return frame

    def get_detection_result(self, detections):
        """Convert detections to API result string"""
        if detections['fire']['detected'] and detections['smoke']['detected']:
            return "Api dan Asap"
        elif detections['fire']['detected']:
            return "Api"
        elif detections['smoke']['detected']:
            return "Asap"
        return "Aman"

class FireSmokeDetectionGUI:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        self.window.state('zoomed')
        
        try:
            self.api_handler = APIHandler()
            self.detection_engine = DetectionEngine()
            
            # Configuration
            self.config_file = 'detection_config.json'
            self.load_config()
            
            # Video handling
            self.vid = None
            self.current_video_source = None
            self.current_camera_info = None
            
            # Detection variables
            self.is_running = True
            self.interval = tk.DoubleVar(value=self.config['interval'])
            self.fire_confidence = tk.DoubleVar(value=self.config['fire_confidence'])
            self.smoke_confidence = tk.DoubleVar(value=self.config['smoke_confidence'])
            self.last_detection_time = time.time()
            self.last_api_send_time = 0
            self.api_send_interval = 2
            
            # Create GUI
            self.create_main_frames()
            self.create_widgets()
            
            # Start main loops
            self.check_api()
            self.update()
            
            self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
            
        except Exception as e:
            print(f"Error initializing application: {e}")
            messagebox.showerror("Initialization Error", str(e))
            self.window.destroy()

    def load_config(self):
        default_config = {
            'interval': 2.0,
            'fire_confidence': 0.5,
            'smoke_confidence': 0.5
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                print("Configuration loaded successfully")
            else:
                self.config = default_config
                self.save_config()
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = default_config

    def save_config(self):
        try:
            config_to_save = {
                'interval': self.interval.get(),
                'fire_confidence': self.fire_confidence.get(),
                'smoke_confidence': self.smoke_confidence.get()
            }
            with open(self.config_file, 'w') as f:
                json.dump(config_to_save, f, indent=4)
            print("Configuration saved successfully")
        except Exception as e:
            print(f"Error saving config: {e}")

    def create_main_frames(self):
        self.left_frame = ttk.Frame(self.window)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        
        self.right_frame = ttk.Frame(self.window)
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        
        self.window.grid_columnconfigure(0, weight=3)
        self.window.grid_columnconfigure(1, weight=1)
        self.window.grid_rowconfigure(0, weight=1)

    def create_widgets(self):
        # Video displays
        video_container = ttk.Frame(self.left_frame, padding="10")
        video_container.grid(row=0, column=0, sticky="nsew")
        
        self.canvas1 = tk.Canvas(video_container, width=800, height=600, bg='black')
        self.canvas1.grid(row=0, column=0, padx=5)
        ttk.Label(video_container, text="Live Feed", font=('Arial', 12, 'bold')).grid(row=1, column=0)
        
        self.canvas2 = tk.Canvas(video_container, width=800, height=600, bg='black')
        self.canvas2.grid(row=2, column=0, padx=5, pady=10)
        ttk.Label(video_container, text="Detection Feed", font=('Arial', 12, 'bold')).grid(row=3, column=0)
        
        # Status
        status_frame = ttk.LabelFrame(self.right_frame, text="Status", padding="10")
        status_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        self.camera_status = ttk.Label(status_frame, text="Camera: Waiting for connection...", 
                                     font=('Arial', 12, 'bold'))
        self.camera_status.grid(row=0, column=0, sticky="w", pady=5)
        
        self.fire_status = ttk.Label(status_frame, text="Fire: Not Detected", font=('Arial', 12, 'bold'))
        self.fire_status.grid(row=1, column=0, sticky="w", pady=5)
        
        self.smoke_status = ttk.Label(status_frame, text="Smoke: Not Detected", font=('Arial', 12, 'bold'))
        self.smoke_status.grid(row=2, column=0, sticky="w", pady=5)

    def check_api(self):
        try:
            if self.api_handler.get_cameras():
                camera = self.api_handler.get_current_camera()
                if camera:
                    new_source = camera['ip']
                    if new_source != self.current_video_source:
                        print(f"Camera source changed to: {new_source}")
                        self.current_camera_info = camera
                        self.load_video(new_source)
                        self.camera_status.configure(
                            text=f"Camera: {camera['name']} ({camera['mode']})",
                            foreground='green'
                        )
                else:
                    # No camera available at specified index
                    if self.vid:
                        self.vid.release()
                        self.vid = None
                    self.current_video_source = None
                    self.current_camera_info = None
                    self.camera_status.configure(
                        text=f"No Camera at Index {self.api_handler.camera_index}",
                        foreground='red'
                    )
                    # Clear detection status
                    self.fire_status.configure(text="Fire: Not Active", foreground='gray')
                    self.smoke_status.configure(text="Smoke: Not Active", foreground='gray')
                    # Clear canvases
                    self.canvas1.create_rectangle(0, 0, 800, 600, fill='black')
                    self.canvas2.create_rectangle(0, 0, 800, 600, fill='black')
        except Exception as e:
            print(f"Error checking API: {e}")
            self.camera_status.configure(
                text="Camera: Connection Error",
                foreground='red'
            )
            
        self.window.after(1000, self.check_api)

    def load_video(self, video_source):
        try:
            if self.vid is not None:
                self.vid.release()
            
            self.vid = cv2.VideoCapture(video_source)
            if not self.vid.isOpened():
                raise Exception("Could not open video source")
            
            self.current_video_source = video_source
            print(f"Successfully loaded video source: {video_source}")
            
        except Exception as e:
            print(f"Error loading video: {e}")
            self.current_video_source = None
            self.vid = None
            self.camera_status.configure(
                text=f"Camera Error: {str(e)}",
                foreground='red'
            )

    def update(self):
        try:
            if self.vid and self.vid.isOpened():
                ret, frame = self.vid.read()
                
                if ret:
                    if frame is None:
                        self.vid.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = self.vid.read()
                    
                    frame = cv2.resize(frame, (800, 600))
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.photo1 = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame_rgb))
                    self.canvas1.create_image(400, 300, image=self.photo1)
                    
                    current_time = time.time()
                    if self.is_running and current_time - self.last_detection_time >= self.interval.get():
                        detections = self.detection_engine.process_frame(
                            frame,
                            self.fire_confidence.get(),
                            self.smoke_confidence.get()
                        )
                        
                        if detections:
                            detection_frame = self.detection_engine.draw_detections(frame, detections)
                            detection_rgb = cv2.cvtColor(detection_frame, cv2.COLOR_BGR2RGB)
                            self.photo2 = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(detection_rgb))
                            self.canvas2.create_image(400, 300, image=self.photo2)
                            
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
                            
                            if current_time - self.last_api_send_time >= self.api_send_interval:
                                if self.current_camera_info:
                                    result = self.detection_engine.get_detection_result(detections)
                                    print(f"Detection result: {result}")
                                    self.api_handler.send_detection_result(
                                        camera_name=self.current_camera_info['name'],
                                        mode=self.current_camera_info['mode'],
                                        result=result
                                    )
                                    self.last_api_send_time = current_time
                            
                            self.last_detection_time = current_time
                else:
                    self.vid.set(cv2.CAP_PROP_POS_FRAMES, 0)
            else:
                # If no video is active, show black screens and inactive status
                self.canvas1.create_rectangle(0, 0, 800, 600, fill='black')
                self.canvas2.create_rectangle(0, 0, 800, 600, fill='black')
                
        except Exception as e:
            print(f"Error in update loop: {e}")
        
        self.window.after(10, self.update)

    def on_closing(self):
        """Clean up on window close"""
        try:
            self.save_config()
            self.is_running = False
            if self.vid and self.vid.isOpened():
                self.vid.release()
            print("Application shutting down...")
            self.window.destroy()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            self.window.destroy()

def main():
    try:
        root = tk.Tk()
        root.title("Fire & Smoke Detection System")
        
        style = ttk.Style()
        style.theme_use('clam')
        
        app = FireSmokeDetectionGUI(root, "Fire & Smoke Detection System")
        root.mainloop()
        
    except Exception as e:
        print(f"Critical error: {e}")
        messagebox.showerror("Critical Error", str(e))

if __name__ == "__main__":
    main()