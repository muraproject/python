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

class VideoOCRApp:
    def __init__(self, window, video_source=0):
        self.window = window
        self.window.title("Video OCR")
        
        # Settings file path
        self.settings_file = 'people_settings.json'
        
        # Threading setup
        self.frame_queue = Queue(maxsize=30)  # Buffer untuk frame video
        self.result_queue = Queue()  # Buffer untuk hasil OCR
        self.processing = True
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Get video properties
        self.vid = cv2.VideoCapture(video_source)
        self.width = int(self.vid.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Initialize EasyOCR
        self.reader = easyocr.Reader(['en'])
        
        self.log_file = 'ocr_log.txt'
        self.video_source = video_source
        
        if not self.vid.isOpened():
            raise ValueError("Could not open video source")
            
        self.roi = None
        self.dragging = False
        self.interval = 5
        self.last_capture = 0
        self.current_frame = None
        
        self.create_widgets()
        self.load_settings()
        
        # Start threads
        self.start_threads()
        self.update()
        
    def start_threads(self):
        # Thread untuk membaca video
        self.video_thread = threading.Thread(target=self.video_stream_thread, daemon=True)
        self.video_thread.start()
        
        # Thread untuk processing OCR
        self.ocr_thread = threading.Thread(target=self.ocr_processing_thread, daemon=True)
        self.ocr_thread.start()
        
        # Thread untuk update UI dengan hasil OCR
        self.ui_thread = threading.Thread(target=self.update_ui_thread, daemon=True)
        self.ui_thread.start()
        
    def video_stream_thread(self):
        """Thread untuk membaca frame video"""
        while self.processing:
            ret, frame = self.vid.read()
            if ret:
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                    except:
                        pass
                self.frame_queue.put(frame)
            else:
                self.vid.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Loop video
            time.sleep(0.01)  # Prevent thread from consuming too much CPU
            
    def ocr_processing_thread(self):
        """Thread untuk memproses OCR"""
        while self.processing:
            if self.roi and self.current_frame is not None:
                current_time = time.time()
                if current_time - self.last_capture >= float(self.interval_var.get()):
                    try:
                        x, y, w, h = self.roi
                        if w <= 0 or h <= 0:
                            continue
                            
                        roi_frame = self.current_frame[int(y):int(y+h), int(x):int(x+w)]
                        if roi_frame.size == 0:
                            continue

                        # Preprocessing
                        gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
                        scaled = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                        
                        # EasyOCR detection
                        results = self.reader.readtext(scaled)
                        
                        if results:
                            text = ' '.join([result[1] for result in results])
                            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                            self.result_queue.put((text, timestamp, scaled))
                            
                        self.last_capture = current_time
                        
                    except Exception as e:
                        print(f"Error in OCR processing: {str(e)}")
                        
            time.sleep(0.1)  # Prevent thread from consuming too much CPU
            
    def update_ui_thread(self):
        """Thread untuk update UI dengan hasil OCR"""
        while self.processing:
            try:
                if not self.result_queue.empty():
                    text, timestamp, scaled_image = self.result_queue.get_nowait()
                    
                    # Update log
                    log_entry = f"[{timestamp}] {text}"
                    self.window.after(0, self.update_log, log_entry)
                    
                    # Update preview
                    preview = PIL.Image.fromarray(scaled_image)
                    preview = preview.resize((320, 240), PIL.Image.LANCZOS)
                    photo = PIL.ImageTk.PhotoImage(image=preview)
                    self.window.after(0, self.update_preview, photo)
                    
            except Exception as e:
                print(f"Error in UI update: {str(e)}")
                
            time.sleep(0.1)  # Prevent thread from consuming too much CPU
            
    def update_log(self, log_entry):
        """Update log text dalam UI thread"""
        self.result_text.insert(tk.END, log_entry + '\n')
        self.result_text.see(tk.END)
        self.save_log(log_entry)
        
    def update_preview(self, photo):
        """Update preview image dalam UI thread"""
        self.roi_photo = photo  # Keep reference
        self.roi_canvas.create_image(0, 0, image=self.roi_photo, anchor=tk.NW)
        
    def create_widgets(self):
        container = ttk.PanedWindow(self.window, orient=tk.HORIZONTAL)
        container.pack(fill=tk.BOTH, expand=True)
        
        # Left panel
        left_frame = ttk.Frame(container)
        container.add(left_frame)
        
        # Create canvas with video dimensions
        self.canvas = tk.Canvas(left_frame, width=self.width, height=self.height)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        controls_frame = ttk.Frame(left_frame)
        controls_frame.pack(fill=tk.X)
        
        ttk.Label(controls_frame, text="Interval (sec):").pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value="5")
        ttk.Entry(controls_frame, textvariable=self.interval_var, width=5).pack(side=tk.LEFT)
        
        ttk.Button(controls_frame, text="Save Settings", command=self.save_settings).pack(side=tk.LEFT, padx=5)
        
        # Right panel
        right_frame = ttk.Frame(container)
        container.add(right_frame)
        
        self.roi_canvas = tk.Canvas(right_frame, width=320, height=240)
        self.roi_canvas.pack()
        
        self.result_text = scrolledtext.ScrolledText(right_frame, height=10, width=40)
        self.result_text.pack(fill=tk.BOTH, expand=True)
        
        ttk.Button(right_frame, text="Clear Log", command=self.clear_log).pack()
        
        self.canvas.bind("<Button-1>", self.start_roi)
        self.canvas.bind("<B1-Motion>", self.drag_roi)
        self.canvas.bind("<ButtonRelease-1>", self.stop_roi)
        
        self.load_log()
        
    def save_settings(self):
        if self.roi:
            settings = {
                'roi': {
                    'x': int(self.roi[0]),
                    'y': int(self.roi[1]),
                    'w': int(self.roi[2]),
                    'h': int(self.roi[3])
                },
                'interval': float(self.interval_var.get())
            }
            try:
                with open(self.settings_file, 'w') as f:
                    json.dump(settings, f, indent=4)
                print("Settings saved successfully")
            except Exception as e:
                print(f"Error saving settings: {str(e)}")
                
    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    if 'roi' in settings:
                        roi_data = settings['roi']
                        self.roi = (
                            roi_data['x'],
                            roi_data['y'],
                            roi_data['w'],
                            roi_data['h']
                        )
                    if 'interval' in settings:
                        self.interval_var.set(str(settings['interval']))
                print("Settings loaded successfully")
        except Exception as e:
            print(f"Error loading settings: {str(e)}")

    def clear_log(self):
        self.result_text.delete(1.0, tk.END)
        if os.path.exists(self.log_file):
            os.remove(self.log_file)
            
    def load_log(self):
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r', encoding='utf-8') as f:
                self.result_text.insert(tk.END, f.read())
                
    def save_log(self, text):
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(text + '\n')
        
    def start_roi(self, event):
        self.roi = (event.x, event.y, 0, 0)
        self.dragging = True
        
    def drag_roi(self, event):
        if self.dragging and self.roi:
            x, y, _, _ = self.roi
            self.roi = (x, y, event.x - x, event.y - y)
            
    def stop_roi(self, event):
        self.dragging = False
        if self.roi:
            x, y, w, h = self.roi
            if w < 0: x, w = x + w, -w
            if h < 0: y, h = y + h, -h
            self.roi = (x, y, w, h)
            self.save_settings()
        
    def update(self):
        """Update main UI"""
        try:
            if not self.frame_queue.empty():
                frame = self.frame_queue.get()
                self.current_frame = frame  # Save current frame for OCR processing
                
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.photo = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame_rgb))
                self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)
                
                if self.roi:
                    x, y, w, h = self.roi
                    self.canvas.create_rectangle(x, y, x+w, y+h, outline='green', width=2)
                
        except Exception as e:
            print(f"Error in update: {str(e)}")
            
        self.window.after(10, self.update)
        
    def __del__(self):
        self.processing = False
        if self.vid:
            self.vid.release()
        self.executor.shutdown(wait=False)

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoOCRApp(root, "jalan.mp4")
    root.mainloop()