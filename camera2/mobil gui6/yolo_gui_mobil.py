# yolo_gui_mobil.py

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
import numpy as np

# Import from other files
from base_utils import SettingsManager, DataManager, GPUProcessor, ObjectTracker
from restart_helper import restart_app

# Import our new enhanced video processor
from enhanced_video_processor import EnhancedVideoProcessor, EnhancedStreamReader

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
        
        # Initialize ENHANCED video processor
        self.video_processor = EnhancedVideoProcessor(self.settings_manager, self.data_manager)
        
        # Initialize variables
        self.video_thread = None
        self.running = False
        self.last_save_time = time.time()
        self.api_check_interval = 5000  # Check API every 5 seconds
        
        # Set main window properties
        self.window.state('zoomed')  # Maximize window
        self.setup_gui()
        self.load_settings()
        
        # Start automatic monitoring
        self.check_api_updates()

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
        file_menu.add_command(label="Exit", command=self.on_closing)
        
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
        """Create video display area"""
        self.video_frame = ttk.LabelFrame(self.left_frame, text="Video Feed")
        self.video_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.video_canvas = tk.Canvas(self.video_frame,
                                    width=self.settings_manager.settings['display']['width'],
                                    height=self.settings_manager.settings['display']['height'])
        self.video_canvas.pack(expand=True)
        
        self.video_label = ttk.Label(self.video_canvas)
        self.video_label.place(relx=0.5, rely=0.5, anchor='center')

    def create_control_panel(self):
        """Create control panel with settings"""
        # Camera Info Panel
        camera_frame = ttk.LabelFrame(self.right_frame, text="Camera Information")
        camera_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Current Camera Info
        self.camera_info_var = tk.StringVar(value="Checking camera status...")
        ttk.Label(camera_frame, textvariable=self.camera_info_var, 
                 wraplength=250).pack(fill=tk.X, padx=5, pady=5)
        
        # Status Info
        self.status_var = tk.StringVar(value="Initializing...")
        ttk.Label(camera_frame, textvariable=self.status_var,
                 wraplength=250).pack(fill=tk.X, padx=5, pady=5)

    def create_monitoring_panel(self):
        """Create monitoring panel"""
        monitor_frame = ttk.LabelFrame(self.right_frame, text="Monitoring")
        monitor_frame.pack(fill=tk.X, padx=5, pady=5)

        self.monitor_vars = {
            'car': {'up': tk.StringVar(value='0'), 'down': tk.StringVar(value='0')},
            'bus': {'up': tk.StringVar(value='0'), 'down': tk.StringVar(value='0')},
            'truck': {'up': tk.StringVar(value='0'), 'down': tk.StringVar(value='0')},
            'person_motor': {'up': tk.StringVar(value='0'), 'down': tk.StringVar(value='0')}
        }
        
        # Create monitoring labels with better layout
        for vehicle_type in self.monitor_vars:
            frame = ttk.Frame(monitor_frame)
            frame.pack(fill=tk.X, padx=5, pady=2)
            
            # Vehicle type label with fixed width
            type_label = ttk.Label(frame, text=vehicle_type.replace('_', '/'), width=15)
            type_label.pack(side=tk.LEFT)
            
            # Up count
            ttk.Label(frame, text="↑").pack(side=tk.LEFT, padx=5)
            ttk.Label(frame, textvariable=self.monitor_vars[vehicle_type]['up'], 
                     width=6).pack(side=tk.LEFT)
            
            # Down count
            ttk.Label(frame, text="↓").pack(side=tk.LEFT, padx=5)
            ttk.Label(frame, textvariable=self.monitor_vars[vehicle_type]['down'], 
                     width=6).pack(side=tk.LEFT)

        # FPS and Object Count in separate frame
        stats_frame = ttk.Frame(monitor_frame)
        stats_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.fps_var = tk.StringVar(value="FPS: 0")
        self.object_count_var = tk.StringVar(value="Objects: 0")
        ttk.Label(stats_frame, textvariable=self.fps_var, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(stats_frame, textvariable=self.object_count_var, width=15).pack(side=tk.LEFT, padx=5)
        
    def load_settings(self):
        """Load initial settings"""
        try:
            # Update camera info if available
            if self.settings_manager.settings.get('camera_name'):
                self.camera_info_var.set(
                    f"Camera: {self.settings_manager.settings['camera_name']}\n"
                    f"Mode: {self.settings_manager.settings['camera_mode']}"
                )
                # Auto start if video source is available
                if self.settings_manager.settings.get('video_source'):
                    self.start_processing()
        except Exception as e:
            self.status_var.set(f"Error loading settings: {str(e)}")
            print(f"Error loading settings: {e}")

    def check_api_updates(self):
        """Check for API updates periodically"""
        try:
            current_source = self.settings_manager.settings.get('video_source')
            current_name = self.settings_manager.settings.get('camera_name')
            current_mode = self.settings_manager.settings.get('camera_mode')
            
            # Update from API
            if self.settings_manager.update_video_source():
                new_source = self.settings_manager.settings['video_source']
                new_name = self.settings_manager.settings['camera_name']
                new_mode = self.settings_manager.settings['camera_mode']
                
                print(f"API Update - New source: {new_source}, Name: {new_name}, Mode: {new_mode}")
                
                # Update display
                self.camera_info_var.set(
                    f"Camera: {new_name}\nMode: {new_mode}"
                )
                
                # Check if source changed
                if current_source != new_source:
                    print("Video source changed, restarting application...")
                    self.status_var.set("Video source changed. Restarting application...")
                    self.window.after(1000, self.restart_application)
                    return
                    
                # Auto start if not running
                if new_source and not self.running:
                    print("Starting video processing...")
                    self.start_processing()
                
            else:
                self.camera_info_var.set("No camera available")
                if self.running:
                    print("No camera available, stopping processing...")
                    self.stop_processing()
                self.status_var.set("Waiting for camera...")
                    
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            print(f"Error in check_api_updates: {e}")
        finally:
            self.window.after(self.api_check_interval, self.check_api_updates)

    def start_processing(self):
        """Start video processing"""
        if not self.running:
            try:
                if not self.settings_manager.settings.get('video_source'):
                    self.status_var.set("No video source available")
                    return

                print(f"Starting video processing with source: {self.settings_manager.settings['video_source']}")
                self.running = True
                self.video_thread = threading.Thread(target=self.process_video)
                self.video_thread.daemon = True
                self.video_thread.start()
                self.status_var.set("Processing started")

            except Exception as e:
                self.status_var.set(f"Error starting: {str(e)}")
                print(f"Error starting processing: {e}")
                self.running = False

    def stop_processing(self):
        """Stop video processing"""
        try:
            print("Stopping video processing...")
            self.running = False
            if self.video_thread and self.video_thread.is_alive():
                self.video_thread.join(timeout=1.0)
            self.status_var.set("Processing stopped")
            print("Video processing stopped")
        except Exception as e:
            self.status_var.set(f"Error stopping: {str(e)}")
            print(f"Error stopping processing: {e}")

    def restart_application(self):
        """Restart the entire application"""
        try:
            print("Initiating restart...")
            self.running = False
            if self.video_thread and self.video_thread.is_alive():
                self.video_thread.join(timeout=1.0)
            self.window.destroy()
            restart_app()
        except Exception as e:
            print(f"Error restarting application: {e}")
            sys.exit(1)
    
    def process_video(self):
        """Main video processing loop - ENHANCED VERSION"""
        try:
            print("Initializing enhanced video capture...")
            reader = self.video_processor.initialize_video_capture()
            if not reader or not reader.is_running():
                raise Exception("Could not open video source")

            print("Video capture initialized successfully")
            self.last_save_time = time.time()
            
            # Define frame processing callback
            def on_frame_processed(processed_frame):
                self.update_image(processed_frame)
                self.update_monitoring(self.data_manager.current_counts)
                
                # Save counts to API at regular intervals
                current_time = time.time()
                if current_time - self.last_save_time >= self.settings_manager.settings['interval']:
                    self.data_manager.save_current_counts(
                        self.settings_manager.settings['camera_name'],
                        self.settings_manager.settings['camera_mode']
                    )
                    self.last_save_time = current_time
                
                # Update UI stats
                self.fps_var.set(f"FPS: {self.video_processor.fps:.1f}")
                self.object_count_var.set(f"Objects: {len(self.video_processor.prev_centroids)}")
                self.window.update_idletasks()
            
            # Start processing with callback
            self.video_processor.process_video_stream(reader, on_frame_processed)
            
        except Exception as e:
            print(f"Video error: {e}")
            self.status_var.set(f"Video error: {str(e)}")
        finally:
            if self.running:  # If we exited due to error, restart
                print("Video processing failed, restarting application...")
                self.window.after(1000, self.restart_application)

    def update_image(self, frame):
        """Update video display"""
        if frame is not None:
            try:
                # Convert to PhotoImage
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(image)
                photo = ImageTk.PhotoImage(image=image)
                
                # Update label
                self.video_label.configure(image=photo)
                self.video_label.image = photo
                
            except Exception as e:
                print(f"Display error: {e}")

    def update_monitoring(self, counts):
        """Update monitoring display"""
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
            
            # Update person/motor counts
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
            print(f"Monitoring error: {e}")

    def show_about(self):
        """Show about dialog"""
        about_text = """Vehicle Counter System
Version 2.1

Real-time vehicle detection and counting
with automatic camera management.

Features:
- Enhanced video stream reliability
- Automatic video source management
- Real-time vehicle detection
- Multiple vehicle type counting
- API integration
- Automatic data saving"""
        
        messagebox.showinfo("About", about_text)

    def on_closing(self):
        """Handle window closing"""
        try:
            if messagebox.askokcancel("Quit", "Do you want to quit?"):
                print("Closing application...")
                self.running = False
                if self.video_thread and self.video_thread.is_alive():
                    self.video_thread.join(timeout=1.0)
                self.window.destroy()
                sys.exit(0)
        except Exception as e:
            print(f"Error during closing: {e}")
            sys.exit(1)

def main():
    try:
        # Create main window
        root = tk.Tk()
        
        # Configure window
        root.title("Vehicle Counter System")
        
        # Get screen dimensions
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        # Set minimum size
        root.minsize(800, 600)
        
        # Set window size to 90% of screen size
        window_width = int(screen_width * 0.9)
        window_height = int(screen_height * 0.9)
        
        # Calculate position for center of screen
        x_position = (screen_width - window_width) // 2
        y_position = (screen_height - window_height) // 2
        
        # Set window size and position
        root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
        
        # Set style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure styles
        style.configure('TLabelframe', borderwidth=2, relief="solid")
        style.configure('TFrame', background="#f0f0f0")
        style.configure('TLabel', background="#f0f0f0", font=('Arial', 10))
        style.configure('TLabelframe.Label', font=('Arial', 10, 'bold'))
        
        # Create application instance
        app = VehicleCounterGUI(root)
        
        # Set window closing protocol
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        
        # Start main loop
        root.mainloop()
        
    except Exception as e:
        print(f"Error initializing application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Starting Vehicle Counter System...")
    main()