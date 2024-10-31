import cv2
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import threading
import time
from datetime import datetime
import os
from ultralytics import YOLO
import numpy as np
from queue import Queue
import concurrent.futures

class FireSmokeDetectionApp:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Fire and Smoke Detection System")
        
        # Initialize variables
        self.frame_queue = Queue(maxsize=2)
        self.current_frame = None
        self.last_screenshot = None
        self.processed_screenshot = None
        self.is_running = False
        self.stop_thread = False
        
        try:
            # URL stream
            self.stream_url = "api4.mp4"
            
            # Initialize video capture
            self.cap = cv2.VideoCapture(self.stream_url)
            if not self.cap.isOpened():
                raise ValueError("Tidak bisa membuka stream!")
            
            # Create screenshots directory
            self.screenshot_dir = "screenshots"
            os.makedirs(self.screenshot_dir, exist_ok=True)
            
            # Initialize YOLO model
            self.model = YOLO('api3.pt')  # Pastikan model sudah ditraining untuk api dan asap
            
            # Setup GUI
            self.setup_gui()
            
            # Start threads
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
            self.executor.submit(self.video_stream_thread)
            self.executor.submit(self.screenshot_thread)
            
            # Start display update
            self.update_display()
            
            # Set closing protocol
            self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            # Start mainloop
            self.window.mainloop()
            
        except Exception as e:
            print(f"Error during initialization: {e}")
            self.show_error_message(f"Error: {str(e)}")

    def setup_gui(self):
        # Main frame
        main_frame = ttk.Frame(self.window)
        main_frame.pack(padx=10, pady=10)
        
        # Video frame
        video_frame = ttk.Frame(main_frame)
        video_frame.pack()
        
        # Canvases
        self.original_canvas = tk.Canvas(video_frame, width=400, height=300)
        self.original_canvas.pack(side=tk.LEFT, padx=5)
        
        self.processed_canvas = tk.Canvas(video_frame, width=400, height=300)
        self.processed_canvas.pack(side=tk.LEFT, padx=5)
        
        # Control frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(pady=10)
        
        # Interval control
        ttk.Label(control_frame, text="Interval (detik):").pack(side=tk.LEFT, padx=5)
        self.interval_var = tk.StringVar(value="5")
        interval_entry = ttk.Entry(control_frame, textvariable=self.interval_var, width=5)
        interval_entry.pack(side=tk.LEFT, padx=5)
        
        # Confidence threshold untuk api
        ttk.Label(control_frame, text="Fire Confidence:").pack(side=tk.LEFT, padx=5)
        self.fire_conf_threshold = tk.DoubleVar(value=0.5)
        fire_conf_scale = ttk.Scale(control_frame, from_=0.1, to=1.0, 
                                  variable=self.fire_conf_threshold, orient="horizontal")
        fire_conf_scale.pack(side=tk.LEFT, padx=5)

        # Confidence threshold untuk asap
        ttk.Label(control_frame, text="Smoke Confidence:").pack(side=tk.LEFT, padx=5)
        self.smoke_conf_threshold = tk.DoubleVar(value=0.5)
        smoke_conf_scale = ttk.Scale(control_frame, from_=0.1, to=1.0, 
                                   variable=self.smoke_conf_threshold, orient="horizontal")
        smoke_conf_scale.pack(side=tk.LEFT, padx=5)
        
        # Start/Stop button
        self.start_button = ttk.Button(control_frame, text="Start Detection", 
                                     command=self.toggle_detection)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        # Status frame for multiple status indicators
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(pady=5)
        
        # Fire status
        self.fire_status_var = tk.StringVar(value="Fire Status: Not Detected")
        ttk.Label(status_frame, textvariable=self.fire_status_var,
                 font=("", 12, "bold"), foreground="red").pack()
        
        # Smoke status
        self.smoke_status_var = tk.StringVar(value="Smoke Status: Not Detected")
        ttk.Label(status_frame, textvariable=self.smoke_status_var,
                 font=("", 12, "bold"), foreground="gray").pack()

        # Last capture time label
        self.last_capture_var = tk.StringVar(value="Last Capture: -")
        ttk.Label(main_frame, textvariable=self.last_capture_var).pack(pady=5)

        # Detection log
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(pady=5, fill=tk.X)
        
        # Treeview for detection log
        self.log_tree = ttk.Treeview(log_frame, columns=('Time', 'Event', 'Confidence'),
                                    show='headings', height=5)
        self.log_tree.heading('Time', text='Time')
        self.log_tree.heading('Event', text='Event')
        self.log_tree.heading('Confidence', text='Confidence')
        
        # Configure column widths
        self.log_tree.column('Time', width=150)
        self.log_tree.column('Event', width=150)
        self.log_tree.column('Confidence', width=100)
        
        self.log_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Scrollbar for log
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, 
                                 command=self.log_tree.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_tree.configure(yscrollcommand=log_scroll.set)

    def video_stream_thread(self):
        """Thread khusus untuk membaca video stream"""
        while not self.stop_thread:
            try:
                ret, frame = self.cap.read()
                if ret:
                    frame = cv2.resize(frame, (400, 300))
                    
                    # Update current frame dengan thread-safe
                    if not self.frame_queue.full():
                        self.frame_queue.put(frame.copy())
                    
                    self.current_frame = frame
                else:
                    # Reconnect jika stream terputus
                    self.cap.release()
                    time.sleep(1)
                    self.cap = cv2.VideoCapture(self.stream_url)
                
                time.sleep(0.01)
                
            except Exception as e:
                print(f"Error in video stream: {e}")
                time.sleep(1)

    def process_screenshot(self, frame):
        """Proses screenshot untuk deteksi api dan asap"""
        try:
            processed_frame = frame.copy()
            results = self.model(processed_frame)
            
            fire_detected = False
            smoke_detected = False
            fire_conf = 0
            smoke_conf = 0
            
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    
                    # Get coordinates
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    
                    # Fire detection
                    if cls == 0 and conf > self.fire_conf_threshold.get():  # Assuming class 0 is fire
                        fire_detected = True
                        fire_conf = max(fire_conf, conf)
                        # Draw red box for fire
                        cv2.rectangle(processed_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.putText(processed_frame, f"Fire: {conf:.2f}", 
                                  (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 
                                  0.5, (0, 0, 255), 2)
                    
                    # Smoke detection
                    elif cls == 1 and conf > self.smoke_conf_threshold.get():  # Assuming class 1 is smoke
                        smoke_detected = True
                        smoke_conf = max(smoke_conf, conf)
                        # Draw blue box for smoke
                        cv2.rectangle(processed_frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                        cv2.putText(processed_frame, f"Smoke: {conf:.2f}", 
                                  (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 
                                  0.5, (255, 0, 0), 2)
            
            # Update status and apply overlays
            if fire_detected:
                processed_frame = self.create_overlay(processed_frame, (0, 0, 255))  # Red overlay
                self.window.after(0, lambda: self.fire_status_var.set("Fire Status: DETECTED!"))
                self.log_detection("Fire Detected", fire_conf)
            else:
                self.window.after(0, lambda: self.fire_status_var.set("Fire Status: Not Detected"))
            
            if smoke_detected:
                if not fire_detected:  # Only apply blue overlay if no fire overlay
                    processed_frame = self.create_overlay(processed_frame, (255, 0, 0))  # Blue overlay
                self.window.after(0, lambda: self.smoke_status_var.set("Smoke Status: DETECTED!"))
                self.log_detection("Smoke Detected", smoke_conf)
            else:
                self.window.after(0, lambda: self.smoke_status_var.set("Smoke Status: Not Detected"))
            
            self.processed_screenshot = processed_frame
            
        except Exception as e:
            print(f"Error processing screenshot: {e}")

    def create_overlay(self, frame, color):
        """Create a semi-transparent overlay with specified color"""
        overlay = frame.copy()
        color_mask = np.zeros_like(frame)
        color_mask[:,:] = color[::-1]  # Reverse color for BGR
        cv2.addWeighted(color_mask, 0.3, overlay, 0.7, 0, overlay)
        return overlay

    def log_detection(self, event_type, confidence):
        """Add detection event to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_tree.insert('', 0, values=(timestamp, event_type, f"{confidence:.2f}"))
        
        # Keep only last 100 entries
        if len(self.log_tree.get_children()) > 100:
            self.log_tree.delete(self.log_tree.get_children()[-1])

    def screenshot_thread(self):
        """Thread khusus untuk mengambil dan memproses screenshot"""
        last_capture = 0
        while not self.stop_thread:
            try:
                if self.is_running:
                    current_time = time.time()
                    interval = float(self.interval_var.get())
                    
                    if current_time - last_capture >= interval:
                        if not self.frame_queue.empty():
                            frame = self.frame_queue.get()
                            
                            # Save screenshot
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"screenshot_{timestamp}.jpg"
                            cv2.imwrite(os.path.join(self.screenshot_dir, filename), frame)
                            
                            self.last_screenshot = frame
                            self.process_screenshot(frame)
                            
                            last_capture = current_time
                            self.last_capture_var.set(f"Last Capture: {timestamp}")
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error in screenshot thread: {e}")
                time.sleep(1)

    def update_display(self):
        """Update GUI display"""
        try:
            # Update original stream
            if self.current_frame is not None:
                frame = self.current_frame
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb_frame)
                img_tk = ImageTk.PhotoImage(image=img)
                self.original_canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
                self.original_canvas.img_tk = img_tk
            
            # Update processed screenshot
            if self.processed_screenshot is not None:
                rgb_processed = cv2.cvtColor(self.processed_screenshot, cv2.COLOR_BGR2RGB)
                processed_img = Image.fromarray(rgb_processed)
                processed_img_tk = ImageTk.PhotoImage(image=processed_img)
                self.processed_canvas.create_image(0, 0, anchor=tk.NW, 
                                                image=processed_img_tk)
                self.processed_canvas.processed_img_tk = processed_img_tk
            
            self.window.after(10, self.update_display)
            
        except Exception as e:
            print(f"Error in display update: {e}")

    def toggle_detection(self):
        self.is_running = not self.is_running
        if self.is_running:
            self.start_button.config(text="Stop Detection")
        else:
            self.start_button.config(text="Start Detection")

    def show_error_message(self, message):
        error_window = tk.Toplevel(self.window)
        error_window.title("Error")
        ttk.Label(error_window, text=message).pack(padx=20, pady=20)
        ttk.Button(error_window, text="OK", command=error_window.destroy).pack(pady=10)

    def on_closing(self):
        self.stop_thread = True
        self.executor.shutdown(wait=False)
        self.cap.release()
        self.window.destroy()

if __name__ == "__main__":
    FireSmokeDetectionApp()