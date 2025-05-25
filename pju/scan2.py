import requests
import json
from datetime import datetime

# API URL and parameters
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

# Langkah 1: Ambil daftar direktori
print("Langkah 1: Mengambil daftar direktori dari Project ID...")
params_direktori = {
    "sid": "4491325c11b6478090fb71e7d6da86fb",
    "cmd": "project-dir",
    "ctrl": "dir-data",
    "version": "1",
    "lang": "en_US"
}

body_direktori = json.dumps(project_id)

try:
    response_direktori = requests.post(
        url,
        params=params_direktori,
        headers=headers,
        cookies=cookies,
        data=body_direktori,
        verify=False
    )
    
    direktori_list = []
    
    if response_direktori.status_code == 200 and response_direktori.text.startswith("1||"):
        json_text = response_direktori.text[3:]
        direktori_list = json.loads(json_text)
        
        print(f"Berhasil mendapatkan {len(direktori_list)} direktori:")
        for idx, dir in enumerate(direktori_list, 1):
            print(f"{idx}. {dir['name']} (ID: {dir['did']})")
            
            # Tampilkan informasi grup lampu jika ada
            if dir.get('lampGroups') and len(dir['lampGroups']) > 0:
                for group in dir['lampGroups']:
                    print(f"   - Grup: {group.get('groupName', 'Tanpa nama')} (ID: {group.get('groupId', 'N/A')})")
    else:
        print(f"Gagal mendapatkan direktori: {response_direktori.status_code}")
    
    # Langkah 2: Ambil daftar lampu menggunakan endpoint map-item
    print("\nLangkah 2: Mengambil daftar lampu dari semua direktori...")
    
    all_lamps = []
    valid_dirs = [d for d in direktori_list if d.get('lat', 0) != 0 and d.get('lng', 0) != 0]
    
    for dir_index, directory in enumerate(valid_dirs, 1):
        print(f"\nMengambil lampu untuk direktori {dir_index}/{len(valid_dirs)}: {directory['name']}")
        
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
        
        response_map = requests.post(
            url,
            params=params_map,
            headers=headers,
            cookies=cookies,
            data=json.dumps(body_map),
            verify=False
        )
        
        if response_map.status_code == 200 and response_map.text.startswith("1||"):
            json_text = response_map.text[3:]
            lamp_list = json.loads(json_text)
            
            # Tambahkan informasi direktori ke setiap lampu
            for lamp in lamp_list:
                lamp['directory_name'] = directory['name']
                lamp['directory_id'] = directory['did']
            
            all_lamps.extend(lamp_list)
            
            print(f"Berhasil mendapatkan {len(lamp_list)} lampu dari direktori ini")
            if lamp_list:
                for idx, lamp in enumerate(lamp_list[:3], 1):  # Tampilkan 3 contoh saja
                    print(f"  {idx}. {lamp.get('name', 'Tanpa nama')} (luid: {lamp.get('luid', 'N/A')})")
        else:
            print(f"Gagal mendapatkan lampu: {response_map.status_code}")
    
    # Hapus duplikat lampu berdasarkan luid
    unique_luids = set()
    unique_lamps = []
    
    for lamp in all_lamps:
        luid = lamp.get('luid', '')
        if luid and luid not in unique_luids:
            unique_luids.add(luid)
            unique_lamps.append(lamp)
    
    print(f"\nTotal lampu unik yang ditemukan: {len(unique_lamps)}")
    
    # Langkah 3: Ambil QS time untuk setiap lampu menggunakan request yang diberikan
    print("\nLangkah 3: Mengambil QS time untuk setiap lampu...")
    
    # Parameter untuk mengambil detail lampu
    params_detail = {
        "sid": "4491325c11b6478090fb71e7d6da86fb",
        "cmd": "data-lcu-light",
        "ctrl": "list",
        "version": "1",
        "lang": "en_US",
        "pid": project_id
    }
    
    # Hasil akhir
    hasil_akhir = []
    
    for idx, lamp in enumerate(unique_lamps, 1):
        lamp_name = lamp.get('name', 'Tanpa nama')
        lamp_luid = lamp.get('luid', '')
        print(f"\nLampu {idx}/{len(unique_lamps)}: {lamp_name} (luid: {lamp_luid})")
        
        # Body request untuk detail lampu (seperti pada contoh yang diberikan)
        body_detail = {
            "wheres": [
                {"k": "cuid", "o": "=", "v": "WMRTS6TCS8CJ"},
                {"k": "ctype", "o": "=", "v": 17},
                {"k": "luid", "o": "=", "v": lamp_luid}
            ],
            "orders": []
        }
        
        # Kirim request
        response_detail = requests.post(
            url,
            params=params_detail,
            headers=headers,
            cookies=cookies,
            data=json.dumps(body_detail),
            verify=False
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
                            "formatted": date_time.strftime('%Y-%m-%d %H:%M:%S')
                        }
                
                # Ambil fields of interest
                fields_of_interest = ["e", "pf", "life", "enabled", "dim", "u", "i", "p"]
                interest_values = {}
                
                for field in fields_of_interest:
                    if field in detail:
                        interest_values[field] = detail[field]
                
                # Tampilkan hasil
                if 'qstime' in timestamps:
                    print(f"  QS Time: {timestamps['qstime']['formatted']}")
                else:
                    print("  QS Time tidak ditemukan")
                
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
                print("  Tidak ada data detail yang ditemukan")
        else:
            print(f"  Gagal mendapatkan detail: {response_detail.status_code}")
    
    # Langkah 4: Tampilkan hasil akhir
    print("\nLangkah 4: Hasil akhir pengambilan data")
    print(f"Berhasil mengambil data untuk {len(hasil_akhir)} lampu")
    
    # Tampilkan data dalam format tabel
    print("\n{:<20} {:<15} {:<15} {:<15} {:<25} {:<10}".format(
        "Nama Lampu", "Direktori", "Latitude", "Longitude", "QS Time", "Status"
    ))
    print("-" * 100)
    
    for lampu in hasil_akhir:
        # Persingkat nama direktori jika terlalu panjang
        direktori_singkat = lampu.get('direktori', 'N/A')
        if len(direktori_singkat) > 12:
            direktori_singkat = direktori_singkat[:12] + "..."
        
        # Ambil QS Time jika ada
        qs_time = "N/A"
        if 'timestamps' in lampu and 'qstime' in lampu['timestamps']:
            qs_time = lampu['timestamps']['qstime']['formatted']
        
        print("{:<20} {:<15} {:<15} {:<15} {:<25} {:<10}".format(
            lampu.get('nama', 'N/A')[:20],
            direktori_singkat,
            str(lampu.get('latitude', 'N/A'))[:15],
            str(lampu.get('longitude', 'N/A'))[:15],
            qs_time,
            lampu.get('status', 'N/A')
        ))
    
    # Tampilkan statistik
    print("\n=== Statistik Lampu ===")
    aktif_count = sum(1 for lampu in hasil_akhir if lampu.get('status') == 'Aktif')
    nonaktif_count = len(hasil_akhir) - aktif_count
    print(f"Total lampu: {len(hasil_akhir)}")
    print(f"Lampu aktif: {aktif_count}")
    print(f"Lampu tidak aktif: {nonaktif_count}")
    
    # Kelompokkan berdasarkan direktori
    by_directory = {}
    for lampu in hasil_akhir:
        direktori = lampu.get('direktori', 'Tidak diketahui')
        if direktori not in by_directory:
            by_directory[direktori] = []
        by_directory[direktori].append(lampu)
    
    print("\n=== Ringkasan per Direktori ===")
    for direktori, lampu_list in by_directory.items():
        aktif = sum(1 for l in lampu_list if l.get('status') == 'Aktif')
        print(f"{direktori}: {len(lampu_list)} lampu ({aktif} aktif, {len(lampu_list) - aktif} tidak aktif)")

except Exception as e:
    import traceback
    print(f"Terjadi kesalahan: {e}")
    traceback.print_exc()