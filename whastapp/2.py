from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import time
import os

class WhatsAppSender:
    def __init__(self):
        # Setup Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--start-maximized")
        
        # Tambahkan path untuk menyimpan data
        user_data_dir = os.path.join(os.getcwd(), "whatsapp_session")
        chrome_options.add_argument(f"user-data-dir={user_data_dir}")
        
        # Setup service dan driver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 30)
        
    def mulai(self):
        """Memulai sesi WhatsApp"""
        print("Membuka WhatsApp Web...")
        self.driver.get("https://web.whatsapp.com")
        
        # Tunggu sampai chat list muncul
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="chat-list"]')))
            print("WhatsApp Web siap digunakan!")
            return True
        except:
            print("Silakan scan QR code untuk login...")
            try:
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="chat-list"]')))
                print("Login berhasil!")
                return True
            except:
                print("Login gagal!")
                return False
    
    def kirim_pesan(self, nomor, pesan):
        """Kirim pesan WhatsApp"""
        try:
            if not nomor.startswith("+"):
                nomor = "+" + nomor
                
            # Buka chat dengan nomor tersebut (tanpa reload halaman)
            search_box = self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, '[data-testid="chat-list-search"]')))
            search_box.clear()
            search_box.send_keys(nomor)
            time.sleep(2)
            
            # Coba klik kontak jika ada
            try:
                chat_item = self.wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '[data-testid="cell-frame-container"]')))
                chat_item.click()
                time.sleep(1)
            except:
                print("Kontak tidak ditemukan!")
                return
            
            # Kirim pesan
            input_box = self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, '[data-testid="conversation-compose-box-input"]')))
            input_box.send_keys(pesan + Keys.ENTER)
            print(f"Pesan berhasil dikirim ke {nomor}")
            
        except Exception as e:
            print(f"Gagal mengirim pesan: {str(e)}")
    
    def tutup(self):
        """Tutup browser"""
        try:
            self.driver.quit()
        except:
            pass

def main():
    sender = None
    try:
        # Inisialisasi WhatsApp
        sender = WhatsAppSender()
        
        # Mulai sesi
        if sender.mulai():
            while True:
                print("\n=== WhatsApp Sender ===")
                print("1. Kirim Pesan")
                print("2. Keluar")
                
                pilihan = input("Pilih menu (1/2): ")
                
                if pilihan == "1":
                    nomor = input("Masukkan nomor tujuan (contoh: +628xxxx): ")
                    pesan = input("Masukkan pesan: ")
                    sender.kirim_pesan(nomor, pesan)
                    
                elif pilihan == "2":
                    print("Menutup program...")
                    break
                else:
                    print("Pilihan tidak valid!")
    except Exception as e:
        print(f"Terjadi error: {str(e)}")
    finally:
        if sender:
            sender.tutup()

if __name__ == "__main__":
    # Install dependencies:
    # pip install selenium webdriver-manager
    main()