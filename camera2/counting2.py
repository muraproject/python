import requests
from requests.auth import HTTPDigestAuth
import json

# Konfigurasi API
base_url = "http://8.215.44.249:3466/LAPI/V1.0"
auth = HTTPDigestAuth('admin', 'admin!123')

def get_people_count_data():
    url = f"{base_url}/Smart/LinesPeopleCounting/1/Status"
    try:
        response = requests.get(url, auth=auth)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {response.headers}")
        print(f"Raw Response: {response.text}")
        
        response.raise_for_status()  # Raise an exception for bad status codes
        
        try:
            return response.json()
        except json.JSONDecodeError:
            print("Respons bukan JSON yang valid")
            return None
    except requests.RequestException as e:
        print(f"Error saat melakukan request: {e}")
        return None

def print_people_count(data):
    print("Data yang diterima:")
    print(json.dumps(data, indent=2))  # Print the entire data structure
    
    if isinstance(data, dict):
        if 'Response' in data and 'Data' in data['Response']:
            count_data = data['Response']['Data']
            if isinstance(count_data, dict):
                print(f"Total masuk: {count_data.get('EnterCount', 'Tidak tersedia')}")
                print(f"Total keluar: {count_data.get('ExitCount', 'Tidak tersedia')}")
                print(f"Total lewat: {count_data.get('PassingCount', 'Tidak tersedia')}")
            else:
                print(f"Data tidak dalam format yang diharapkan. Tipe data: {type(count_data)}")
        else:
            print("Struktur data tidak sesuai yang diharapkan")
    else:
        print(f"Data bukan dictionary. Tipe data: {type(data)}")

def main():
    print("Mengambil data people counting...")
    data = get_people_count_data()
    if data is not None:
        print_people_count(data)
    else:
        print("Gagal mendapatkan data people counting")

if __name__ == "__main__":
    main()