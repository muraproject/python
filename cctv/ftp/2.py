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
        self.ensure_csv_exists()

    def ensure_csv_exists(self):
        # Membuat file CSV jika belum ada dengan header
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Tanggal', 'Waktu', 'IP', 'Username', 'Deteksi', 'Path'])

    def log_to_csv(self, detection, path):
        now = datetime.now()
        tanggal = now.strftime('%Y-%m-%d')
        waktu = now.strftime('%H:%M:%S')
        
        # Menulis ke CSV
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
        
        # Print informasi
        print(f"\n[{tanggal} {waktu}] Deteksi: {detection}")
        print(f"IP: {self.remote_ip}")
        print(f"Username: {self.username}")
        print(f"Path: {path}")
        print("-" * 50)

    def on_connect(self):
        self.log_to_csv("CONNECT", "")
        
    def on_disconnect(self):
        self.log_to_csv("DISCONNECT", "")

    def on_file_received(self, file):
        self.log_to_csv("UPLOAD", file)

    def on_file_sent(self, file):
        self.log_to_csv("DOWNLOAD", file)

    # Monitor perubahan direktori (CWD)
    def on_cwd(self, path):
        self.log_to_csv("CWD", path)
        return super().on_cwd(path)

    # Monitor permintaan rename (RNFR)
    def on_rnfr(self, path):
        self.log_to_csv("RENAME_FROM", path)
        return super().on_rnfr(path)

    # Monitor rename selesai (RNTO)
    def on_rnto(self, path):
        self.log_to_csv("RENAME_TO", path)
        return super().on_rnto(path)

    # Monitor penghapusan file
    def on_dele(self, path):
        self.log_to_csv("DELETE", path)
        return super().on_dele(path)

    # Monitor pembuatan direktori
    def on_mkd(self, path):
        self.log_to_csv("MKDIR", path)
        return super().on_mkd(path)

    # Monitor penghapusan direktori
    def on_rmd(self, path):
        self.log_to_csv("RMDIR", path)
        return super().on_rmd(path)

def main():
    controller = FTPServerController()
    controller.setup_signal_handlers()
    
    # Konfigurasi logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Buat direktori untuk FTP jika belum ada
        ftp_dir = "ftp_directory"
        if not os.path.exists(ftp_dir):
            os.makedirs(ftp_dir)
        
        # Buat authorizer untuk menangani otentikasi
        authorizer = DummyAuthorizer()
        
        # Tambahkan user dengan username "user" dan password "12345"
        authorizer.add_user("android", "android", ftp_dir, perm="elradfmw")
        
        # Inisialisasi handler
        handler = CustomFTPHandler
        handler.authorizer = authorizer
        handler.banner = "Selamat datang di FTP Server Python!"
        
        # Dapatkan IP lokal
        local_ip = controller.get_local_ip()
        port = 2221
        
        # Konfigurasi server dengan IP lokal
        address = (local_ip, port)
        controller.server = FTPServer(address, handler)
        
        # Set maksimum koneksi
        controller.server.max_cons = 256
        controller.server.max_cons_per_ip = 5
        
        print("\n=== FTP Server Information ===")
        print("\nAktivitas yang dilog ke CSV:")
        print("- CONNECT   : Koneksi baru")
        print("- DISCONNECT: Klien terputus")
        print("- CWD       : Perubahan direktori")
        print("- UPLOAD    : File diunggah")
        print("- DOWNLOAD  : File diunduh")
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
        print("- Username : user")
        print("- Password : 12345")
        print("\nTekan Ctrl+C untuk menghentikan server")
        print("=" * 30)
        
        # Mulai server
        controller.server.serve_forever()
        
    except Exception as e:
        print(f"\nTerjadi kesalahan: {str(e)}")
        if controller.server:
            controller.server.close_all()
        sys.exit(1)

if __name__ == "__main__":
    main()