import requests
import json
import time
from datetime import datetime
import sys

BASE_URL = "https://sirekappilkada-obj-data.kpu.go.id"

# Data paslon
PASLON = {
    "1000786": "Paslon No. 1",
    "1000787": "Paslon No. 2"
}

def get_data_from_api(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def update_progress(text):
    sys.stdout.write('\r' + text)
    sys.stdout.flush()

def format_suara(data_suara):
    if not data_suara:
        return "Belum ada data"
    
    total_suara = sum(v for k, v in data_suara.items() if k in PASLON and v is not None)
    result = []
    for kode, nama in PASLON.items():
        suara = data_suara.get(kode, 0) or 0
        persentase = (suara/total_suara*100) if total_suara > 0 else 0
        result.append(f"{nama}: {suara:,} suara ({persentase:.2f}%)")
    return "\n".join(result)

def check_tps_data(kode_kecamatan, kode_desa, kode_tps):
    url = f"{BASE_URL}/pilkada/hhcw/pkwkk/35/3571/{kode_kecamatan}/{kode_desa}/{kode_tps}.json"
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
    url_tps = f"{BASE_URL}/wilayah/pilkada/pkwkk/35/3571/{kode_kecamatan}/{kode_desa}.json"
    daftar_tps = get_data_from_api(url_tps)
    
    if not daftar_tps:
        return None
    
    total_tps = len(daftar_tps)
    sudah_masuk = 0
    total_suara = {
        "1000786": 0,
        "1000787": 0,
        
    }
    
    for idx, tps in enumerate(daftar_tps, 1):
        update_progress(f"Checking {nama_desa} - {tps['nama']} ({idx}/{total_tps})")
        
        hasil = check_tps_data(kode_kecamatan, kode_desa, tps['kode'])
        if hasil['status'] == 'Sudah masuk':
            sudah_masuk += 1
            for kandidat, suara in hasil['data'].items():
                if kandidat in total_suara and suara is not None:
                    total_suara[kandidat] += suara
            
            # Tampilkan hasil suara untuk TPS yang sudah masuk
            print(f"\nData masuk {nama_desa} - {tps['nama']}:")
            print(format_suara(hasil['data']))
            
        time.sleep(0.1)
    
    print()  # New line after progress
    
    return {
        'nama_desa': nama_desa,
        'total_tps': total_tps,
        'sudah_masuk': sudah_masuk,
        'belum_masuk': total_tps - sudah_masuk,
        'persentase': (sudah_masuk/total_tps)*100 if total_tps > 0 else 0,
        'total_suara': total_suara
    }

def scan_kecamatan(kode_kecamatan, nama_kecamatan):
    print(f"\nMulai scan Kecamatan {nama_kecamatan}")
    
    url_desa = f"{BASE_URL}/wilayah/pilkada/pkwkk/35/3571/{kode_kecamatan}.json"
    daftar_desa = get_data_from_api(url_desa)
    
    if not daftar_desa:
        return None
    
    print(f"Total {len(daftar_desa)} desa akan di scan")
    
    hasil_kecamatan = []
    total_suara_kecamatan = {
        "1000786": 0,
        "1000787": 0
    }
    total_tps = 0
    total_masuk = 0
    
    for idx, desa in enumerate(daftar_desa, 1):
        print(f"\nProses desa {idx}/{len(daftar_desa)}: {desa['nama']}")
        hasil_desa = scan_satu_desa(kode_kecamatan, desa['kode'], desa['nama'])
        if hasil_desa:
            hasil_kecamatan.append(hasil_desa)
            total_tps += hasil_desa['total_tps']
            total_masuk += hasil_desa['sudah_masuk']
            
            for kandidat in total_suara_kecamatan:
                total_suara_kecamatan[kandidat] += hasil_desa['total_suara'][kandidat]
            
            # Tampilkan total suara desa
            print(f"\nTotal suara {desa['nama']}:")
            print(format_suara(hasil_desa['total_suara']))
    
    return {
        'nama_kecamatan': nama_kecamatan,
        'hasil_desa': hasil_kecamatan,
        'total_tps': total_tps,
        'total_masuk': total_masuk,
        'total_suara': total_suara_kecamatan
    }

def scan_kabupaten():
    print("=== SCANNING KOTA KEDIRI ===")
    print(f"Waktu mulai: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    url_kecamatan = f"{BASE_URL}/wilayah/pilkada/pkwkk/35/3571.json"
    daftar_kecamatan = get_data_from_api(url_kecamatan)
    
    if not daftar_kecamatan:
        print("Tidak dapat mengambil daftar kecamatan")
        return
    
    print(f"Total {len(daftar_kecamatan)} kecamatan akan di scan\n")
    
    hasil_kabupaten = []
    total_suara_kabupaten = {
        "1000786": 0,
        "1000787": 0
    }
    total_tps_kab = 0
    total_masuk_kab = 0
    
    for idx, kecamatan in enumerate(daftar_kecamatan, 1):
        print(f"Proses kecamatan {idx}/{len(daftar_kecamatan)}")
        hasil_kec = scan_kecamatan(kecamatan['kode'], kecamatan['nama'])
        if hasil_kec:
            hasil_kabupaten.append(hasil_kec)
            total_tps_kab += hasil_kec['total_tps']
            total_masuk_kab += hasil_kec['total_masuk']
            
            for kandidat in total_suara_kabupaten:
                total_suara_kabupaten[kandidat] += hasil_kec['total_suara'][kandidat]
            
            # Tampilkan total suara kecamatan
            print(f"\nTotal suara Kecamatan {kecamatan['nama']}:")
            print(format_suara(hasil_kec['total_suara']))
    
    print(f"\nWaktu selesai: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n=== REKAP KOTA KEDIRI ===")
    print(f"\nProgress Input TPS:")
    print(f"Total TPS: {total_tps_kab:,}")
    print(f"Sudah masuk: {total_masuk_kab:,}")
    print(f"Belum masuk: {total_tps_kab - total_masuk_kab:,}")
    print(f"Persentase: {(total_masuk_kab/total_tps_kab*100 if total_tps_kab > 0 else 0):.2f}%")
    
    print("\nPerolehan Suara Sementara:")
    print(format_suara(total_suara_kabupaten))

if __name__ == "__main__":
    scan_kabupaten()