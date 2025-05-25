import requests
import json
from datetime import datetime, timedelta
import urllib.parse
import time
import random
import schedule
import sys
import os
import logging

# Siapkan logging
logging_dir = "logs"
os.makedirs(logging_dir, exist_ok=True)
log_file = os.path.join(logging_dir, f"lamp_monitoring_{datetime.now().strftime('%Y%m%d')}.log")

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# API URL dan parameter
url = "http://36.67.153.74:8800/api/json"

# Headers HTTP
headers = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Content-Type": "text/plain;charset=UTF-8",
    "Host": "36.67.153.74:8800",
    "Origin": "http://36.67.153.74:8800",
    "Referer": "http://36.67.153.74:8800/web/map/panels/lamp.html",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
}

# Cookies
cookies = {
    "AXWEBSID": "4491325c11b6478090fb71e7d6da86fb",
    "userFlag": "4491325c11b6478090fb71e7d6da86fb",
    "language": "en_US"
}

# Project ID
project_id = "855b7708e2434eae9cffb330e8c96da2"

# Telegram settings
telegram_bot_token = "8044584756:AAFlFu-iq2w1iIqa1NKJHbj2h8jL5J3rKVI"
telegram_chat_id = "-4738822004"

# Fungsi untuk mengirim pesan ke Telegram
def send_telegram_message(message):
    encoded_message = urllib.parse.quote(message)
    telegram_url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage?chat_id={telegram_chat_id}&text={encoded_message}"
    
    try:
        response = requests.get(telegram_url)
        if response.status_code == 200:
            logging.info(f"Pesan berhasil dikirim ke Telegram: {message[:50]}...")
            return True
        else:
            logging.error(f"Gagal mengirim pesan ke Telegram. Status code: {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"Error mengirim pesan ke Telegram: {e}")
        return False

# Fungsi untuk melakukan request dengan retry dan delay
def make_request_with_retry(request_type, url, params, headers, cookies, data=None, max_retries=3, base_delay=1):
    for attempt in range(max_retries + 1):
        try:
            # Tambahkan delay untuk menghindari rate limiting (semakin lama jika retry)
            if attempt > 0:
                delay = base_delay + (attempt * random.uniform(0.5, 1.5))
                logging.info(f"  Mencoba kembali dalam {delay:.2f} detik... (percobaan {attempt}/{max_retries})")
                time.sleep(delay)
            
            # Buat request sesuai jenis yang diminta
            if request_type.lower() == 'post':
                response = requests.post(
                    url,
                    params=params,
                    headers=headers,
                    cookies=cookies,
                    data=data,
                    verify=False,
                    timeout=10  # Set timeout untuk menghindari hang
                )
            else:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    cookies=cookies,
                    verify=False,
                    timeout=10
                )
                
            # Jika berhasil, kembalikan response
            return response
        
        except (requests.ConnectionError, requests.Timeout) as e:
            # Jika ini adalah percobaan terakhir, kembalikan error
            if attempt == max_retries:
                logging.error(f"  Gagal setelah {max_retries} percobaan: {e}")
                raise
            else:
                logging.warning(f"  Koneksi terputus: {e}")
                # Tunggu sebelum percobaan berikutnya (delay ditambahkan di awal loop)

# Fungsi utama untuk memeriksa lampu
def check_lamps():
    start_time = datetime.now()
    logging.info(f"Memulai pemeriksaan lampu pada {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        logging.info("Langkah 1: Mengambil daftar direktori dari Project ID...")
        params_direktori = {
            "sid": "4491325c11b6478090fb71e7d6da86fb",
            "cmd": "project-dir",
            "ctrl": "dir-data",
            "version": "1",
            "lang": "en_US"
        }

        body_direktori = json.dumps(project_id)

        # Gunakan fungsi request dengan retry
        response_direktori = make_request_with_retry(
            'post',
            url,
            params_direktori,
            headers,
            cookies,
            body_direktori
        )
        
        direktori_list = []
        
        if response_direktori.status_code == 200 and response_direktori.text.startswith("1||"):
            json_text = response_direktori.text[3:]
            direktori_list = json.loads(json_text)
            
            logging.info(f"Berhasil mendapatkan {len(direktori_list)} direktori:")
            for idx, dir in enumerate(direktori_list, 1):
                logging.info(f"{idx}. {dir['name']} (ID: {dir['did']})")
                
                # Tampilkan informasi grup lampu jika ada
                if dir.get('lampGroups') and len(dir['lampGroups']) > 0:
                    for group in dir['lampGroups']:
                        logging.info(f"   - Grup: {group.get('groupName', 'Tanpa nama')} (ID: {group.get('groupId', 'N/A')})")
        else:
            logging.error(f"Gagal mendapatkan direktori: {response_direktori.status_code}")
        
        # Delay sebelum langkah berikutnya
        time.sleep(1)
        
        # Langkah 2: Ambil daftar lampu menggunakan endpoint map-item
        logging.info("\nLangkah 2: Mengambil daftar lampu dari semua direktori...")
        
        all_lamps = []
        valid_dirs = [d for d in direktori_list if d.get('lat', 0) != 0 and d.get('lng', 0) != 0]
        
        for dir_index, directory in enumerate(valid_dirs, 1):
            logging.info(f"\nMengambil lampu untuk direktori {dir_index}/{len(valid_dirs)}: {directory['name']}")
            
            params_map = {
                "sid": "4491325c11b6478090fb71e7d6da86fb",
                "cmd": "map-item",
                "ctrl": "get-map-lamps",
                "version": "1",
                "lang": "en_US"
            }
            
            lat = directory.get('lat', 0)
            lng = directory.get('lng', 0)
            
            body_map = {
                "projectId": project_id,
                "ctype": 16,
                "view": {
                    "left": lng - 0.02,
                    "bottom": lat - 0.02,
                    "right": lng + 0.02,
                    "top": lat + 0.02
                },
                "cuid": "WMRTS6TCS8CJ"
            }
            
            # Gunakan fungsi request dengan retry
            response_map = make_request_with_retry(
                'post',
                url,
                params_map,
                headers,
                cookies,
                json.dumps(body_map)
            )
            
            if response_map.status_code == 200 and response_map.text.startswith("1||"):
                json_text = response_map.text[3:]
                lamp_list = json.loads(json_text)
                
                # Tambahkan informasi direktori ke setiap lampu
                for lamp in lamp_list:
                    lamp['directory_name'] = directory['name']
                    lamp['directory_id'] = directory['did']
                
                all_lamps.extend(lamp_list)
                
                logging.info(f"Berhasil mendapatkan {len(lamp_list)} lampu dari direktori ini")
                if lamp_list:
                    for idx, lamp in enumerate(lamp_list[:3], 1):  # Tampilkan 3 contoh saja
                        logging.info(f"  {idx}. {lamp.get('name', 'Tanpa nama')} (luid: {lamp.get('luid', 'N/A')})")
            else:
                logging.error(f"Gagal mendapatkan lampu: {response_map.status_code}")
            
            # Delay antar request direktori - PENTING untuk menghindari rate limiting
            time.sleep(2)
        
        # Hapus duplikat lampu berdasarkan luid
        unique_luids = set()
        unique_lamps = []
        
        for lamp in all_lamps:
            luid = lamp.get('luid', '')
            if luid and luid not in unique_luids:
                unique_luids.add(luid)
                unique_lamps.append(lamp)
        
        logging.info(f"\nTotal lampu unik yang ditemukan: {len(unique_lamps)}")
        
        # Langkah 3: Ambil QS time untuk setiap lampu menggunakan request yang diberikan
        logging.info("\nLangkah 3: Mengambil QS time untuk setiap lampu...")
        
        # Parameter untuk mengambil detail lampu
        params_detail = {
            "sid": "4491325c11b6478090fb71e7d6da86fb",
            "cmd": "data-lcu-light",
            "ctrl": "list",
            "version": "1",
            "lang": "en_US",
            "pid": project_id
        }
        
        # Variabel untuk melacak lampu dengan QS time lebih dari 1 jam yang lalu
        current_time = datetime.now()
        one_hour_ago = current_time - timedelta(hours=1)
        outdated_lamps = []
        
        # Hasil akhir
        hasil_akhir = []
        
        for idx, lamp in enumerate(unique_lamps, 1):
            lamp_name = lamp.get('name', 'Tanpa nama')
            lamp_luid = lamp.get('luid', '')
            logging.info(f"\nLampu {idx}/{len(unique_lamps)}: {lamp_name} (luid: {lamp_luid})")
            
            # Body request untuk detail lampu (seperti pada contoh yang diberikan)
            body_detail = {
                "wheres": [
                    {"k": "cuid", "o": "=", "v": "WMRTS6TCS8CJ"},
                    {"k": "ctype", "o": "=", "v": 17},
                    {"k": "luid", "o": "=", "v": lamp_luid}
                ],
                "orders": []
            }
            
            try:
                # Gunakan fungsi request dengan retry
                response_detail = make_request_with_retry(
                    'post',
                    url,
                    params_detail,
                    headers,
                    cookies,
                    json.dumps(body_detail)
                )
                
                if response_detail.status_code == 200 and response_detail.text.startswith("1||"):
                    json_text = response_detail.text[3:]
                    detail_data = json.loads(json_text)
                    
                    if detail_data and len(detail_data) > 0:
                        detail = detail_data[0]
                        
                        # Ambil timestamp dari data
                        timestamp_fields = ["rtime", "ltime", "dtime", "qstime"]
                        timestamps = {}
                        
                        for field in timestamp_fields:
                            if field in detail and detail[field]:
                                timestamp = detail[field]
                                date_time = datetime.fromtimestamp(timestamp / 1000)
                                timestamps[field] = {
                                    "timestamp": timestamp,
                                    "formatted": date_time.strftime('%Y-%m-%d %H:%M:%S'),
                                    "datetime": date_time
                                }
                        
                        # Ambil fields of interest
                        fields_of_interest = ["e", "pf", "life", "enabled", "dim", "u", "i", "p"]
                        interest_values = {}
                        
                        for field in fields_of_interest:
                            if field in detail:
                                interest_values[field] = detail[field]
                        
                        # Tampilkan hasil
                        if 'qstime' in timestamps:
                            logging.info(f"  QS Time: {timestamps['qstime']['formatted']}")
                            
                            # Periksa apakah QS time lebih dari 1 jam yang lalu
                            qs_datetime = timestamps['qstime']['datetime']
                            if qs_datetime < one_hour_ago:
                                logging.warning(f"  WARNING: QS time lebih dari 1 jam yang lalu!")
                                
                                # Tambahkan ke daftar lampu outdated
                                lamp_data = {
                                    'nama': lamp_name,
                                    'direktori': lamp.get('directory_name', ''),
                                    'luid': lamp_luid,
                                    'qstime': timestamps['qstime']['formatted'],
                                    'selisih': str(current_time - qs_datetime).split('.')[0]  # Format HH:MM:SS
                                }
                                outdated_lamps.append(lamp_data)
                        else:
                            logging.info("  QS Time tidak ditemukan")
                        
                        # Tambahkan ke hasil akhir
                        hasil_lampu = {
                            'nama': lamp_name,
                            'direktori': lamp.get('directory_name', ''),
                            'latitude': lamp.get('lat', 0),
                            'longitude': lamp.get('lng', 0),
                            'luid': lamp_luid,
                            'status': 'Aktif' if lamp.get('dim', 0) > 0 else 'Tidak aktif',
                            'timestamps': timestamps,
                            'values': interest_values
                        }
                        
                        hasil_akhir.append(hasil_lampu)
                    else:
                        logging.warning("  Tidak ada data detail yang ditemukan")
                else:
                    logging.error(f"  Gagal mendapatkan detail: {response_detail.status_code}")
            
            except Exception as e:
                logging.error(f"  Error saat mengambil detail lampu: {e}")
            
            # Delay antar request lampu - SANGAT PENTING untuk menghindari Connection Reset
            # Tambahkan delay random untuk mengurangi kemungkinan terdeteksi sebagai bot
            delay = random.uniform(1.0, 2.0)
            time.sleep(delay)
        
        # Langkah 4: Tampilkan statistik hasil
        logging.info("\nLangkah 4: Hasil akhir pengambilan data")
        logging.info(f"Berhasil mengambil data untuk {len(hasil_akhir)} lampu")
        
        # Tampilkan statistik
        aktif_count = sum(1 for lampu in hasil_akhir if lampu.get('status') == 'Aktif')
        nonaktif_count = len(hasil_akhir) - aktif_count
        logging.info(f"Total lampu: {len(hasil_akhir)}")
        logging.info(f"Lampu aktif: {aktif_count}")
        logging.info(f"Lampu tidak aktif: {nonaktif_count}")
        logging.info(f"Lampu dengan QS time > 1 jam yang lalu: {len(outdated_lamps)}")
        
        # Kelompokkan berdasarkan direktori
        by_directory = {}
        for lampu in hasil_akhir:
            direktori = lampu.get('direktori', 'Tidak diketahui')
            if direktori not in by_directory:
                by_directory[direktori] = []
            by_directory[direktori].append(lampu)
        
        logging.info("\n=== Ringkasan per Direktori ===")
        for direktori, lampu_list in by_directory.items():
            aktif = sum(1 for l in lampu_list if l.get('status') == 'Aktif')
            logging.info(f"{direktori}: {len(lampu_list)} lampu ({aktif} aktif, {len(lampu_list) - aktif} tidak aktif)")
        
        # Langkah 5: Kirim pesan ke Telegram jika ada lampu dengan QS time outdated
        if outdated_lamps:
            logging.info("\nLangkah 5: Mengirim notifikasi ke Telegram...")
            
            # Buat pesan untuk Telegram
            current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
            message = f"⚠️ PERINGATAN: {len(outdated_lamps)} lampu terdeteksi mati (QS time > 1 jam)\n"
            message += f"Waktu pemeriksaan: {current_time_str}\n\n"
            
            # Kelompokkan lampu outdated berdasarkan direktori
            outdated_by_dir = {}
            for lamp in outdated_lamps:
                dir_name = lamp['direktori']
                if dir_name not in outdated_by_dir:
                    outdated_by_dir[dir_name] = []
                outdated_by_dir[dir_name].append(lamp)
            
            # Tambahkan detail per direktori
            for dir_name, lamps in outdated_by_dir.items():
                message += f"\n📍 {dir_name} ({len(lamps)} lampu):\n"
                for i, lamp in enumerate(lamps, 1):
                    message += f"{i}. {lamp['nama']} - QS: {lamp['qstime']} (telat {lamp['selisih']})\n"
            
            # Tambahkan footer dengan link untuk akses ke dashboard
            message += "\n🔗 Akses dashboard: http://36.67.153.74:8800/web/map/panels/lamp.html"
            
            # Kirim pesan ke Telegram
            send_telegram_message(message)
        else:
            logging.info("\nSemua lampu memiliki QS time dalam 1 jam terakhir, tidak perlu mengirim notifikasi.")
        
        # Catat waktu selesai
        end_time = datetime.now()
        duration = end_time - start_time
        logging.info(f"Pemeriksaan selesai pada {end_time.strftime('%Y-%m-%d %H:%M:%S')}, durasi: {duration}")
        
        # Kirim laporan sukses ke Telegram
        success_message = f"✅ Pemeriksaan lampu selesai pada {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        success_message += f"Durasi: {duration}\n"
        success_message += f"Total lampu: {len(hasil_akhir)} ({aktif_count} aktif, {nonaktif_count} tidak aktif)\n"
        success_message += f"Lampu dengan QS time > 1 jam: {len(outdated_lamps)}"
        
        send_telegram_message(success_message)
        
        return True

    except Exception as e:
        import traceback
        error_message = f"❌ ERROR: Gagal melakukan pemeriksaan lampu: {e}"
        logging.error(error_message)
        logging.error(traceback.format_exc())
        send_telegram_message(error_message)
        return False

# Fungsi untuk menjalankan pada waktu tertentu
def run_scheduled_check():
    logging.info("Menjalankan pemeriksaan terjadwal")
    check_lamps()

# Set up scheduler
schedule.every().day.at("07:00").do(run_scheduled_check)  # Setiap hari jam 7 pagi
schedule.every().day.at("20:00").do(run_scheduled_check)  # Setiap hari jam 8 malam

# Jalankan langsung saat pertama kali dijalankan
if len(sys.argv) > 1 and sys.argv[1] == "--now":
    logging.info("Menjalankan pemeriksaan sekarang...")
    check_lamps()

# Informasikan jadwal pengecekan
logging.info("Program pengecek lampu dijalankan. Jadwal pemeriksaan:")
logging.info("- Setiap hari pukul 07:00 pagi")
logging.info("- Setiap hari pukul 20:00 malam")
logging.info("Program akan terus berjalan. Tekan Ctrl+C untuk menghentikan.")

# Loop utama untuk scheduler
try:
    while True:
        schedule.run_pending()
        time.sleep(60)  # Cek setiap 1 menit
except KeyboardInterrupt:
    logging.info("Program dihentikan oleh pengguna")