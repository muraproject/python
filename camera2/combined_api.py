import cv2
import numpy as np
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import threading
import csv
import json
from datetime import datetime
from ultralytics import YOLO

class CombinedDetectionApp:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        
        # Initialize models
        print("Loading models...")
        self.people_model = YOLO('yolov8n.pt')
        self.fire_model = YOLO('api3.pt')
        print("Models loaded successfully")

        # Create window elements
        self.create_gui_elements()
        
        # Initialize video capture
        self.init_video()
        
        # Load settings
        self.load_settings()
        
        # Start update loop
        self.update()
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window.mainloop()

    def create_gui_elements(self):
        # Video displays frame
        video_frame = ttk.Frame(self.window)
        video_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5)
        
        # People detection canvas (left)
        self.people_canvas = tk.Canvas(video_frame, width=320, height=240)
        self.people_canvas.grid(row=0, column=0, padx=5)
        
        # Fire detection canvas (right)
        self.fire_canvas = tk.Canvas(video_frame, width=320, height=240)
        self.fire_canvas.grid(row=0, column=1, padx=5)
        
        # Controls frame
        control_frame = ttk.Frame(self.window)
        control_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5)
        
        # Interval setting
        ttk.Label(control_frame, text="Interval (detik):").grid(row=0, column=0, padx=5, pady=2)
        self.interval = tk.StringVar(value="5")
        ttk.Entry(control_frame, textvariable=self.interval, width=10).grid(row=0, column=1, padx=5, pady=2)

        # Confidence Thresholds
        ttk.Label(control_frame, text="People Confidence:").grid(row=1, column=0, padx=5, pady=2)
        self.people_conf = tk.DoubleVar(value=0.4)
        ttk.Scale(control_frame, from_=0.1, to=1.0, variable=self.people_conf, orient="horizontal").grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(control_frame, text="Fire Confidence:").grid(row=2, column=0, padx=5, pady=2)
        self.fire_conf = tk.DoubleVar(value=0.5)
        ttk.Scale(control_frame, from_=0.1, to=1.0, variable=self.fire_conf, orient="horizontal").grid(row=2, column=1, padx=5, pady=2)
        
        # Start/Stop button
        self.start_button = ttk.Button(control_frame, text="Start", command=self.toggle_detection)
        self.start_button.grid(row=3, column=0, columnspan=2, pady=5)
        
        # Status labels
        self.people_label = ttk.Label(control_frame, text="Jumlah Orang: 0", font=("", 12, "bold"))
        self.people_label.grid(row=4, column=0, columnspan=2, pady=2)
        
        self.fire_label = ttk.Label(control_frame, text="Status Api: Tidak terdeteksi", font=("", 12, "bold"))
        self.fire_label.grid(row=5, column=0, columnspan=2, pady=2)
        
        # Results list
        columns = ('Waktu', 'Jumlah Orang', 'Status Api')
        self.tree = ttk.Treeview(self.window, columns=columns, show='headings', height=10)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150)
        self.tree.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")

        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.window, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.grid(row=2, column=2, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

    def init_video(self):
        self.vid = cv2.VideoCapture("https://cctvjss.jogjakota.go.id/malioboro/NolKm_Utara.stream/playlist.m3u8")
        if not self.vid.isOpened():
            raise ValueError("Tidak dapat membuka video stream")
        
        self.is_running = False
        self.detection_active = False

    def toggle_detection(self):
        if not self.detection_active:
            self.detection_active = True
            self.start_button.configure(text="Stop")
            threading.Thread(target=self.detection_loop, daemon=True).start()
        else:
            self.detection_active = False
            self.start_button.configure(text="Start")

    def detection_loop(self):
        while self.detection_active:
            try:
                interval = int(self.interval.get())
                time.sleep(interval)
                
                if hasattr(self, 'current_frame'):
                    # Process frame for people detection
                    people_frame = self.current_frame.copy()
                    people_results = self.people_model(people_frame, conf=self.people_conf.get())
                    people_count = 0
                    
                    # Draw people detections
                    for r in people_results:
                        for box in r.boxes:
                            if self.people_model.names[int(box.cls[0])] == 'person':
                                people_count += 1
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                cv2.rectangle(people_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                cv2.putText(people_frame, 'Person', (x1, y1-10),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # Process frame for fire detection
                    fire_frame = self.current_frame.copy()
                    fire_results = self.fire_model(fire_frame, conf=self.fire_conf.get())
                    fire_detected = False
                    
                    # Draw fire detections
                    for r in fire_results:
                        for box in r.boxes:
                            if self.fire_model.names[int(box.cls[0])] == 'Fire':
                                fire_detected = True
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                cv2.rectangle(fire_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                                cv2.putText(fire_frame, 'Fire', (x1, y1-10),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    
                    if fire_detected:
                        fire_frame = self.create_red_overlay(fire_frame)
                        cv2.putText(fire_frame, "FIRE DETECTED!", 
                                  (fire_frame.shape[1] // 4, fire_frame.shape[0] // 2),
                                  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    
                    # Update displays
                    self.show_frame(people_frame, self.people_canvas)
                    self.show_frame(fire_frame, self.fire_canvas)
                    
                    # Update labels
                    self.people_label.configure(text=f"Jumlah Orang: {people_count}")
                    fire_status = "Api Terdeteksi!" if fire_detected else "Tidak terdeteksi"
                    self.fire_label.configure(text=f"Status Api: {fire_status}")
                    
                    # Save to CSV and update list
                    self.save_detection(people_count, fire_status)
                    
            except Exception as e:
                print(f"Error in detection loop: {e}")

    def create_red_overlay(self, frame):
        overlay = frame.copy()
        red_mask = np.zeros_like(frame)
        red_mask[:,:] = (0, 0, 255)  # BGR format - pure red
        cv2.addWeighted(red_mask, 0.3, overlay, 0.7, 0, overlay)
        return overlay

    def show_frame(self, frame, canvas):
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (320, 240))
        img = Image.fromarray(frame)
        photo = ImageTk.PhotoImage(image=img)
        canvas.create_image(0, 0, image=photo, anchor=tk.NW)
        canvas.photo = photo

    def update(self):
        ret, frame = self.vid.read()
        if ret:
            self.current_frame = frame
            self.show_frame(frame, self.people_canvas)
            self.show_frame(frame, self.fire_canvas)
        
        self.window.after(10, self.update)

    def save_detection(self, people_count, fire_status):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open('cctv.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([timestamp, people_count, fire_status])
        
        self.tree.insert('', 0, values=(timestamp, people_count, fire_status))
        
        if len(self.tree.get_children()) > 100:
            self.tree.delete(self.tree.get_children()[-1])

    def save_settings(self):
        settings = {
            'interval': self.interval.get(),
            'people_conf': self.people_conf.get(),
            'fire_conf': self.fire_conf.get()
        }
        with open('detection_settings.json', 'w') as file:
            json.dump(settings, file)

    def load_settings(self):
        try:
            with open('detection_settings.json', 'r') as file:
                settings = json.load(file)
                self.interval.set(settings.get('interval', 5))
                self.people_conf.set(settings.get('people_conf', 0.4))
                self.fire_conf.set(settings.get('fire_conf', 0.5))
        except FileNotFoundError:
            pass

    def on_closing(self):
        self.save_settings()
        if hasattr(self, 'vid'):
            self.vid.release()
        self.window.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = CombinedDetectionApp(root, "Sistem Monitoring CCTV")