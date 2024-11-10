import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2

class DetectionGUI:
    def __init__(self, window, detection_manager):
        self.window = window
        self.detection_manager = detection_manager
        self.is_running = False
        
        self.setup_gui()
        self.load_existing_data()

    def setup_gui(self):
        """Setup GUI components"""
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
        
        # Labels untuk canvas
        ttk.Label(video_frame, text="Live Stream").place(x=150, y=5)
        ttk.Label(video_frame, text="Detection Result").place(x=550, y=5)
        
        # Control frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(pady=10)
        
        # Interval control
        ttk.Label(control_frame, text="Interval (detik):").pack(side=tk.LEFT, padx=5)
        self.interval_var = tk.StringVar(value="5")
        ttk.Entry(control_frame, textvariable=self.interval_var, width=5).pack(side=tk.LEFT, padx=5)
        
        # Confidence thresholds
        ttk.Label(control_frame, text="Fire Conf:").pack(side=tk.LEFT, padx=5)
        self.fire_conf_threshold = tk.DoubleVar(value=0.5)
        ttk.Scale(control_frame, from_=0.1, to=1.0, 
                variable=self.fire_conf_threshold, orient="horizontal").pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame, text="Smoke Conf:").pack(side=tk.LEFT, padx=5)
        self.smoke_conf_threshold = tk.DoubleVar(value=0.5)
        ttk.Scale(control_frame, from_=0.1, to=1.0, 
                variable=self.smoke_conf_threshold, orient="horizontal").pack(side=tk.LEFT, padx=5)
        
        # Start/Stop button
        self.start_button = ttk.Button(control_frame, text="Start Detection", 
                                     command=self.toggle_detection)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        # Status frame
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(pady=5)
        
        # Status indicators
        self.fire_status_var = tk.StringVar(value="Fire: Not Detected")
        self.smoke_status_var = tk.StringVar(value="Smoke: Not Detected")
        
        ttk.Label(status_frame, textvariable=self.fire_status_var,
                 font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=10)
        ttk.Label(status_frame, textvariable=self.smoke_status_var,
                 font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=10)
        
        # Detection log
        self.setup_log_view(main_frame)

    def setup_log_view(self, parent):
        """Setup detection log view"""
        log_frame = ttk.LabelFrame(parent, text="Detection Log")
        log_frame.pack(pady=5, fill=tk.X, padx=5)
        
        self.log_tree = ttk.Treeview(log_frame, 
                                    columns=('DateTime', 'Detection'),
                                    show='headings', 
                                    height=6)
        
        self.log_tree.heading('DateTime', text='Tanggal & Waktu')
        self.log_tree.heading('Detection', text='Deteksi (Api, Asap)')
        
        self.log_tree.column('DateTime', width=200)
        self.log_tree.column('Detection', width=400)
        
        self.log_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_tree.configure(yscrollcommand=scrollbar.set)

    def update_display(self):
        """Update display dengan frame terbaru"""
        try:
            # Update original stream
            current_frame = self.detection_manager.current_frame
            if current_frame is not None:
                frame = cv2.cvtColor(current_frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                img_tk = ImageTk.PhotoImage(image=img)
                self.original_canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
                self.original_canvas.img_tk = img_tk
            
            # Update processed view
            display_frame = self.detection_manager.get_display_frame()
            if display_frame is not None:
                # Apply overlays based on detection
                if self.detection_manager.fire_detected:
                    display_frame = self.detection_manager.create_overlay(display_frame, (0, 0, 255))
                elif self.detection_manager.smoke_detected:
                    display_frame = self.detection_manager.create_overlay(display_frame, (255, 0, 0))
                
                processed = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                processed_img = Image.fromarray(processed)
                processed_img_tk = ImageTk.PhotoImage(image=processed_img)
                self.processed_canvas.create_image(0, 0, anchor=tk.NW, image=processed_img_tk)
                self.processed_canvas.processed_img_tk = processed_img_tk
        except Exception as e:
            print(f"Error updating display: {e}")

    def update_status(self):
        """Update status labels dan log"""
        try:
            # Update status labels
            if self.detection_manager.fire_detected:
                self.fire_status_var.set(f"Fire Detected: {self.detection_manager.fire_conf:.2f}")
            else:
                self.fire_status_var.set("Fire: Not Detected")
            
            if self.detection_manager.smoke_detected:
                self.smoke_status_var.set(f"Smoke Detected: {self.detection_manager.smoke_conf:.2f}")
            else:
                self.smoke_status_var.set("Smoke: Not Detected")
            
            # Add to log tree
            from datetime import datetime
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            detection_text = f"Api: {'Ada' if self.detection_manager.fire_detected else 'Tidak Ada'}, " + \
                           f"Asap: {'Ada' if self.detection_manager.smoke_detected else 'Tidak Ada'}"
            
            self.log_tree.insert('', 0, values=(current_time, detection_text))
            
            # Keep only last 100 entries
            if len(self.log_tree.get_children()) > 100:
                self.log_tree.delete(self.log_tree.get_children()[-1])
                
        except Exception as e:
            print(f"Error updating status: {e}")

    def toggle_detection(self):
        """Toggle detection on/off"""
        self.is_running = not self.is_running
        if self.is_running:
            self.start_button.config(text="Stop Detection")
        else:
            self.start_button.config(text="Start Detection")

    def load_existing_data(self):
        """Load existing log data from CSV"""
        try:
            import csv
            with open(self.detection_manager.csv_file, 'r') as file:
                reader = csv.reader(file)
                next(reader)  # Skip header
                data = list(reader)
                for row in reversed(data[-100:]):  # Load last 100 entries
                    date, time, fire, smoke = row
                    self.log_tree.insert('', 0, values=(
                        f"{date} {time}",
                        f"Api: {fire}, Asap: {smoke}"
                    ))
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error loading existing data: {e}")