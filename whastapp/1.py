import pywhatkit
import time
from datetime import datetime
import os
import webbrowser

# Set Chrome sebagai browser default untuk script ini
chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
webbrowser.register('chrome', None, webbrowser.BackgroundBrowser(chrome_path))

def kirim_pesan():
    """
    Fungsi untuk mengirim pesan WhatsApp menggunakan pywhatkit dengan Chrome
    """
    try:
        # Input nomor dan pesan
        nomor = input("Masukkan nomor tujuan (contoh: +628xxxx): ")
        if not nomor.startswith('+'):
            nomor = '+' + nomor
        
        pesan = input("Masukkan pesan: ")
        
        # Dapatkan waktu sekarang
        now = datetime.now()
        
        # Konfigurasi pywhatkit untuk menggunakan Chrome
        pywhatkit.core.browser = "chrome"
        
        print("Membuka WhatsApp Web di Chrome...")
        # Kirim pesan 20 detik dari sekarang
        pywhatkit.sendwhatmsg(nomor, 
                             pesan,
                             now.hour,
                             now.minute + 1,
                             15,    # Waktu tunggu
                             True,  # Close tab
                             2)     # Wait time
        
        print(f"Pesan berhasil dikirim ke {nomor}")
        time.sleep(2)
        
    except Exception as e:
        print(f"Gagal mengirim pesan: {str(e)}")
        print("Pastikan Chrome terinstall di lokasi default")

def main():
    print("Memastikan menggunakan Chrome...")
    try:
        # Cek apakah Chrome ada
        if not os.path.exists(chrome_path):
            print("Error: Chrome tidak ditemukan di lokasi default!")
            print("Pastikan Chrome terinstall di:", chrome_path)
            return
            
        while True:
            print("\n=== WhatsApp Sender (Chrome) ===")
            print("1. Kirim Pesan")
            print("2. Keluar")
            
            pilihan = input("Pilih menu (1/2): ")
            
            if pilihan == "1":
                kirim_pesan()
            elif pilihan == "2":
                print("Menutup program...")
                break
            else:
                print("Pilihan tidak valid!")
                
    except Exception as e:
        print(f"Terjadi error: {str(e)}")

if __name__ == "__main__":
    # Install dengan: pip install pywhatkit
    print("Pastikan Anda sudah login di WhatsApp Web di Chrome")
    main()