import requests
import json
import time

BASE_URL = "https://sirekappilkada-obj-data.kpu.go.id"

def get_data_from_api(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def check_tps_data(kode_desa, kode_tps):
    url = f"{BASE_URL}/pilkada/hhcw/pkwkk/35/3518/351814/{kode_desa}/{kode_tps}.json"
    data = get_data_from_api(url)
    
    if data and data.get('tungsura') and data['tungsura'].get('chart'):
        return {
            'status': 'Sudah masuk',
            'data': data['tungsura']['chart']
        }
    return {
        'status': 'Belum masuk',
        'data': None
    }

def scan_satu_desa(kode_desa):
    print(f"\nMengecek TPS di desa dengan kode: {kode_desa}")
    
    # Dapatkan daftar TPS
    url_tps = f"{BASE_URL}/wilayah/pilkada/pkwkk/35/3518/351814/{kode_desa}.json"
    daftar_tps = get_data_from_api(url_tps)
    
    if not daftar_tps:
        print("Tidak dapat mengambil daftar TPS")
        return
    
    total_tps = len(daftar_tps)
    sudah_masuk = 0
    
    print(f"Total TPS: {total_tps}")
    
    for tps in daftar_tps:
        hasil = check_tps_data(kode_desa, tps['kode'])
        print(f"\nTPS {tps['nama']}:")
        print(f"Status: {hasil['status']}")
        
        if hasil['status'] == 'Sudah masuk':
            sudah_masuk += 1
            print("Hasil suara:")
            for kandidat, suara in hasil['data'].items():
                if kandidat != 'null' and suara is not None:
                    print(f"  Kandidat {kandidat}: {suara} suara")
        
        time.sleep(0.5)  # Jeda untuk menghindari rate limiting
    
    print(f"\nRingkasan:")
    print(f"Total TPS: {total_tps}")
    print(f"Sudah masuk: {sudah_masuk}")
    print(f"Belum masuk: {total_tps - sudah_masuk}")
    print(f"Persentase: {(sudah_masuk/total_tps)*100:.2f}%")

# Contoh penggunaan untuk satu desa
kode_desa = "3518142012"  # Ganti dengan kode desa yang ingin dicek
scan_satu_desa(kode_desa)