import requests
import json

# Konfigurasi koneksi ke kamera
ip_address = "192.168.0.3"
username = "admin"
password = "admin!123"
base_url = f"http://{ip_address}/LAPI/V1.0"

# Fungsi untuk mengambil data people counter berdasarkan area
def get_people_counter_area_data():
    people_counter_url = f"{base_url}/System/Event/Notification/PeopleCount/AreaRuleData"
    headers = {
        "Referer": "http://localhost:8000/receive_people_count"
    }
    response = requests.post(people_counter_url, auth=(username, password), headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print("Gagal mengambil data people counter berdasarkan area.")
        print("Status Code:", response.status_code)
        print("Response:", response.text)
        return None

# Fungsi untuk mencetak data people counter
def print_people_counter_data(data):
    if data:
        print("Data People Counter:")
        if "ChannelID" in data:
            print(f"  Channel ID: {data['ChannelID']}")
        if "AreaNum" in data:
            print(f"  Jumlah Area: {data['AreaNum']}")

        for area_rule_data in data.get("AreaRuleDataList", []):
            print(f"    Area ID: {area_rule_data['AreaID']}")
            print(f"    Jumlah Orang: {area_rule_data['ObjectNum']}")
            print()
    else:
        print("Tidak ada data people counter yang diterima.")

# Contoh penggunaan
people_counter_data = get_people_counter_area_data()
print_people_counter_data(people_counter_data)