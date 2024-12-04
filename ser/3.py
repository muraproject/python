import requests
import time
import json
from datetime import datetime
import pytz
import traceback

BRIDGE_URL = 'https://myproject123.com/bridge.php'

def get_dashboard():
    """Menghasilkan konten dashboard"""
    return {
        'content_type': 'text/html',
        'content': '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .animate-pulse {
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: .5; }
        }
    </style>
</head>
<body class="bg-gray-100">
    <div class="min-h-screen">
        <!-- Sidebar -->
        <nav class="fixed top-0 left-0 h-full w-64 bg-gray-800 text-white p-4">
            <div class="text-2xl font-bold mb-8">Dashboard</div>
            <ul class="space-y-2">
                <li class="hover:bg-gray-700 p-2 rounded cursor-pointer">Overview</li>
                <li class="hover:bg-gray-700 p-2 rounded cursor-pointer">Analytics</li>
                <li class="hover:bg-gray-700 p-2 rounded cursor-pointer">Reports</li>
                <li class="hover:bg-gray-700 p-2 rounded cursor-pointer">Settings</li>
            </ul>
        </nav>

        <!-- Main Content -->
        <div class="ml-64 p-8">
            <header class="bg-white shadow rounded-lg p-4 mb-6">
                <div class="flex justify-between items-center">
                    <h1 class="text-2xl font-bold">Overview</h1>
                    <div id="current-time" class="text-gray-600"></div>
                </div>
            </header>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-gray-500 text-sm font-medium">Total Users</h3>
                    <p class="text-3xl font-bold" id="total-users">0</p>
                </div>
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-gray-500 text-sm font-medium">Active Sessions</h3>
                    <p class="text-3xl font-bold" id="active-sessions">0</p>
                </div>
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-gray-500 text-sm font-medium">Revenue</h3>
                    <p class="text-3xl font-bold" id="revenue">$0</p>
                </div>
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-gray-500 text-sm font-medium">Growth</h3>
                    <p class="text-3xl font-bold" id="growth">0%</p>
                </div>
            </div>

            <div class="bg-white rounded-lg shadow p-6">
                <h2 class="text-xl font-bold mb-4">Analytics Overview</h2>
                <div id="chart" class="h-64 bg-gray-50"></div>
            </div>
        </div>
    </div>

    <script>
        // Update waktu
        function updateTime() {
            const now = new Date();
            document.getElementById('current-time').textContent = now.toLocaleTimeString();
        }
        setInterval(updateTime, 1000);
        updateTime();

        // Update statistik
        function updateStats() {
            document.getElementById('total-users').textContent = Math.floor(Math.random() * 10000);
            document.getElementById('active-sessions').textContent = Math.floor(Math.random() * 1000);
            document.getElementById('revenue').textContent = '$' + Math.floor(Math.random() * 100000);
            document.getElementById('growth').textContent = (Math.random() * 20).toFixed(1) + '%';
        }
        setInterval(updateStats, 5000);
        updateStats();
    </script>
</body>
</html>'''
    }

def handle_request(request_data):
    """Handle request dan return response yang sesuai"""
    try:
        endpoint = request_data.get('endpoint')
        request_id = request_data.get('request_id')

        if endpoint == 'dashboard':
            return {
                'request_id': request_id,
                'data': get_dashboard()
            }
        else:
            return {
                'request_id': request_id,
                'data': {
                    'content_type': 'text/plain',
                    'content': f'Unknown endpoint: {endpoint}'
                }
            }
    except Exception as e:
        print(f"Error handling request: {e}")
        traceback.print_exc()
        return None

def start_polling():
    """Main polling loop"""
    print(f"Starting polling to {BRIDGE_URL}")
    
    while True:
        try:
            # Check untuk request baru
            response = requests.get(f"{BRIDGE_URL}?action=check")
            requests_data = response.json()
            
            # Handle requests jika ada
            if isinstance(requests_data, list):  # Perubahan di sini
                for request in requests_data:  # Dan di sini
                    result = handle_request(request)
                    if result:
                        # Kirim response
                        response = requests.post(
                            f"{BRIDGE_URL}?action=response",
                            json=result
                        )
                        print(f"Response sent: {response.status_code}")
            
            # Tunggu sebentar sebelum polling lagi
            time.sleep(1)
            
        except Exception as e:
            print(f"Error in polling loop: {e}")
            traceback.print_exc()
            time.sleep(5)

if __name__ == '__main__':
    start_polling()