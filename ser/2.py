import requests
import time
import json
from datetime import datetime
import pytz

BRIDGE_URL = 'https://myproject123.com/bridge.php'

def handle_request(request):
    """Handle berbagai jenis request"""
    endpoint = request.get('endpoint')
    request_id = request.get('request_id')
    data = request.get('data', {})
    
    # Timezone Jakarta
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(jakarta_tz)
    
    responses = {
        'time': {
            'current_time': now.strftime('%H:%M:%S'),
            'timezone': 'Asia/Jakarta'
        },
        'date': {
            'current_date': now.strftime('%Y-%m-%d'),
            'day': now.strftime('%A')
        },
        'datetime': {
            'datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
            'timezone': 'Asia/Jakarta'
        },
        'status': {
            'status': 'online',
            'uptime': 'running',
            'timestamp': now.isoformat()
        }
    }
    
    # Return response sesuai endpoint atau default
    response_data = responses.get(endpoint, {
        'message': f'Unknown endpoint: {endpoint}',
        'received_data': data,
        'timestamp': now.isoformat()
    })
    
    return response_data, request_id

def start_polling():
    print(f"Starting polling to {BRIDGE_URL}")
    
    while True:
        try:
            # Cek request baru
            response = requests.get(f"{BRIDGE_URL}?action=check")
            data = response.json()
            
            if data['status'] == 'success' and data['requests']:
                for request in data['requests']:
                    # Process request
                    result, request_id = handle_request(request)
                    
                    # Kirim response dengan request_id
                    requests.post(
                        f"{BRIDGE_URL}?action=response&request_id={request_id}", 
                        json={'data': result}
                    )
            
            time.sleep(1)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    start_polling()