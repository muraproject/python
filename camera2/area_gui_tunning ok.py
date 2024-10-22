import cv2
import numpy as np
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import threading

class PeopleCounterApp:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)

        # Video source
        self.stream_url = "https://cctvjss.jogjakota.go.id/malioboro/NolKm_Utara.stream/playlist.m3u8"
        self.vid = cv2.VideoCapture(self.stream_url)

        # YOLO initialization
        self.net = cv2.dnn.readNet("yolov3-spp.weights", "yolov3-spp.cfg")
        self.classes = open("coco.names").read().strip().split("\n")

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

        # Area setting
        ttk.Label(control_frame, text="Area (x1,y1,x2,y2):").grid(row=1, column=0, padx=5, pady=2)
        self.area_var = tk.StringVar(value="50,75,320,240")
        ttk.Entry(control_frame, textvariable=self.area_var, width=15).grid(row=1, column=1, padx=5, pady=2)

        # Confidence Threshold
        ttk.Label(control_frame, text="Confidence Threshold:").grid(row=2, column=0, padx=5, pady=2)
        self.conf_threshold_var = tk.DoubleVar(value=0.4)
        ttk.Scale(control_frame, from_=0.1, to=1.0, variable=self.conf_threshold_var, orient="horizontal").grid(row=2, column=1, padx=5, pady=2)

        # NMS Threshold
        ttk.Label(control_frame, text="NMS Threshold:").grid(row=3, column=0, padx=5, pady=2)
        self.nms_threshold_var = tk.DoubleVar(value=0.4)
        ttk.Scale(control_frame, from_=0.1, to=1.0, variable=self.nms_threshold_var, orient="horizontal").grid(row=3, column=1, padx=5, pady=2)

        # Input Size
        ttk.Label(control_frame, text="Input Size:").grid(row=4, column=0, padx=5, pady=2)
        self.input_size_var = tk.IntVar(value=416)
        ttk.Combobox(control_frame, textvariable=self.input_size_var, values=[320, 416, 608]).grid(row=4, column=1, padx=5, pady=2)

        # Scale Factor
        ttk.Label(control_frame, text="Scale Factor:").grid(row=5, column=0, padx=5, pady=2)
        self.scale_factor_var = tk.DoubleVar(value=1/255.0)
        ttk.Entry(control_frame, textvariable=self.scale_factor_var, width=10).grid(row=5, column=1, padx=5, pady=2)

        # Start button
        self.start_button = ttk.Button(control_frame, text="Mulai Hitung", command=self.start_counting)
        self.start_button.grid(row=6, column=0, columnspan=2, pady=5)

        # Count display
        self.count_var = tk.StringVar(value="Jumlah Orang: 0")
        ttk.Label(control_frame, textvariable=self.count_var, font=("", 12, "bold")).grid(row=7, column=0, columnspan=2, pady=5)

        # Initialize variables
        self.is_counting = False
        self.current_frame = None
        self.processed_frame = None
        self.people_count = 0

        self.update()
        self.window.mainloop()

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

    def start_counting(self):
        if not self.is_counting:
            self.is_counting = True
            self.start_button.config(text="Hentikan")
            threading.Thread(target=self.counting_thread, daemon=True).start()
        else:
            self.is_counting = False
            self.start_button.config(text="Mulai Hitung")

    def counting_thread(self):
        while self.is_counting:
            try:
                interval = int(self.interval_var.get())
                area = list(map(int, self.area_var.get().split(',')))
                if len(area) != 4:
                    raise ValueError("Format area tidak valid")
                
                time.sleep(interval)
                
                if self.current_frame is not None:
                    self.people_count, self.processed_frame = self.count_people(self.current_frame.copy(), area)
                    self.count_var.set(f"Jumlah Orang: {self.people_count}")
            except ValueError as e:
                print(f"Error: {e}")
                self.is_counting = False
                self.start_button.config(text="Mulai Hitung")

    def count_people(self, frame, area):
        height, width = frame.shape[:2]
        input_size = self.input_size_var.get()
        scale_factor = self.scale_factor_var.get()
        blob = cv2.dnn.blobFromImage(frame, scale_factor, (input_size, input_size), swapRB=True, crop=False)
        self.net.setInput(blob)
        outs = self.net.forward(self.get_output_layers())

        class_ids = []
        confidences = []
        boxes = []
        conf_threshold = self.conf_threshold_var.get()
        nms_threshold = self.nms_threshold_var.get()

        for out in outs:
            for detection in out:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                if confidence > conf_threshold and self.classes[class_id] == "person":
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)
                    x = center_x - w // 2
                    y = center_y - h // 2
                    class_ids.append(class_id)
                    confidences.append(float(confidence))
                    boxes.append([x, y, w, h])

        indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, nms_threshold)

        count = 0
        for i in indices:
            i = i[0] if isinstance(i, (tuple, list)) else i
            box = boxes[i]
            x, y, w, h = box
            if self.point_in_area(x + w//2, y + h//2, area):
                count += 1
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # Draw counting area
        cv2.rectangle(frame, (area[0], area[1]), (area[2], area[3]), (0, 0, 255), 2)

        return count, frame

    def get_output_layers(self):
        return [self.net.getLayerNames()[i - 1] for i in self.net.getUnconnectedOutLayers()]

    def point_in_area(self, x, y, area):
        x1, y1, x2, y2 = area
        return x1 < x < x2 and y1 < y < y2

# Create a window and pass it to the Application object
PeopleCounterApp(tk.Tk(), "Penghitung Orang")