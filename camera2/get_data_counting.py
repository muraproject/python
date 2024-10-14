import requests
from requests.auth import HTTPDigestAuth

base_url = "http://8.215.44.249:3466/LAPI/V1.0"
auth = HTTPDigestAuth('admin', 'admin!123')

def get_latest_line_people_count():
    url = f"{base_url}/Smart/LinesPeopleCounting/1/Status"
    response = requests.get(url, auth=auth)
    if response.status_code == 200:
        data = response.json()
        print(data)
        # Asumsi struktur respons, sesuaikan jika berbeda
        if 'Response' in data and 'Data' in data['Response']:
            count_data = data['Response']['Data']
            return count_data
        else:
            return "Struktur respons tidak sesuai yang diharapkan"
    else:
        return f"Error: {response.status_code}, {response.text}"

# Main execution
if __name__ == "__main__":
    print("Mengambil data Lines People Counting terakhir...")
    latest_count = get_latest_line_people_count()
    print("Data terakhir Lines People Counting:")
    print(latest_count)

    # Jika struktur respons diketahui, kita bisa mengekstrak informasi spesifik
    if isinstance(latest_count, dict):
        if 'EnterCount' in latest_count:
            print(f"Jumlah orang masuk: {latest_count['EnterCount']}")
        if 'ExitCount' in latest_count:
            print(f"Jumlah orang keluar: {latest_count['ExitCount']}")
        if 'PassingCount' in latest_count:
            print(f"Jumlah orang lewat: {latest_count['PassingCount']}")
    else:
        print(latest_count)  # Mencetak pesan error jika ada