from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
import os
import logging
import socket
import signal
import sys
from datetime import datetime
import csv
import requests
import json
from urllib.parse import quote

class FTPServerController:
    def __init__(self):
        self.server = None
        
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "127.0.0.1"

    def signal_handler(self, signum, frame):
        print("\nMenerima sinyal untuk berhenti...")
        if self.server:
            print("Menutup FTP server...")
            self.server.close_all()
            sys.exit(0)

    def setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

class CustomFTPHandler(FTPHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.csv_file = "ftp_logs.csv"
        self.api_base_url = "http://103.139.192.236:5000"
        self.ensure_csv_exists()

    def ensure_csv_exists(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Tanggal', 'Waktu', 'IP', 'Username', 'Deteksi', 'Path'])

    def log_to_csv(self, detection, path):
        now = datetime.now()
        tanggal = now.strftime('%Y-%m-%d')
        waktu = now.strftime('%H:%M:%S')
        
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                tanggal,
                waktu,
                self.remote_ip,
                self.username,
                detection,
                path
            ])
        
        print(f"\n[{tanggal} {waktu}] Deteksi: {detection}")
        print(f"IP: {self.remote_ip}")
        print(f"Username: {self.username}")
        print(f"Path: {path}")
        print("-" * 50)

    def get_camera_settings(self):
        try:
            response = requests.get(f"{self.api_base_url}/api/camera-settings")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting camera settings: {str(e)}")
            return None

    def find_camera_by_ip(self, ip_address):
        camera_settings = self.get_camera_settings()
        if camera_settings:
            for camera in camera_settings:
                if camera['enabled'] and camera['ip'] == ip_address:
                    return camera
        return None

    def send_detection_result(self, camera_name, mode, result):
        try:
            # URL encode the parameters
            encoded_camera = quote(camera_name)
            encoded_mode = quote(mode)
            encoded_result = quote(result)
            
            url = f"{self.api_base_url}/api/save?camera_name={encoded_camera}&mode={encoded_mode}&result={encoded_result}"
            
            response = requests.get(url)
            if response.status_code == 200:
                print(f"Successfully sent detection result for {camera_name}")
                return True
            else:
                print(f"Failed to send detection result: {response.status_code}")
                return False
        except Exception as e:
            print(f"Error sending detection result: {str(e)}")
            return False

    def generate_result_by_mode(self, mode):
        # Define default results for each mode
        mode_results = {
            "Counting Kendaraan": "1 kendaraan",
            "Counting Orang Lewat": "1 orang",
            "Api dan Asap": "terdeteksi api",
            "People Cross": "1 orang melintas",
            "In Area": "1 orang masuk area",
            "Out Area": "1 orang keluar area",
            "Intrusion": "terdeteksi intrusi",
            "Face Detection": "1 wajah terdeteksi"
        }
        return mode_results.get(mode, "deteksi berhasil")

    def on_file_received(self, file):
        self.log_to_csv("UPLOAD", file)
        
        # Only process .jpg files
        if not file.lower().endswith('.jpg'):
            return
        
        # Find camera settings for the IP that sent the file
        camera = self.find_camera_by_ip(self.remote_ip)
        if camera and camera['enabled'] and camera['mode']:
            # Generate result based on camera mode
            result = self.generate_result_by_mode(camera['mode'])
            
            # Send detection result
            self.send_detection_result(
                camera_name=camera['name'],
                mode=camera['mode'],
                result=result
            )
            
            print(f"Processed upload from camera {camera['name']} with mode {camera['mode']}")

    def on_connect(self):
        self.log_to_csv("CONNECT", "")
        
    def on_disconnect(self):
        self.log_to_csv("DISCONNECT", "")

    def on_file_sent(self, file):
        self.log_to_csv("DOWNLOAD", file)

    def on_cwd(self, path):
        self.log_to_csv("CWD", path)
        return super().on_cwd(path)

    def on_rnfr(self, path):
        self.log_to_csv("RENAME_FROM", path)
        return super().on_rnfr(path)

    def on_rnto(self, path):
        self.log_to_csv("RENAME_TO", path)
        return super().on_rnto(path)

    def on_dele(self, path):
        self.log_to_csv("DELETE", path)
        return super().on_dele(path)

    def on_mkd(self, path):
        self.log_to_csv("MKDIR", path)
        return super().on_mkd(path)

    def on_rmd(self, path):
        self.log_to_csv("RMDIR", path)
        return super().on_rmd(path)

def main():
    controller = FTPServerController()
    controller.setup_signal_handlers()
    
    logging.basicConfig(level=logging.INFO)
    
    try:
        ftp_dir = "ftp_directory"
        if not os.path.exists(ftp_dir):
            os.makedirs(ftp_dir)
        
        authorizer = DummyAuthorizer()
        authorizer.add_user("android", "android", ftp_dir, perm="elradfmw")
        
        handler = CustomFTPHandler
        handler.authorizer = authorizer
        handler.banner = "Selamat datang di FTP Server Python!"
        
        local_ip = controller.get_local_ip()
        port = 2221
        
        address = (local_ip, port)
        controller.server = FTPServer(address, handler)
        
        controller.server.max_cons = 256
        controller.server.max_cons_per_ip = 5
        
        print("\n=== FTP Server Information ===")
        print("\nAktivitas yang dilog ke CSV:")
        print("- CONNECT   : Koneksi baru")
        print("- DISCONNECT: Klien terputus")
        print("- UPLOAD    : File diunggah (JPG akan diproses)")
        print("- DOWNLOAD  : File diunduh")
        print("- CWD       : Perubahan direktori")
        print("- RENAME    : Perubahan nama file")
        print("- DELETE    : Penghapusan file")
        print("- MKDIR     : Pembuatan direktori")
        print("- RMDIR     : Penghapusan direktori")
        print(f"\nFile log: {os.path.abspath('ftp_logs.csv')}")
        print(f"\nServer berjalan di:")
        print(f"- Local IP   : ftp://{local_ip}:{port}")
        print(f"- Localhost  : ftp://127.0.0.1:{port}")
        print(f"\nDirektori FTP: {os.path.abspath(ftp_dir)}")
        print("\nKredensial login:")
        print("- Username : android")
        print("- Password : android")
        print("\nTekan Ctrl+C untuk menghentikan server")
        print("=" * 30)
        
        controller.server.serve_forever()
        
    except Exception as e:
        print(f"\nTerjadi kesalahan: {str(e)}")
        if controller.server:
            controller.server.close_all()
        sys.exit(1)

if __name__ == "__main__":
    main()