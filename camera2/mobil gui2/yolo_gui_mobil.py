# main_gui.py

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import threading
import time
from datetime import datetime
import json
import sys
import os

# Import from other files
from base_utils import SettingsManager, DataManager, GPUProcessor, ObjectTracker
from video_processor import VideoProcessor

class VehicleCounterGUI:
    def __init__(self, window):
        self.window = window
        self.window.title("Vehicle Counter System")
        
        # Initialize managers
        self.settings_manager = SettingsManager()
        self.data_manager = DataManager()
        self.gpu_processor = GPUProcessor()
        self.tracker = ObjectTracker()
        
        # Share GPU and tracker with settings manager
        self.settings_manager.gpu_processor = self.gpu_processor
        self.settings_manager.tracker = self.tracker
        
        # Initialize video processor
        self.video_processor = VideoProcessor(self.settings_manager, self.data_manager)
        
        # Initialize variables
        self.video_thread = None
        self.running = False
        self.last_save_time = time.time()
        
        # Set main window properties
        self.window.state('zoomed')  # Maximize window
        self.setup_gui()
        self.load_settings()

    def setup_gui(self):
        """Setup the complete GUI layout"""
        self.create_menu()
        self.create_main_frames()
        self.create_video_display()
        self.create_control_panel()
        self.create_monitoring_panel()

    def create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.window)
        self.window.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save Settings", command=self.save_settings)
        file_menu.add_command(label="Reset Settings", command=self.reset_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Apply Settings", command=lambda: self.apply_settings())
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

    def create_main_frames(self):
        """Create main layout frames"""
        # Main container
        self.main_container = ttk.Frame(self.window)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left frame for video
        self.left_frame = ttk.Frame(self.main_container)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Right frame for controls
        self.right_frame = ttk.Frame(self.main_container, width=300)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        self.right_frame.pack_propagate(False)

    def create_video_display(self):
        """Create video display area with fixed size"""
        self.video_frame = ttk.LabelFrame(self.left_frame, text="Video Feed")
        self.video_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create canvas with fixed size for video
        self.video_canvas = tk.Canvas(self.video_frame, 
                                    width=self.settings_manager.settings['display']['width'],
                                    height=self.settings_manager.settings['display']['height'])
        self.video_canvas.pack(padx=5, pady=5)
        
        self.video_label = ttk.Label(self.video_canvas)
        self.video_label.place(relx=0.5, rely=0.5, anchor='center')

    def create_control_panel(self):
        """Create control panel with settings"""
        # Control Panel
        control_frame = ttk.LabelFrame(self.right_frame, text="Control Panel")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Interval setting
        interval_frame = ttk.Frame(control_frame)
        interval_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(interval_frame, text="Save Interval (seconds):").pack(side=tk.LEFT)
        self.interval_var = tk.StringVar()
        self.interval_entry = ttk.Entry(interval_frame, textvariable=self.interval_var, width=10)
        self.interval_entry.pack(side=tk.LEFT, padx=5)
        
        # Line Position Controls
        lines_frame = ttk.LabelFrame(self.right_frame, text="Line Positions")
        lines_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Up lines
        up_frame = ttk.LabelFrame(lines_frame, text="Up Lines (0-1)")
        up_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.line_vars = {}
        for i in range(1, 7):
            frame = ttk.Frame(up_frame)
            frame.pack(fill=tk.X, padx=2, pady=2)
            ttk.Label(frame, text=f"Line {i}:").pack(side=tk.LEFT)
            self.line_vars[f'up{i}'] = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=self.line_vars[f'up{i}'], width=10)
            entry.pack(side=tk.LEFT, padx=5)
            self.line_vars[f'up{i}'].widget = entry
        
        # Down lines
        down_frame = ttk.LabelFrame(lines_frame, text="Down Lines (0-1)")
        down_frame.pack(fill=tk.X, padx=5, pady=5)
        
        for i in range(1, 7):
            frame = ttk.Frame(down_frame)
            frame.pack(fill=tk.X, padx=2, pady=2)
            ttk.Label(frame, text=f"Line {i}:").pack(side=tk.LEFT)
            self.line_vars[f'down{i}'] = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=self.line_vars[f'down{i}'], width=10)
            entry.pack(side=tk.LEFT, padx=5)
            self.line_vars[f'down{i}'].widget = entry
        
        # Control Buttons
        button_frame = ttk.Frame(self.right_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.start_button = ttk.Button(button_frame, text="Start", command=self.start_processing)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_processing)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.stop_button.config(state='disabled')
        
        settings_frame = ttk.Frame(button_frame)
        settings_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(settings_frame, text="Save Settings", 
                  command=self.save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(settings_frame, text="Reset Settings", 
                  command=self.reset_settings).pack(side=tk.LEFT, padx=5)

    def create_monitoring_panel(self):
        """Create monitoring panel with current counts and realtime monitoring"""
        monitor_frame = ttk.LabelFrame(self.right_frame, text="Monitoring")
        monitor_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Realtime monitoring section
        realtime_frame = ttk.LabelFrame(monitor_frame, text="Realtime Counts")
        realtime_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create monitoring variables
        self.monitor_vars = {
            'car': {'up': tk.StringVar(value='0'), 'down': tk.StringVar(value='0')},
            'bus': {'up': tk.StringVar(value='0'), 'down': tk.StringVar(value='0')},
            'truck': {'up': tk.StringVar(value='0'), 'down': tk.StringVar(value='0')},
            'person_motor': {'up': tk.StringVar(value='0'), 'down': tk.StringVar(value='0')}
        }
        
        # Create monitoring labels
        row = 0
        for vehicle_type in self.monitor_vars.keys():
            ttk.Label(realtime_frame, text=vehicle_type.replace('_', '/')).grid(row=row, column=0, padx=5, pady=2)
            ttk.Label(realtime_frame, text="↑").grid(row=row, column=1, padx=5, pady=2)
            ttk.Label(realtime_frame, textvariable=self.monitor_vars[vehicle_type]['up']).grid(row=row, column=2, padx=5, pady=2)
            ttk.Label(realtime_frame, text="↓").grid(row=row, column=3, padx=5, pady=2)
            ttk.Label(realtime_frame, textvariable=self.monitor_vars[vehicle_type]['down']).grid(row=row, column=4, padx=5, pady=2)
            row += 1
        
        # FPS and Object Count display
        stats_frame = ttk.Frame(realtime_frame)
        stats_frame.grid(row=row, column=0, columnspan=5, pady=5)
        
        self.fps_var = tk.StringVar(value="FPS: 0")
        self.object_count_var = tk.StringVar(value="Objects: 0")
        
        ttk.Label(stats_frame, textvariable=self.fps_var).pack(side=tk.LEFT, padx=10)
        ttk.Label(stats_frame, textvariable=self.object_count_var).pack(side=tk.LEFT, padx=10)
        
        # Historical data table
        table_frame = ttk.LabelFrame(monitor_frame, text="Historical Data")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create Treeview
        columns = ('timestamp', 'car_up', 'car_down', 'bus_up', 'bus_down', 
                  'truck_up', 'truck_down', 'person_motor_up', 'person_motor_down')
        
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=10)
        
        # Configure columns
        column_widths = {
            'timestamp': 150,
            'car_up': 70,
            'car_down': 70,
            'bus_up': 70,
            'bus_down': 70,
            'truck_up': 70,
            'truck_down': 70,
            'person_motor_up': 100,
            'person_motor_down': 100
        }
        
        for col in columns:
            title = col.replace('_', ' ').title()
            self.tree.heading(col, text=title)
            self.tree.column(col, width=column_widths.get(col, 100))
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def load_settings(self):
        """Load settings from file"""
        settings = self.settings_manager.settings
        self.interval_var.set(str(settings['interval']))
        for line, value in settings['lines'].items():
            if line in self.line_vars:
                self.line_vars[line].set(str(value))

    def save_settings(self):
        """Save current settings to file"""
        try:
            # Validate and get current settings
            interval = int(self.interval_var.get())
            if interval < 1:
                raise ValueError("Interval must be greater than 0")
            
            lines = {}
            for line, var in self.line_vars.items():
                value = float(var.get())
                if not 0 <= value <= 1:
                    raise ValueError(f"Line position {line} must be between 0 and 1")
                lines[line] = value
            
            # Save settings
            settings = {
                'interval': interval,
                'lines': lines,
                'video_source': self.settings_manager.settings['video_source'],
                'display': self.settings_manager.settings['display']
            }
            
            self.settings_manager.save_settings(settings)
            messagebox.showinfo("Success", "Settings saved successfully")
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid setting value: {str(e)}")

    def reset_settings(self):
        """Reset settings to default"""
        self.settings_manager.settings = self.settings_manager.default_settings.copy()
        self.load_settings()
        messagebox.showinfo("Success", "Settings reset to default")

    def validate_settings(self):
        """Validate current settings"""
        try:
            interval = int(self.interval_var.get())
            if interval < 1:
                return False, "Interval must be greater than 0"
            
            for line, var in self.line_vars.items():
                try:
                    value = float(var.get())
                    if not 0 <= value <= 1:
                        return False, f"Line position {line} must be between 0 and 1"
                except ValueError:
                    return False, f"Invalid value for {line}"
            
            return True, ""
        except ValueError:
            return False, "Invalid interval value"

    def apply_settings(self):
        """Apply current settings without saving"""
        is_valid, message = self.validate_settings()
        if is_valid:
            settings = self.get_current_settings()
            self.settings_manager.settings = settings
            return True, "Settings applied successfully"
        return False, message

    def get_current_settings(self):
        """Get current settings from GUI"""
        return {
            'interval': int(self.interval_var.get()),
            'lines': {line: float(var.get()) for line, var in self.line_vars.items()},
            'video_source': self.settings_manager.settings['video_source'],
            'display': self.settings_manager.settings['display']
        }

    def start_processing(self):
        """Start video processing"""
        if not self.running:
            try:
                # Validate settings before starting
                is_valid, message = self.validate_settings()
                if not is_valid:
                    messagebox.showerror("Error", message)
                    return
                
                # Apply current settings
                self.apply_settings()
                
                # Start processing
                self.running = True
                self.start_button.config(state='disabled')
                self.stop_button.config(state='normal')
                
                # Disable settings inputs while running
                self.disable_settings_inputs()
                
                # Start video thread
                self.video_thread = threading.Thread(target=self.process_video)
                self.video_thread.daemon = True
                self.video_thread.start()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to start processing: {str(e)}")
                self.stop_processing()

    def stop_processing(self):
        """Stop video processing"""
        try:
            self.running = False
            
            # Wait for video thread to finish
            if self.video_thread and self.video_thread.is_alive():
                self.video_thread.join(timeout=1.0)
            
            # Reset UI
            self.start_button.config(state='normal')
            self.stop_button.config(state='disabled')
            
            # Enable settings inputs
            self.enable_settings_inputs()
            
            # Save final counts if needed
            if hasattr(self, 'last_save_time'):
                current_time = time.time()
                if current_time - self.last_save_time >= int(self.interval_var.get()):
                    counts = self.data_manager.save_current_counts()
                    self.update_table(counts)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error stopping process: {str(e)}")

    def disable_settings_inputs(self):
        """Disable settings inputs while processing"""
        self.interval_entry.config(state='disabled')
        for line_var in self.line_vars.values():
            if hasattr(line_var, 'widget'):
                line_var.widget.config(state='disabled')

    def enable_settings_inputs(self):
        """Enable settings inputs after stopping"""
        self.interval_entry.config(state='normal')
        for line_var in self.line_vars.values():
            if hasattr(line_var, 'widget'):
                line_var.widget.config(state='normal')

    def update_image(self, frame):
        """Update video display with fixed size"""
        if frame is not None:
            try:
                # Resize frame to fixed size
                width = self.settings_manager.settings['display']['width']
                height = self.settings_manager.settings['display']['height']
                frame = cv2.resize(frame, (width, height))
                
                # Convert to PhotoImage
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(image)
                photo = ImageTk.PhotoImage(image=image)
                
                # Update label
                self.video_label.configure(image=photo)
                self.video_label.image = photo
                
            except Exception as e:
                print(f"Error updating image: {str(e)}")

    def process_video(self):
        """Main video processing loop with monitoring updates"""
        try:
            cap = self.video_processor.initialize_video_capture()
            if not cap.isOpened():
                raise Exception("Could not open video source")

            frame_time = time.time()
            frames_count = 0
            self.last_save_time = time.time()

            while self.running:
                try:
                    ret, frame = cap.read()
                    if not ret:
                        raise Exception("Failed to read video frame")

                    # Process frame
                    processed_frame = self.video_processor.process_frame(frame)
                    self.update_image(processed_frame)

                    # Update FPS calculation
                    frames_count += 1
                    if frames_count % 30 == 0:  # Update every 30 frames
                        current_time = time.time()
                        fps = 30 / (current_time - frame_time)
                        frame_time = current_time
                        self.fps_var.set(f"FPS: {fps:.1f}")

                    # Update object count
                    self.object_count_var.set(f"Objects: {len(self.video_processor.prev_centroids)}")

                    # Update realtime monitoring
                    self.update_monitoring(self.data_manager.current_counts)

                    # Check if it's time to save counts
                    current_time = time.time()
                    if current_time - self.last_save_time >= int(self.interval_var.get()):
                        counts = self.data_manager.save_current_counts()
                        self.update_table(counts)
                        self.last_save_time = current_time

                    # Process any pending events
                    self.window.update_idletasks()

                except Exception as e:
                    print(f"Error in processing loop: {str(e)}")
                    continue

        except Exception as e:
            messagebox.showerror("Error", f"Video processing error: {str(e)}")
        
        finally:
            if 'cap' in locals():
                cap.release()
            self.stop_processing()

    def update_monitoring(self, counts):
        """Update realtime monitoring display"""
        try:
            # Update car counts
            car_up = max([counts['car'][f'up{i}'] for i in range(1, 7)])
            car_down = max([counts['car'][f'down{i}'] for i in range(1, 7)])
            self.monitor_vars['car']['up'].set(str(car_up))
            self.monitor_vars['car']['down'].set(str(car_down))
            
            # Update bus counts
            bus_up = max([counts['bus'][f'up{i}'] for i in range(1, 7)])
            bus_down = max([counts['bus'][f'down{i}'] for i in range(1, 7)])
            self.monitor_vars['bus']['up'].set(str(bus_up))
            self.monitor_vars['bus']['down'].set(str(bus_down))
            
            # Update truck counts
            truck_up = max([counts['truck'][f'up{i}'] for i in range(1, 7)])
            truck_down = max([counts['truck'][f'down{i}'] for i in range(1, 7)])
            self.monitor_vars['truck']['up'].set(str(truck_up))
            self.monitor_vars['truck']['down'].set(str(truck_down))
            
            # Update person/motor counts (including bicycle)
            person_up = max([counts['person'][f'up{i}'] for i in range(1, 7)])
            motor_up = max([counts['motorcycle'][f'up{i}'] for i in range(1, 7)])
            bike_up = max([counts['bicycle'][f'up{i}'] for i in range(1, 7)])
            
            person_down = max([counts['person'][f'down{i}'] for i in range(1, 7)])
            motor_down = max([counts['motorcycle'][f'down{i}'] for i in range(1, 7)])
            bike_down = max([counts['bicycle'][f'down{i}'] for i in range(1, 7)])
            
            combined_up = max(person_up, motor_up, bike_up)
            combined_down = max(person_down, motor_down, bike_down)
            self.monitor_vars['person_motor']['up'].set(str(combined_up))
            self.monitor_vars['person_motor']['down'].set(str(combined_down))

        except Exception as e:
            print(f"Error updating monitoring: {str(e)}")

    def update_table(self, counts):
        """Update historical data table"""
        try:
            # Add new row at the top
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            values = [
                timestamp,
                counts['car_up'],
                counts['car_down'],
                counts['bus_up'],
                counts['bus_down'],
                counts['truck_up'],
                counts['truck_down'],
                counts['person_motor_up'],
                counts['person_motor_down']
            ]
            
            self.tree.insert('', 0, values=values)
            
            # Keep only the last 100 entries
            if len(self.tree.get_children()) > 100:
                self.tree.delete(self.tree.get_children()[-1])

        except Exception as e:
            print(f"Error updating table: {str(e)}")

    def show_about(self):
        """Show about dialog"""
        about_text = """Vehicle Counter System
Version 1.0

This application counts and tracks vehicles
using computer vision and deep learning.

Features:
- Real-time vehicle detection and tracking
- Multiple detection lines
- Detailed counting statistics
- CSV data export
- Configurable settings"""
        
        messagebox.showinfo("About Vehicle Counter", about_text)

    def on_closing(self):
        """Handle window closing"""
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.running = False
            if self.video_thread and self.video_thread.is_alive():
                self.video_thread.join(timeout=1.0)
            self.window.destroy()
            sys.exit(0)

def main():
    # Create main window
    root = tk.Tk()
    
    # Set style
    style = ttk.Style()
    style.theme_use('clam')
    
    # Create application
    app = VehicleCounterGUI(root)
    
    # Set window closing protocol
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Start main loop
    root.mainloop()

if __name__ == "__main__":
    main()