import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
import json
import csv
from datetime import datetime
import numpy as np
from video_processor import VideoProcessor

class TrafficCounterApp:
    def create_frames(self):
        # Left frame untuk video
        self.left_frame = ttk.Frame(self.root)
        self.left_frame.pack(side=tk.LEFT, padx=10, pady=10)
        
        # Right frame untuk controls dan monitoring
        self.right_frame = ttk.Frame(self.root)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        
        # Video label dengan fixed size
        self.video_label = ttk.Label(self.left_frame)
        self.video_label.pack()

        # Monitoring frame
        self.monitoring_frame = ttk.LabelFrame(self.right_frame, text="Real-time Monitoring")
        self.monitoring_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Labels untuk monitoring
        self.monitor_labels = {}
        for vehicle in ['car', 'bus', 'truck', 'person', 'motorcycle']:
            frame = ttk.Frame(self.monitoring_frame)
            frame.pack(fill=tk.X, padx=5, pady=2)
            ttk.Label(frame, text=f"{vehicle.capitalize()}:").pack(side=tk.LEFT)
            self.monitor_labels[vehicle] = {
                'up': ttk.Label(frame, text="UP: 0"),
                'down': ttk.Label(frame, text="DOWN: 0")
            }
            self.monitor_labels[vehicle]['up'].pack(side=tk.LEFT, padx=5)
            self.monitor_labels[vehicle]['down'].pack(side=tk.LEFT, padx=5)

    def update_monitoring(self, counts):
        for vehicle in counts:
            up_total = sum(counts[vehicle][f'up{i}'] for i in range(1, 7))
            down_total = sum(counts[vehicle][f'down{i}'] for i in range(1, 7))
            self.monitor_labels[vehicle]['up'].configure(text=f"UP: {up_total}")
            self.monitor_labels[vehicle]['down'].configure(text=f"DOWN: {down_total}")

    def update_video(self):
        frame = self.video_processor.get_processed_frame(self.settings['lines'])
        if frame is not None:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = Image.fromarray(frame)
            frame = ImageTk.PhotoImage(image=frame)
            self.video_label.configure(image=frame)
            self.video_label.image = frame
            
            # Update monitoring panel
            counts = self.video_processor.get_current_counts()
            self.update_monitoring(counts)
            
            # Check if we need to save counts
            self.check_save_counts()
        
        self.root.after(30, self.update_video)
        
    def __init__(self, root):
        self.root = root
        self.root.title("Traffic Counter")
        self.root.state('zoomed')  # Maximize window
        
        # Initialize settings
        self.load_settings()
        self.last_save_time = datetime.now()
        
        # Create main frames
        self.create_frames()
        self.create_controls()
        self.create_table()
        
        # Initialize video
        self.video_processor = VideoProcessor()
        self.update_video()

    def load_settings(self):
        try:
            with open('settings_mobil.json', 'r') as f:
                self.settings = json.load(f)
        except FileNotFoundError:
            self.settings = {
                'lines': {
                    'up1': 100, 'up2': 150, 'up3': 200,
                    'up4': 250, 'up5': 300, 'up6': 350,
                    'down1': 120, 'down2': 170, 'down3': 220,
                    'down4': 270, 'down5': 320, 'down6': 370
                },
                'interval': 5  # minutes
            }
            self.save_settings()

    def save_settings(self):
        with open('settings_mobil.json', 'w') as f:
            json.dump(self.settings, f, indent=4)

    

    def create_controls(self):
        # Line controls
        lines_frame = ttk.LabelFrame(self.right_frame, text="Line Positions")
        lines_frame.pack(padx=5, pady=5, fill=tk.X)
        
        self.line_vars = {}
        for i in range(6):
            # Up lines
            ttk.Label(lines_frame, text=f"Up {i+1}:").grid(row=i, column=0, padx=5, pady=2)
            self.line_vars[f'up{i+1}'] = tk.StringVar(value=str(self.settings['lines'][f'up{i+1}']))
            ttk.Entry(lines_frame, textvariable=self.line_vars[f'up{i+1}'], width=8).grid(row=i, column=1, padx=5, pady=2)
            
            # Down lines
            ttk.Label(lines_frame, text=f"Down {i+1}:").grid(row=i, column=2, padx=5, pady=2)
            self.line_vars[f'down{i+1}'] = tk.StringVar(value=str(self.settings['lines'][f'down{i+1}']))
            ttk.Entry(lines_frame, textvariable=self.line_vars[f'down{i+1}'], width=8).grid(row=i, column=3, padx=5, pady=2)

        ttk.Button(lines_frame, text="Save Lines", command=self.save_line_positions).grid(row=6, column=0, columnspan=4, pady=5)

        # Interval settings
        interval_frame = ttk.LabelFrame(self.right_frame, text="Interval Settings")
        interval_frame.pack(padx=5, pady=5, fill=tk.X)
        
        ttk.Label(interval_frame, text="Save Interval (minutes):").grid(row=0, column=0, padx=5, pady=5)
        self.interval_var = tk.StringVar(value=str(self.settings['interval']))
        ttk.Entry(interval_frame, textvariable=self.interval_var, width=8).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(interval_frame, text="Save Interval", command=self.save_interval).grid(row=1, column=0, columnspan=2, pady=5)

    def create_table(self):
        table_frame = ttk.LabelFrame(self.right_frame, text="Traffic Counts")
        table_frame.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        
        # Create Treeview
        columns = ('Time', 'Car UP', 'Car DOWN', 'Bus UP', 'Bus DOWN', 
                  'Truck UP', 'Truck DOWN', 'Person/Bike UP', 'Person/Bike DOWN')
        
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack elements
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_frames(self):
        # Left frame for video with specific size
        self.left_frame = ttk.Frame(self.root)
        self.left_frame.pack(side=tk.LEFT, padx=10, pady=10)
        
        # Right frame for controls and table
        self.right_frame = ttk.Frame(self.root)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        
        # Video label with fixed size
        self.video_label = ttk.Label(self.left_frame)
        self.video_label.pack()

    def update_video(self):
        frame = self.video_processor.get_processed_frame(self.settings['lines'])
        if frame is not None:
            # No need to resize here as it's already resized in video_processor
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = Image.fromarray(frame)
            frame = ImageTk.PhotoImage(image=frame)
            self.video_label.configure(image=frame)
            self.video_label.image = frame
            
            # Check if we need to save counts
            self.check_save_counts()
            
        self.root.after(30, self.update_video)

    def save_line_positions(self):
        for line_name, var in self.line_vars.items():
            self.settings['lines'][line_name] = int(var.get())
        self.save_settings()

    def save_interval(self):
        self.settings['interval'] = int(self.interval_var.get())
        self.save_settings()

    def check_save_counts(self):
        current_time = datetime.now()
        interval_minutes = self.settings['interval']
        
        if (current_time - self.last_save_time).total_seconds() >= interval_minutes * 60:
            counts = self.video_processor.get_current_counts()
            self.save_counts_to_csv(counts)
            self.update_table(counts)
            self.last_save_time = current_time

    def save_counts_to_csv(self, counts):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get max counts
        max_counts = {
            'car': {'up': max(counts['car'][f'up{i}'] for i in range(1, 7)),
                   'down': max(counts['car'][f'down{i}'] for i in range(1, 7))},
            'bus': {'up': max(counts['bus'][f'up{i}'] for i in range(1, 7)),
                   'down': max(counts['bus'][f'down{i}'] for i in range(1, 7))},
            'truck': {'up': max(counts['truck'][f'up{i}'] for i in range(1, 7)),
                     'down': max(counts['truck'][f'down{i}'] for i in range(1, 7))},
        }
        
        # Compare person and motorcycle counts
        person_up = max(counts['person'][f'up{i}'] for i in range(1, 7))
        motor_up = max(counts['motorcycle'][f'up{i}'] for i in range(1, 7))
        person_down = max(counts['person'][f'down{i}'] for i in range(1, 7))
        motor_down = max(counts['motorcycle'][f'down{i}'] for i in range(1, 7))
        
        person_bike = {
            'up': max(person_up, motor_up),
            'down': max(person_down, motor_down)
        }
        
        # Write to CSV
        row = [
            timestamp,
            max_counts['car']['up'], max_counts['car']['down'],
            max_counts['bus']['up'], max_counts['bus']['down'],
            max_counts['truck']['up'], max_counts['truck']['down'],
            person_bike['up'], person_bike['down']
        ]
        
        file_exists = False
        try:
            with open('counter_mobil.csv', 'r'):
                file_exists = True
        except FileNotFoundError:
            pass
        
        with open('counter_mobil.csv', 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['Time', 'Car UP', 'Car DOWN', 'Bus UP', 'Bus DOWN',
                               'Truck UP', 'Truck DOWN', 'Person/Bike UP', 'Person/Bike DOWN'])
            writer.writerow(row)

    def update_table(self, counts):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        max_car_up = max(counts['car'][f'up{i}'] for i in range(1, 7))
        max_car_down = max(counts['car'][f'down{i}'] for i in range(1, 7))
        max_bus_up = max(counts['bus'][f'up{i}'] for i in range(1, 7))
        max_bus_down = max(counts['bus'][f'down{i}'] for i in range(1, 7))
        max_truck_up = max(counts['truck'][f'up{i}'] for i in range(1, 7))
        max_truck_down = max(counts['truck'][f'down{i}'] for i in range(1, 7))
        
        person_up = max(counts['person'][f'up{i}'] for i in range(1, 7))
        motor_up = max(counts['motorcycle'][f'up{i}'] for i in range(1, 7))
        person_down = max(counts['person'][f'down{i}'] for i in range(1, 7))
        motor_down = max(counts['motorcycle'][f'down{i}'] for i in range(1, 7))
        
        max_person_bike_up = max(person_up, motor_up)
        max_person_bike_down = max(person_down, motor_down)
        
        self.tree.insert('', 0, values=(
            timestamp,
            max_car_up, max_car_down,
            max_bus_up, max_bus_down,
            max_truck_up, max_truck_down,
            max_person_bike_up, max_person_bike_down
        ))

def main():
    root = tk.Tk()
    app = TrafficCounterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()