import cv2
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import threading
import time
from ultralytics import YOLO
from detection_utils import DetectionManager
from gui_components import DetectionGUI

class FireSmokeDetectionApp:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Fire and Smoke Detection System")
        
        # Initialize components
        self.stream_url = "api3.mp4"
        self.cap = cv2.VideoCapture(self.stream_url)
        self.model = YOLO('api3.pt')
        
        # Initialize managers
        self.detection_manager = DetectionManager()
        self.gui = DetectionGUI(self.window, self.detection_manager)
        
        # Start threads
        self.stop_thread = False
        self.start_threads()
        
        # Set closing protocol
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window.mainloop()

    def start_threads(self):
        """Start video dan detection threads"""
        self.thread_video = threading.Thread(target=self.video_stream_thread, daemon=True)
        self.thread_video.start()
        
        self.thread_detection = threading.Thread(target=self.detection_thread, daemon=True)
        self.thread_detection.start()

    def video_stream_thread(self):
        """Thread untuk membaca video stream"""
        while not self.stop_thread:
            try:
                ret, frame = self.cap.read()
                if ret:
                    frame = cv2.resize(frame, (400, 300))
                    self.detection_manager.update_current_frame(frame)
                    self.gui.update_display()
                else:
                    # Reconnect jika stream terputus
                    self.cap.release()
                    time.sleep(1)
                    self.cap = cv2.VideoCapture(self.stream_url)
                time.sleep(0.01)
            except Exception as e:
                print(f"Error in video stream: {e}")
                time.sleep(1)

    def detection_thread(self):
        """Thread untuk proses deteksi"""
        while not self.stop_thread:
            if self.gui.is_running:
                try:
                    frame = self.detection_manager.get_current_frame()
                    if frame is not None:
                        results = self.model(frame)
                        self.detection_manager.process_results(
                            results, 
                            self.gui.fire_conf_threshold.get(),
                            self.gui.smoke_conf_threshold.get()
                        )
                        self.gui.update_status()
                    time.sleep(float(self.gui.interval_var.get()))
                except Exception as e:
                    print(f"Error in detection: {e}")
                    time.sleep(1)
            else:
                time.sleep(0.1)

    def on_closing(self):
        """Cleanup dan tutup aplikasi"""
        self.stop_thread = True
        self.detection_manager.cleanup()
        self.cap.release()
        self.window.destroy()