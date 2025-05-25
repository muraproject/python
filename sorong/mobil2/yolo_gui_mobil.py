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

# Import our enhanced video processor
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
        """Create menu bar with settings menu"""
        menubar = tk.Menu(self.window)
        self.window.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Display Settings", command=self.show_display_settings)
        settings_menu.add_command(label="Processing Settings", command=self.show_processing_settings)
        settings_menu.add_command(label="Server Settings", command=self.show_server_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label="Save Settings", command=self.save_current_settings)
        
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
        
        # Get display size from settings
        width, height = self.settings_manager.get_display_size()
        
        self.video_canvas = tk.Canvas(self.video_frame, width=width, height=height)
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

    def show_display_settings(self):
        """Show display settings dialog"""
        settings_dialog = tk.Toplevel(self.window)
        settings_dialog.title("Display Settings")
        settings_dialog.geometry("400x200")
        settings_dialog.resizable(False, False)
        settings_dialog.grab_set()  # Make dialog modal
        
        # Get current resize factor
        current_factor = self.settings_manager.settings['display']['resize_factor']
        
        # Create form for display settings
        ttk.Label(settings_dialog, text="Display Resize Factor:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        # Resize factor slider
        factor_var = tk.DoubleVar(value=current_factor)
        factor_scale = ttk.Scale(settings_dialog, from_=0.1, to=1.5, orient=tk.HORIZONTAL, 
                                variable=factor_var, length=200)
        factor_scale.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        factor_label = ttk.Label(settings_dialog, textvariable=factor_var, width=5)
        factor_label.grid(row=0, column=2, padx=5, pady=10, sticky="w")
        
        # Current resolution preview
        resolution_var = tk.StringVar()
        if hasattr(self.video_processor, 'original_width') and hasattr(self.video_processor, 'original_height'):
            orig_width = self.video_processor.original_width
            orig_height = self.video_processor.original_height
            resolution_var.set(f"Original: {orig_width}x{orig_height}")
        else:
            base_width = self.settings_manager.settings['display']['base_width']
            base_height = self.settings_manager.settings['display']['base_height']
            resolution_var.set(f"Base: {base_width}x{base_height}")
            
        ttk.Label(settings_dialog, text="Source Resolution:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        ttk.Label(settings_dialog, textvariable=resolution_var).grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="w")
        
        # Display resolution preview
        display_resolution_var = tk.StringVar()
        
        def update_preview(event=None):
            """Update display resolution preview when slider changes"""
            factor = factor_var.get()
            factor_var.set(round(factor, 2))  # Round to 2 decimal places
            
            if hasattr(self.video_processor, 'original_width') and hasattr(self.video_processor, 'original_height'):
                width = int(self.video_processor.original_width * factor)
                height = int(self.video_processor.original_height * factor)
            else:
                base_width = self.settings_manager.settings['display']['base_width']
                base_height = self.settings_manager.settings['display']['base_height']
                width = int(base_width * factor)
                height = int(base_height * factor)
                
            display_resolution_var.set(f"Display: {width}x{height}")
            
        update_preview()  # Initial update
        factor_scale.bind("<Motion>", update_preview)
        
        ttk.Label(settings_dialog, text="Display Resolution:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        ttk.Label(settings_dialog, textvariable=display_resolution_var).grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="w")
        
        # Buttons
        def apply_settings():
            try:
                factor = round(factor_var.get(), 2)
                
                if factor <= 0 or factor > 2.0:
                    messagebox.showerror("Invalid Value", "Resize factor should be between 0.1-1.5")
                    return
                    
                # Update settings
                self.settings_manager.settings['display']['resize_factor'] = factor
                
                # Update video processor
                if hasattr(self.video_processor, 'update_settings'):
                    self.video_processor.update_settings(resize_factor=factor)
                
                # Save settings
                self.settings_manager.save_settings(self.settings_manager.settings)
                messagebox.showinfo("Success", "Display settings updated.\nChanges will take full effect after restart.")
                settings_dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Error updating display settings: {str(e)}")
        
        button_frame = ttk.Frame(settings_dialog)
        button_frame.grid(row=3, column=0, columnspan=3, pady=20)
        
        ttk.Button(button_frame, text="Apply", command=apply_settings).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancel", command=settings_dialog.destroy).pack(side=tk.LEFT, padx=10)

    def show_processing_settings(self):
        """Show processing settings dialog"""
        settings_dialog = tk.Toplevel(self.window)
        settings_dialog.title("Processing Settings")
        settings_dialog.geometry("400x250")
        settings_dialog.resizable(False, False)
        settings_dialog.grab_set()  # Make dialog modal
        
        # Get current processing settings
        current_fps = self.settings_manager.settings['processing']['target_fps']
        current_confidence = self.settings_manager.settings['processing']['confidence_threshold']
        current_tracking_points = self.settings_manager.settings['processing']['tracking_points']
        
        # FPS setting
        ttk.Label(settings_dialog, text="Target FPS:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        fps_values = ["15", "20", "25", "30", "60"]
        fps_var = tk.StringVar(value=str(current_fps))
        fps_combo = ttk.Combobox(settings_dialog, textvariable=fps_var, values=fps_values, width=10, state="readonly")
        fps_combo.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        
        # Confidence threshold
        ttk.Label(settings_dialog, text="Detection Confidence:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        confidence_var = tk.DoubleVar(value=current_confidence)
        confidence_scale = ttk.Scale(settings_dialog, from_=0.1, to=0.9, orient=tk.HORIZONTAL, 
                                variable=confidence_var, length=200)
        confidence_scale.grid(row=1, column=1, padx=5, pady=10, sticky="w")
        confidence_label = ttk.Label(settings_dialog, textvariable=confidence_var, width=5)
        confidence_label.grid(row=1, column=2, padx=5, pady=10, sticky="w")
        
        # Update confidence label when scale changes
        def update_confidence_label(event):
            confidence_var.set(round(confidence_scale.get(), 1))
        confidence_scale.bind("<Motion>", update_confidence_label)
        
        # Object tracking setting
        ttk.Label(settings_dialog, text="Tracking History:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        history_var = tk.StringVar(value=str(current_tracking_points))
        history_entry = ttk.Entry(settings_dialog, textvariable=history_var, width=10)
        history_entry.grid(row=2, column=1, padx=5, pady=10, sticky="w")
        ttk.Label(settings_dialog, text="frames").grid(row=2, column=2, padx=5, pady=10, sticky="w")
        
        # Buttons
        def apply_settings():
            try:
                fps = int(fps_var.get())
                confidence = round(confidence_var.get(), 1)
                history = int(history_var.get())
                
                if history < 1 or history > 100:
                    messagebox.showerror("Invalid Value", "Tracking history should be between 1-100 frames")
                    return
                
                # Update settings
                self.settings_manager.settings['processing']['target_fps'] = fps
                self.settings_manager.settings['processing']['confidence_threshold'] = confidence
                self.settings_manager.settings['processing']['tracking_points'] = history
                
                # Update video processor
                if hasattr(self.video_processor, 'update_settings'):
                    self.video_processor.update_settings(target_fps=fps, confidence=confidence)
                
                # Update tracker max points
                if hasattr(self.tracker, 'max_points'):
                    self.tracker.max_points = history
                
                # Save settings
                self.settings_manager.save_settings(self.settings_manager.settings)
                messagebox.showinfo("Success", "Processing settings updated")
                settings_dialog.destroy()
                
            except ValueError:
                messagebox.showerror("Invalid Value", "Please enter valid numbers")
        
        button_frame = ttk.Frame(settings_dialog)
        button_frame.grid(row=3, column=0, columnspan=3, pady=20)
        
        ttk.Button(button_frame, text="Apply", command=apply_settings).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancel", command=settings_dialog.destroy).pack(side=tk.LEFT, padx=10)

    def show_server_settings(self):
        """Show server settings dialog"""
        settings_dialog = tk.Toplevel(self.window)
        settings_dialog.title("Server Settings")
        settings_dialog.geometry("400x200")
        settings_dialog.resizable(False, False)
        settings_dialog.grab_set()  # Make dialog modal
        
        # Data upload interval
        ttk.Label(settings_dialog, text="Data Upload Interval:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        interval_var = tk.StringVar(value=str(self.settings_manager.settings['interval']))
        interval_entry = ttk.Entry(settings_dialog, textvariable=interval_var, width=10)
        interval_entry.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        ttk.Label(settings_dialog, text="seconds").grid(row=0, column=2, padx=5, pady=10, sticky="w")
        
        # API check interval
        ttk.Label(settings_dialog, text="API Check Interval:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        
        api_interval_var = tk.StringVar(value=str(self.api_check_interval // 1000))  # Convert from ms to seconds
        api_interval_entry = ttk.Entry(settings_dialog, textvariable=api_interval_var, width=10)
        api_interval_entry.grid(row=1, column=1, padx=5, pady=10, sticky="w")
        ttk.Label(settings_dialog, text="seconds").grid(row=1, column=2, padx=5, pady=10, sticky="w")
        
        # Buttons
        def apply_settings():
            try:
                interval = int(interval_var.get())
                api_interval = int(api_interval_var.get())
                
                if interval < 10 or interval > 3600:
                    messagebox.showerror("Invalid Value", "Data upload interval should be between 10-3600 seconds")
                    return
                    
                if api_interval < 1 or api_interval > 60:
                    messagebox.showerror("Invalid Value", "API check interval should be between 1-60 seconds")
                    return
                    
                # Update settings
                self.settings_manager.settings['interval'] = interval
                self.api_check_interval = api_interval * 1000  # Convert to milliseconds
                
                # Save settings
                self.settings_manager.save_settings(self.settings_manager.settings)
                messagebox.showinfo("Success", "Server settings updated")
                settings_dialog.destroy()
                
            except ValueError:
                messagebox.showerror("Invalid Value", "Intervals must be numbers")
        
        button_frame = ttk.Frame(settings_dialog)
        button_frame.grid(row=2, column=0, columnspan=3, pady=20)
        
        ttk.Button(button_frame, text="Apply", command=apply_settings).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancel", command=settings_dialog.destroy).pack(side=tk.LEFT, padx=10)

    def save_current_settings(self):
        """Save current settings to file"""
        try:
            self.settings_manager.save_settings(self.settings_manager.settings)
            messagebox.showinfo("Success", "Settings saved to file")
        except Exception as e:
            messagebox.showerror("Error", f"Error saving settings: {str(e)}")

    def show_about(self):
        """Show about dialog"""
        about_text = """Vehicle Counter System
Version 2.1

Real-time vehicle detection and counting
with automatic camera management.

Features:
- Enhanced video stream reliability
- Dynamic display resize factor
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