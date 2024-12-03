import tkinter as tk
from tkinter import ttk, scrolledtext
import cv2
import PIL.Image, PIL.ImageTk
import time
import os
import easyocr
import numpy as np

class VideoOCRApp:
    def __init__(self, window, video_source=0):
        self.window = window
        self.window.title("Video OCR")
        
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
        
        self.create_widgets()
        self.update()
        
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
    
    def process_roi(self, frame):
        if not self.roi:
            return
            
        try:
            x, y, w, h = self.roi
            if w <= 0 or h <= 0:
                return
                
            roi_frame = frame[int(y):int(y+h), int(x):int(x+w)]
            if roi_frame.size == 0:
                return

            current_time = time.time()
            if current_time - self.last_capture >= float(self.interval_var.get()):
                # Preprocessing
                gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
                scaled = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                
                # EasyOCR detection
                results = self.reader.readtext(scaled)
                
                if results:
                    text = ' '.join([result[1] for result in results])
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    log_entry = f"[{timestamp}] {text}"
                    self.result_text.insert(tk.END, log_entry + '\n')
                    self.result_text.see(tk.END)
                    self.save_log(log_entry)
                
                self.last_capture = current_time
                
                # Update preview
                preview = PIL.Image.fromarray(scaled)
                preview = preview.resize((320, 240), PIL.Image.LANCZOS)
                self.roi_photo = PIL.ImageTk.PhotoImage(image=preview)
                self.roi_canvas.create_image(0, 0, image=self.roi_photo, anchor=tk.NW)
                
        except Exception as e:
            print(f"Error in process_roi: {str(e)}")
            import traceback
            traceback.print_exc()
        
    def update(self):
        try:
            ret, frame = self.vid.read()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.photo = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(frame_rgb))
                self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)
                
                if self.roi:
                    x, y, w, h = self.roi
                    self.canvas.create_rectangle(x, y, x+w, y+h, outline='green', width=2)
                
                self.process_roi(frame)
                
        except Exception as e:
            print(f"Error in update: {str(e)}")
            import traceback
            traceback.print_exc()
            
        self.window.after(10, self.update)
        
    def __del__(self):
        if self.vid:
            self.vid.release()

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoOCRApp(root, "jalan.mp4")  # Ganti dengan path video Anda
    root.mainloop()