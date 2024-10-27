import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import csv
import json
from datetime import datetime
from ultralytics import YOLO

class PeopleCounterApp:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        
        # Video source URL
        self.stream_url = "https://cctvjss.jogjakota.go.id/malioboro/NolKm_Utara.stream/playlist.m3u8"

        # YOLO initialization
        self.model = YOLO('yolov8s.pt')

        # Create canvases for original image and processed image
        self.original_canvas = tk.Canvas(window, width=320, height=240)
        self.original_canvas.grid(row=0, column=0, padx=5, pady=5)

        self.processed_canvas = tk.Canvas(window, width=320, height=240)
        self.processed_canvas.grid(row=0, column=1, padx=5, pady=5)

        # Control frame
        control_frame = ttk.Frame(window)
        control_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

        # Capture Button
        self.capture_button = ttk.Button(control_frame, text="Ambil Screenshot", command=self.capture_image)
        self.capture_button.grid(row=0, column=0, columnspan=2, pady=5)

        # Area setting
        ttk.Label(control_frame, text="Area (x1,y1,x2,y2):").grid(row=1, column=0, padx=5, pady=2)
        self.area_var = tk.StringVar(value="50,75,320,240")
        ttk.Entry(control_frame, textvariable=self.area_var, width=15).grid(row=1, column=1, padx=5, pady=2)

        # Confidence Threshold
        ttk.Label(control_frame, text="Confidence Threshold:").grid(row=2, column=0, padx=5, pady=2)
        self.conf_threshold_var = tk.DoubleVar(value=0.4)
        ttk.Scale(control_frame, from_=0.1, to=1.0, variable=self.conf_threshold_var, orient="horizontal").grid(row=2, column=1, padx=5, pady=2)

        # Process button
        self.process_button = ttk.Button(control_frame, text="Proses Gambar", command=self.process_image)
        self.process_button.grid(row=3, column=0, columnspan=2, pady=5)

        # Count display
        self.count_var = tk.StringVar(value="Jumlah Orang: 0")
        ttk.Label(control_frame, textvariable=self.count_var, font=("", 12, "bold")).grid(row=4, column=0, columnspan=2, pady=5)

        # Data list with scrollbar
        self.data_frame = ttk.Frame(window)
        self.data_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        self.data_list = ttk.Treeview(self.data_frame, columns=('Tanggal', 'Waktu', 'Jumlah'), show='headings', height=10)
        self.data_list.heading('Tanggal', text='Tanggal')
        self.data_list.heading('Waktu', text='Waktu')
        self.data_list.heading('Jumlah', text='Jumlah Orang')
        self.data_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.data_frame, orient=tk.VERTICAL, command=self.data_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.data_list.configure(yscrollcommand=scrollbar.set)

        # Initialize variables
        self.current_image = None
        self.processed_image = None
        self.people_count = 0
        self.vid = None

        # Load settings and CSV data
        self.load_settings()
        self.load_csv_data()

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window.mainloop()

    def capture_image(self):
        try:
            # Open video capture
            self.vid = cv2.VideoCapture(self.stream_url)
            
            # Read a frame
            ret, frame = self.vid.read()
            
            if ret:
                # Resize frame
                self.current_image = cv2.resize(frame, (320, 240))
                # Display original image
                self.display_image(self.current_image, self.original_canvas)
                # Clear processed image
                self.processed_canvas.delete("all")
                # Reset count
                self.count_var.set("Jumlah Orang: 0")
            
            # Release video capture
            self.vid.release()
            
        except Exception as e:
            print(f"Error capturing image: {e}")
            self.count_var.set("Error: Tidak dapat mengambil gambar")

    def display_image(self, image, canvas):
        canvas.delete("all")
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        photo = ImageTk.PhotoImage(image=Image.fromarray(image_rgb))
        canvas.image = photo  # Keep a reference!
        canvas.create_image(0, 0, image=photo, anchor=tk.NW)

    def process_image(self):
        if self.current_image is not None:
            try:
                area = list(map(int, self.area_var.get().split(',')))
                if len(area) != 4:
                    raise ValueError("Format area tidak valid")
                
                self.people_count, self.processed_image = self.count_people(self.current_image.copy(), area)
                self.count_var.set(f"Jumlah Orang: {self.people_count}")
                self.display_image(self.processed_image, self.processed_canvas)
                self.save_to_csv(self.people_count)
                self.update_data_list(self.people_count)
            except ValueError as e:
                print(f"Error: {e}")

    def count_people(self, frame, area):
        # Get detection from YOLOv8
        conf_threshold = self.conf_threshold_var.get()
        results = self.model(frame, conf=conf_threshold)
        
        processed_frame = frame.copy()
        count = 0
        
        # Draw detection area
        cv2.rectangle(processed_frame, (area[0], area[1]), (area[2], area[3]), (0, 0, 255), 2)
        
        if len(results) > 0:
            boxes = results[0].boxes
            for box in boxes:
                # Get box coordinates
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                # Get class information
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                
                # Check if detection is person (class 0 in COCO)
                if cls == 0:  # person class
                    # Calculate center point of detection
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2
                    
                    # Check if person is in counting area
                    if self.point_in_area(center_x, center_y, area):
                        count += 1
                        # Draw bounding box for person in area
                        cv2.rectangle(processed_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        # Add confidence label
                        cv2.putText(processed_frame, f"{conf:.2f}", (x1, y1-10),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        return count, processed_frame

    def point_in_area(self, x, y, area):
        x1, y1, x2, y2 = area
        return x1 < x < x2 and y1 < y < y2

    def save_to_csv(self, count):
        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")
        with open('people_counter.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([date, time, count])

    def update_data_list(self, count):
        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")
        self.data_list.insert('', 0, values=(date, time, count))

    def save_settings(self):
        settings = {
            'area': self.area_var.get(),
            'conf_threshold': self.conf_threshold_var.get()
        }
        with open('settings.json', 'w') as file:
            json.dump(settings, file)

    def load_settings(self):
        try:
            with open('settings.json', 'r') as file:
                settings = json.load(file)
            self.area_var.set(settings['area'])
            self.conf_threshold_var.set(settings['conf_threshold'])
        except FileNotFoundError:
            pass  # Use default values if file not found

    def load_csv_data(self):
        try:
            with open('people_counter.csv', 'r') as file:
                reader = csv.reader(file)
                for row in reversed(list(reader)):
                    self.data_list.insert('', 0, values=row)
        except FileNotFoundError:
            pass  # No existing data to load

    def on_closing(self):
        self.save_settings()
        self.window.destroy()

if __name__ == "__main__":
    # Create a window and pass it to the Application object
    PeopleCounterApp(tk.Tk(), "Penghitung Orang dari Screenshot Stream")