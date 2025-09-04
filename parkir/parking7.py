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
        self.connect_timeout = 10
        self.frame_queue = queue.Queue(maxsize=2)
        
    def connect_with_timeout(self):
        def connect_worker():
            try:
                if not self.rtsp_url:
                    return False
                    
                print(f"Connecting to: {self.rtsp_url}")
                cap = cv2.VideoCapture(self.rtsp_url)
                
                if cap is None:
                    return False
                    
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 15)
                
                for i in range(3):
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
                            
                            try:
                                self.frame_queue.put_nowait(frame.copy())
                            except queue.Full:
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
                    
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"Capture worker error: {e}")
                    consecutive_failures += 1
                    time.sleep(1)
        
        if not hasattr(self, 'capture_thread') or not self.capture_thread.is_alive():
            self.capture_thread = threading.Thread(target=capture_worker, daemon=True)
            self.capture_thread.start()
    
    def get_latest_frame(self):
        try:
            latest_frame = None
            while not self.frame_queue.empty():
                latest_frame = self.frame_queue.get_nowait()
            return latest_frame
        except queue.Empty:
            return self.last_frame
    
    def save_photo(self, filename):
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
        self.rfid_members = []
        self.settings = {
            'camera_masuk': '',
            'camera_keluar': '',
            'tarif_per_jam': 2000
        }
        self.cameras = {}
        self.load_data()
        
    def load_data(self):
        try:
            if os.path.exists('parking_data.json'):
                with open('parking_data.json', 'r') as f:
                    self.parking_data = json.load(f)
            if os.path.exists('rfid_members.json'):
                with open('rfid_members.json', 'r') as f:
                    self.rfid_members = json.load(f)
            if os.path.exists('settings.json'):
                with open('settings.json', 'r') as f:
                    self.settings = json.load(f)
        except Exception as e:
            print(f"Load data error: {e}")
    
    def save_data(self):
        try:
            with open('parking_data.json', 'w') as f:
                json.dump(self.parking_data, f, indent=2)
            with open('rfid_members.json', 'w') as f:
                json.dump(self.rfid_members, f, indent=2)
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
    
    def find_member_by_rfid(self, rfid_id):
        for member in self.rfid_members:
            if member['rfid_id'] == rfid_id:
                return member
        return None
    
    def add_vehicle(self, rfid_id=None, plat_nomor="", member_info=None):
        camera = self.get_camera('masuk')
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"masuk_{timestamp}.jpg"
        
        photo_path = camera.save_photo(filename)
        
        barcode = self.generate_barcode()
        vehicle_data = {
            'barcode': barcode,
            'rfid_id': rfid_id,
            'plat_nomor': plat_nomor,
            'member_info': member_info,
            'tanggal_masuk': datetime.datetime.now().strftime('%Y-%m-%d'),
            'waktu_masuk': datetime.datetime.now().strftime('%H:%M:%S'),
            'foto_masuk': photo_path or f"photos/{filename}",
            'status': 'masuk',
            'is_member': member_info is not None
        }
        
        self.parking_data.append(vehicle_data)
        self.save_data()
        return vehicle_data
    
    def exit_vehicle(self, barcode, exit_photo_path=None, nopol_keluar=None):
        for vehicle in self.parking_data:
            if vehicle['barcode'] == barcode and vehicle['status'] == 'masuk':
                # Use provided photo path or create default filename
                if exit_photo_path:
                    photo_path = exit_photo_path
                else:
                    # Fallback: try to save from camera if no photo path provided
                    camera = self.get_camera('keluar')
                    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"keluar_{timestamp}.jpg"
                    photo_path = camera.save_photo(filename)
                
                vehicle['tanggal_keluar'] = datetime.datetime.now().strftime('%Y-%m-%d')
                vehicle['waktu_keluar'] = datetime.datetime.now().strftime('%H:%M:%S')
                vehicle['foto_keluar'] = photo_path or f"photos/keluar_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                vehicle['nopol_keluar'] = nopol_keluar or "N/A"  # Store exit license plate
                vehicle['status'] = 'keluar'
                
                # Calculate duration and cost
                try:
                    masuk = datetime.datetime.strptime(f"{vehicle['tanggal_masuk']} {vehicle['waktu_masuk']}", '%Y-%m-%d %H:%M:%S')
                    keluar = datetime.datetime.strptime(f"{vehicle['tanggal_keluar']} {vehicle['waktu_keluar']}", '%Y-%m-%d %H:%M:%S')
                    duration = keluar - masuk
                    vehicle['durasi'] = str(duration)
                    
                    # Calculate cost based on hours (minimum 1 hour)
                    hours = max(1, int(duration.total_seconds() / 3600))
                    if duration.total_seconds() % 3600 > 0:  # If there's remaining time, add 1 hour
                        hours += 1
                    
                    base_cost = hours * self.settings.get('tarif_per_jam', 2000)
                    if vehicle.get('is_member', False):
                        vehicle['biaya'] = int(base_cost * 0.8)  # 20% discount for members
                    else:
                        vehicle['biaya'] = base_cost
                        
                except Exception as e:
                    print(f"Duration calculation error: {e}")
                    vehicle['durasi'] = "Unknown"
                    vehicle['biaya'] = 0
                
                self.save_data()
                return vehicle
        return None
    
    def get_parked_vehicles(self):
        return [v for v in self.parking_data if v['status'] == 'masuk']
    
    def get_exited_vehicles(self):
        return [v for v in self.parking_data if v['status'] == 'keluar']
    
    def find_vehicle(self, barcode):
        for vehicle in self.parking_data:
            if vehicle['barcode'] == barcode:
                return vehicle
        return None
    
    def find_vehicle_by_rfid(self, rfid_id):
        for vehicle in self.parking_data:
            if vehicle.get('rfid_id') == rfid_id and vehicle['status'] == 'masuk':
                return vehicle
        return None
    
    def add_member(self, rfid_id, nama, plat_nomor, telepon=""):
        member_data = {
            'rfid_id': rfid_id,
            'nama': nama,
            'plat_nomor': plat_nomor,
            'telepon': telepon,
            'tanggal_daftar': datetime.datetime.now().strftime('%Y-%m-%d'),
            'status': 'aktif'
        }
        self.rfid_members.append(member_data)
        self.save_data()
        return member_data
    
    def update_member(self, rfid_id, nama, plat_nomor, telepon=""):
        for member in self.rfid_members:
            if member['rfid_id'] == rfid_id:
                member['nama'] = nama
                member['plat_nomor'] = plat_nomor
                member['telepon'] = telepon
                self.save_data()
                return member
        return None
    
    def delete_member(self, rfid_id):
        for i, member in enumerate(self.rfid_members):
            if member['rfid_id'] == rfid_id:
                del self.rfid_members[i]
                self.save_data()
                return True
        return False

class ParkingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PLAZA PONDOK GEDE - Parking System")
        self.root.geometry("1600x900")
        self.root.configure(bg='#E3F2FD')
        self.root.minsize(1400, 800)
        
        self.parking_system = ParkingSystem()
        self.current_barcode = None
        self.running = True
        self.temp_exit_photo = None  # Store exit screenshot in RAM temporarily
        
        # Create main interface
        self.create_main_interface()
        
        # Start background processes
        self.start_background_processes()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        print("\nShutting down...")
        self.on_closing()
    
    def create_main_interface(self):
        # Create notebook for different pages
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create pages
        self.page_masuk = ttk.Frame(self.notebook)
        self.page_keluar = ttk.Frame(self.notebook)
        self.page_history = ttk.Frame(self.notebook)
        self.page_settings = ttk.Frame(self.notebook)
        
        self.notebook.add(self.page_masuk, text='PINTU MASUK')
        self.notebook.add(self.page_keluar, text='PINTU KELUAR')
        self.notebook.add(self.page_history, text='HISTORY')
        self.notebook.add(self.page_settings, text='SETTINGS')
        
        self.create_entry_page()
        self.create_exit_page()
        self.create_history_page()
        self.create_settings_page()
    
    def create_entry_page(self):
        # Main container
        main_frame = tk.Frame(self.page_masuk, bg='#E3F2FD')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title
        title_frame = tk.Frame(main_frame, bg='#E3F2FD')
        title_frame.pack(fill='x', pady=(0, 20))
        
        title_label = tk.Label(title_frame, text="PLAZA PONDOK GEDE", 
                             font=('Arial', 20, 'bold'), bg='#E3F2FD')
        title_label.pack()
        
        datetime_label = tk.Label(title_frame, text="", 
                                font=('Arial', 12), bg='#E3F2FD')
        datetime_label.pack()
        self.datetime_label_masuk = datetime_label
        
        # Content area
        content_frame = tk.Frame(main_frame, bg='#E3F2FD')
        content_frame.pack(fill='both', expand=True)
        
        # Left side - Form
        left_frame = tk.Frame(content_frame, bg='#E3F2FD')
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 20))
        
        # RFID Section
        rfid_frame = tk.LabelFrame(left_frame, text="ID RFID (Member)", 
                                 font=('Arial', 12, 'bold'), bg='#E3F2FD')
        rfid_frame.pack(fill='x', pady=(0, 10))
        
        self.rfid_entry = tk.Entry(rfid_frame, font=('Arial', 14), width=30)
        self.rfid_entry.pack(padx=10, pady=10)
        self.rfid_entry.bind('<Return>', self.check_rfid_member)
        
        check_rfid_btn = tk.Button(rfid_frame, text="CEK MEMBER", 
                                 command=self.check_rfid_member,
                                 bg='#2196F3', fg='white', font=('Arial', 10, 'bold'))
        check_rfid_btn.pack(pady=(0, 10))
        
        # Member info display
        self.member_info_frame = tk.Frame(rfid_frame, bg='lightgreen')
        self.member_info_label = tk.Label(self.member_info_frame, text="", 
                                        bg='lightgreen', font=('Arial', 10))
        
        # Vehicle Details
        details_frame = tk.LabelFrame(left_frame, text="Detail Kendaraan", 
                                    font=('Arial', 12, 'bold'), bg='#E3F2FD')
        details_frame.pack(fill='x', pady=(0, 10))
        
        # Plate number
        tk.Label(details_frame, text="NoBarcode:", font=('Arial', 10), 
               bg='#E3F2FD').grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.barcode_display = tk.Label(details_frame, text="-", font=('Arial', 10), 
                                      bg='white', relief='sunken', width=20)
        self.barcode_display.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(details_frame, text="Nomor Kartu:", font=('Arial', 10), 
               bg='#E3F2FD').grid(row=1, column=0, sticky='w', padx=10, pady=5)
        self.plat_entry = tk.Entry(details_frame, font=('Arial', 10), width=20)
        self.plat_entry.grid(row=1, column=1, padx=10, pady=5)
        
        tk.Label(details_frame, text="Waktu Masuk:", font=('Arial', 10), 
               bg='#E3F2FD').grid(row=2, column=0, sticky='w', padx=10, pady=5)
        self.waktu_masuk_display = tk.Label(details_frame, text="-", font=('Arial', 10), 
                                          bg='white', relief='sunken', width=20)
        self.waktu_masuk_display.grid(row=2, column=1, padx=10, pady=5)
        
        tk.Label(details_frame, text="Jenis:", font=('Arial', 10), 
               bg='#E3F2FD').grid(row=3, column=0, sticky='w', padx=10, pady=5)
        self.jenis_display = tk.Label(details_frame, text="-", font=('Arial', 10), 
                                    bg='white', relief='sunken', width=20)
        self.jenis_display.grid(row=3, column=1, padx=10, pady=5)
        
        # Process button
        self.process_entry_btn = tk.Button(left_frame, text="PROSES MASUK", 
                                         command=self.process_entry_async,
                                         bg='#4CAF50', fg='white', 
                                         font=('Arial', 14, 'bold'), height=2)
        self.process_entry_btn.pack(fill='x', pady=10)
        
        # Right side - Cameras
        right_frame = tk.Frame(content_frame, bg='#E3F2FD')
        right_frame.pack(side='right', fill='both', expand=True)
        
        # Entry camera
        camera_frame = tk.LabelFrame(right_frame, text="GAMBAR MASUK", 
                                   font=('Arial', 12, 'bold'), bg='#E3F2FD')
        camera_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        self.camera_masuk_label = tk.Label(camera_frame, bg='gray', text='Camera Loading...', 
                                         width=50, height=25)
        self.camera_masuk_label.pack(fill='both', expand=True, padx=10, pady=10)
    
    def create_exit_page(self):
        # Main container matching entry page design
        main_frame = tk.Frame(self.page_keluar, bg='#E3F2FD')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title
        title_frame = tk.Frame(main_frame, bg='#E3F2FD')
        title_frame.pack(fill='x', pady=(0, 20))
        
        title_label = tk.Label(title_frame, text="PLAZA PONDOK GEDE", 
                             font=('Arial', 20, 'bold'), bg='#E3F2FD')
        title_label.pack()
        
        datetime_label = tk.Label(title_frame, text="", 
                                font=('Arial', 12), bg='#E3F2FD')
        datetime_label.pack()
        self.datetime_label_keluar = datetime_label
        
        # Content area
        content_frame = tk.Frame(main_frame, bg='#E3F2FD')
        content_frame.pack(fill='both', expand=True)
        
        # Left side - Form
        left_frame = tk.Frame(content_frame, bg='#E3F2FD')
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 20))
        
        # Search section with improved layout
        search_frame = tk.LabelFrame(left_frame, text="PENCARIAN KENDARAAN", 
                                   font=('Arial', 12, 'bold'), bg='#E3F2FD')
        search_frame.pack(fill='x', pady=(0, 10))
        
        # Barcode search row
        barcode_row = tk.Frame(search_frame, bg='#E3F2FD')
        barcode_row.pack(fill='x', padx=10, pady=(10, 5))
        
        tk.Label(barcode_row, text="NoBarcode:", font=('Arial', 10), 
               bg='#E3F2FD', width=12).pack(side='left')
        self.barcode_search_entry = tk.Entry(barcode_row, font=('Arial', 12), width=25)
        self.barcode_search_entry.pack(side='left', padx=(0, 10))
        self.barcode_search_entry.bind('<Return>', self.search_by_barcode_async)
        
        search_barcode_btn = tk.Button(barcode_row, text="CARI", 
                                     command=self.search_by_barcode_async,
                                     bg='#2196F3', fg='white', font=('Arial', 9, 'bold'), width=8)
        search_barcode_btn.pack(side='left')
        
        # RFID search row
        rfid_row = tk.Frame(search_frame, bg='#E3F2FD')
        rfid_row.pack(fill='x', padx=10, pady=(5, 10))
        
        tk.Label(rfid_row, text="RFID ID:", font=('Arial', 10), 
               bg='#E3F2FD', width=12).pack(side='left')
        self.rfid_search_entry = tk.Entry(rfid_row, font=('Arial', 12), width=25)
        self.rfid_search_entry.pack(side='left', padx=(0, 10))
        self.rfid_search_entry.bind('<Return>', self.search_by_rfid_async)
        
        search_rfid_btn = tk.Button(rfid_row, text="CARI", 
                                  command=self.search_by_rfid_async,
                                  bg='#FF9800', fg='white', font=('Arial', 9, 'bold'), width=8)
        search_rfid_btn.pack(side='left')
        
        # Clear button row
        clear_row = tk.Frame(search_frame, bg='#E3F2FD')
        clear_row.pack(fill='x', padx=10, pady=(0, 10))
        
        clear_search_btn = tk.Button(clear_row, text="CLEAR SEMUA", 
                                   command=self.clear_search_fields,
                                   bg='#9E9E9E', fg='white', font=('Arial', 9, 'bold'))
        clear_search_btn.pack()
        
        # Vehicle details
        details_frame = tk.LabelFrame(left_frame, text="Detail Kendaraan", 
                                    font=('Arial', 12, 'bold'), bg='#E3F2FD')
        details_frame.pack(fill='x', pady=(0, 10))
        
        # Details grid
        tk.Label(details_frame, text="NoBarcode:", font=('Arial', 10), 
               bg='#E3F2FD').grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.exit_barcode_display = tk.Label(details_frame, text="-", font=('Arial', 10), 
                                           bg='white', relief='sunken', width=20)
        self.exit_barcode_display.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(details_frame, text="Nomor Kartu:", font=('Arial', 10), 
               bg='#E3F2FD').grid(row=1, column=0, sticky='w', padx=10, pady=5)
        self.exit_plat_display = tk.Label(details_frame, text="-", font=('Arial', 10), 
                                        bg='white', relief='sunken', width=20)
        self.exit_plat_display.grid(row=1, column=1, padx=10, pady=5)
        
        tk.Label(details_frame, text="Waktu Masuk:", font=('Arial', 10), 
               bg='#E3F2FD').grid(row=2, column=0, sticky='w', padx=10, pady=5)
        self.exit_waktu_masuk_display = tk.Label(details_frame, text="-", font=('Arial', 10), 
                                               bg='white', relief='sunken', width=20)
        self.exit_waktu_masuk_display.grid(row=2, column=1, padx=10, pady=5)
        
        tk.Label(details_frame, text="Waktu Keluar:", font=('Arial', 10), 
               bg='#E3F2FD').grid(row=3, column=0, sticky='w', padx=10, pady=5)
        self.exit_waktu_keluar_display = tk.Label(details_frame, text="-", font=('Arial', 10), 
                                                bg='white', relief='sunken', width=20)
        self.exit_waktu_keluar_display.grid(row=3, column=1, padx=10, pady=5)
        
        tk.Label(details_frame, text="HTG:", font=('Arial', 10), 
               bg='#E3F2FD').grid(row=4, column=0, sticky='w', padx=10, pady=5)
        self.htg_display = tk.Label(details_frame, text="-", font=('Arial', 10), 
                                  bg='white', relief='sunken', width=20)
        self.htg_display.grid(row=4, column=1, padx=10, pady=5)
        
        # License plate input for exit (REQUIRED)
        tk.Label(details_frame, text="No. Polisi:", font=('Arial', 10, 'bold'), 
               bg='#E3F2FD', fg='red').grid(row=5, column=0, sticky='w', padx=10, pady=5)
        self.nopol_exit_entry = tk.Entry(details_frame, font=('Arial', 10), width=20)
        self.nopol_exit_entry.grid(row=5, column=1, padx=10, pady=5)
        self.nopol_exit_entry.bind('<KeyRelease>', self.validate_exit_form)
        
        # Cost display
        self.cost_frame = tk.Frame(left_frame, bg='#4CAF50')
        self.cost_frame.pack(fill='x', pady=10)
        
        self.cost_label = tk.Label(self.cost_frame, text="Rp.0,-", 
                                 font=('Arial', 20, 'bold'), 
                                 bg='#4CAF50', fg='white')
        self.cost_label.pack(pady=10)
        
        # Exit button
        self.process_exit_btn = tk.Button(left_frame, text="PROSES KELUAR", 
                                        command=self.process_exit_async,
                                        bg='#f44336', fg='white', 
                                        font=('Arial', 14, 'bold'), height=2,
                                        state='disabled')
        self.process_exit_btn.pack(fill='x', pady=10)
        
        # Right side - Cameras
        right_frame = tk.Frame(content_frame, bg='#E3F2FD')
        right_frame.pack(side='right', fill='both', expand=True)
        
        # Entry photo (from search)
        entry_photo_frame = tk.LabelFrame(right_frame, text="GAMBAR MASUK", 
                                        font=('Arial', 12, 'bold'), bg='#E3F2FD')
        entry_photo_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        self.entry_photo_display = tk.Label(entry_photo_frame, bg='lightgray', 
                                          text='Foto Masuk', width=50, height=15)
        self.entry_photo_display.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Exit photo (captured screenshot)
        exit_photo_frame = tk.LabelFrame(right_frame, text="GAMBAR KELUAR", 
                                        font=('Arial', 12, 'bold'), bg='#E3F2FD')
        exit_photo_frame.pack(fill='both', expand=True)
        
        self.camera_keluar_label = tk.Label(exit_photo_frame, bg='lightgray', 
                                          text='Screenshot akan diambil saat pencarian', 
                                          width=50, height=15, font=('Arial', 10))
        self.camera_keluar_label.pack(fill='both', expand=True, padx=10, pady=10)
    
    def create_history_page(self):
        main_frame = tk.Frame(self.page_history, bg='#E3F2FD')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title
        title_label = tk.Label(main_frame, text="HISTORY KENDARAAN", 
                             font=('Arial', 18, 'bold'), bg='#E3F2FD')
        title_label.pack(pady=(0, 20))
        
        # Tab for parked vs exited
        history_notebook = ttk.Notebook(main_frame)
        history_notebook.pack(fill='both', expand=True)
        
        # Currently parked vehicles
        parked_frame = ttk.Frame(history_notebook)
        history_notebook.add(parked_frame, text='SEDANG PARKIR')
        
        # Parked vehicles tree
        parked_columns = ('Barcode', 'RFID', 'Plat', 'Waktu Masuk', 'Durasi', 'Member')
        self.parked_tree = ttk.Treeview(parked_frame, columns=parked_columns, show='headings', height=15)
        
        for col in parked_columns:
            self.parked_tree.heading(col, text=col)
            self.parked_tree.column(col, width=120)
        
        parked_scrollbar = ttk.Scrollbar(parked_frame, orient='vertical', command=self.parked_tree.yview)
        self.parked_tree.configure(yscrollcommand=parked_scrollbar.set)
        
        self.parked_tree.pack(side='left', fill='both', expand=True)
        parked_scrollbar.pack(side='right', fill='y')
        
        # Exited vehicles
        exited_frame = ttk.Frame(history_notebook)
        history_notebook.add(exited_frame, text='SUDAH KELUAR')
        
        # Exited vehicles tree (added NoPolKeluar column)
        exited_columns = ('Barcode', 'RFID', 'Plat', 'Masuk', 'Keluar', 'NoPolKeluar', 'Durasi', 'Biaya', 'Member')
        self.exited_tree = ttk.Treeview(exited_frame, columns=exited_columns, show='headings', height=15)
        
        for col in exited_columns:
            self.exited_tree.heading(col, text=col)
            if col in ['NoPolKeluar', 'Barcode', 'RFID']:
                self.exited_tree.column(col, width=90)
            else:
                self.exited_tree.column(col, width=85)
        
        exited_scrollbar = ttk.Scrollbar(exited_frame, orient='vertical', command=self.exited_tree.yview)
        self.exited_tree.configure(yscrollcommand=exited_scrollbar.set)
        
        self.exited_tree.pack(side='left', fill='both', expand=True)
        exited_scrollbar.pack(side='right', fill='y')
        
        # Refresh button
        refresh_btn = tk.Button(main_frame, text="REFRESH", command=self.refresh_history,
                              bg='#2196F3', fg='white', font=('Arial', 12, 'bold'))
        refresh_btn.pack(pady=10)
    
    def create_settings_page(self):
        main_frame = tk.Frame(self.page_settings, bg='#E3F2FD')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Settings notebook
        settings_notebook = ttk.Notebook(main_frame)
        settings_notebook.pack(fill='both', expand=True)
        
        # Camera settings
        camera_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(camera_frame, text='KAMERA')
        self.create_camera_settings(camera_frame)
        
        # RFID Member management
        rfid_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(rfid_frame, text='MEMBER RFID')
        self.create_rfid_management(rfid_frame)
        
        # General settings
        general_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(general_frame, text='UMUM')
        self.create_general_settings(general_frame)
    
    def create_camera_settings(self, parent):
        # Camera configuration
        config_frame = tk.LabelFrame(parent, text="Konfigurasi Kamera", 
                                   font=('Arial', 12, 'bold'))
        config_frame.pack(fill='x', padx=20, pady=20)
        
        tk.Label(config_frame, text="Kamera Masuk (RTSP/Device):", 
               font=('Arial', 10)).grid(row=0, column=0, sticky='w', padx=10, pady=10)
        self.camera_masuk_entry = tk.Entry(config_frame, font=('Arial', 10), width=50)
        self.camera_masuk_entry.grid(row=0, column=1, padx=10, pady=10)
        self.camera_masuk_entry.insert(0, self.parking_system.settings.get('camera_masuk', ''))
        
        tk.Label(config_frame, text="Kamera Keluar (RTSP/Device):", 
               font=('Arial', 10)).grid(row=1, column=0, sticky='w', padx=10, pady=10)
        self.camera_keluar_entry = tk.Entry(config_frame, font=('Arial', 10), width=50)
        self.camera_keluar_entry.grid(row=1, column=1, padx=10, pady=10)
        self.camera_keluar_entry.insert(0, self.parking_system.settings.get('camera_keluar', ''))
        
        # Buttons
        btn_frame = tk.Frame(config_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        save_btn = tk.Button(btn_frame, text="SIMPAN", command=self.save_camera_settings,
                           bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'))
        save_btn.pack(side='left', padx=10)
        
        test_btn = tk.Button(btn_frame, text="TEST KONEKSI", command=self.test_cameras,
                           bg='#2196F3', fg='white', font=('Arial', 10, 'bold'))
        test_btn.pack(side='left', padx=10)
    
    def create_rfid_management(self, parent):
        # RFID Member CRUD
        crud_frame = tk.Frame(parent)
        crud_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Input form
        form_frame = tk.LabelFrame(crud_frame, text="Tambah/Edit Member", 
                                 font=('Arial', 12, 'bold'))
        form_frame.pack(fill='x', pady=(0, 20))
        
        # Form fields
        tk.Label(form_frame, text="RFID ID:", font=('Arial', 10)).grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.rfid_id_entry = tk.Entry(form_frame, font=('Arial', 10), width=20)
        self.rfid_id_entry.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(form_frame, text="Nama:", font=('Arial', 10)).grid(row=0, column=2, sticky='w', padx=10, pady=5)
        self.nama_entry = tk.Entry(form_frame, font=('Arial', 10), width=25)
        self.nama_entry.grid(row=0, column=3, padx=10, pady=5)
        
        tk.Label(form_frame, text="Plat Nomor:", font=('Arial', 10)).grid(row=1, column=0, sticky='w', padx=10, pady=5)
        self.plat_member_entry = tk.Entry(form_frame, font=('Arial', 10), width=20)
        self.plat_member_entry.grid(row=1, column=1, padx=10, pady=5)
        
        tk.Label(form_frame, text="Telepon:", font=('Arial', 10)).grid(row=1, column=2, sticky='w', padx=10, pady=5)
        self.telepon_entry = tk.Entry(form_frame, font=('Arial', 10), width=25)
        self.telepon_entry.grid(row=1, column=3, padx=10, pady=5)
        
        # Buttons
        btn_frame = tk.Frame(form_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=20)
        
        add_btn = tk.Button(btn_frame, text="TAMBAH", command=self.add_member,
                          bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'))
        add_btn.pack(side='left', padx=5)
        
        update_btn = tk.Button(btn_frame, text="UPDATE", command=self.update_member,
                             bg='#FF9800', fg='white', font=('Arial', 10, 'bold'))
        update_btn.pack(side='left', padx=5)
        
        delete_btn = tk.Button(btn_frame, text="HAPUS", command=self.delete_member,
                             bg='#f44336', fg='white', font=('Arial', 10, 'bold'))
        delete_btn.pack(side='left', padx=5)
        
        clear_btn = tk.Button(btn_frame, text="CLEAR", command=self.clear_member_form,
                            bg='#9E9E9E', fg='white', font=('Arial', 10, 'bold'))
        clear_btn.pack(side='left', padx=5)
        
        # Members list
        list_frame = tk.LabelFrame(crud_frame, text="Daftar Member", 
                                 font=('Arial', 12, 'bold'))
        list_frame.pack(fill='both', expand=True)
        
        # Members tree
        member_columns = ('RFID ID', 'Nama', 'Plat Nomor', 'Telepon', 'Tanggal Daftar', 'Status')
        self.member_tree = ttk.Treeview(list_frame, columns=member_columns, show='headings', height=12)
        
        for col in member_columns:
            self.member_tree.heading(col, text=col)
            self.member_tree.column(col, width=120)
        
        member_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.member_tree.yview)
        self.member_tree.configure(yscrollcommand=member_scrollbar.set)
        
        self.member_tree.pack(side='left', fill='both', expand=True)
        member_scrollbar.pack(side='right', fill='y')
        
        # Double click to edit
        self.member_tree.bind('<Double-1>', self.select_member_for_edit)
        
        # Refresh members list
        self.refresh_members_list()
    
    def create_general_settings(self, parent):
        settings_frame = tk.LabelFrame(parent, text="Pengaturan Umum", 
                                     font=('Arial', 12, 'bold'))
        settings_frame.pack(fill='x', padx=20, pady=20)
        
        tk.Label(settings_frame, text="Tarif per Jam (Rp):", 
               font=('Arial', 10)).grid(row=0, column=0, sticky='w', padx=10, pady=10)
        self.tarif_entry = tk.Entry(settings_frame, font=('Arial', 10), width=20)
        self.tarif_entry.grid(row=0, column=1, padx=10, pady=10)
        self.tarif_entry.insert(0, str(self.parking_system.settings.get('tarif_per_jam', 2000)))
        
        save_general_btn = tk.Button(settings_frame, text="SIMPAN", command=self.save_general_settings,
                                   bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'))
        save_general_btn.grid(row=1, column=0, columnspan=2, pady=20)
    
    # Event handlers and async methods
    def check_rfid_member(self, event=None):
        rfid_id = self.rfid_entry.get().strip()
        if not rfid_id:
            self.member_info_frame.pack_forget()
            return
        
        member = self.parking_system.find_member_by_rfid(rfid_id)
        if member:
            info_text = f"Member: {member['nama']}\nPlat: {member['plat_nomor']}\nTelepon: {member['telepon']}"
            self.member_info_label.configure(text=info_text)
            self.member_info_frame.pack(fill='x', padx=10, pady=10)
            self.member_info_label.pack(padx=10, pady=10)
            self.plat_entry.delete(0, tk.END)
            self.plat_entry.insert(0, member['plat_nomor'])
            self.jenis_display.configure(text="MEMBER")
            
            # Auto-process entry for RFID members
            self.process_entry_async(auto_member=True)
        else:
            self.member_info_frame.pack_forget()
            self.jenis_display.configure(text="REGULAR")
    
    def process_entry_async(self, auto_member=False):
        def entry_worker():
            try:
                rfid_id = self.rfid_entry.get().strip() or None
                plat_nomor = self.plat_entry.get().strip()
                
                member_info = None
                if rfid_id:
                    member_info = self.parking_system.find_member_by_rfid(rfid_id)
                
                vehicle = self.parking_system.add_vehicle(rfid_id, plat_nomor, member_info)
                
                def update_ui():
                    self.barcode_display.configure(text=vehicle['barcode'])
                    self.waktu_masuk_display.configure(text=vehicle['waktu_masuk'])
                    
                    # Clear form
                    self.rfid_entry.delete(0, tk.END)
                    self.plat_entry.delete(0, tk.END)
                    self.member_info_frame.pack_forget()
                    self.jenis_display.configure(text="-")
                    
                    if auto_member:
                        messagebox.showinfo("Auto Entry", f"Member {member_info['nama']} berhasil masuk otomatis!")
                    else:
                        messagebox.showinfo("Sukses", "Kendaraan berhasil masuk!")
                    
                    # Reset displays after 3 seconds
                    self.root.after(3000, self.reset_entry_displays)
                
                self.root.after_idle(update_ui)
                
            except Exception as e:
                print(f"Entry error: {e}")
                def show_error():
                    messagebox.showerror("Error", f"Error: {str(e)}")
                self.root.after_idle(show_error)
        
        threading.Thread(target=entry_worker, daemon=True).start()
    
    def validate_exit_form(self, event=None):
        """Validate exit form and enable/disable exit button"""
        try:
            nopol = self.nopol_exit_entry.get().strip()
            has_vehicle = hasattr(self, 'current_barcode') and self.current_barcode
            
            if has_vehicle and nopol:
                self.process_exit_btn.configure(state='normal', bg='#f44336')
            else:
                self.process_exit_btn.configure(state='disabled', bg='#CCCCCC')
        except Exception as e:
            print(f"Validation error: {e}")
    
    def search_by_barcode_async(self, event=None):
        def search_worker():
            try:
                barcode = self.barcode_search_entry.get().strip()
                if not barcode:
                    self.root.after_idle(lambda: messagebox.showerror("Error", "Barcode tidak boleh kosong!"))
                    return
                
                vehicle = self.parking_system.find_vehicle(barcode)
                if not vehicle:
                    def update_ui():
                        messagebox.showerror("Error", "Barcode tidak ditemukan!")
                        self.clear_exit_displays()
                    self.root.after_idle(update_ui)
                    return
                
                if vehicle['status'] == 'keluar':
                    def update_ui():
                        messagebox.showinfo("Info", "Kendaraan sudah keluar!")
                        self.clear_exit_displays()
                    self.root.after_idle(update_ui)
                    return
                
                self.process_search_result(vehicle, barcode, 'barcode')
                
            except Exception as e:
                print(f"Search error: {e}")
                def show_error():
                    messagebox.showerror("Error", f"Error: {str(e)}")
                self.root.after_idle(show_error)
        
        threading.Thread(target=search_worker, daemon=True).start()
    
    def search_by_rfid_async(self, event=None):
        def search_worker():
            try:
                rfid_id = self.rfid_search_entry.get().strip()
                if not rfid_id:
                    self.root.after_idle(lambda: messagebox.showerror("Error", "RFID ID tidak boleh kosong!"))
                    return
                
                vehicle = self.parking_system.find_vehicle_by_rfid(rfid_id)
                if not vehicle:
                    def update_ui():
                        messagebox.showerror("Error", "RFID ID tidak ditemukan atau kendaraan sudah keluar!")
                        self.clear_exit_displays()
                    self.root.after_idle(update_ui)
                    return
                
                self.process_search_result(vehicle, vehicle['barcode'], 'rfid')
                
            except Exception as e:
                print(f"RFID search error: {e}")
                def show_error():
                    messagebox.showerror("Error", f"Error: {str(e)}")
                self.root.after_idle(show_error)
        
        threading.Thread(target=search_worker, daemon=True).start()
    
    def process_search_result(self, vehicle, search_key, search_type):
        """Process search result and update UI"""
        def search_result_worker():
            try:
                # Calculate current time and cost
                masuk_time = datetime.datetime.strptime(f"{vehicle['tanggal_masuk']} {vehicle['waktu_masuk']}", '%Y-%m-%d %H:%M:%S')
                now = datetime.datetime.now()
                duration = now - masuk_time
                
                # Calculate cost based on hours (minimum 1 hour)
                hours = max(1, int(duration.total_seconds() / 3600))
                if duration.total_seconds() % 3600 > 0:  # If there's remaining time, add 1 hour
                    hours += 1
                
                base_cost = hours * self.parking_system.settings.get('tarif_per_jam', 2000)
                if vehicle.get('is_member', False):
                    cost = int(base_cost * 0.8)  # 20% discount
                else:
                    cost = base_cost
                
                def update_ui():
                    self.exit_barcode_display.configure(text=vehicle['barcode'])
                    self.exit_plat_display.configure(text=vehicle.get('plat_nomor', '-'))
                    self.exit_waktu_masuk_display.configure(text=vehicle['waktu_masuk'])
                    self.exit_waktu_keluar_display.configure(text=now.strftime('%H:%M:%S'))
                    self.htg_display.configure(text=str(duration).split('.')[0])
                    self.cost_label.configure(text=f"Rp.{cost:,},-")
                    
                    self.current_barcode = vehicle['barcode']
                    # Button will be enabled only after license plate is entered
                    self.validate_exit_form()
                    
                    # Load entry photo with proper size (640x360 to match live view)
                    self.load_and_display_photo(vehicle.get('foto_masuk'), self.entry_photo_display, 640, 360)
                    
                    # Capture exit screenshot and display it
                    screenshot_success = self.capture_exit_screenshot()
                    if screenshot_success:
                        self.display_temp_exit_photo()
                    else:
                        self.camera_keluar_label.configure(image="", text="Gagal mengambil screenshot")
                    
                    # Show member info if found via RFID
                    if search_type == 'rfid' and vehicle.get('is_member', False):
                        member_info = vehicle.get('member_info', {})
                        member_name = member_info.get('nama', 'Unknown') if member_info else 'Member'
                        messagebox.showinfo("Sukses", f"Member {member_name} ditemukan via RFID!\nSilakan isi No. Polisi untuk melanjutkan.")
                    else:
                        messagebox.showinfo("Sukses", f"Kendaraan ditemukan!\nSilakan isi No. Polisi untuk melanjutkan.")
                
                self.root.after_idle(update_ui)
                
            except Exception as e:
                print(f"Process search result error: {e}")
                def show_error():
                    messagebox.showerror("Error", f"Error: {str(e)}")
                self.root.after_idle(show_error)
        
        threading.Thread(target=search_result_worker, daemon=True).start()
    
    def capture_exit_screenshot(self):
        """Capture screenshot from exit camera and store in RAM"""
        try:
            camera_keluar = self.parking_system.get_camera('keluar')
            
            # Manually capture one frame (without live capture thread)
            if camera_keluar.rtsp_url and not camera_keluar.is_connected:
                # Connect only if not already connected
                camera_keluar.connect_with_timeout()
            
            # Get single frame manually
            if camera_keluar.cap and camera_keluar.cap.isOpened():
                ret, frame = camera_keluar.cap.read()
                if ret and frame is not None:
                    # Store the frame in memory temporarily
                    self.temp_exit_photo = frame.copy()
                    print("Exit screenshot captured and stored in RAM")
                    return True
                else:
                    print("Failed to read frame from exit camera")
                    return False
            else:
                print("Exit camera not available")
                return False
        except Exception as e:
            print(f"Error capturing exit screenshot: {e}")
            return False
    
    def display_temp_exit_photo(self):
        """Display the temporarily stored exit photo"""
        try:
            if self.temp_exit_photo is not None:
                # Resize and display the temporary photo
                frame_resized = cv2.resize(self.temp_exit_photo, (640, 360))
                frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                photo = ImageTk.PhotoImage(image=img)
                
                self.camera_keluar_label.configure(image=photo, text="")
                self.camera_keluar_label.image = photo
            else:
                self.camera_keluar_label.configure(image="", text="Screenshot tidak tersedia")
        except Exception as e:
            print(f"Error displaying temp exit photo: {e}")
            self.camera_keluar_label.configure(image="", text="Error menampilkan foto")
    
    def save_temp_exit_photo(self, filename):
        """Save temporarily stored exit photo to file"""
        try:
            if self.temp_exit_photo is not None:
                os.makedirs('photos', exist_ok=True)
                filepath = os.path.join('photos', filename)
                success = cv2.imwrite(filepath, self.temp_exit_photo)
                if success:
                    print(f"Exit photo saved: {filepath}")
                    return filepath
                else:
                    print("Failed to save exit photo")
            else:
                print("No temporary exit photo to save")
            return None
        except Exception as e:
            print(f"Save temp exit photo error: {e}")
            return None
    
    def process_exit_async(self):
        def exit_worker():
            try:
                # Get license plate number
                nopol = self.nopol_exit_entry.get().strip()
                if not nopol:
                    def show_warning():
                        messagebox.showwarning("Peringatan", "No. Polisi harus diisi!")
                    self.root.after_idle(show_warning)
                    return
                
                # Save the temporary exit photo first
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                exit_filename = f"keluar_{timestamp}.jpg"
                saved_photo_path = self.save_temp_exit_photo(exit_filename)
                
                # Process exit with the saved photo path and license plate
                vehicle = self.parking_system.exit_vehicle(self.current_barcode, saved_photo_path, nopol)
                
                def update_ui():
                    if vehicle:
                        messagebox.showinfo("Sukses", f"Kendaraan berhasil keluar!\nNo. Polisi: {nopol}\nTotal biaya: Rp.{vehicle['biaya']:,},-")
                        self.clear_exit_displays()
                        self.clear_search_fields()
                        self.current_barcode = None
                        self.temp_exit_photo = None  # Clear temporary photo from RAM
                    else:
                        messagebox.showerror("Error", "Gagal memproses kendaraan keluar!")
                
                self.root.after_idle(update_ui)
                
            except Exception as e:
                print(f"Exit error: {e}")
                def show_error():
                    messagebox.showerror("Error", f"Error: {str(e)}")
                self.root.after_idle(show_error)
        
        threading.Thread(target=exit_worker, daemon=True).start()
    
    def clear_search_fields(self):
        """Clear both search fields"""
        self.barcode_search_entry.delete(0, tk.END)
        self.rfid_search_entry.delete(0, tk.END)
        self.clear_exit_displays()
    
    # Helper methods
    def load_and_display_photo(self, photo_path, label_widget, max_width=200, max_height=150):
        try:
            if not photo_path or not os.path.exists(photo_path):
                label_widget.configure(image="", text="No Photo")
                return
            
            img = Image.open(photo_path)
            img_width, img_height = img.size
            width_ratio = max_width / img_width
            height_ratio = max_height / img_height
            ratio = min(width_ratio, height_ratio)
            
            new_width = int(img_width * ratio)
            new_height = int(img_height * ratio)
            
            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img_resized)
            
            label_widget.configure(image=photo, text="")
            label_widget.image = photo
            
        except Exception as e:
            print(f"Error loading photo {photo_path}: {e}")
            label_widget.configure(image="", text="Error Loading Photo")
    
    def clear_exit_displays(self):
        self.exit_barcode_display.configure(text="-")
        self.exit_plat_display.configure(text="-")
        self.exit_waktu_masuk_display.configure(text="-")
        self.exit_waktu_keluar_display.configure(text="-")
        self.htg_display.configure(text="-")
        self.cost_label.configure(text="Rp.0,-")
        self.nopol_exit_entry.delete(0, tk.END)  # Clear license plate field
        self.process_exit_btn.configure(state='disabled', bg='#CCCCCC')
        self.entry_photo_display.configure(image="", text="Foto Masuk")
        self.entry_photo_display.image = None
        # Clear exit photo display and temporary photo
        self.camera_keluar_label.configure(image="", text="Screenshot akan diambil saat pencarian")
        self.camera_keluar_label.image = None
        self.temp_exit_photo = None
    
    def reset_entry_displays(self):
        self.barcode_display.configure(text="-")
        self.waktu_masuk_display.configure(text="-")
    
    # Member management methods
    def add_member(self):
        try:
            rfid_id = self.rfid_id_entry.get().strip()
            nama = self.nama_entry.get().strip()
            plat_nomor = self.plat_member_entry.get().strip()
            telepon = self.telepon_entry.get().strip()
            
            if not rfid_id or not nama or not plat_nomor:
                messagebox.showerror("Error", "RFID ID, Nama, dan Plat Nomor harus diisi!")
                return
            
            # Check if RFID already exists
            if self.parking_system.find_member_by_rfid(rfid_id):
                messagebox.showerror("Error", "RFID ID sudah terdaftar!")
                return
            
            self.parking_system.add_member(rfid_id, nama, plat_nomor, telepon)
            messagebox.showinfo("Sukses", "Member berhasil ditambahkan!")
            self.clear_member_form()
            self.refresh_members_list()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error: {str(e)}")
    
    def update_member(self):
        try:
            rfid_id = self.rfid_id_entry.get().strip()
            nama = self.nama_entry.get().strip()
            plat_nomor = self.plat_member_entry.get().strip()
            telepon = self.telepon_entry.get().strip()
            
            if not rfid_id or not nama or not plat_nomor:
                messagebox.showerror("Error", "RFID ID, Nama, dan Plat Nomor harus diisi!")
                return
            
            result = self.parking_system.update_member(rfid_id, nama, plat_nomor, telepon)
            if result:
                messagebox.showinfo("Sukses", "Member berhasil diupdate!")
                self.clear_member_form()
                self.refresh_members_list()
            else:
                messagebox.showerror("Error", "Member tidak ditemukan!")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error: {str(e)}")
    
    def delete_member(self):
        try:
            rfid_id = self.rfid_id_entry.get().strip()
            if not rfid_id:
                messagebox.showerror("Error", "RFID ID harus diisi!")
                return
            
            if messagebox.askyesno("Konfirmasi", "Yakin ingin menghapus member ini?"):
                result = self.parking_system.delete_member(rfid_id)
                if result:
                    messagebox.showinfo("Sukses", "Member berhasil dihapus!")
                    self.clear_member_form()
                    self.refresh_members_list()
                else:
                    messagebox.showerror("Error", "Member tidak ditemukan!")
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error: {str(e)}")
    
    def clear_member_form(self):
        self.rfid_id_entry.delete(0, tk.END)
        self.nama_entry.delete(0, tk.END)
        self.plat_member_entry.delete(0, tk.END)
        self.telepon_entry.delete(0, tk.END)
    
    def select_member_for_edit(self, event):
        try:
            selection = self.member_tree.selection()
            if selection:
                item = self.member_tree.item(selection[0])
                values = item['values']
                
                self.rfid_id_entry.delete(0, tk.END)
                self.rfid_id_entry.insert(0, values[0])
                
                self.nama_entry.delete(0, tk.END)
                self.nama_entry.insert(0, values[1])
                
                self.plat_member_entry.delete(0, tk.END)
                self.plat_member_entry.insert(0, values[2])
                
                self.telepon_entry.delete(0, tk.END)
                self.telepon_entry.insert(0, values[3])
        except Exception as e:
            print(f"Select member error: {e}")
    
    def refresh_members_list(self):
        # Clear existing items
        for item in self.member_tree.get_children():
            self.member_tree.delete(item)
        
        # Add members
        for member in self.parking_system.rfid_members:
            self.member_tree.insert('', 'end', values=(
                member['rfid_id'],
                member['nama'],
                member['plat_nomor'],
                member.get('telepon', ''),
                member['tanggal_daftar'],
                member['status']
            ))
    
    def refresh_history(self):
        # Refresh parked vehicles
        for item in self.parked_tree.get_children():
            self.parked_tree.delete(item)
        
        parked_vehicles = self.parking_system.get_parked_vehicles()
        for vehicle in parked_vehicles:
            try:
                masuk_time = datetime.datetime.strptime(f"{vehicle['tanggal_masuk']} {vehicle['waktu_masuk']}", '%Y-%m-%d %H:%M:%S')
                now = datetime.datetime.now()
                duration = now - masuk_time
                duration_str = str(duration).split('.')[0]
                
                member_status = "Yes" if vehicle.get('is_member', False) else "No"
                
                self.parked_tree.insert('', 'end', values=(
                    vehicle['barcode'],
                    vehicle.get('rfid_id', '-'),
                    vehicle.get('plat_nomor', '-'),
                    vehicle['waktu_masuk'],
                    duration_str,
                    member_status
                ))
            except Exception as e:
                print(f"Parked vehicle processing error: {e}")
        
        # Refresh exited vehicles
        for item in self.exited_tree.get_children():
            self.exited_tree.delete(item)
        
        exited_vehicles = self.parking_system.get_exited_vehicles()
        for vehicle in exited_vehicles:
            try:
                member_status = "Yes" if vehicle.get('is_member', False) else "No"
                
                self.exited_tree.insert('', 'end', values=(
                    vehicle['barcode'],
                    vehicle.get('rfid_id', '-'),
                    vehicle.get('plat_nomor', '-'),
                    vehicle['waktu_masuk'],
                    vehicle.get('waktu_keluar', '-'),
                    vehicle.get('nopol_keluar', '-'),  # License plate at exit
                    vehicle.get('durasi', '-'),
                    f"Rp.{vehicle.get('biaya', 0):,}",
                    member_status
                ))
            except Exception as e:
                print(f"Exited vehicle processing error: {e}")
    
    # Settings methods
    def save_camera_settings(self):
        try:
            self.parking_system.settings['camera_masuk'] = self.camera_masuk_entry.get()
            self.parking_system.settings['camera_keluar'] = self.camera_keluar_entry.get()
            self.parking_system.save_data()
            
            # Restart cameras
            for camera in self.parking_system.cameras.values():
                camera.release()
            self.parking_system.cameras.clear()
            
            messagebox.showinfo("Sukses", "Pengaturan kamera berhasil disimpan!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error: {str(e)}")
    
    def test_cameras(self):
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
                    message = "Semua kamera terhubung dengan baik!"
                elif success_count == 1:
                    message = "Hanya 1 kamera yang terhubung"
                else:
                    message = "Tidak ada kamera yang terhubung"
                
                def update_ui():
                    messagebox.showinfo("Test Result", message)
                
                self.root.after_idle(update_ui)
                
            except Exception as e:
                def show_error():
                    messagebox.showerror("Error", f"Test error: {str(e)}")
                self.root.after_idle(show_error)
        
        threading.Thread(target=test_worker, daemon=True).start()
    
    def save_general_settings(self):
        try:
            tarif = int(self.tarif_entry.get())
            self.parking_system.settings['tarif_per_jam'] = tarif
            self.parking_system.save_data()
            messagebox.showinfo("Sukses", "Pengaturan umum berhasil disimpan!")
        except ValueError:
            messagebox.showerror("Error", "Tarif harus berupa angka!")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {str(e)}")
    
    def start_background_processes(self):
        # Update datetime labels
        def update_datetime():
            while self.running:
                try:
                    current_time = datetime.datetime.now().strftime('%H:%M - %d/%m/%Y')
                    if hasattr(self, 'datetime_label_masuk'):
                        self.root.after_idle(lambda: self.datetime_label_masuk.configure(text=current_time))
                    if hasattr(self, 'datetime_label_keluar'):
                        self.root.after_idle(lambda: self.datetime_label_keluar.configure(text=current_time))
                    time.sleep(1)
                except Exception as e:
                    print(f"DateTime update error: {e}")
                    time.sleep(5)
        
        threading.Thread(target=update_datetime, daemon=True).start()
        
        # Camera display updates (ONLY for entry camera - NO exit camera live view)
        def camera_display_worker():
            while self.running:
                try:
                    # ONLY update entry camera with live view
                    camera_masuk = self.parking_system.get_camera('masuk')
                    frame = camera_masuk.get_latest_frame()
                    if frame is not None:
                        try:
                            frame_resized = cv2.resize(frame, (640, 360))
                            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                            img = Image.fromarray(frame_rgb)
                            photo = ImageTk.PhotoImage(image=img)
                            
                            def update_entry_camera():
                                self.camera_masuk_label.configure(image=photo, text="")
                                self.camera_masuk_label.image = photo
                            
                            self.root.after_idle(update_entry_camera)
                        except Exception as e:
                            print(f"Entry camera display error: {e}")
                    
                    # EXIT CAMERA: NO LIVE VIEW - COMPLETELY DISABLED
                    # Exit camera only used for manual screenshots during search
                    
                    time.sleep(0.2)
                except Exception as e:
                    print(f"Camera display worker error: {e}")
                    time.sleep(1)
        
        threading.Thread(target=camera_display_worker, daemon=True).start()
        
        # Initialize cameras (HANYA entry camera yang live, exit camera TIDAK live)
        def init_cameras():
            time.sleep(2)
            
            # HANYA initialize entry camera untuk live view
            try:
                camera_masuk = self.parking_system.get_camera('masuk')
                if camera_masuk.rtsp_url:
                    print(f"Initializing entry camera for LIVE VIEW...")
                    success = camera_masuk.connect_with_timeout()
                    if success:
                        camera_masuk.start_capture_thread()  # START live capture thread
                        print(f"Entry camera LIVE VIEW started")
                    else:
                        print(f"Failed to initialize entry camera")
            except Exception as e:
                print(f"Entry camera initialization error: {e}")
            
            # Exit camera: JANGAN inisialisasi sama sekali untuk live view
            # Exit camera akan di-connect manual saat butuh screenshot saja
            print("Exit camera: NO LIVE VIEW - akan di-connect manual saat screenshot")

        
        threading.Thread(target=init_cameras, daemon=True).start()
        
        # Auto-refresh history every 10 seconds (realtime)
        def auto_refresh_history():
            while self.running:
                try:
                    time.sleep(10)  # Refresh every 10 seconds for realtime updates
                    # Only refresh if history tab is currently selected
                    if hasattr(self, 'notebook') and self.notebook.select() == str(self.page_history):
                        self.root.after_idle(self.refresh_history)
                except Exception as e:
                    print(f"Auto refresh error: {e}")
        
        threading.Thread(target=auto_refresh_history, daemon=True).start()
    
    def on_closing(self):
        print("Shutting down application...")
        self.running = False
        
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
        
        os._exit(0)

if __name__ == "__main__":
    print("PLAZA PONDOK GEDE - Parking System Starting...")
    print("Data files: parking_data.json, rfid_members.json, settings.json")
    print("Photos folder: photos/")
    print("Features:")
    print("- RFID Member System with CRUD")
    print("- Entry/Exit Processing")
    print("- Vehicle History Tracking")
    print("- Live Camera Integration")
    print("- Member Discount System")
    
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