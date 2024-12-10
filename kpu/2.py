import requests
import json
import time
from datetime import datetime

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
            'data': data['tungsura']['chart'],
            'timestamp': data.get('ts', '')
        }
    return {
        'status': 'Belum masuk',
        'data': None,
        'timestamp': None
    }

def scan_satu_desa(kode_desa, nama_desa):
    print(f"\nMengecek desa: {nama_desa} ({kode_desa})")
    
    # Dapatkan daftar TPS
    url_tps = f"{BASE_URL}/wilayah/pilkada/pkwkk/35/3518/351814/{kode_desa}.json"
    daftar_tps = get_data_from_api(url_tps)
    
    if not daftar_tps:
        print("Tidak dapat mengambil daftar TPS")
        return None
    
    total_tps = len(daftar_tps)
    sudah_masuk = 0
    total_suara = {
        "1000759": 0,  # Paslon 1
        "1000760": 0,  # Paslon 2
        "1000761": 0   # Paslon 3
    }
    
    for tps in daftar_tps:
        hasil = check_tps_data(kode_desa, tps['kode'])
        if hasil['status'] == 'Sudah masuk':
            sudah_masuk += 1
            for kandidat, suara in hasil['data'].items():
                if kandidat in total_suara and suara is not None:
                    total_suara[kandidat] += suara
        time.sleep(0.2)  # Jeda kecil
    
    return {
        'nama_desa': nama_desa,
        'total_tps': total_tps,
        'sudah_masuk': sudah_masuk,
        'belum_masuk': total_tps - sudah_masuk,
        'persentase': (sudah_masuk/total_tps)*100 if total_tps > 0 else 0,
        'total_suara': total_suara
    }

def scan_kecamatan():
    print("Memulai scanning kecamatan Bagor...")
    
    # Get daftar desa
    url_desa = f"{BASE_URL}/wilayah/pilkada/pkwkk/35/3518/351814.json"
    daftar_desa = get_data_from_api(url_desa)
    
    if not daftar_desa:
        print("Tidak dapat mengambil daftar desa")
        return
    
    hasil_kecamatan = []
    total_suara_kecamatan = {
        "1000759": 0,  # Paslon 1
        "1000760": 0,  # Paslon 2
        "1000761": 0   # Paslon 3
    }
    total_tps = 0
    total_masuk = 0
    
    print(f"\nTotal desa: {len(daftar_desa)}")
    
    for desa in daftar_desa:
        hasil_desa = scan_satu_desa(desa['kode'], desa['nama'])
        if hasil_desa:
            hasil_kecamatan.append(hasil_desa)
            total_tps += hasil_desa['total_tps']
            total_masuk += hasil_desa['sudah_masuk']
            
            for kandidat in total_suara_kecamatan:
                total_suara_kecamatan[kandidat] += hasil_desa['total_suara'][kandidat]
    
    # Print hasil
    print("\n=== HASIL SCANNING KECAMATAN ===")
    print(f"Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nProgress Input TPS:")
    print(f"Total TPS: {total_tps}")
    print(f"Sudah masuk: {total_masuk}")
    print(f"Belum masuk: {total_tps - total_masuk}")
    print(f"Persentase: {(total_masuk/total_tps)*100:.2f}%")
    
    print("\nPerolehan Suara Sementara:")
    print(f"Paslon 1: {total_suara_kecamatan['1000759']:,} suara")
    print(f"Paslon 2: {total_suara_kecamatan['1000760']:,} suara")
    print(f"Paslon 3: {total_suara_kecamatan['1000761']:,} suara")
    
    print("\nDetail per Desa:")
    for hasil in hasil_kecamatan:
        print(f"\n{hasil['nama_desa']}:")
        print(f"Progress: {hasil['sudah_masuk']}/{hasil['total_tps']} TPS ({hasil['persentase']:.2f}%)")
        print(f"Suara: {sum(hasil['total_suara'].values()):,}")

if __name__ == "__main__":
    scan_kecamatan()