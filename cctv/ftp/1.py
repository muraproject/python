from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
import os
import logging
import socket
import signal
import sys

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
    def on_file_received(self, file):
        print(f"\nFile baru diterima: {file}")
        print(f"Ukuran file: {os.path.getsize(file)} bytes")
        print(f"Waktu modifikasi: {os.path.getmtime(file)}")
        print("-" * 50)

    def on_connect(self):
        print(f"\nKoneksi baru dari: {self.remote_ip}")

    def on_disconnect(self):
        print(f"\nKlien terputus: {self.remote_ip}")

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
        print(f"Server berjalan di:")
        print(f"- Local IP   : ftp://{local_ip}:{port}")
        print(f"- Localhost  : ftp://127.0.0.1:{port}")
        print(f"\nDirektori FTP: {os.path.abspath(ftp_dir)}")
        print("\nKredensial login:")
        print("- Username : user")
        print("- Password : 12345")
        print("\nCara mengakses:")
        print("1. Menggunakan FileZilla:")
        print(f"   - Host: {local_ip}")
        print(f"   - Port: {port}")
        print("   - Username: user")
        print("   - Password: 12345")
        print("\n2. Menggunakan browser:")
        print(f"   ftp://user:12345@{local_ip}:{port}")
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