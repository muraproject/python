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
        self.video_source = 'JADI.mp4'
        self.vid = cv2.VideoCapture(self.video_source)
        
        # Get video dimensions
        self.vid_width = int(self.vid.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.vid_height = int(self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Calculate display dimensions to fit screen
        screen_width = self.window.winfo_screenwidth() - 100  # Leave some margin
        screen_height = self.window.winfo_screenheight() - 200  # Leave space for controls
        
        # Calculate scaling factor to fit two videos side by side
        width_scale = screen_width / (2 * self.vid_width)
        height_scale = screen_height / self.vid_height
        self.scale = min(width_scale, height_scale)
        
        # Set display dimensions
        self.display_width = int(self.vid_width * self.scale)
        self.display_height = int(self.vid_height * self.scale)
        
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
        
        # Center window on screen
        self.center_window()
        
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def center_window(self):
        # Update window size based on content
        self.window.update()
        
        # Get window size
        window_width = self.window.winfo_width()
        window_height = self.window.winfo_height()
        
        # Calculate position
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Set window position
        self.window.geometry(f'+{x}+{y}')
        
    def create_widgets(self):
        # Main container
        main_container = ttk.Frame(self.window, padding="10")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Video frames container
        video_container = ttk.Frame(main_container)
        video_container.grid(row=0, column=0, columnspan=2, pady=10)
        
        # Original video canvas
        self.canvas1 = tk.Canvas(video_container, 
                               width=self.display_width, 
                               height=self.display_height)
        self.canvas1.grid(row=0, column=0, padx=5)
        ttk.Label(video_container, text="Live Feed").grid(row=1, column=0)
        
        # Detection video canvas
        self.canvas2 = tk.Canvas(video_container, 
                               width=self.display_width, 
                               height=self.display_height)
        self.canvas2.grid(row=0, column=1, padx=5)
        ttk.Label(video_container, text="Detection Feed").grid(row=1, column=1)
        
        # Controls frame
        controls_frame = ttk.LabelFrame(main_container, text="Controls", padding="10")
        controls_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
        
        # Interval control with value display
        interval_frame = ttk.Frame(controls_frame)
        interval_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        ttk.Label(interval_frame, text="Detection Interval:").grid(row=0, column=0, sticky=tk.W)
        self.interval_label = ttk.Label(interval_frame, text="2.0s")
        self.interval_label.grid(row=0, column=2, padx=5)
        
        interval_scale = ttk.Scale(interval_frame, from_=0.5, to=10.0, 
                                 variable=self.interval, 
                                 orient=tk.HORIZONTAL,
                                 command=lambda v: self.interval_label.configure(
                                     text=f"{float(v):.1f}s"))
        interval_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # Confidence controls with value display
        fire_frame = ttk.Frame(controls_frame)
        fire_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(fire_frame, text="Fire Confidence:").grid(row=0, column=0, sticky=tk.W)
        self.fire_conf_label = ttk.Label(fire_frame, text="50%")
        self.fire_conf_label.grid(row=0, column=2, padx=5)
        
        fire_conf_scale = ttk.Scale(fire_frame, from_=0.0, to=1.0, 
                                  variable=self.fire_confidence,
                                  orient=tk.HORIZONTAL,
                                  command=lambda v: self.fire_conf_label.configure(
                                      text=f"{int(float(v)*100)}%"))
        fire_conf_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        smoke_frame = ttk.Frame(controls_frame)
        smoke_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        ttk.Label(smoke_frame, text="Smoke Confidence:").grid(row=0, column=0, sticky=tk.W)
        self.smoke_conf_label = ttk.Label(smoke_frame, text="50%")
        self.smoke_conf_label.grid(row=0, column=2, padx=5)
        
        smoke_conf_scale = ttk.Scale(smoke_frame, from_=0.0, to=1.0, 
                                   variable=self.smoke_confidence,
                                   orient=tk.HORIZONTAL,
                                   command=lambda v: self.smoke_conf_label.configure(
                                       text=f"{int(float(v)*100)}%"))
        smoke_conf_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
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
            
            # Resize frame
            frame = cv2.resize(frame, (self.display_width, self.display_height))
            
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
                                  cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 2)
                    
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
            
            # Always update detection canvas with current frame when not detecting
            else:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.photo2 = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame_rgb))
                self.canvas2.create_image(0, 0, image=self.photo2, anchor=tk.NW)
            
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