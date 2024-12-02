import tkinter as tk
from tkinter import ttk, scrolledtext
import cv2
import PIL.Image, PIL.ImageTk
import time
import os
import easyocr
import numpy as np
import json
import threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import requests
from datetime import datetime
import urllib.parse

class VideoProcessorApp:
    def __init__(self, window):
        self.window = window
        self.window.title("Video Processor")
        
        # API Configuration
        self.api_url = "http://103.139.192.236:5000/api/processor?mode=Counting%20Orang%20Lewat"
        self.save_api_url = "http://103.139.192.236:5000/api/save"
        self.api_check_interval = 5  # seconds
        
        # Camera Index
        self.camera_index = 0  # Ubah sesuai kebutuhan (0 = kamera pertama)
        
        # Debug flag
        self.debug = True
        
        # Camera states
        self.active_camera = None
        self.camera_state = "standby"
        self.vid = None
        self.current_camera_name = None
        self.current_camera_mode = None
        
        # Settings file path
        self.settings_file = 'processor_settings.json'
        
        # Threading setup
        self.frame_queue = Queue(maxsize=30)
        self.result_queue = Queue()
        self.processing = True
        self.processing_enabled = True
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Initialize EasyOCR
        self.reader = easyocr.Reader(['en'])
        
        self.log_file = 'processor_log.txt'
        self.roi = None
        self.dragging = False
        self.interval = 5
        self.last_capture = 0
        self.current_frame = None
        
        # Create UI
        self.create_widgets()
        self.load_settings()
        
        # Start threads
        self.start_threads()
        self.update()
        
        # Initial API check
        self.check_api()

    def check_api(self):
        """Check API for camera updates"""
        try:
            response = requests.get(self.api_url)
            
            if self.debug:
                self.log_message(f"API Response Status: {response.status_code}")
                self.log_message(f"API Content: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                cameras = data.get('cameras', [])
                
                if cameras and len(cameras) > self.camera_index:
                    target_camera = cameras[self.camera_index]
                    
                    if self.camera_state == "standby":
                        # Kamera dalam keadaan standby, aktifkan
                        self.switch_to_active(target_camera)
                    else:
                        # Kamera sudah aktif, cek apakah perlu update info
                        self.update_camera_info(target_camera)
                else:
                    if self.camera_state != "standby":
                        self.switch_to_standby()
                        
        except requests.exceptions.RequestException as e:
            self.log_message(f"API Connection Error: {str(e)}")
            if self.camera_state != "standby":
                self.switch_to_standby()
        except Exception as e:
            self.log_message(f"API Error: {str(e)}")
            if self.camera_state != "standby":
                self.switch_to_standby()
        finally:
            self.window.after(self.api_check_interval * 1000, self.check_api)
    
    def update_camera_info(self, camera_info):
        """Update camera information without restarting video"""
        try:
            # Cek apakah video source sama
            if self.active_camera == camera_info['ip']:
                # Update info jika ada perubahan
                if (self.current_camera_name != camera_info['name'] or 
                    self.current_camera_mode != camera_info['mode']):
                    
                    old_name = self.current_camera_name
                    old_mode = self.current_camera_mode
                    
                    # Update info
                    self.current_camera_name = camera_info['name']
                    self.current_camera_mode = camera_info['mode']
                    
                    # Update UI
                    self.camera_label.config(text=f"Camera: {camera_info['name']}")
                    
                    # Log perubahan
                    self.log_message(f"Camera info updated: {old_name} -> {camera_info['name']}")
                    self.log_message(f"Mode updated: {old_mode} -> {camera_info['mode']}")
            else:
                # Video source berbeda, perlu switch
                self.switch_to_active(camera_info)
                
        except Exception as e:
            self.log_message(f"Error updating camera info: {str(e)}")

    def create_widgets(self):
        """Create UI widgets"""
        # Main container
        container = ttk.PanedWindow(self.window, orient=tk.HORIZONTAL)
        container.pack(fill=tk.BOTH, expand=True)
        
        # Left panel
        left_frame = ttk.Frame(container)
        container.add(left_frame)
        
        # Video canvas with black background
        self.canvas = tk.Canvas(left_frame, width=800, height=600, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Status frame
        status_frame = ttk.Frame(left_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.status_label = ttk.Label(status_frame, text="Status: Standby")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        self.camera_label = ttk.Label(status_frame, text="Camera: None")
        self.camera_label.pack(side=tk.LEFT, padx=5)
        
        # Right panel
        right_frame = ttk.Frame(container)
        container.add(right_frame)
        
        # ROI Preview
        roi_frame = ttk.LabelFrame(right_frame, text="ROI Preview")
        roi_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.roi_canvas = tk.Canvas(roi_frame, width=320, height=240, bg='black')
        self.roi_canvas.pack(padx=5, pady=5)
        
        # Results log
        log_frame = ttk.LabelFrame(right_frame, text="Processing Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.result_text = scrolledtext.ScrolledText(log_frame, height=20)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ROI selection bindings
        self.canvas.bind("<Button-1>", self.start_roi)
        self.canvas.bind("<B1-Motion>", self.drag_roi)
        self.canvas.bind("<ButtonRelease-1>", self.stop_roi)
        
        self.load_log()

    def switch_to_active(self, camera_info):
        """Switch to active monitoring state"""
        try:
            self.log_message(f"Activating camera: {camera_info['name']} ({camera_info['ip']})")
            
            if self.vid:
                self.vid.release()
                self.vid = None
            
            # Save camera info for API save
            self.current_camera_name = camera_info['name']
            self.current_camera_mode = camera_info['mode']
            
            video_source = camera_info['ip']
            
            if self.debug:
                self.log_message(f"Opening video source: {video_source}")
            
            self.vid = cv2.VideoCapture(video_source)
            
            if not self.vid.isOpened():
                raise Exception(f"Could not open video source: {video_source}")
            
            self.width = int(self.vid.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            if self.debug:
                self.log_message(f"Video dimensions: {self.width}x{self.height}")
            
            if not self.roi:
                self.roi = (10, 10, self.width - 20, self.height - 20)
                self.save_settings()
            
            self.active_camera = camera_info['ip']
            self.camera_state = "active"
            
            self.canvas.config(width=self.width, height=self.height)
            self.status_label.config(text="Status: Active")
            self.camera_label.config(text=f"Camera: {camera_info['name']}")
            
            self.log_message("Camera activated successfully")
            
        except Exception as e:
            self.log_message(f"Error activating camera: {str(e)}")
            self.switch_to_standby()

    def switch_to_standby(self):
        """Switch to standby state"""
        try:
            self.log_message("Switching to standby mode")
            
            if self.vid:
                self.vid.release()
                self.vid = None
            
            self.active_camera = None
            self.camera_state = "standby"
            self.current_frame = None
            
            # Reset camera info
            self.current_camera_name = None
            self.current_camera_mode = None
            
            self.canvas.delete("all")
            self.canvas.create_text(
                self.canvas.winfo_width() // 2,
                self.canvas.winfo_height() // 2,
                text="Standby - Waiting for active camera",
                fill="white",
                font=("Arial", 20)
            )
            
            self.status_label.config(text="Status: Standby")
            self.camera_label.config(text="Camera: None")
            
        except Exception as e:
            self.log_message(f"Error switching to standby: {str(e)}")
    def start_threads(self):
        """Start all worker threads"""
        self.video_thread = threading.Thread(target=self.video_stream_thread, daemon=True)
        self.video_thread.start()
        
        self.ocr_thread = threading.Thread(target=self.ocr_processing_thread, daemon=True)
        self.ocr_thread.start()
        
        self.ui_thread = threading.Thread(target=self.update_ui_thread, daemon=True)
        self.ui_thread.start()

    def video_stream_thread(self):
        """Thread for video capture"""
        while self.processing:
            try:
                if self.camera_state == "active" and self.vid and self.vid.isOpened():
                    ret, frame = self.vid.read()
                    if ret:
                        if self.frame_queue.full():
                            try:
                                self.frame_queue.get_nowait()
                            except:
                                pass
                        self.frame_queue.put(frame)
                    else:
                        # Reset video to beginning
                        self.vid.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        if self.debug:
                            self.log_message("Video restarted")
            except Exception as e:
                self.log_message(f"Error in video stream: {str(e)}")
            time.sleep(0.01)

    def ocr_processing_thread(self):
        """Thread for OCR processing"""
        while self.processing:
            try:
                if (self.processing_enabled and self.roi and 
                    self.current_frame is not None and 
                    self.camera_state == "active"):
                    
                    current_time = time.time()
                    if current_time - self.last_capture >= self.interval:
                        x, y, w, h = self.roi
                        if w > 0 and h > 0:
                            roi_frame = self.current_frame[int(y):int(y+h), 
                                                        int(x):int(x+w)]
                            
                            # Process image
                            gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
                            scaled = cv2.resize(gray, None, fx=2, fy=2, 
                                             interpolation=cv2.INTER_CUBIC)
                            
                            # OCR detection
                            results = self.reader.readtext(scaled)
                            
                            if results:
                                # Combine OCR results
                                text = ' '.join([result[1] for result in results])
                                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                                
                                # Send to API save
                                try:
                                    params = {
                                        'camera_name': self.current_camera_name,
                                        'mode': self.current_camera_mode,
                                        'result': text
                                    }
                                    
                                    save_response = requests.get(self.save_api_url, params=params)
                                    
                                    if save_response.status_code == 200:
                                        self.result_queue.put((text, timestamp, scaled))
                                        if self.debug:
                                            self.log_message(f"Result saved to API: {text}")
                                    else:
                                        self.log_message(f"Failed to save to API: {save_response.status_code}")
                                        
                                except Exception as e:
                                    self.log_message(f"Error saving to API: {str(e)}")
                                
                            self.last_capture = current_time
                                
            except Exception as e:
                self.log_message(f"Error in OCR processing: {str(e)}")
            time.sleep(0.1)

    def update_ui_thread(self):
        """Thread for updating UI with OCR results"""
        while self.processing:
            try:
                if not self.result_queue.empty():
                    text, timestamp, scaled_image = self.result_queue.get_nowait()
                    
                    # Update log
                    log_entry = f"[{timestamp}] Text: {text}"
                    self.window.after(0, self.update_log, log_entry)
                    
                    # Update preview
                    preview = PIL.Image.fromarray(scaled_image)
                    preview = preview.resize((320, 240), PIL.Image.LANCZOS)
                    photo = PIL.ImageTk.PhotoImage(image=preview)
                    self.window.after(0, self.update_preview, photo)
                    
            except Exception as e:
                self.log_message(f"Error in UI update: {str(e)}")
            time.sleep(0.1)

    def update(self):
        """Update main video display"""
        try:
            if not self.frame_queue.empty():
                frame = self.frame_queue.get()
                self.current_frame = frame
                
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                photo = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame_rgb))
                
                self.canvas.delete("all")
                self.canvas.create_image(0, 0, image=photo, anchor=tk.NW)
                self.photo = photo
                
                if self.roi:
                    x, y, w, h = self.roi
                    self.canvas.create_rectangle(x, y, x+w, y+h, 
                                              outline='green', width=2)
                
        except Exception as e:
            self.log_message(f"Error updating display: {str(e)}")
            
        self.window.after(10, self.update)

    def update_preview(self, photo):
        """Update ROI preview"""
        self.roi_photo = photo
        self.roi_canvas.delete("all")
        self.roi_canvas.create_image(0, 0, image=self.roi_photo, anchor=tk.NW)

    def update_log(self, log_entry):
        """Update log in UI"""
        self.result_text.insert(tk.END, log_entry + '\n')
        self.result_text.see(tk.END)

    def log_message(self, message):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.window.after(0, self.update_log, log_entry)

    def start_roi(self, event):
        """Start ROI selection"""
        if self.camera_state == "active":
            self.roi = (event.x, event.y, 0, 0)
            self.dragging = True

    def load_log(self):
        """Load previous log entries if exist"""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content:
                        self.result_text.insert(tk.END, content)
                        self.result_text.see(tk.END)
        except Exception as e:
            self.log_message(f"Error loading log: {str(e)}")

    def drag_roi(self, event):
        """Update ROI during mouse drag"""
        if self.dragging and self.roi and self.camera_state == "active":
            x, y, _, _ = self.roi
            w = max(0, min(event.x - x, self.canvas.winfo_width() - x))
            h = max(0, min(event.y - y, self.canvas.winfo_height() - y))
            self.roi = (x, y, w, h)

    def stop_roi(self, event):
        """Finish ROI selection"""
        if self.camera_state == "active":
            self.dragging = False
            if self.roi:
                x, y, w, h = self.roi
                if w < 0:
                    x, w = x + w, -w
                if h < 0:
                    y, h = y + h, -h
                self.roi = (x, y, w, h)
                self.save_settings()
                if self.debug:
                    self.log_message(f"ROI updated: x={x}, y={y}, w={w}, h={h}")

    def save_settings(self):
        """Save settings to file"""
        try:
            settings = {
                'roi': self.roi,
                'interval': self.interval
            }
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            self.log_message(f"Error saving settings: {str(e)}")

    def load_settings(self):
        """Load settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    
                self.roi = settings.get('roi')
                self.interval = settings.get('interval', 5)
                
                if self.debug:
                    self.log_message("Settings loaded successfully")
                    
        except Exception as e:
            self.log_message(f"Error loading settings: {str(e)}")

    def on_closing(self):
        """Clean up resources when closing"""
        try:
            self.processing = False
            if self.vid:
                self.vid.release()
            self.executor.shutdown(wait=False)
            self.save_settings()
            self.window.destroy()
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        root.title("Video Processor")
        
        app = VideoProcessorApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        
        # Center window
        window_width = 1200
        window_height = 800
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        center_x = int((screen_width - window_width) / 2)
        center_y = int((screen_height - window_height) / 2)
        root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        
        root.mainloop()
    except Exception as e:
        print(f"Error starting application: {str(e)}")