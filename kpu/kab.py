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

def check_tps_data(kode_kecamatan, kode_desa, kode_tps):
    url = f"{BASE_URL}/pilkada/hhcw/pkwkk/35/3518/{kode_kecamatan}/{kode_desa}/{kode_tps}.json"
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

def scan_satu_desa(kode_kecamatan, kode_desa, nama_desa):
    # Dapatkan daftar TPS
    url_tps = f"{BASE_URL}/wilayah/pilkada/pkwkk/35/3518/{kode_kecamatan}/{kode_desa}.json"
    daftar_tps = get_data_from_api(url_tps)
    
    if not daftar_tps:
        return None
    
    total_tps = len(daftar_tps)
    sudah_masuk = 0
    total_suara = {
        "1000759": 0,  # Paslon 1
        "1000760": 0,  # Paslon 2
        "1000761": 0   # Paslon 3
    }
    
    for tps in daftar_tps:
        hasil = check_tps_data(kode_kecamatan, kode_desa, tps['kode'])
        if hasil['status'] == 'Sudah masuk':
            sudah_masuk += 1
            for kandidat, suara in hasil['data'].items():
                if kandidat in total_suara and suara is not None:
                    total_suara[kandidat] += suara
        time.sleep(0.1)  # Jeda kecil
    
    return {
        'nama_desa': nama_desa,
        'total_tps': total_tps,
        'sudah_masuk': sudah_masuk,
        'belum_masuk': total_tps - sudah_masuk,
        'persentase': (sudah_masuk/total_tps)*100 if total_tps > 0 else 0,
        'total_suara': total_suara
    }

def scan_kecamatan(kode_kecamatan, nama_kecamatan):
    print(f"\nScanning kecamatan {nama_kecamatan}...")
    
    url_desa = f"{BASE_URL}/wilayah/pilkada/pkwkk/35/3518/{kode_kecamatan}.json"
    daftar_desa = get_data_from_api(url_desa)
    
    if not daftar_desa:
        return None
    
    hasil_kecamatan = []
    total_suara_kecamatan = {
        "1000759": 0,  # Paslon 1
        "1000760": 0,  # Paslon 2
        "1000761": 0   # Paslon 3
    }
    total_tps = 0
    total_masuk = 0
    
    for desa in daftar_desa:
        hasil_desa = scan_satu_desa(kode_kecamatan, desa['kode'], desa['nama'])
        if hasil_desa:
            hasil_kecamatan.append(hasil_desa)
            total_tps += hasil_desa['total_tps']
            total_masuk += hasil_desa['sudah_masuk']
            
            for kandidat in total_suara_kecamatan:
                total_suara_kecamatan[kandidat] += hasil_desa['total_suara'][kandidat]
    
    return {
        'nama_kecamatan': nama_kecamatan,
        'hasil_desa': hasil_kecamatan,
        'total_tps': total_tps,
        'total_masuk': total_masuk,
        'total_suara': total_suara_kecamatan
    }

def scan_kabupaten():
    print("Memulai scanning Kabupaten Nganjuk...")
    
    # Get daftar kecamatan
    url_kecamatan = f"{BASE_URL}/wilayah/pilkada/pkwkk/35/3518.json"
    daftar_kecamatan = get_data_from_api(url_kecamatan)
    
    if not daftar_kecamatan:
        print("Tidak dapat mengambil daftar kecamatan")
        return
    
    hasil_kabupaten = []
    total_suara_kabupaten = {
        "1000759": 0,  # Paslon 1
        "1000760": 0,  # Paslon 2
        "1000761": 0   # Paslon 3
    }
    total_tps_kab = 0
    total_masuk_kab = 0
    
    print(f"Total kecamatan: {len(daftar_kecamatan)}")
    
    for kecamatan in daftar_kecamatan:
        hasil_kec = scan_kecamatan(kecamatan['kode'], kecamatan['nama'])
        if hasil_kec:
            hasil_kabupaten.append(hasil_kec)
            total_tps_kab += hasil_kec['total_tps']
            total_masuk_kab += hasil_kec['total_masuk']
            
            for kandidat in total_suara_kabupaten:
                total_suara_kabupaten[kandidat] += hasil_kec['total_suara'][kandidat]
    
    # Print detail per kecamatan
    print("\n=== DETAIL PER KECAMATAN ===")
    for hasil_kec in hasil_kabupaten:
        print(f"\nKecamatan {hasil_kec['nama_kecamatan']}:")
        print(f"Progress: {hasil_kec['total_masuk']}/{hasil_kec['total_tps']} TPS " +
              f"({(hasil_kec['total_masuk']/hasil_kec['total_tps']*100 if hasil_kec['total_tps'] > 0 else 0):.2f}%)")
        for hasil_desa in hasil_kec['hasil_desa']:
            print(f"  {hasil_desa['nama_desa']}: {hasil_desa['sudah_masuk']}/{hasil_desa['total_tps']} " +
                  f"({hasil_desa['persentase']:.2f}%)")
    
    # Print rekap
    print("\n=== REKAP KABUPATEN NGANJUK ===")
    print(f"Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nProgress Input TPS:")
    print(f"Total TPS: {total_tps_kab:,}")
    print(f"Sudah masuk: {total_masuk_kab:,}")
    print(f"Belum masuk: {total_tps_kab - total_masuk_kab:,}")
    print(f"Persentase: {(total_masuk_kab/total_tps_kab*100 if total_tps_kab > 0 else 0):.2f}%")
    
    print("\nPerolehan Suara Sementara:")
    total_suara = sum(total_suara_kabupaten.values())
    for kandidat, suara in total_suara_kabupaten.items():
        persentase = (suara/total_suara*100) if total_suara > 0 else 0
        print(f"Paslon {kandidat[-1]}: {suara:,} suara ({persentase:.2f}%)")

if __name__ == "__main__":
    scan_kabupaten()