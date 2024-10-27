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

        # Video source
        self.stream_url = "https://cctvjss.jogjakota.go.id/malioboro/NolKm_Utara.stream/playlist.m3u8"
        self.vid = cv2.VideoCapture(self.stream_url)

        # YOLO initialization
        self.people_model = YOLO('yolov8s.pt')
        self.fire_model = YOLO('api3.pt')

        # Create canvases for live video and processed video
        self.live_canvas = tk.Canvas(window, width=320, height=240)
        self.live_canvas.grid(row=0, column=0, padx=5, pady=5)

        self.processed_canvas = tk.Canvas(window, width=320, height=240)
        self.processed_canvas.grid(row=0, column=1, padx=5, pady=5)

        # Control frame
        control_frame = ttk.Frame(window)
        control_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

        # Interval setting
        ttk.Label(control_frame, text="Interval (detik):").grid(row=0, column=0, padx=5, pady=2)
        self.interval_var = tk.StringVar(value="5")
        ttk.Entry(control_frame, textvariable=self.interval_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        # Confidence Thresholds
        ttk.Label(control_frame, text="People Confidence:").grid(row=1, column=0, padx=5, pady=2)
        self.people_conf_var = tk.DoubleVar(value=0.4)
        ttk.Scale(control_frame, from_=0.1, to=1.0, variable=self.people_conf_var, orient="horizontal").grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(control_frame, text="Fire Confidence:").grid(row=2, column=0, padx=5, pady=2)
        self.fire_conf_var = tk.DoubleVar(value=0.5)
        ttk.Scale(control_frame, from_=0.1, to=1.0, variable=self.fire_conf_var, orient="horizontal").grid(row=2, column=1, padx=5, pady=2)

        # Start button
        self.start_button = ttk.Button(control_frame, text="Mulai Deteksi", command=self.start_detection)
        self.start_button.grid(row=3, column=0, columnspan=2, pady=5)

        # Status displays
        self.people_var = tk.StringVar(value="Jumlah Orang: 0")
        ttk.Label(control_frame, textvariable=self.people_var, font=("", 12, "bold")).grid(row=4, column=0, columnspan=2, pady=5)

        self.fire_var = tk.StringVar(value="Status Api: Tidak Terdeteksi")
        ttk.Label(control_frame, textvariable=self.fire_var, font=("", 12, "bold")).grid(row=5, column=0, columnspan=2, pady=5)

        # Data list with scrollbar
        self.data_frame = ttk.Frame(window)
        self.data_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        self.data_list = ttk.Treeview(self.data_frame, 
                                     columns=('Tanggal', 'Waktu', 'Jumlah_Orang', 'Status_Api'), 
                                     show='headings', 
                                     height=10)
        self.data_list.heading('Tanggal', text='Tanggal')
        self.data_list.heading('Waktu', text='Waktu')
        self.data_list.heading('Jumlah_Orang', text='Jumlah Orang')
        self.data_list.heading('Status_Api', text='Status Api')
        self.data_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.data_frame, orient=tk.VERTICAL, command=self.data_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.data_list.configure(yscrollcommand=scrollbar.set)

        # Initialize variables
        self.is_detecting = False
        self.current_frame = None
        self.processed_frame = None

        # Load settings and CSV data
        self.load_settings()
        self.load_csv_data()

        self.update()
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_red_overlay(self, frame):
        overlay = frame.copy()
        red_mask = np.zeros_like(frame)
        red_mask[:,:] = (0, 0, 255)  # BGR format - pure red
        cv2.addWeighted(red_mask, 0.3, overlay, 0.7, 0, overlay)
        return overlay

    def update(self):
        ret, frame = self.vid.read()
        if ret:
            self.current_frame = cv2.resize(frame, (320, 240))
            self.photo = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)))
            self.live_canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

            if self.processed_frame is not None:
                self.processed_photo = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(self.processed_frame, cv2.COLOR_BGR2RGB)))
                self.processed_canvas.create_image(0, 0, image=self.processed_photo, anchor=tk.NW)

        self.window.after(15, self.update)

    def start_detection(self):
        if not self.is_detecting:
            self.is_detecting = True
            self.start_button.config(text="Hentikan")
            threading.Thread(target=self.detection_thread, daemon=True).start()
        else:
            self.is_detecting = False
            self.start_button.config(text="Mulai Deteksi")

    def detection_thread(self):
        while self.is_detecting:
            try:
                interval = int(self.interval_var.get())
                time.sleep(interval)
                
                if self.current_frame is not None:
                    # Process frame for both detections
                    frame_copy = self.current_frame.copy()
                    
                    # Detect people
                    people_count = self.count_people(frame_copy)
                    self.people_var.set(f"Jumlah Orang: {people_count}")
                    
                    # Detect fire
                    fire_detected, frame_with_fire = self.detect_fire(frame_copy)
                    fire_status = "Api Terdeteksi!" if fire_detected else "Tidak ada api"
                    self.fire_var.set(f"Status Api: {fire_status}")
                    
                    # Save results
                    self.save_to_csv(people_count, fire_status)
                    self.update_data_list(people_count, fire_status)
                    
                    # Update processed frame
                    self.processed_frame = frame_with_fire

            except ValueError as e:
                print(f"Error: {e}")
                self.is_detecting = False
                self.start_button.config(text="Mulai Deteksi")

    def count_people(self, frame):
        results = self.people_model(frame, conf=self.people_conf_var.get())
        count = 0
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                class_name = self.people_model.names[cls]
                
                if class_name == 'person':
                    count += 1
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"Person: {conf:.2f}", (x1, y1-10), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return count

    def detect_fire(self, frame):
        results = self.fire_model(frame, conf=self.fire_conf_var.get())
        fire_detected = False
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                class_name = self.fire_model.names[cls]
                
                if class_name == 'Fire':
                    fire_detected = True
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(frame, f"Fire: {conf:.2f}", (x1, y1-10), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        if fire_detected:
            frame = self.create_red_overlay(frame)
            cv2.putText(frame, "FIRE DETECTED!", 
                       (frame.shape[1] // 4, frame.shape[0] // 2),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        return fire_detected, frame

    def save_to_csv(self, people_count, fire_status):
        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")
        with open('cctv.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([date, time, people_count, fire_status])

    def update_data_list(self, people_count, fire_status):
        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")
        self.data_list.insert('', 0, values=(date, time, people_count, fire_status))

    def save_settings(self):
        settings = {
            'interval': self.interval_var.get(),
            'people_conf': self.people_conf_var.get(),
            'fire_conf': self.fire_conf_var.get()
        }
        with open('combined_settings.json', 'w') as file:
            json.dump(settings, file)

    def load_settings(self):
        try:
            with open('combined_settings.json', 'r') as file:
                settings = json.load(file)
            self.interval_var.set(settings['interval'])
            self.people_conf_var.set(settings['people_conf'])
            self.fire_conf_var.set(settings['fire_conf'])
        except FileNotFoundError:
            pass

    def load_csv_data(self):
        try:
            with open('cctv.csv', 'r') as file:
                reader = csv.reader(file)
                for row in reversed(list(reader)):
                    self.data_list.insert('', 0, values=row)
        except FileNotFoundError:
            pass

    def on_closing(self):
        self.save_settings()
        self.window.destroy()

if __name__ == "__main__":
    CombinedDetectionApp(tk.Tk(), "Sistem Monitoring CCTV")