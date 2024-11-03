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

class FireDetectionGUI:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        
        # Initialize model
        self.model = YOLO('api3.pt')
        
        # Video source
        self.video_source = 'api3.mp4'
        self.vid = cv2.VideoCapture(self.video_source)
        
        # Variables for detection
        self.is_running = False
        self.interval = tk.DoubleVar(value=2.0)
        self.fire_confidence = tk.DoubleVar(value=0.5)
        self.smoke_confidence = tk.DoubleVar(value=0.5)
        self.fire_detected = False
        self.smoke_detected = False
        self.last_detection_time = time.time()
        
        # Queue for thread-safe communication
        self.frame_queue = Queue(maxsize=1)
        self.detection_queue = Queue(maxsize=1)
        
        # Create GUI elements
        self.create_widgets()
        
        # Start video loop
        self.update()
        
        # Detection logs
        self.detection_logs = []
        
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def create_widgets(self):
        # Main container
        main_container = ttk.Frame(self.window, padding="10")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Video frames container
        video_container = ttk.Frame(main_container)
        video_container.grid(row=0, column=0, columnspan=2, pady=10)
        
        # Original video canvas
        self.canvas1 = tk.Canvas(video_container, width=640, height=360)
        self.canvas1.grid(row=0, column=0, padx=5)
        ttk.Label(video_container, text="Live Feed").grid(row=1, column=0)
        
        # Detection video canvas
        self.canvas2 = tk.Canvas(video_container, width=640, height=360)
        self.canvas2.grid(row=0, column=1, padx=5)
        ttk.Label(video_container, text="Detection Feed").grid(row=1, column=1)
        
        # Controls frame
        controls_frame = ttk.LabelFrame(main_container, text="Controls", padding="10")
        controls_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
        
        # Interval control
        ttk.Label(controls_frame, text="Detection Interval (seconds):").grid(row=0, column=0, sticky=tk.W)
        interval_scale = ttk.Scale(controls_frame, from_=0.5, to=10.0, 
                                 variable=self.interval, orient=tk.HORIZONTAL)
        interval_scale.grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        # Confidence controls
        ttk.Label(controls_frame, text="Fire Confidence:").grid(row=1, column=0, sticky=tk.W)
        fire_conf_scale = ttk.Scale(controls_frame, from_=0.0, to=1.0, 
                                  variable=self.fire_confidence, orient=tk.HORIZONTAL)
        fire_conf_scale.grid(row=1, column=1, sticky=(tk.W, tk.E))
        
        ttk.Label(controls_frame, text="Smoke Confidence:").grid(row=2, column=0, sticky=tk.W)
        smoke_conf_scale = ttk.Scale(controls_frame, from_=0.0, to=1.0, 
                                   variable=self.smoke_confidence, orient=tk.HORIZONTAL)
        smoke_conf_scale.grid(row=2, column=1, sticky=(tk.W, tk.E))
        
        # Start/Stop button
        self.start_stop_btn = ttk.Button(controls_frame, text="Start Detection", 
                                       command=self.toggle_detection)
        self.start_stop_btn.grid(row=3, column=0, columnspan=2, pady=10)
        
        # Status frame
        status_frame = ttk.LabelFrame(main_container, text="Status", padding="10")
        status_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=10, padx=10)
        
        self.fire_status = ttk.Label(status_frame, text="Fire: Not Detected")
        self.fire_status.grid(row=0, column=0, sticky=tk.W)
        
        self.smoke_status = ttk.Label(status_frame, text="Smoke: Not Detected")
        self.smoke_status.grid(row=1, column=0, sticky=tk.W)
        
        # Detection log frame
        log_frame = ttk.LabelFrame(main_container, text="Detection Log", padding="10")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create Treeview for logs
        self.log_tree = ttk.Treeview(log_frame, columns=('Time', 'Detection'), 
                                   show='headings', height=5)
        self.log_tree.heading('Time', text='Time')
        self.log_tree.heading('Detection', text='Detection')
        self.log_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Add scrollbar to log
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_tree.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_tree.configure(yscrollcommand=scrollbar.set)
        
    def toggle_detection(self):
        self.is_running = not self.is_running
        self.start_stop_btn.configure(text="Stop Detection" if self.is_running else "Start Detection")
        
    def update(self):
        # Get a frame from the video source
        ret, frame = self.vid.read()
        
        if ret:
            # Reset video if it reaches the end
            if frame is None:
                self.vid.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.vid.read()
            
            # Convert frame to RGB for tkinter
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Update original video canvas
            self.photo1 = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame_rgb))
            self.canvas1.create_image(0, 0, image=self.photo1, anchor=tk.NW)
            
            # Process detection if running
            if self.is_running:
                current_time = time.time()
                if current_time - self.last_detection_time >= self.interval.get():
                    # Perform detection
                    results = self.model(frame)
                    
                    # Process detections
                    detection_frame = frame.copy()
                    self.fire_detected = False
                    self.smoke_detected = False
                    
                    for r in results:
                        boxes = r.boxes
                        for box in boxes:
                            cls = int(box.cls[0])
                            conf = float(box.conf[0])
                            class_name = self.model.names[cls]
                            
                            if conf > self.fire_confidence.get() and class_name == 'Fire':
                                self.fire_detected = True
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                cv2.rectangle(detection_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                                cv2.putText(detection_frame, f"Fire: {conf:.2f}", (x1, y1-10),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    
                    # Apply overlay based on detection
                    if self.fire_detected:
                        overlay = detection_frame.copy()
                        red_mask = np.zeros_like(detection_frame)
                        red_mask[:,:] = (0, 0, 255)
                        cv2.addWeighted(red_mask, 0.3, overlay, 0.7, 0, detection_frame)
                        cv2.putText(detection_frame, "FIRE DETECTED!",
                                  (detection_frame.shape[1] // 4, detection_frame.shape[0] // 2),
                                  cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)
                    
                    # Update detection canvas
                    detection_rgb = cv2.cvtColor(detection_frame, cv2.COLOR_BGR2RGB)
                    self.photo2 = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(detection_rgb))
                    self.canvas2.create_image(0, 0, image=self.photo2, anchor=tk.NW)
                    
                    # Update status labels
                    self.fire_status.configure(
                        text=f"Fire: {'Detected' if self.fire_detected else 'Not Detected'}")
                    
                    # Add to log if detection occurred
                    if self.fire_detected:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        detection_type = "Fire" if self.fire_detected else ""
                        self.log_tree.insert('', 0, values=(timestamp, detection_type))
                        
                        # Keep only last 10 logs
                        if len(self.log_tree.get_children()) > 10:
                            self.log_tree.delete(self.log_tree.get_children()[-1])
                    
                    self.last_detection_time = current_time
            
        # Schedule the next update
        self.window.after(10, self.update)
        
    def on_closing(self):
        self.is_running = False
        if self.vid.isOpened():
            self.vid.release()
        self.window.destroy()

def main():
    root = tk.Tk()
    app = FireDetectionGUI(root, "Fire Detection System")
    root.mainloop()

if __name__ == "__main__":
    main()