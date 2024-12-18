import requests
import json
import time
import csv
from datetime import datetime

def get_session():
    session = requests.Session()
    
    # First, visit the main page to get initial cookies
    main_url = "https://sipp.bpjsketenagakerjaan.go.id"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "id,en-US;q=0.7,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }
    
    try:
        # Get main page first
        session.get(main_url, headers=headers)
        
        # Now set headers for API requests
        api_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
            "Accept": "*/*",
            "Accept-Language": "id,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://sipp.bpjsketenagakerjaan.go.id",
            "Connection": "keep-alive",
            "Referer": "https://sipp.bpjsketenagakerjaan.go.id/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        }
        session.headers.update(api_headers)
        
        return session
    except Exception as e:
        print(f"Error initializing session: {e}")
        return None

def process_kpj(kpj, session, csv_writer):
    url = "https://sipp.bpjsketenagakerjaan.go.id/tenaga-kerja/baru/get-tk-kpj"
    data = {"kpj": kpj}
    
    try:
        response = session.post(url, data=data)
        
        # Print debug information
        print(f"\nRequest URL: {url}")
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response text: {response.text[:200]}...")
        
        if response.status_code == 404:
            print("Error: Endpoint not found. Checking alternative URL...")
            # You might want to try alternative URLs here
            return
            
        formatted_response, csv_data = format_response(response.text)
        print(formatted_response)
        
        if csv_data:
            csv_writer.writerow(csv_data)
        
        time.sleep(1)
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to process KPJ {kpj}: {e}")
        csv_writer.writerow({
            'KPJ': kpj,
            'Status': 'FAILED',
            'Error': str(e)
        })

def format_response(response_text):
    try:
        data = json.loads(response_text)
        
        if data['ret'] == '-1':
            return f"KPJ {data['msg']}", None
            
        if data['ret'] == '0' and 'data' in data and len(data['data']) > 0:
            tk_data = data['data'][0]
            formatted = (
                f"{tk_data.get('tgl_lahir', '').split('-')[1]}-{tk_data.get('tgl_lahir', '').split('-')[2]}&"
                f"{tk_data.get('nomor_identitas', 'null')}&"
                f"{tk_data.get('nama_tk', 'null')}&"
                f"{tk_data.get('tempat_lahir', 'null')}&"
                f"{tk_data.get('alamat', 'null')}&"
                f"{tk_data.get('tgl_lahir', 'null')}&0&"
                f"{tk_data.get('jenis_identitas', 'null')}&"
                f"{tk_data.get('jenis_kelamin', 'null')}&"
                f"{tk_data.get('email', 'null')}&"
                f"{tk_data.get('handphone', 'null')}"
            )
            
            csv_data = {
                'KPJ': tk_data.get('kpj', ''),
                'Nama': tk_data.get('nama_tk', ''),
                'NIK': tk_data.get('nomor_identitas', ''),
                'Jenis Kelamin': tk_data.get('jenis_kelamin', ''),
                'Tempat Lahir': tk_data.get('tempat_lahir', ''),
                'Tanggal Lahir': tk_data.get('tgl_lahir', ''),
                'Alamat': tk_data.get('alamat', ''),
                'Email': tk_data.get('email', ''),
                'No HP': tk_data.get('handphone', ''),
                'Status': 'ACTIVE'
            }
            return formatted, csv_data
        
        return f"Error processing response: {response_text}", None
        
    except json.JSONDecodeError:
        return f"Invalid JSON response: {response_text}", None
    except Exception as e:
        return f"Error: {str(e)}", None

def main():
    session = get_session()
    if not session:
        print("Failed to initialize session. Exiting...")
        return
        
    # Create CSV file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"bpjs_data_{timestamp}.csv"
    
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['KPJ', 'Nama', 'NIK', 'Jenis Kelamin', 'Tempat Lahir', 
                     'Tanggal Lahir', 'Alamat', 'Email', 'No HP', 'Status', 'Error']
        csv_writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        csv_writer.writeheader()
        
        print("Enter KPJ numbers (one per line, empty line to finish):")
        while True:
            kpj = input().strip()
            if not kpj:
                break
            process_kpj(kpj, session, csv_writer)
        
        print(f"\nData saved to {csv_filename}")

if __name__ == "__main__":
    main()