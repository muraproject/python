import cv2
import numpy as np
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import threading

class FireAndPeopleCounterApp:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)

        # Video source
        # self.stream_url = "https://cctvjss.jogjakota.go.id/malioboro/NolKm_Utara.stream/playlist.m3u8"
        self.stream_url = "api.mp4"
        self.vid = cv2.VideoCapture(self.stream_url)

        # YOLO initialization for people detection
        self.net = cv2.dnn.readNet("yolov3.weights", "yolov3.cfg")
        self.classes = open("coco.names").read().strip().split("\n")

        # Create frames for organization
        video_frame = ttk.Frame(window)
        video_frame.grid(row=0, column=0, padx=5, pady=5)

        # Create canvases for live video, people detection, and fire detection
        self.live_canvas = tk.Canvas(video_frame, width=320, height=240)
        self.live_canvas.grid(row=0, column=0, padx=5, pady=5)

        self.people_canvas = tk.Canvas(video_frame, width=320, height=240)
        self.people_canvas.grid(row=0, column=1, padx=5, pady=5)

        self.fire_canvas = tk.Canvas(video_frame, width=320, height=240)
        self.fire_canvas.grid(row=0, column=2, padx=5, pady=5)

        # Control frame
        control_frame = ttk.Frame(window)
        control_frame.grid(row=1, column=0, padx=5, pady=5)

        # People Detection Controls
        people_frame = ttk.LabelFrame(control_frame, text="Pengaturan Deteksi Orang")
        people_frame.grid(row=0, column=0, padx=5, pady=5)

        # Interval setting
        ttk.Label(people_frame, text="Interval (detik):").grid(row=0, column=0, padx=5, pady=2)
        self.interval_var = tk.StringVar(value="5")
        ttk.Entry(people_frame, textvariable=self.interval_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        # Area setting
        ttk.Label(people_frame, text="Area (x1,y1,x2,y2):").grid(row=1, column=0, padx=5, pady=2)
        self.area_var = tk.StringVar(value="50,75,320,240")
        ttk.Entry(people_frame, textvariable=self.area_var, width=15).grid(row=1, column=1, padx=5, pady=2)

        # Fire Detection Controls
        fire_frame = ttk.LabelFrame(control_frame, text="Pengaturan Deteksi Api")
        fire_frame.grid(row=0, column=1, padx=5, pady=5)

        # Fire detection interval
        ttk.Label(fire_frame, text="Interval Api (detik):").grid(row=0, column=0, padx=5, pady=2)
        self.fire_interval_var = tk.StringVar(value="3")
        ttk.Entry(fire_frame, textvariable=self.fire_interval_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        # Fire detection threshold
        ttk.Label(fire_frame, text="Threshold Api:").grid(row=1, column=0, padx=5, pady=2)
        self.fire_threshold_var = tk.IntVar(value=100)
        ttk.Scale(fire_frame, from_=0, to=255, variable=self.fire_threshold_var, orient="horizontal").grid(row=1, column=1, padx=5, pady=2)

        # Common Controls
        common_frame = ttk.Frame(control_frame)
        common_frame.grid(row=1, column=0, columnspan=2, pady=5)

        # Start buttons
        self.people_button = ttk.Button(common_frame, text="Mulai Hitung Orang", command=self.toggle_people_counting)
        self.people_button.grid(row=0, column=0, padx=5)

        self.fire_button = ttk.Button(common_frame, text="Mulai Deteksi Api", command=self.toggle_fire_detection)
        self.fire_button.grid(row=0, column=1, padx=5)

        # Count displays
        self.count_var = tk.StringVar(value="Jumlah Orang: 0")
        ttk.Label(common_frame, textvariable=self.count_var, font=("", 12, "bold")).grid(row=1, column=0, pady=5)

        self.fire_status_var = tk.StringVar(value="Status Api: Tidak Terdeteksi")
        ttk.Label(common_frame, textvariable=self.fire_status_var, font=("", 12, "bold")).grid(row=1, column=1, pady=5)

        # Initialize variables
        self.is_counting_people = False
        self.is_detecting_fire = False
        self.current_frame = None
        self.people_processed_frame = None
        self.fire_processed_frame = None
        self.people_count = 0

        self.update()
        self.window.mainloop()

    def update(self):
        ret, frame = self.vid.read()
        if ret:
            self.current_frame = cv2.resize(frame, (320, 240))
            self.photo = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)))
            self.live_canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

            if self.people_processed_frame is not None:
                self.people_photo = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(self.people_processed_frame, cv2.COLOR_BGR2RGB)))
                self.people_canvas.create_image(0, 0, image=self.people_photo, anchor=tk.NW)

            if self.fire_processed_frame is not None:
                self.fire_photo = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(self.fire_processed_frame, cv2.COLOR_BGR2RGB)))
                self.fire_canvas.create_image(0, 0, image=self.fire_photo, anchor=tk.NW)

        self.window.after(15, self.update)

    def toggle_people_counting(self):
        if not self.is_counting_people:
            self.is_counting_people = True
            self.people_button.config(text="Hentikan Hitung Orang")
            threading.Thread(target=self.people_counting_thread, daemon=True).start()
        else:
            self.is_counting_people = False
            self.people_button.config(text="Mulai Hitung Orang")

    def toggle_fire_detection(self):
        if not self.is_detecting_fire:
            self.is_detecting_fire = True
            self.fire_button.config(text="Hentikan Deteksi Api")
            threading.Thread(target=self.fire_detection_thread, daemon=True).start()
        else:
            self.is_detecting_fire = False
            self.fire_button.config(text="Mulai Deteksi Api")

    def people_counting_thread(self):
        while self.is_counting_people:
            try:
                interval = int(self.interval_var.get())
                area = list(map(int, self.area_var.get().split(',')))
                if len(area) != 4:
                    raise ValueError("Format area tidak valid")
                
                time.sleep(interval)
                
                if self.current_frame is not None:
                    self.people_count, self.people_processed_frame = self.count_people(self.current_frame.copy(), area)
                    self.count_var.set(f"Jumlah Orang: {self.people_count}")
            except ValueError as e:
                print(f"Error: {e}")
                self.is_counting_people = False
                self.people_button.config(text="Mulai Hitung Orang")

    def fire_detection_thread(self):
        while self.is_detecting_fire:
            try:
                interval = int(self.fire_interval_var.get())
                time.sleep(interval)
                
                if self.current_frame is not None:
                    has_fire, self.fire_processed_frame = self.detect_fire(self.current_frame.copy())
                    status = "Terdeteksi" if has_fire else "Tidak Terdeteksi"
                    self.fire_status_var.set(f"Status Api: {status}")
                    
                    if has_fire:
                        # You could add an alarm sound or notification here
                        print("PERINGATAN: Api Terdeteksi!")
            except Exception as e:
                print(f"Error in fire detection: {e}")
                self.is_detecting_fire = False
                self.fire_button.config(text="Mulai Deteksi Api")

    def detect_fire(self, frame):
        # Convert to multiple color spaces
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        
        # Create masks for different color spaces
        # HSV mask for fire colors
        lower_hsv1 = np.array([0, 50, 50])
        upper_hsv1 = np.array([35, 255, 255])
        mask_hsv1 = cv2.inRange(hsv, lower_hsv1, upper_hsv1)
        
        # Second HSV range for darker fire colors
        lower_hsv2 = np.array([160, 50, 50])
        upper_hsv2 = np.array([179, 255, 255])
        mask_hsv2 = cv2.inRange(hsv, lower_hsv2, upper_hsv2)
        
        # Combine HSV masks
        mask_hsv = cv2.bitwise_or(mask_hsv1, mask_hsv2)
        
        # YCrCb mask for fire colors
        lower_ycrcb = np.array([0, 150, 90])
        upper_ycrcb = np.array([255, 255, 255])
        mask_ycrcb = cv2.inRange(ycrcb, lower_ycrcb, upper_ycrcb)
        
        # Combine all masks
        mask = cv2.bitwise_and(mask_hsv, mask_ycrcb)
        
        # Apply morphological operations to remove noise
        kernel = np.ones((3,3), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)
        
        # Apply threshold from UI
        threshold = self.fire_threshold_var.get()
        ret, thresh = cv2.threshold(mask, threshold, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        has_fire = False
        min_fire_area = 500  # Minimum area to be considered as fire
        confirmed_fire_contours = []
        
        # Analyze each potential fire region
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_fire_area:
                continue
                
            # Get the region of interest
            x, y, w, h = cv2.boundingRect(contour)
            roi = frame[y:y+h, x:x+w]
            
            if roi.size == 0:
                continue
                
            # Convert ROI to various color spaces for analysis
            roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            
            # Calculate color and intensity metrics
            avg_hsv = np.mean(roi_hsv, axis=(0,1))
            avg_intensity = np.mean(roi_gray)
            
            # Color variation check
            hsv_std = np.std(roi_hsv, axis=(0,1))
            
            # Criteria for fire detection
            is_fire = (
                avg_hsv[0] < 30 or avg_hsv[0] > 160 and  # Hue check
                avg_hsv[1] > 50 and                       # Saturation check
                avg_hsv[2] > 150 and                      # Value check
                hsv_std[0] > 5 and                        # Color variation check
                avg_intensity > 100                       # Brightness check
            )
            
            if is_fire:
                confirmed_fire_contours.append(contour)
                has_fire = True
        
        # Draw confirmed fire regions
        for contour in confirmed_fire_contours:
            # Draw contour
            cv2.drawContours(frame, [contour], -1, (0, 0, 255), 2)
            
            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)
            
            # Draw rectangle and label
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
            cv2.putText(frame, "FIRE", (x, y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        
        # Add detection parameters to frame
        params_text = [
            f"Threshold: {threshold}",
            f"Min Area: {min_fire_area}",
            f"Regions: {len(confirmed_fire_contours)}"
        ]
        
        for i, text in enumerate(params_text):
            cv2.putText(frame, text, (10, 30 + (i * 25)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return has_fire, frame
        # Convert to HSV color space
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Define fire color range in HSV
        lower_fire = np.array([0, 50, 50])
        upper_fire = np.array([35, 255, 255])
        
        # Create mask for fire colors
        mask = cv2.inRange(hsv, lower_fire, upper_fire)
        
        # Apply threshold
        threshold = self.fire_threshold_var.get()
        ret, thresh = cv2.threshold(mask, threshold, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        has_fire = False
        # Draw contours and check size
        for contour in contours:
            if cv2.contourArea(contour) > 200:  # Minimum area threshold
                has_fire = True
                cv2.drawContours(frame, [contour], -1, (0, 0, 255), 2)
        
        # Draw fire detection area
        cv2.putText(frame, "Fire Detection Area", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        return has_fire, frame

    def count_people(self, frame, area):
        height, width = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
        self.net.setInput(blob)
        outs = self.net.forward(self.get_output_layers())

        class_ids = []
        confidences = []
        boxes = []

        for out in outs:
            for detection in out:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                if confidence > 0.5 and self.classes[class_id] == "person":
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)
                    x = center_x - w // 2
                    y = center_y - h // 2
                    class_ids.append(class_id)
                    confidences.append(float(confidence))
                    boxes.append([x, y, w, h])

        indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)

        count = 0
        for i in indices:
            i = i[0] if isinstance(i, (tuple, list)) else i
            box = boxes[i]
            x, y, w, h = box
            if self.point_in_area(x + w//2, y + h//2, area):
                count += 1
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        cv2.rectangle(frame, (area[0], area[1]), (area[2], area[3]), (0, 0, 255), 2)

        return count, frame

    def get_output_layers(self):
        return [self.net.getLayerNames()[i - 1] for i in self.net.getUnconnectedOutLayers()]

    def point_in_area(self, x, y, area):
        x1, y1, x2, y2 = area
        return x1 < x < x2 and y1 < y < y2

# Create a window and pass it to the Application object
FireAndPeopleCounterApp(tk.Tk(), "Penghitung Orang dan Deteksi Api")