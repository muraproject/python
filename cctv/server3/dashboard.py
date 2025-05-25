# dashboard.py
from flask import Flask, render_template, jsonify, request
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
from flask_cors import CORS

# Inisialisasi aplikasi Flask
app = Flask(__name__)
CORS(app)

# Konfigurasi
MAIN_SERVER_URL = "http://localhost:5000"  # URL server utama
DASHBOARD_PORT = 5001  # Port untuk dashboard analitik

# Routes
@app.route('/')
def index():
    """Halaman utama dashboard"""
    return render_template('index.html')

@app.route('/api/summary')
def get_summary():
    """Mendapatkan ringkasan data counting kendaraan untuk bulan ini"""
    try:
        # Mengambil data dari server utama
        response = requests.get(f"{MAIN_SERVER_URL}/api/data/counting-kendaraan/current-month/summary")
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": "Gagal mengambil data dari server utama"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/hourly-distribution')
def get_hourly_distribution():
    """Mendapatkan distribusi lalu lintas per jam"""
    try:
        # Parameter
        date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        camera_name = request.args.get('camera_name')
        
        # Membangun URL request
        url = f"{MAIN_SERVER_URL}/api/data/daily-stats?date={date}"
        if camera_name:
            url += f"&camera_name={camera_name}"
        
        # Mengambil data dari server utama
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return jsonify(data)
        else:
            return jsonify({"error": "Gagal mengambil data dari server utama"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/weekly-trend')
def get_weekly_trend():
    """Mendapatkan tren mingguan untuk data lalu lintas"""
    try:
        # Parameter
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        camera_name = request.args.get('camera_name')
        
        # Format tanggal
        start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
        end_date_str = end_date.strftime('%Y-%m-%d %H:%M:%S')
        
        # Membangun URL request
        url = f"{MAIN_SERVER_URL}/api/data/filter?start_date={start_date_str}&end_date={end_date_str}"
        if camera_name:
            url += f"&camera_name={camera_name}"
        
        # Mengambil data dari server utama
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            # Proses data untuk tren mingguan (agregasi per hari)
            trend_data = process_weekly_trend(data)
            return jsonify(trend_data)
        else:
            return jsonify({"error": "Gagal mengambil data dari server utama"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/camera-list')
def get_camera_list():
    """Mendapatkan daftar kamera yang aktif untuk filter"""
    try:
        # Mengambil data dari server utama
        response = requests.get(f"{MAIN_SERVER_URL}/api/camera-settings")
        if response.status_code == 200:
            # Filter hanya kamera yang aktif untuk counting kendaraan
            cameras = [camera for camera in response.json() 
                      if camera.get('mode') == 'Counting Kendaraan' and camera.get('enabled')]
            return jsonify(cameras)
        else:
            return jsonify({"error": "Gagal mengambil data dari server utama"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vehicle-comparison')
def get_vehicle_comparison():
    """Mendapatkan perbandingan jenis kendaraan"""
    try:
        # Parameter
        month = request.args.get('month', datetime.now().month)
        year = request.args.get('year', datetime.now().year)
        camera_name = request.args.get('camera_name')
        
        # Membangun URL request
        url = f"{MAIN_SERVER_URL}/api/data/time-filter?month={month}&year={year}"
        if camera_name:
            url += f"&camera_name={camera_name}"
        
        # Mengambil data dari server utama
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            # Proses data untuk perbandingan jenis kendaraan
            comparison_data = process_vehicle_comparison(data)
            return jsonify(comparison_data)
        else:
            return jsonify({"error": "Gagal mengambil data dari server utama"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/peak-hours')
def get_peak_hours():
    """Mendapatkan jam-jam sibuk berdasarkan data historis"""
    try:
        # Parameter
        days = int(request.args.get('days', 30))  # Default 30 hari terakhir
        camera_name = request.args.get('camera_name')
        
        # Hitung tanggal
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Format tanggal
        start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
        end_date_str = end_date.strftime('%Y-%m-%d %H:%M:%S')
        
        # Membangun URL request
        url = f"{MAIN_SERVER_URL}/api/data/filter?start_date={start_date_str}&end_date={end_date_str}&mode=Counting Kendaraan"
        if camera_name:
            url += f"&camera_name={camera_name}"
        
        # Mengambil data dari server utama
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            # Proses data untuk analisis jam sibuk
            peak_hours_data = process_peak_hours(data)
            return jsonify(peak_hours_data)
        else:
            return jsonify({"error": "Gagal mengambil data dari server utama"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/direction-flow')
def get_direction_flow():
    """Mendapatkan data arus lalu lintas berdasarkan arah (up/down)"""
    try:
        # Parameter
        days = int(request.args.get('days', 7))  # Default 7 hari terakhir
        camera_name = request.args.get('camera_name')
        
        # Hitung tanggal
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Format tanggal
        start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
        end_date_str = end_date.strftime('%Y-%m-%d %H:%M:%S')
        
        # Membangun URL request
        url = f"{MAIN_SERVER_URL}/api/data/filter?start_date={start_date_str}&end_date={end_date_str}&mode=Counting Kendaraan"
        if camera_name:
            url += f"&camera_name={camera_name}"
        
        # Mengambil data dari server utama
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            # Proses data untuk analisis arah lalu lintas
            direction_data = process_direction_flow(data)
            return jsonify(direction_data)
        else:
            return jsonify({"error": "Gagal mengambil data dari server utama"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/data/filter')
def get_filtered_data():
    """Mendapatkan data berdasarkan filter"""
    try:
        # Parameter
        camera_name = request.args.get('camera_name')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        mode = request.args.get('mode')
        
        # Membangun URL request ke server utama
        url = f"{MAIN_SERVER_URL}/api/data/filter?start_date={start_date}&end_date={end_date}"
        if camera_name:
            url += f"&camera_name={camera_name}"
        if mode:
            url += f"&mode={mode}"
        
        # Mengambil data dari server utama
        response = requests.get(url)
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": "Gagal mengambil data dari server utama"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Fungsi pemrosesan data
def process_weekly_trend(data):
    """Memproses data untuk tren mingguan"""
    if not data:
        return {"days": [], "counts": []}
    
    # Konversi data ke pandas DataFrame untuk analisis lebih mudah
    records = []
    for item in data:
        try:
            result = json.loads(item['result'])
            timestamp = datetime.strptime(item['timestamp'], '%Y-%m-%d %H:%M:%S')
            date_only = timestamp.date()
            
            total_vehicles = (
                result.get('car_up', 0) + result.get('car_down', 0) +
                result.get('bus_up', 0) + result.get('bus_down', 0) +
                result.get('truck_up', 0) + result.get('truck_down', 0) +
                result.get('person_motor_up', 0) + result.get('person_motor_down', 0)
            )
            
            records.append({
                'date': date_only,
                'total_vehicles': total_vehicles
            })
        except (json.JSONDecodeError, KeyError):
            continue
    
    df = pd.DataFrame(records)
    
    if df.empty:
        return {"days": [], "counts": []}
    
    # Agregasi data per hari
    daily_counts = df.groupby('date')['total_vehicles'].sum().reset_index()
    
    # Format output
    trend_data = {
        "days": [date.strftime('%Y-%m-%d') for date in daily_counts['date']],
        "counts": daily_counts['total_vehicles'].tolist()
    }
    
    return trend_data

def process_vehicle_comparison(data):
    """Memproses data untuk perbandingan jenis kendaraan"""
    if not data:
        return {
            "labels": ["Mobil", "Bus", "Truk", "Motor/Orang"],
            "data": [0, 0, 0, 0]
        }
    
    # Variabel untuk menyimpan total
    total_car = 0
    total_bus = 0
    total_truck = 0
    total_person_motor = 0
    
    # Iterasi melalui data
    for item in data:
        try:
            result = json.loads(item['result'])
            
            # Menambahkan ke total
            total_car += result.get('car_up', 0) + result.get('car_down', 0)
            total_bus += result.get('bus_up', 0) + result.get('bus_down', 0)
            total_truck += result.get('truck_up', 0) + result.get('truck_down', 0)
            total_person_motor += result.get('person_motor_up', 0) + result.get('person_motor_down', 0)
        except (json.JSONDecodeError, KeyError):
            continue
    
    # Format output
    comparison_data = {
        "labels": ["Mobil", "Bus", "Truk", "Motor/Orang"],
        "data": [total_car, total_bus, total_truck, total_person_motor]
    }
    
    return comparison_data

def process_peak_hours(data):
    """Memproses data untuk analisis jam sibuk"""
    if not data:
        return {"hours": list(range(24)), "counts": [0] * 24}
    
    # Inisialisasi counter untuk setiap jam
    hourly_counts = {hour: 0 for hour in range(24)}
    
    # Iterasi melalui data
    for item in data:
        try:
            result = json.loads(item['result'])
            timestamp = datetime.strptime(item['timestamp'], '%Y-%m-%d %H:%M:%S')
            hour = timestamp.hour
            
            # Hitung total kendaraan
            total_vehicles = (
                result.get('car_up', 0) + result.get('car_down', 0) +
                result.get('bus_up', 0) + result.get('bus_down', 0) +
                result.get('truck_up', 0) + result.get('truck_down', 0) +
                result.get('person_motor_up', 0) + result.get('person_motor_down', 0)
            )
            
            # Tambahkan ke counter jam
            hourly_counts[hour] += total_vehicles
        except (json.JSONDecodeError, KeyError):
            continue
    
    # Format output
    peak_hours_data = {
        "hours": list(range(24)),
        "counts": [hourly_counts[hour] for hour in range(24)]
    }
    
    return peak_hours_data

def process_direction_flow(data):
    """Memproses data untuk analisis arah lalu lintas"""
    if not data:
        return {
            "labels": ["Mobil", "Bus", "Truk", "Motor/Orang"], 
            "up_counts": [0, 0, 0, 0], 
            "down_counts": [0, 0, 0, 0]
        }
    
    # Variabel untuk menyimpan total
    total_car_up = 0
    total_car_down = 0
    total_bus_up = 0
    total_bus_down = 0
    total_truck_up = 0
    total_truck_down = 0
    total_person_motor_up = 0
    total_person_motor_down = 0
    
    # Iterasi melalui data
    for item in data:
        try:
            result = json.loads(item['result'])
            
            # Menambahkan ke total
            total_car_up += result.get('car_up', 0)
            total_car_down += result.get('car_down', 0)
            total_bus_up += result.get('bus_up', 0)
            total_bus_down += result.get('bus_down', 0)
            total_truck_up += result.get('truck_up', 0)
            total_truck_down += result.get('truck_down', 0)
            total_person_motor_up += result.get('person_motor_up', 0)
            total_person_motor_down += result.get('person_motor_down', 0)
        except (json.JSONDecodeError, KeyError):
            continue
    
    # Format output
    direction_data = {
        "labels": ["Mobil", "Bus", "Truk", "Motor/Orang"],
        "up_counts": [total_car_up, total_bus_up, total_truck_up, total_person_motor_up],
        "down_counts": [total_car_down, total_bus_down, total_truck_down, total_person_motor_down]
    }
    
    return direction_data

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=DASHBOARD_PORT, debug=True)