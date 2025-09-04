import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import threading
import time
import datetime
import random
import string
import json
import os
from PIL import Image, ImageTk
import queue
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import signal
import sys

class RobustCamera:
    def __init__(self, rtsp_url=""):
        self.rtsp_url = rtsp_url
        self.cap = None
        self.is_connected = False
        self.last_frame = None
        self.running = False
        self.lock = threading.Lock()
        self.connect_timeout = 10  # 10 second timeout
        self.frame_queue = queue.Queue(maxsize=2)
        
    def connect_with_timeout(self):
        """Connect to camera with timeout"""
        def connect_worker():
            try:
                if not self.rtsp_url:
                    return False
                    
                print(f"Attempting to connect to: {self.rtsp_url}")
                cap = cv2.VideoCapture(self.rtsp_url)
                
                if cap is None:
                    return False
                    
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 15)
                
                # Try to read a frame to verify connection
                for i in range(3):  # Try 3 times
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        with self.lock:
                            if self.cap:
                                self.cap.release()
                            self.cap = cap
                            self.last_frame = frame
                            self.is_connected = True
                        print("Camera connected successfully")
                        return True
                    time.sleep(0.5)
                
                cap.release()
                return False
                
            except Exception as e:
                print(f"Camera connection error: {e}")
                return False
        
        # Use ThreadPoolExecutor with timeout
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(connect_worker)
                result = future.result(timeout=self.connect_timeout)
                return result
        except TimeoutError:
            print(f"Camera connection timeout after {self.connect_timeout} seconds")
            self.is_connected = False
            return False
        except Exception as e:
            print(f"Connection error: {e}")
            self.is_connected = False
            return False
    
    def start_capture_thread(self):
        """Start background thread for frame capture"""
        def capture_worker():
            self.running = True
            consecutive_failures = 0
            
            while self.running:
                try:
                    if not self.is_connected:
                        time.sleep(2)
                        continue
                    
                    with self.lock:
                        if self.cap is None or not self.cap.isOpened():
                            consecutive_failures += 1
                            if consecutive_failures > 5:
                                self.is_connected = False
                                consecutive_failures = 0
                            time.sleep(1)
                            continue
                        
                        ret, frame = self.cap.read()
                        if ret and frame is not None:
                            consecutive_failures = 0
                            self.last_frame = frame
                            
                            # Put frame in queue (non-blocking)
                            try:
                                self.frame_queue.put_nowait(frame.copy())
                            except queue.Full:
                                # Remove old frame and add new one
                                try:
                                    self.frame_queue.get_nowait()
                                    self.frame_queue.put_nowait(frame.copy())
                                except queue.Empty:
                                    pass
                        else:
                            consecutive_failures += 1
                            if consecutive_failures > 10:
                                print("Too many consecutive failures, disconnecting camera")
                                self.is_connected = False
                                consecutive_failures = 0
                    
                    time.sleep(0.1)  # 10 FPS max
                    
                except Exception as e:
                    print(f"Capture worker error: {e}")
                    consecutive_failures += 1
                    time.sleep(1)
        
        if not hasattr(self, 'capture_thread') or not self.capture_thread.is_alive():
            self.capture_thread = threading.Thread(target=capture_worker, daemon=True)
            self.capture_thread.start()
    
    def get_latest_frame(self):
        """Get latest frame from queue (non-blocking)"""
        try:
            # Get the most recent frame
            latest_frame = None
            while not self.frame_queue.empty():
                latest_frame = self.frame_queue.get_nowait()
            return latest_frame
        except queue.Empty:
            return self.last_frame
    
    def save_photo(self, filename):
        """Save current frame to file"""
        frame = self.get_latest_frame()
        if frame is not None:
            try:
                os.makedirs('photos', exist_ok=True)
                filepath = os.path.join('photos', filename)
                success = cv2.imwrite(filepath, frame)
                if success:
                    print(f"Photo saved: {filepath}")
                    return filepath
                else:
                    print("Failed to save photo")
            except Exception as e:
                print(f"Save photo error: {e}")
        return None
    
    def release(self):
        """Release camera resources"""
        self.running = False
        try:
            with self.lock:
                if self.cap:
                    self.cap.release()
                    self.cap = None
                self.is_connected = False
        except Exception as e:
            print(f"Release error: {e}")

class ParkingSystem:
    def __init__(self):
        self.parking_data = []
        self.settings = {
            'camera_masuk': '',
            'camera_keluar': ''
        }
        self.cameras = {}
        self.load_data()
        
    def load_data(self):
        try:
            if os.path.exists('parking_data.json'):
                with open('parking_data.json', 'r') as f:
                    self.parking_data = json.load(f)
            if os.path.exists('settings.json'):
                with open('settings.json', 'r') as f:
                    self.settings = json.load(f)
        except Exception as e:
            print(f"Load data error: {e}")
    
    def save_data(self):
        try:
            with open('parking_data.json', 'w') as f:
                json.dump(self.parking_data, f, indent=2)
            with open('settings.json', 'w') as f:
                json.dump(self.settings, f, indent=2)
            print("Data saved successfully")
        except Exception as e:
            print(f"Save data error: {e}")
    
    def generate_barcode(self):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    def get_camera(self, camera_type):
        camera_key = f'camera_{camera_type}'
        rtsp_url = self.settings.get(camera_key, '')
        
        if camera_type not in self.cameras:
            self.cameras[camera_type] = RobustCamera(rtsp_url)
        elif self.cameras[camera_type].rtsp_url != rtsp_url:
            self.cameras[camera_type].release()
            self.cameras[camera_type] = RobustCamera(rtsp_url)
        
        return self.cameras[camera_type]
    
    def add_vehicle(self):
        camera = self.get_camera('masuk')
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"masuk_{timestamp}.jpg"
        
        photo_path = camera.save_photo(filename)
        
        barcode = self.generate_barcode()
        vehicle_data = {
            'barcode': barcode,
            'tanggal_masuk': datetime.datetime.now().strftime('%Y-%m-%d'),
            'waktu_masuk': datetime.datetime.now().strftime('%H:%M:%S'),
            'foto_masuk': photo_path or f"photos/{filename}",
            'status': 'masuk'
        }
        
        self.parking_data.append(vehicle_data)
        self.save_data()
        return vehicle_data
    
    def exit_vehicle(self, barcode):
        for vehicle in self.parking_data:
            if vehicle['barcode'] == barcode and vehicle['status'] == 'masuk':
                camera = self.get_camera('keluar')
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"keluar_{timestamp}.jpg"
                
                photo_path = camera.save_photo(filename)
                
                vehicle['tanggal_keluar'] = datetime.datetime.now().strftime('%Y-%m-%d')
                vehicle['waktu_keluar'] = datetime.datetime.now().strftime('%H:%M:%S')
                vehicle['foto_keluar'] = photo_path or f"photos/{filename}"
                vehicle['status'] = 'keluar'
                
                # Calculate duration
                try:
                    masuk = datetime.datetime.strptime(f"{vehicle['tanggal_masuk']} {vehicle['waktu_masuk']}", '%Y-%m-%d %H:%M:%S')
                    keluar = datetime.datetime.strptime(f"{vehicle['tanggal_keluar']} {vehicle['waktu_keluar']}", '%Y-%m-%d %H:%M:%S')
                    duration = keluar - masuk
                    vehicle['durasi'] = str(duration)
                except Exception as e:
                    print(f"Duration calculation error: {e}")
                    vehicle['durasi'] = "Unknown"
                
                self.save_data()
                return vehicle
        return None
    
    def get_parked_vehicles(self):
        return [v for v in self.parking_data if v['status'] == 'masuk']
    
    def find_vehicle(self, barcode):
        for vehicle in self.parking_data:
            if vehicle['barcode'] == barcode and vehicle['status'] == 'masuk':
                return vehicle
        return None

class ParkingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🚗 Sistem Parkir - Robust Version")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')
        
        self.parking_system = ParkingSystem()
        self.current_barcode = None
        self.running = True
        self.ui_update_queue = queue.Queue()
        
        # Create GUI
        self.create_widgets()
        
        # Start background processes
        self.start_background_processes()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Handle Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        print("\nReceived interrupt signal, shutting down...")
        self.on_closing()
    
    def create_widgets(self):
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create tabs
        self.tab_masuk = ttk.Frame(self.notebook)
        self.tab_keluar = ttk.Frame(self.notebook)
        self.tab_admin = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_masuk, text='🚪 Pintu Masuk')
        self.notebook.add(self.tab_keluar, text='🚪 Pintu Keluar')
        self.notebook.add(self.tab_admin, text='⚙️ Admin')
        
        self.create_masuk_tab()
        self.create_keluar_tab()
        self.create_admin_tab()
    
    def create_masuk_tab(self):
        # Main frame
        main_frame = ttk.Frame(self.tab_masuk)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left side - Camera
        left_frame = ttk.LabelFrame(main_frame, text="📹 Kamera Masuk", padding="10")
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Camera display
        self.camera_masuk_label = tk.Label(left_frame, bg='gray', text='📷 Camera Starting...', 
                                          width=60, height=20, font=('Arial', 12))
        self.camera_masuk_label.pack(pady=10)
        
        # Camera status
        self.camera_masuk_status = tk.Label(left_frame, text="Status: Initializing...", 
                                           font=('Arial', 9), fg='orange')
        self.camera_masuk_status.pack()
        
        # Capture button
        self.capture_btn = tk.Button(left_frame, text="📸 Capture & Buka Pintu", 
                                   command=self.capture_masuk_async, bg='#4CAF50', fg='white',
                                   font=('Arial', 12, 'bold'), height=2, width=25)
        self.capture_btn.pack(pady=10)
        
        # Right side - Status
        right_frame = ttk.LabelFrame(main_frame, text="📋 Status & Info", padding="10")
        right_frame.pack(side='right', fill='both', expand=True)
        
        # Status display
        self.status_frame = tk.Frame(right_frame, bg='lightblue', relief='raised', bd=2)
        self.status_frame.pack(fill='both', expand=True, pady=10)
        
        self.status_label = tk.Label(self.status_frame, 
                                   text="⚡ Tekan tombol untuk memproses kendaraan masuk",
                                   font=('Arial', 12), bg='lightblue', wraplength=300)
        self.status_label.pack(expand=True)
    
    def create_keluar_tab(self):
        # Main frame
        main_frame = ttk.Frame(self.tab_keluar)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Top frame - Input and list
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Left side - Barcode input
        left_frame = ttk.LabelFrame(top_frame, text="🔍 Scan Barcode", padding="10")
        left_frame.pack(side='left', fill='y', padx=(0, 10))
        
        # Barcode input
        tk.Label(left_frame, text="Masukkan Barcode:", font=('Arial', 10, 'bold')).pack(anchor='w')
        self.barcode_entry = tk.Entry(left_frame, font=('Arial', 12), width=20)
        self.barcode_entry.pack(pady=5)
        self.barcode_entry.bind('<Return>', lambda e: self.cek_barcode_async())
        
        self.check_btn = tk.Button(left_frame, text="🔍 Cek Detail", command=self.cek_barcode_async,
                                 bg='#2196F3', fg='white', font=('Arial', 10, 'bold'))
        self.check_btn.pack(pady=5)
        
        # Vehicle details
        self.detail_frame = tk.Frame(left_frame, bg='lightgreen', relief='raised', bd=2)
        self.detail_label = tk.Label(self.detail_frame, text="", bg='lightgreen', 
                                   font=('Arial', 9), justify='left')
        
        # Exit button
        self.exit_btn = tk.Button(left_frame, text="🚪 Buka Pintu Keluar", 
                                command=self.proses_keluar_async, bg='#f44336', fg='white',
                                font=('Arial', 10, 'bold'), state='disabled')
        self.exit_btn.pack(pady=5)
        
        # Right side - Parking list
        right_frame = ttk.LabelFrame(top_frame, text="🚗 Kendaraan Sedang Parkir", padding="10")
        right_frame.pack(side='right', fill='both', expand=True)
        
        # Treeview for parking list
        columns = ('Barcode', 'Tanggal', 'Waktu', 'Durasi')
        self.parking_tree = ttk.Treeview(right_frame, columns=columns, show='headings', height=12)
        
        for col in columns:
            self.parking_tree.heading(col, text=col)
            self.parking_tree.column(col, width=100)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(right_frame, orient='vertical', command=self.parking_tree.yview)
        self.parking_tree.configure(yscrollcommand=scrollbar.set)
        
        self.parking_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Quick exit button
        self.parking_tree.bind('<Double-1>', self.on_tree_double_click)
        
        # Bottom frame - Camera keluar
        bottom_frame = ttk.LabelFrame(main_frame, text="📹 Kamera Keluar", padding="10")
        bottom_frame.pack(fill='x')
        
        self.camera_keluar_label = tk.Label(bottom_frame, bg='gray', text='📷 Camera Starting...', 
                                          width=80, height=15, font=('Arial', 10))
        self.camera_keluar_label.pack()
        
        self.camera_keluar_status = tk.Label(bottom_frame, text="Status: Initializing...", 
                                           font=('Arial', 9), fg='orange')
        self.camera_keluar_status.pack()
    
    def create_admin_tab(self):
        main_frame = ttk.Frame(self.tab_admin)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title
        title_label = tk.Label(main_frame, text="⚙️ Admin Settings", 
                             font=('Arial', 16, 'bold'), bg='#f0f0f0')
        title_label.pack(pady=(0, 20))
        
        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="📹 Konfigurasi Kamera", padding="15")
        settings_frame.pack(fill='x', pady=(0, 20))
        
        # Camera masuk
        tk.Label(settings_frame, text="🚪 Kamera Pintu Masuk (RTSP URL):", 
                font=('Arial', 10, 'bold')).pack(anchor='w')
        self.camera_masuk_entry = tk.Entry(settings_frame, font=('Arial', 10), width=60)
        self.camera_masuk_entry.pack(pady=(5, 10), fill='x')
        self.camera_masuk_entry.insert(0, self.parking_system.settings.get('camera_masuk', ''))
        
        # Camera keluar  
        tk.Label(settings_frame, text="🚪 Kamera Pintu Keluar (RTSP URL):", 
                font=('Arial', 10, 'bold')).pack(anchor='w')
        self.camera_keluar_entry = tk.Entry(settings_frame, font=('Arial', 10), width=60)
        self.camera_keluar_entry.pack(pady=(5, 10), fill='x')
        self.camera_keluar_entry.insert(0, self.parking_system.settings.get('camera_keluar', ''))
        
        # Buttons frame
        btn_frame = tk.Frame(settings_frame)
        btn_frame.pack(fill='x', pady=10)
        
        self.save_btn = tk.Button(btn_frame, text="💾 Simpan Pengaturan", 
                                command=self.save_settings_async, bg='#4CAF50', fg='white',
                                font=('Arial', 10, 'bold'), width=20)
        self.save_btn.pack(side='left', padx=(0, 10))
        
        self.test_btn = tk.Button(btn_frame, text="🔧 Test Koneksi", 
                                command=self.test_cameras_async, bg='#2196F3', fg='white',
                                font=('Arial', 10, 'bold'), width=20)
        self.test_btn.pack(side='left')
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="📊 System Status", padding="15")
        status_frame.pack(fill='x')
        
        self.status_masuk_label = tk.Label(status_frame, text="Kamera Masuk: Initializing...", 
                                         font=('Arial', 10), fg='orange')
        self.status_masuk_label.pack(anchor='w', pady=2)
        
        self.status_keluar_label = tk.Label(status_frame, text="Kamera Keluar: Initializing...", 
                                          font=('Arial', 10), fg='orange')
        self.status_keluar_label.pack(anchor='w', pady=2)
        
        # Instructions
        instructions = tk.Label(status_frame, 
                              text="💡 Tips: Gunakan webcam dengan URL: 0 atau 1\n"
                                   "Untuk RTSP: rtsp://username:password@ip:port/path",
                              font=('Arial', 9), fg='gray', justify='left')
        instructions.pack(anchor='w', pady=10)
    
    def start_background_processes(self):
        """Start all background threads"""
        # UI update thread
        def ui_update_worker():
            while self.running:
                try:
                    # Process UI update queue
                    try:
                        update_func = self.ui_update_queue.get_nowait()
                        self.root.after_idle(update_func)
                    except queue.Empty:
                        pass
                    
                    # Update parking list
                    self.root.after_idle(self.update_parking_list)
                    
                    time.sleep(1)
                except Exception as e:
                    print(f"UI update worker error: {e}")
                    time.sleep(2)
        
        threading.Thread(target=ui_update_worker, daemon=True).start()
        
        # Camera display update thread
        def camera_display_worker():
            while self.running:
                try:
                    # Update masuk camera display
                    camera_masuk = self.parking_system.get_camera('masuk')
                    frame = camera_masuk.get_latest_frame()
                    if frame is not None:
                        try:
                            frame_resized = cv2.resize(frame, (480, 360))
                            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                            img = Image.fromarray(frame_rgb)
                            photo = ImageTk.PhotoImage(image=img)
                            
                            def update_masuk():
                                self.camera_masuk_label.configure(image=photo, text="")
                                self.camera_masuk_label.image = photo
                                self.camera_masuk_status.configure(text="Status: ✅ Connected", fg='green')
                            
                            self.root.after_idle(update_masuk)
                        except Exception as e:
                            print(f"Masuk camera display error: {e}")
                    else:
                        def update_masuk_disconnected():
                            self.camera_masuk_label.configure(image="", text="📷 No Signal")
                            self.camera_masuk_status.configure(text="Status: ❌ Disconnected", fg='red')
                        self.root.after_idle(update_masuk_disconnected)
                    
                    # Update keluar camera display  
                    camera_keluar = self.parking_system.get_camera('keluar')
                    frame = camera_keluar.get_latest_frame()
                    if frame is not None:
                        try:
                            frame_resized = cv2.resize(frame, (640, 240))
                            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                            img = Image.fromarray(frame_rgb)
                            photo = ImageTk.PhotoImage(image=img)
                            
                            def update_keluar():
                                self.camera_keluar_label.configure(image=photo, text="")
                                self.camera_keluar_label.image = photo
                                self.camera_keluar_status.configure(text="Status: ✅ Connected", fg='green')
                            
                            self.root.after_idle(update_keluar)
                        except Exception as e:
                            print(f"Keluar camera display error: {e}")
                    else:
                        def update_keluar_disconnected():
                            self.camera_keluar_label.configure(image="", text="📷 No Signal")
                            self.camera_keluar_status.configure(text="Status: ❌ Disconnected", fg='red')
                        self.root.after_idle(update_keluar_disconnected)
                    
                    time.sleep(0.2)  # 5 FPS
                except Exception as e:
                    print(f"Camera display worker error: {e}")
                    time.sleep(1)
        
        threading.Thread(target=camera_display_worker, daemon=True).start()
        
        # Initialize cameras
        def init_cameras():
            time.sleep(2)  # Wait for UI to stabilize
            
            for camera_type in ['masuk', 'keluar']:
                try:
                    camera = self.parking_system.get_camera(camera_type)
                    if camera.rtsp_url:
                        print(f"Initializing {camera_type} camera...")
                        success = camera.connect_with_timeout()
                        if success:
                            camera.start_capture_thread()
                            print(f"{camera_type} camera initialized successfully")
                        else:
                            print(f"Failed to initialize {camera_type} camera")
                except Exception as e:
                    print(f"Camera initialization error for {camera_type}: {e}")
        
        threading.Thread(target=init_cameras, daemon=True).start()
    
    def capture_masuk_async(self):
        """Async capture to prevent UI blocking"""
        def capture_worker():
            try:
                print("Processing vehicle entry...")
                vehicle = self.parking_system.add_vehicle()
                
                def update_ui():
                    status_text = f"✅ BERHASIL MASUK!\n\n" \
                                 f"Barcode: {vehicle['barcode']}\n" \
                                 f"Tanggal: {vehicle['tanggal_masuk']}\n" \
                                 f"Waktu: {vehicle['waktu_masuk']}\n\n" \
                                 f"📸 Foto: {os.path.basename(vehicle['foto_masuk'])}"
                    
                    self.status_label.configure(text=status_text, bg='lightgreen')
                    self.status_frame.configure(bg='lightgreen')
                    messagebox.showinfo("Sukses", "✅ Kendaraan berhasil masuk!\n🚪 Palang terbuka!")
                    
                    # Reset after 5 seconds
                    self.root.after(5000, self.reset_masuk_status)
                
                self.root.after_idle(update_ui)
                
            except Exception as e:
                print(f"Capture error: {e}")
                def show_error():
                    messagebox.showerror("Error", f"❌ Error: {str(e)}")
                self.root.after_idle(show_error)
        
        threading.Thread(target=capture_worker, daemon=True).start()
    
    def cek_barcode_async(self):
        """Async barcode check"""
        def check_worker():
            try:
                barcode = self.barcode_entry.get().strip()
                if not barcode:
                    self.root.after_idle(lambda: messagebox.showerror("Error", "❌ Barcode tidak boleh kosong!"))
                    return
                
                vehicle = self.parking_system.find_vehicle(barcode)
                if not vehicle:
                    def update_ui():
                        messagebox.showerror("Error", "❌ Barcode tidak ditemukan!")
                        self.detail_frame.pack_forget()
                        self.exit_btn.configure(state='disabled')
                    self.root.after_idle(update_ui)
                    return
                
                # Calculate current duration
                masuk_time = datetime.datetime.strptime(f"{vehicle['tanggal_masuk']} {vehicle['waktu_masuk']}", '%Y-%m-%d %H:%M:%S')
                now = datetime.datetime.now()
                duration = now - masuk_time
                duration_str = str(duration).split('.')[0]
                
                def update_ui():
                    detail_text = f"✅ DETAIL KENDARAAN\n\n" \
                                 f"Barcode: {vehicle['barcode']}\n" \
                                 f"Tanggal Masuk: {vehicle['tanggal_masuk']}\n" \
                                 f"Waktu Masuk: {vehicle['waktu_masuk']}\n" \
                                 f"Durasi: {duration_str}"
                    
                    self.detail_label.configure(text=detail_text)
                    self.detail_frame.pack(fill='x', pady=10)
                    self.detail_label.pack(padx=10, pady=10)
                    
                    self.exit_btn.configure(state='normal')
                    self.current_barcode = barcode
                    messagebox.showinfo("Sukses", "✅ Kendaraan ditemukan!")
                
                self.root.after_idle(update_ui)
                
            except Exception as e:
                print(f"Check barcode error: {e}")
                def show_error():
                    messagebox.showerror("Error", f"❌ Error: {str(e)}")
                self.root.after_idle(show_error)
        
        threading.Thread(target=check_worker, daemon=True).start()
    
    def proses_keluar_async(self):
        """Async exit process"""
        def exit_worker():
            try:
                print(f"Processing exit for: {self.current_barcode}")
                vehicle = self.parking_system.exit_vehicle(self.current_barcode)
                
                def update_ui():
                    if vehicle:
                        messagebox.showinfo("Sukses", "✅ Kendaraan berhasil keluar!\n🚪 Palang terbuka!")
                        
                        # Reset form
                        self.barcode_entry.delete(0, tk.END)
                        self.detail_frame.pack_forget()
                        self.exit_btn.configure(state='disabled')
                        self.current_barcode = None
                        
                        # Update parking list will be handled by background thread
                    else:
                        messagebox.showerror("Error", "❌ Gagal memproses kendaraan keluar!")
                
                self.root.after_idle(update_ui)
                
            except Exception as e:
                print(f"Exit error: {e}")
                def show_error():
                    messagebox.showerror("Error", f"❌ Error: {str(e)}")
                self.root.after_idle(show_error)
        
        threading.Thread(target=exit_worker, daemon=True).start()
    
    def save_settings_async(self):
        """Async save settings"""
        def save_worker():
            try:
                # Get values from UI
                camera_masuk_url = self.camera_masuk_entry.get()
                camera_keluar_url = self.camera_keluar_entry.get()
                
                # Save settings
                self.parking_system.settings['camera_masuk'] = camera_masuk_url
                self.parking_system.settings['camera_keluar'] = camera_keluar_url
                self.parking_system.save_data()
                
                # Restart cameras
                for camera in self.parking_system.cameras.values():
                    camera.release()
                self.parking_system.cameras.clear()
                
                # Reinitialize cameras
                time.sleep(1)
                for camera_type in ['masuk', 'keluar']:
                    camera = self.parking_system.get_camera(camera_type)
                    if camera.rtsp_url:
                        success = camera.connect_with_timeout()
                        if success:
                            camera.start_capture_thread()
                
                def update_ui():
                    messagebox.showinfo("Sukses", "✅ Pengaturan berhasil disimpan!")
                    self.update_camera_status()
                
                self.root.after_idle(update_ui)
                
            except Exception as e:
                print(f"Save settings error: {e}")
                def show_error():
                    messagebox.showerror("Error", f"❌ Error: {str(e)}")
                self.root.after_idle(show_error)
        
        threading.Thread(target=save_worker, daemon=True).start()
    
    def test_cameras_async(self):
        """Async camera test"""
        def test_worker():
            try:
                results = {}
                for camera_type in ['masuk', 'keluar']:
                    camera = self.parking_system.get_camera(camera_type)
                    success = camera.connect_with_timeout()
                    results[camera_type] = success
                    if success:
                        camera.start_capture_thread()
                
                success_count = sum(results.values())
                
                if success_count == 2:
                    message = "✅ Semua kamera terhubung dengan baik!"
                elif success_count == 1:
                    message = "⚠️ Hanya 1 kamera yang terhubung"
                else:
                    message = "❌ Tidak ada kamera yang terhubung"
                
                def update_ui():
                    messagebox.showinfo("Test Result", message)
                    self.update_camera_status()
                
                self.root.after_idle(update_ui)
                
            except Exception as e:
                print(f"Test cameras error: {e}")
                def show_error():
                    messagebox.showerror("Error", f"❌ Test error: {str(e)}")
                self.root.after_idle(show_error)
        
        threading.Thread(target=test_worker, daemon=True).start()
    
    def update_parking_list(self):
        """Update parking list (runs in UI thread)"""
        try:
            # Clear existing items
            for item in self.parking_tree.get_children():
                self.parking_tree.delete(item)
            
            # Add current vehicles
            vehicles = self.parking_system.get_parked_vehicles()
            for vehicle in vehicles:
                try:
                    # Calculate current duration
                    masuk_time = datetime.datetime.strptime(f"{vehicle['tanggal_masuk']} {vehicle['waktu_masuk']}", '%Y-%m-%d %H:%M:%S')
                    now = datetime.datetime.now()
                    duration = now - masuk_time
                    duration_str = str(duration).split('.')[0]
                    
                    self.parking_tree.insert('', 'end', values=(
                        vehicle['barcode'],
                        vehicle['tanggal_masuk'],
                        vehicle['waktu_masuk'],
                        duration_str
                    ))
                except Exception as e:
                    print(f"Vehicle processing error: {e}")
                    
        except Exception as e:
            print(f"Update parking list error: {e}")
    
    def update_camera_status(self):
        """Update camera status indicators"""
        try:
            # Check masuk camera
            camera_masuk = self.parking_system.get_camera('masuk')
            if camera_masuk.is_connected:
                self.status_masuk_label.configure(text="Kamera Masuk: ✅ Online", fg='green')
            else:
                self.status_masuk_label.configure(text="Kamera Masuk: ❌ Offline", fg='red')
            
            # Check keluar camera
            camera_keluar = self.parking_system.get_camera('keluar')
            if camera_keluar.is_connected:
                self.status_keluar_label.configure(text="Kamera Keluar: ✅ Online", fg='green')
            else:
                self.status_keluar_label.configure(text="Kamera Keluar: ❌ Offline", fg='red')
                
        except Exception as e:
            print(f"Status update error: {e}")
    
    def reset_masuk_status(self):
        """Reset entry status display"""
        self.status_label.configure(text="⚡ Tekan tombol untuk memproses kendaraan masuk", 
                                  bg='lightblue')
        self.status_frame.configure(bg='lightblue')
    
    def on_tree_double_click(self, event):
        """Handle double-click on parking list"""
        try:
            item = self.parking_tree.selection()[0]
            barcode = self.parking_tree.item(item, "values")[0]
            self.barcode_entry.delete(0, tk.END)
            self.barcode_entry.insert(0, barcode)
            self.cek_barcode_async()
        except Exception as e:
            print(f"Tree click error: {e}")
    
    def on_closing(self):
        """Handle application closing"""
        print("Shutting down application...")
        self.running = False
        
        # Release cameras
        try:
            for camera in self.parking_system.cameras.values():
                camera.release()
        except Exception as e:
            print(f"Camera release error: {e}")
        
        try:
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            print(f"Shutdown error: {e}")
        
        # Force exit if needed
        os._exit(0)

if __name__ == "__main__":
    print("🚗 Starting Robust Parking System...")
    print("📁 Data saved to: parking_data.json & settings.json")
    print("📸 Photos saved to: photos/ folder")
    print("💡 Use webcam: 0 or 1, RTSP: rtsp://user:pass@ip:port/path")
    print("🔧 Camera timeout: 10 seconds per connection attempt")
    
    try:
        root = tk.Tk()
        app = ParkingApp(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt")
        sys.exit(0)
    except Exception as e:
        print(f"Application error: {e}")
        input("Press Enter to exit...")