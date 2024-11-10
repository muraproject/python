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
import pandas as pd
import json
import os

class FireSmokeDetectionGUI:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        
        # Maximize window instead of fullscreen
        self.window.state('zoomed')  # Untuk Windows
        # self.window.attributes('-zoomed', True)  # Uncomment ini untuk Linux
        
        # File paths
        self.config_file = 'detection_config.json'
        self.log_file = 'detection_log.csv'
        
        # Load configuration
        self.load_config()
        
        # Initialize model dengan file yang benar
        try:
            self.model = YOLO('api3.pt')
            print("Model loaded successfully")
        except Exception as e:
            print(f"Error loading model: {e}")
            self.window.destroy()
            return
        
        # Video source dengan file yang benar
        try:
            self.video_source = 'JADI.mp4'
            self.vid = cv2.VideoCapture(self.video_source)
            if not self.vid.isOpened():
                raise Exception("Could not open video file")
            print("Video loaded successfully")
        except Exception as e:
            print(f"Error loading video: {e}")
            self.window.destroy()
            return
            
        # Get video dimensions
        self.vid_width = int(self.vid.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.vid_height = int(self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Calculate display dimensions to fit screen
        self.screen_width = self.window.winfo_screenwidth()
        self.screen_height = self.window.winfo_screenheight()
        
        # Calculate dimensions for two-part layout with proper aspect ratio
        self.display_width = int(self.screen_width * 0.45)  # 45% of screen width for each video
        self.display_height = int(self.display_width * (self.vid_height / self.vid_width))
        
        # Adjust height if it's too tall
        if self.display_height > self.screen_height * 0.8:  # Limit to 80% of screen height
            self.display_height = int(self.screen_height * 0.8)
            self.display_width = int(self.display_height * (self.vid_width / self.vid_height))
        
        # Variables for detection
        self.is_running = False
        self.interval = tk.DoubleVar(value=self.config['interval'])
        self.fire_confidence = tk.DoubleVar(value=self.config['fire_confidence'])
        self.smoke_confidence = tk.DoubleVar(value=self.config['smoke_confidence'])
        self.fire_detected = False
        self.smoke_detected = False
        self.last_detection_time = time.time()
        
        # Rest of initialization
        self.create_main_frames()
        self.frame_queue = Queue(maxsize=1)
        self.detection_queue = Queue(maxsize=1)
        self.create_widgets()
        self.load_logs()
        self.update()
        
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update(self):
        """Update video frames and perform detection"""
        ret, frame = self.vid.read()
        
        if ret:
            if frame is None:
                self.vid.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.vid.read()
            
            # Resize dengan mempertahankan aspect ratio
            frame = cv2.resize(frame, (self.display_width, self.display_height))
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            self.photo1 = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame_rgb))
            self.canvas1.create_image(
                self.display_width//2,  # Center horizontally
                self.display_height//2,  # Center vertically
                image=self.photo1
            )
            
            if self.is_running:
                current_time = time.time()
                if current_time - self.last_detection_time >= self.interval.get():
                    # Collect 10 frames for batch processing
                    frames = []
                    frames_original = []
                    current_pos = self.vid.get(cv2.CAP_PROP_POS_FRAMES)
                    
                    for _ in range(10):
                        ret_batch, frame_batch = self.vid.read()
                        if ret_batch:
                            frame_resized = cv2.resize(frame_batch, (self.display_width, self.display_height))
                            frames.append(frame_resized)
                            frames_original.append(frame_batch)
                        else:
                            self.vid.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            ret_batch, frame_batch = self.vid.read()
                            if ret_batch:
                                frame_resized = cv2.resize(frame_batch, (self.display_width, self.display_height))
                                frames.append(frame_resized)
                                frames_original.append(frame_batch)
                    
                    # Set video position back
                    self.vid.set(cv2.CAP_PROP_POS_FRAMES, current_pos)
                    
                    # Process batch of frames
                    best_fire_conf = 0.0
                    best_smoke_conf = 0.0
                    best_fire_frame = None
                    best_smoke_frame = None
                    best_fire_box = None
                    best_smoke_box = None
                    
                    self.fire_detected = False
                    self.smoke_detected = False
                    
                    # Analyze each frame
                    for frame_detect in frames:
                        results = self.model(frame_detect)
                        
                        for r in results:
                            boxes = r.boxes
                            for box in boxes:
                                cls = int(box.cls[0])
                                conf = float(box.conf[0])
                                class_name = self.model.names[cls]
                                
                                # Check for fire
                                if conf > self.fire_confidence.get() and class_name == 'Fire':
                                    self.fire_detected = True
                                    if conf > best_fire_conf:
                                        best_fire_conf = conf
                                        best_fire_frame = frame_detect.copy()
                                        best_fire_box = box.xyxy[0]
                                
                                # Check for smoke
                                elif conf > self.smoke_confidence.get() and class_name == 'Smoke':
                                    self.smoke_detected = True
                                    if conf > best_smoke_conf:
                                        best_smoke_conf = conf
                                        best_smoke_frame = frame_detect.copy()
                                        best_smoke_box = box.xyxy[0]
                    
                    # Prepare final detection frame
                    if self.fire_detected or self.smoke_detected:
                        # Use frame with highest confidence detection
                        if best_fire_conf >= best_smoke_conf:
                            detection_frame = best_fire_frame.copy()
                        else:
                            detection_frame = best_smoke_frame.copy()
                    else:
                        # If no detection, use last frame
                        detection_frame = frames[-1].copy()
                    
                    # Draw detections on final frame
                    if self.fire_detected and best_fire_box is not None:
                        x1, y1, x2, y2 = map(int, best_fire_box)
                        cv2.rectangle(detection_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.putText(detection_frame, f"Fire: {best_fire_conf:.2f}", (x1, y1-10),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    
                    if self.smoke_detected and best_smoke_box is not None:
                        x1, y1, x2, y2 = map(int, best_smoke_box)
                        cv2.rectangle(detection_frame, (x1, y1), (x2, y2), (128, 128, 128), 2)
                        cv2.putText(detection_frame, f"Smoke: {best_smoke_conf:.2f}", (x1, y1-10),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 2)
                    
                    # Update detection canvas
                    detection_rgb = cv2.cvtColor(detection_frame, cv2.COLOR_BGR2RGB)
                    self.photo2 = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(detection_rgb))
                    self.canvas2.create_image(
                        self.display_width//2,
                        self.display_height//2,
                        image=self.photo2
                    )
                    
                    # Update status labels
                    if self.fire_detected:
                        self.fire_status.configure(
                            text=f"Fire: Detected ({best_fire_conf:.2f})",
                            foreground='red')
                    else:
                        self.fire_status.configure(
                            text="Fire: Not Detected",
                            foreground='black')
                    
                    if self.smoke_detected:
                        self.smoke_status.configure(
                            text=f"Smoke: Detected ({best_smoke_conf:.2f})",
                            foreground='red')
                    else:
                        self.smoke_status.configure(
                            text="Smoke: Not Detected",
                            foreground='black')
                    
                    # Log detections
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    if self.fire_detected:
                        self.log_tree.insert('', 0, values=(timestamp, 'Fire', f"{best_fire_conf:.2f}"))
                        self.save_log(timestamp, 'Fire', f"{best_fire_conf:.2f}")
                    
                    if self.smoke_detected:
                        self.log_tree.insert('', 0, values=(timestamp, 'Smoke', f"{best_smoke_conf:.2f}"))
                        self.save_log(timestamp, 'Smoke', f"{best_smoke_conf:.2f}")
                    
                    # Keep only last 100 logs in GUI
                    while len(self.log_tree.get_children()) > 100:
                        self.log_tree.delete(self.log_tree.get_children()[-1])
                    
                    self.last_detection_time = current_time
                
            else:
                # Show current frame in detection canvas when not detecting
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.photo2 = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame_rgb))
                self.canvas2.create_image(
                    self.display_width//2,
                    self.display_height//2,
                    image=self.photo2
                )
        
        # Schedule next update
        self.window.after(10, self.update)
    def create_main_frames(self):
        """Create main layout frames"""
        # Left side frame (Video feeds)
        self.left_frame = ttk.Frame(self.window)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        
        # Right side frame (Controls and logs)
        self.right_frame = ttk.Frame(self.window)
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        
        # Configure grid weights
        self.window.grid_columnconfigure(0, weight=3)  # Left side takes 3/4
        self.window.grid_columnconfigure(1, weight=1)  # Right side takes 1/4
        self.window.grid_rowconfigure(0, weight=1)
        
    def load_config(self):
        """Load configuration from JSON file or create default"""
        default_config = {
            'interval': 2.0,
            'fire_confidence': 0.5,
            'smoke_confidence': 0.5
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                print("Configuration loaded successfully")
            except Exception as e:
                print(f"Error loading configuration: {e}")
                self.config = default_config
        else:
            self.config = default_config
            self.save_config()
            
    def save_config(self):
        """Save current configuration to JSON file"""
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
            print(f"Error saving configuration: {e}")

    def create_widgets(self):
        # Video frames container in left frame
        video_container = ttk.Frame(self.left_frame, padding="10")
        video_container.grid(row=0, column=0, sticky="nsew")
        
        # Original video canvas
        self.canvas1 = tk.Canvas(video_container, 
                               width=self.display_width, 
                               height=self.display_height,
                               bg='black')
        self.canvas1.grid(row=0, column=0, padx=5)
        ttk.Label(video_container, text="Live Feed", font=('Arial', 12, 'bold')).grid(row=1, column=0)
        
        # Detection video canvas
        self.canvas2 = tk.Canvas(video_container, 
                               width=self.display_width, 
                               height=self.display_height,
                               bg='black')
        self.canvas2.grid(row=2, column=0, padx=5, pady=10)
        ttk.Label(video_container, text="Detection Feed", font=('Arial', 12, 'bold')).grid(row=3, column=0)
        
        # Right side controls and logs
        # Controls frame
        controls_frame = ttk.LabelFrame(self.right_frame, text="Controls", padding="10")
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        # Interval control
        interval_frame = ttk.Frame(controls_frame)
        interval_frame.grid(row=0, column=0, sticky="ew", pady=5)
        
        ttk.Label(interval_frame, text="Detection Interval:").grid(row=0, column=0, sticky="w")
        self.interval_label = ttk.Label(interval_frame, text=f"{self.interval.get():.1f}s")
        self.interval_label.grid(row=0, column=2, padx=5)
        
        interval_scale = ttk.Scale(interval_frame, from_=0.5, to=10.0, 
                                 variable=self.interval, 
                                 orient=tk.HORIZONTAL,
                                 command=self.update_interval)
        interval_scale.grid(row=1, column=0, columnspan=3, sticky="ew")
        
        # Confidence controls
        confidence_frame = ttk.Frame(controls_frame)
        confidence_frame.grid(row=1, column=0, sticky="ew", pady=10)
        
        # Fire confidence
        ttk.Label(confidence_frame, text="Fire Confidence:").grid(row=0, column=0, sticky="w")
        self.fire_conf_label = ttk.Label(confidence_frame, text=f"{int(self.fire_confidence.get()*100)}%")
        self.fire_conf_label.grid(row=0, column=2, padx=5)
        
        fire_conf_scale = ttk.Scale(confidence_frame, from_=0.0, to=1.0, 
                                  variable=self.fire_confidence,
                                  orient=tk.HORIZONTAL,
                                  command=self.update_fire_conf)
        fire_conf_scale.grid(row=1, column=0, columnspan=3, sticky="ew")
        
        # Smoke confidence
        ttk.Label(confidence_frame, text="Smoke Confidence:").grid(row=2, column=0, sticky="w", pady=(10,0))
        self.smoke_conf_label = ttk.Label(confidence_frame, text=f"{int(self.smoke_confidence.get()*100)}%")
        self.smoke_conf_label.grid(row=2, column=2, padx=5, pady=(10,0))
        
        smoke_conf_scale = ttk.Scale(confidence_frame, from_=0.0, to=1.0, 
                                   variable=self.smoke_confidence,
                                   orient=tk.HORIZONTAL,
                                   command=self.update_smoke_conf)
        smoke_conf_scale.grid(row=3, column=0, columnspan=3, sticky="ew")

        # Buttons frame
        buttons_frame = ttk.Frame(controls_frame)
        buttons_frame.grid(row=2, column=0, sticky="ew", pady=10)
        
        # Start/Stop button
        self.start_stop_btn = ttk.Button(buttons_frame, text="Start Detection", 
                                       command=self.toggle_detection,
                                       style='Accent.TButton')
        self.start_stop_btn.grid(row=0, column=0, padx=5)
        
        # Save config button
        save_config_btn = ttk.Button(buttons_frame, text="Save Configuration",
                                   command=self.save_config)
        save_config_btn.grid(row=0, column=1, padx=5)
        # Status frame
        status_frame = ttk.LabelFrame(self.right_frame, text="Status", padding="10")
        status_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        self.fire_status = ttk.Label(status_frame, text="Fire: Not Detected", 
                                   font=('Arial', 10, 'bold'))
        self.fire_status.grid(row=0, column=0, sticky="w")
        
        self.smoke_status = ttk.Label(status_frame, text="Smoke: Not Detected",
                                    font=('Arial', 10, 'bold'))
        self.smoke_status.grid(row=1, column=0, sticky="w")
        
        # Detection log frame
        log_frame = ttk.LabelFrame(self.right_frame, text="Detection Log", padding="10")
        log_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        
        # Create Treeview for logs
        self.log_tree = ttk.Treeview(log_frame, 
                                   columns=('Time', 'Detection', 'Confidence'), 
                                   show='headings',
                                   height=15)
        
        self.log_tree.heading('Time', text='Time')
        self.log_tree.heading('Detection', text='Detection')
        self.log_tree.heading('Confidence', text='Confidence')
        
        # Configure column widths
        self.log_tree.column('Time', width=150)
        self.log_tree.column('Detection', width=100)
        self.log_tree.column('Confidence', width=100)
        
        self.log_tree.grid(row=0, column=0, sticky="nsew")
        
        # Add scrollbar to log
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, 
                                command=self.log_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_tree.configure(yscrollcommand=scrollbar.set)
        
        # Configure weights for log frame
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)

    def update_interval(self, value):
        self.interval_label.configure(text=f"{float(value):.1f}s")
        self.save_config()
        
    def update_fire_conf(self, value):
        self.fire_conf_label.configure(text=f"{int(float(value)*100)}%")
        self.save_config()
        
    def update_smoke_conf(self, value):
        self.smoke_conf_label.configure(text=f"{int(float(value)*100)}%")
        self.save_config()

    def toggle_detection(self):
        self.is_running = not self.is_running
        self.start_stop_btn.configure(
            text="Stop Detection" if self.is_running else "Start Detection"
        )

    def load_logs(self):
        if os.path.exists(self.log_file):
            try:
                df = pd.read_csv(self.log_file)
                for _, row in df.iterrows():
                    self.log_tree.insert('', 0, values=(row['Time'], 
                                                      row['Detection'], 
                                                      row['Confidence']))
            except Exception as e:
                print(f"Error loading logs: {e}")

    def save_log(self, timestamp, detection_type, confidence):
        try:
            new_log = pd.DataFrame({
                'Time': [timestamp], 
                'Detection': [detection_type],
                'Confidence': [confidence]
            })
            
            if os.path.exists(self.log_file):
                existing_logs = pd.read_csv(self.log_file)
                updated_logs = pd.concat([existing_logs, new_log], ignore_index=True)
            else:
                updated_logs = new_log
            
            updated_logs.to_csv(self.log_file, index=False)
        except Exception as e:
            print(f"Error saving log: {e}")


    def on_closing(self):
        self.save_config()
        self.is_running = False
        if self.vid.isOpened():
            self.vid.release()
        self.window.destroy()

def main():
    root = tk.Tk()
    # Set theme untuk tampilan modern
    style = ttk.Style()
    style.theme_use('clam')  # atau 'alt', 'default', 'classic' sesuai preferensi
    
    # Konfigurasi style khusus
    style.configure('Accent.TButton', font=('Arial', 10, 'bold'))
    
    app = FireSmokeDetectionGUI(root, "Fire & Smoke Detection System")
    root.mainloop()

if __name__ == "__main__":
    main()