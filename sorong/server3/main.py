# app.py
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
import logging

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Inisialisasi aplikasi
app = Flask(__name__)
app.config.update(
    SQLALCHEMY_DATABASE_URI='sqlite:///monitoring.db',
    SECRET_KEY='rahasia123',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)

# Inisialisasi ekstensi
db = SQLAlchemy(app)
CORS(app)  # Mengizinkan cross-origin requests

# Konfigurasi SocketIO
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True,
    async_mode='threading'
)

# Model Database
class CameraData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    camera_name = db.Column(db.String(100), nullable=False)
    mode = db.Column(db.String(50), nullable=False)
    result = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'camera_name': self.camera_name,
            'mode': self.mode,
            'result': self.result,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }

class CameraSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ip = db.Column(db.String(15), nullable=False)
    mode = db.Column(db.String(50))
    enabled = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'ip': self.ip,
            'mode': self.mode,
            'enabled': self.enabled
        }

# Inisialisasi database dan data awal
def init_db():
    with app.app_context():
        db.create_all()
        # Inisialisasi 30 kamera jika belum ada
        if CameraSettings.query.count() == 0:
            logger.info("Initializing default camera settings...")
            for i in range(1, 31):
                camera = CameraSettings(
                    name=f'Camera {i}',
                    ip=f'192.168.1.{i}',
                    enabled=False
                )
                db.session.add(camera)
            db.session.commit()
            logger.info("Default camera settings initialized successfully")

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# Routes untuk monitoring
@app.route('/')
@app.route('/monitoring')
def monitoring():
    logger.info("Accessing monitoring page")
    return render_template('layout.html', page='monitoring')

@app.route('/settings')
def settings():
    logger.info("Accessing settings page")
    return render_template('layout.html', page='settings')

# API untuk monitoring
@app.route('/api/data/all')
def get_all_data():
    try:
        data = CameraData.query.order_by(CameraData.timestamp.desc()).all()
        return jsonify([item.to_dict() for item in data])
    except Exception as e:
        logger.error(f"Error getting all data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/data/filter')
def get_filtered_data():
    try:
        # Mengambil parameter dari request
        camera_name = request.args.get('camera_name')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Memulai query dasar
        query = CameraData.query
        
        # Menambahkan filter berdasarkan nama kamera jika parameter ada
        if camera_name:
            query = query.filter(CameraData.camera_name == camera_name)
        
        # Menambahkan filter berdasarkan rentang waktu jika parameter ada
        if start_date:
            try:
                # Mencoba dengan format lengkap terlebih dahulu
                try:
                    start_datetime = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    # Jika gagal, coba format tanggal saja dan tambahkan waktu 00:00:00
                    start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                query = query.filter(CameraData.timestamp >= start_datetime)
            except ValueError:
                return jsonify({'error': 'Format tanggal mulai tidak valid. Gunakan format YYYY-MM-DD atau YYYY-MM-DD HH:MM:SS'}), 400
        
        if end_date:
            try:
                # Mencoba dengan format lengkap terlebih dahulu
                try:
                    end_datetime = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    # Jika gagal, coba format tanggal saja dan tambahkan waktu 23:59:59
                    end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                    end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
                query = query.filter(CameraData.timestamp <= end_datetime)
            except ValueError:
                return jsonify({'error': 'Format tanggal akhir tidak valid. Gunakan format YYYY-MM-DD atau YYYY-MM-DD HH:MM:SS'}), 400
        
        # Menjalankan query
        data = query.order_by(CameraData.timestamp.desc()).all()
        
        # Mengembalikan hasil
        logger.info(f"Filtered data retrieved: camera={camera_name}, start={start_date}, end={end_date}, count={len(data)}")
        return jsonify([item.to_dict() for item in data])
    except Exception as e:
        logger.error(f"Error getting filtered data: {str(e)}")
        return jsonify({'error': str(e)}), 500
@app.route('/api/save')
def save_data():
    try:
        camera_name = request.args.get('camera_name')
        mode = request.args.get('mode')
        result = request.args.get('result')
        
        if not all([camera_name, mode, result]):
            return jsonify({'error': 'Semua parameter harus diisi'}), 400
            
        new_data = CameraData(
            camera_name=camera_name,
            mode=mode,
            result=result
        )
        db.session.add(new_data)
        db.session.commit()
        
        data_dict = new_data.to_dict()
        socketio.emit('new_data', data_dict)
        logger.info(f"New data saved: {data_dict}")
        return jsonify({'message': 'Data berhasil disimpan', 'data': data_dict}), 200
    except Exception as e:
        logger.error(f"Error saving data: {str(e)}")
        return jsonify({'error': str(e)}), 400

# API untuk settings
@app.route('/api/camera-settings')
def get_camera_settings():
    try:
        cameras = CameraSettings.query.all()
        return jsonify([camera.to_dict() for camera in cameras])
    except Exception as e:
        logger.error(f"Error getting camera settings: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/processor')
def get_processor_cameras():
    try:
        mode = request.args.get('mode')
        if not mode:
            return jsonify({'error': 'Parameter mode harus diisi'}), 400

        cameras = CameraSettings.query.filter_by(
            mode=mode,
            enabled=True
        ).all()

        camera_list = [{
            'id': camera.id,
            'name': camera.name,
            'ip': camera.ip,
            'mode': camera.mode
        } for camera in cameras]

        logger.info(f"Retrieved {len(camera_list)} cameras for mode: {mode}")
        return jsonify({
            'total': len(camera_list),
            'cameras': camera_list
        })

    except Exception as e:
        logger.error(f"Error getting processor cameras: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/camera-settings/<int:id>', methods=['PATCH'])
def update_camera_settings(id):
    try:
        camera = CameraSettings.query.get_or_404(id)
        data = request.json
        
        if 'mode' in data:
            new_mode = data['mode']
            if new_mode:
                mode_counts = db.session.query(
                    CameraSettings.mode,
                    db.func.count(CameraSettings.id)
                ).filter(
                    CameraSettings.mode.isnot(None),
                    CameraSettings.id != id
                ).group_by(CameraSettings.mode).all()
                
                mode_usage = dict(mode_counts)
                
                if new_mode == 'Counting Kendaraan' and mode_usage.get('Counting Kendaraan', 0) >= 3:
                    return jsonify({'error': 'Maksimal 3 kamera untuk Counting Kendaraan'}), 400
                elif new_mode == 'api dan asap' and mode_usage.get('api dan asap', 0) >= 6:
                    return jsonify({'error': 'Maksimal 6 kamera untuk api dan asap'}), 400
        
        for field, value in data.items():
            setattr(camera, field, value)
        
        db.session.commit()
        logger.info(f"Camera {id} settings updated: {data}")
        return jsonify(camera.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating camera {id} settings: {str(e)}")
        return jsonify({'error': str(e)}), 400

# Endpoint untuk mendapatkan data counting kendaraan bulan ini
@app.route('/api/data/counting-kendaraan/current-month')
def get_current_month_counting():
    try:
        # Mendapatkan tanggal awal dan akhir bulan ini
        now = datetime.utcnow()
        start_of_month = datetime(now.year, now.month, 1)
        
        # Menentukan akhir bulan (untuk bulan selanjutnya, hari ke-0 adalah hari terakhir bulan ini)
        if now.month == 12:
            end_of_month = datetime(now.year + 1, 1, 1)
        else:
            end_of_month = datetime(now.year, now.month + 1, 1)
        
        # Memfilter data
        data = CameraData.query.filter(
            CameraData.mode == 'Counting Kendaraan',
            CameraData.timestamp >= start_of_month,
            CameraData.timestamp < end_of_month
        ).order_by(CameraData.timestamp.desc()).all()
        
        logger.info(f"Retrieved {len(data)} counting kendaraan records for current month")
        return jsonify([item.to_dict() for item in data])
    except Exception as e:
        logger.error(f"Error getting current month counting data: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Endpoint untuk mendapatkan statistik counting kendaraan bulan ini
@app.route('/api/data/counting-kendaraan/current-month/summary')
def get_current_month_counting_summary():
    try:
        # Mendapatkan parameter opsional
        camera_name = request.args.get('camera_name')
        
        # Mendapatkan tanggal awal dan akhir bulan ini
        now = datetime.utcnow()
        start_of_month = datetime(now.year, now.month, 1)
        
        # Menentukan akhir bulan (untuk bulan selanjutnya, hari ke-0 adalah hari terakhir bulan ini)
        if now.month == 12:
            end_of_month = datetime(now.year + 1, 1, 1)
        else:
            end_of_month = datetime(now.year, now.month + 1, 1)
        
        # Memulai query dasar
        query = CameraData.query.filter(
            CameraData.mode == 'Counting Kendaraan',
            CameraData.timestamp >= start_of_month,
            CameraData.timestamp < end_of_month
        )
        
        # Menambahkan filter kamera jika ada
        if camera_name:
            query = query.filter(CameraData.camera_name == camera_name)
        
        # Mengambil data
        data = query.order_by(CameraData.timestamp.desc()).all()
        
        # Menghitung total untuk setiap jenis kendaraan
        summary = {
            'car_up': 0,
            'car_down': 0,
            'bus_up': 0,
            'bus_down': 0,
            'truck_up': 0,
            'truck_down': 0,
            'person_motor_up': 0,
            'person_motor_down': 0,
            'total_records': len(data),
            'date_range': f"{start_of_month.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}"
        }
        
        # Mengakumulasi data
        import json
        for item in data:
            try:
                result = json.loads(item.result)
                summary['car_up'] += result.get('car_up', 0)
                summary['car_down'] += result.get('car_down', 0)
                summary['bus_up'] += result.get('bus_up', 0)
                summary['bus_down'] += result.get('bus_down', 0)
                summary['truck_up'] += result.get('truck_up', 0)
                summary['truck_down'] += result.get('truck_down', 0)
                summary['person_motor_up'] += result.get('person_motor_up', 0)
                summary['person_motor_down'] += result.get('person_motor_down', 0)
            except (json.JSONDecodeError, AttributeError):
                logger.warning(f"Failed to parse result data for record ID {item.id}")
                continue
        
        # Menambahkan total untuk setiap kategori
        summary['total_car'] = summary['car_up'] + summary['car_down']
        summary['total_bus'] = summary['bus_up'] + summary['bus_down']
        summary['total_truck'] = summary['truck_up'] + summary['truck_down']
        summary['total_person_motor'] = summary['person_motor_up'] + summary['person_motor_down']
        summary['total_vehicles'] = summary['total_car'] + summary['total_bus'] + summary['total_truck'] + summary['total_person_motor']
        
        logger.info(f"Generated counting kendaraan summary for current month: {len(data)} records processed")
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Error generating current month counting summary: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Endpoint untuk memfilter data berdasarkan hari, minggu, dan jam
@app.route('/api/data/time-filter')
def get_time_filtered_data():
    try:
        # Mengambil parameter dari request
        camera_name = request.args.get('camera_name')
        mode = request.args.get('mode')
        day = request.args.get('day')  # Hari dalam bentuk angka (0=Senin, 6=Minggu)
        week = request.args.get('week')  # Minggu dalam bulan (1, 2, 3, 4, 5)
        hour_start = request.args.get('hour_start')  # Jam mulai (0-23)
        hour_end = request.args.get('hour_end')  # Jam akhir (0-23)
        month = request.args.get('month')  # Bulan (1-12)
        year = request.args.get('year')  # Tahun (YYYY)
        
        # Memulai query dasar
        query = CameraData.query
        
        # Menambahkan filter berdasarkan nama kamera jika parameter ada
        if camera_name:
            query = query.filter(CameraData.camera_name == camera_name)
        
        # Menambahkan filter berdasarkan mode jika parameter ada
        if mode:
            query = query.filter(CameraData.mode == mode)
        
        # Menambahkan filter berdasarkan bulan dan tahun
        if month and year:
            try:
                month = int(month)
                year = int(year)
                if 1 <= month <= 12 and year >= 2000:
                    # Menentukan tanggal awal bulan
                    start_of_month = datetime(year, month, 1)
                    
                    # Menentukan tanggal akhir bulan
                    if month == 12:
                        end_of_month = datetime(year + 1, 1, 1)
                    else:
                        end_of_month = datetime(year, month + 1, 1)
                    
                    query = query.filter(
                        CameraData.timestamp >= start_of_month,
                        CameraData.timestamp < end_of_month
                    )
                else:
                    return jsonify({'error': 'Nilai bulan harus antara 1-12 dan tahun harus >= 2000'}), 400
            except ValueError:
                return jsonify({'error': 'Format bulan atau tahun tidak valid'}), 400
        
        # Filter berdasarkan hari dalam seminggu (0=Senin, 6=Minggu)
        if day is not None:
            try:
                day = int(day)
                if 0 <= day <= 6:
                    # SQLite/PostgreSQL: strftime('%w', timestamp) returns 0-6 where 0 is Sunday
                    # Mengkonversi ke 0=Senin, 6=Minggu
                    # SQLite: (strftime('%w', timestamp) + 6) % 7
                    # PostgreSQL: EXTRACT(DOW FROM timestamp + INTERVAL '1 day') % 7
                    # Kita gunakan SQLAlchemy func untuk kompatibilitas
                    from sqlalchemy import func, text
                    
                    # Deteksi database engine untuk menggunakan sintaks yang sesuai
                    engine = str(db.engine.url).split('://')[0].lower()
                    
                    if 'sqlite' in engine:
                        # SQLite: 0=Minggu, jadi kita perlu konversi
                        dow_expr = text(f"((strftime('%w', timestamp) + 6) % 7) = {day}")
                        query = query.filter(dow_expr)
                    elif 'postgresql' in engine:
                        # PostgreSQL: 0=Minggu, jadi kita perlu konversi
                        dow_expr = text(f"EXTRACT(DOW FROM timestamp + INTERVAL '1 day') % 7 = {day}")
                        query = query.filter(dow_expr)
                    else:
                        # Untuk database lain, kita gunakan Python filter setelah query
                        pass
                else:
                    return jsonify({'error': 'Nilai hari harus antara 0-6 (0=Senin, 6=Minggu)'}), 400
            except ValueError:
                return jsonify({'error': 'Format hari tidak valid'}), 400
        
        # Filter berdasarkan minggu dalam bulan (1-5)
        if week is not None:
            try:
                week = int(week)
                if 1 <= week <= 5:
                    # SQLite: (strftime('%d', timestamp) - 1) / 7 + 1
                    # PostgreSQL: CEIL(EXTRACT(DAY FROM timestamp) / 7.0)
                    from sqlalchemy import func, text
                    
                    # Deteksi database engine
                    engine = str(db.engine.url).split('://')[0].lower()
                    
                    if 'sqlite' in engine:
                        week_expr = text(f"CAST((strftime('%d', timestamp) - 1) / 7 + 1 AS INTEGER) = {week}")
                        query = query.filter(week_expr)
                    elif 'postgresql' in engine:
                        week_expr = text(f"CEIL(EXTRACT(DAY FROM timestamp) / 7.0) = {week}")
                        query = query.filter(week_expr)
                    else:
                        # Untuk database lain, kita gunakan Python filter setelah query
                        pass
                else:
                    return jsonify({'error': 'Nilai minggu harus antara 1-5'}), 400
            except ValueError:
                return jsonify({'error': 'Format minggu tidak valid'}), 400
        
        # Filter berdasarkan rentang jam
        if hour_start is not None and hour_end is not None:
            try:
                hour_start = int(hour_start)
                hour_end = int(hour_end)
                if 0 <= hour_start <= 23 and 0 <= hour_end <= 23:
                    # SQLite: strftime('%H', timestamp)
                    # PostgreSQL: EXTRACT(HOUR FROM timestamp)
                    from sqlalchemy import func, text
                    
                    # Deteksi database engine
                    engine = str(db.engine.url).split('://')[0].lower()
                    
                    if 'sqlite' in engine:
                        if hour_start <= hour_end:
                            hour_expr = text(f"CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN {hour_start} AND {hour_end}")
                        else:
                            # Untuk kasus jam melewati tengah malam (mis. 22-3)
                            hour_expr = text(f"CAST(strftime('%H', timestamp) AS INTEGER) >= {hour_start} OR CAST(strftime('%H', timestamp) AS INTEGER) <= {hour_end}")
                        query = query.filter(hour_expr)
                    elif 'postgresql' in engine:
                        if hour_start <= hour_end:
                            hour_expr = text(f"EXTRACT(HOUR FROM timestamp) BETWEEN {hour_start} AND {hour_end}")
                        else:
                            # Untuk kasus jam melewati tengah malam
                            hour_expr = text(f"EXTRACT(HOUR FROM timestamp) >= {hour_start} OR EXTRACT(HOUR FROM timestamp) <= {hour_end}")
                        query = query.filter(hour_expr)
                    else:
                        # Untuk database lain, kita gunakan Python filter setelah query
                        pass
                else:
                    return jsonify({'error': 'Nilai jam harus antara 0-23'}), 400
            except ValueError:
                return jsonify({'error': 'Format jam tidak valid'}), 400
        
        # Menjalankan query dan mendapatkan hasilnya
        data = query.order_by(CameraData.timestamp.desc()).all()
        
        # Untuk database yang tidak didukung langsung, lakukan filter di Python
        engine = str(db.engine.url).split('://')[0].lower()
        if day is not None and ('sqlite' not in engine and 'postgresql' not in engine):
            # Filter hari dalam seminggu
            day = int(day)
            # Konversi dari 0=Senin, 6=Minggu ke format Python datetime dimana 0=Senin, 6=Minggu juga
            data = [item for item in data if item.timestamp.weekday() == day]
        
        if week is not None and ('sqlite' not in engine and 'postgresql' not in engine):
            # Filter minggu dalam bulan
            week = int(week)
            # Minggu dalam bulan (1-5) berdasarkan tanggal dibagi 7 dibulatkan ke atas
            import math
            data = [item for item in data if math.ceil((item.timestamp.day) / 7.0) == week]
        
        if hour_start is not None and hour_end is not None and ('sqlite' not in engine and 'postgresql' not in engine):
            # Filter rentang jam
            hour_start = int(hour_start)
            hour_end = int(hour_end)
            if hour_start <= hour_end:
                data = [item for item in data if hour_start <= item.timestamp.hour <= hour_end]
            else:
                # Untuk kasus jam melewati tengah malam
                data = [item for item in data if item.timestamp.hour >= hour_start or item.timestamp.hour <= hour_end]
        
        # Mengembalikan hasil
        logger.info(f"Time filtered data retrieved: {len(data)} records found")
        return jsonify([item.to_dict() for item in data])
    except Exception as e:
        logger.error(f"Error getting time filtered data: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Endpoint untuk mendapatkan statistik harian
@app.route('/api/data/daily-stats')
def get_daily_stats():
    try:
        # Mengambil parameter dari request
        camera_name = request.args.get('camera_name')
        mode = request.args.get('mode', 'Counting Kendaraan')  # Default mode: Counting Kendaraan
        date_str = request.args.get('date')  # Format: YYYY-MM-DD
        
        if not date_str:
            # Jika tanggal tidak disediakan, gunakan hari ini
            date_str = datetime.utcnow().strftime('%Y-%m-%d')
        
        try:
            # Parse tanggal
            date = datetime.strptime(date_str, '%Y-%m-%d')
            start_of_day = datetime(date.year, date.month, date.day)
            end_of_day = datetime(date.year, date.month, date.day, 23, 59, 59)
        except ValueError:
            return jsonify({'error': 'Format tanggal tidak valid. Gunakan format YYYY-MM-DD'}), 400
        
        # Memulai query dasar
        query = CameraData.query.filter(
            CameraData.mode == mode,
            CameraData.timestamp >= start_of_day,
            CameraData.timestamp <= end_of_day
        )
        
        # Menambahkan filter kamera jika ada
        if camera_name:
            query = query.filter(CameraData.camera_name == camera_name)
        
        # Mengambil data
        data = query.order_by(CameraData.timestamp.asc()).all()
        
        # Mengelompokkan data berdasarkan jam
        hourly_data = {}
        for hour in range(24):
            hourly_data[hour] = {
                'count': 0,
                'data': []
            }
        
        # Jika mode adalah Counting Kendaraan, prepare untuk statistik kendaraan
        vehicle_stats = {
            'total_car_up': 0,
            'total_car_down': 0,
            'total_bus_up': 0,
            'total_bus_down': 0,
            'total_truck_up': 0,
            'total_truck_down': 0,
            'total_person_motor_up': 0,
            'total_person_motor_down': 0,
            'hourly': {},
            'total_records': len(data)
        }
        
        # Inisialisasi statistik per jam
        for hour in range(24):
            vehicle_stats['hourly'][hour] = {
                'car_up': 0,
                'car_down': 0,
                'bus_up': 0,
                'bus_down': 0, 
                'truck_up': 0,
                'truck_down': 0,
                'person_motor_up': 0,
                'person_motor_down': 0,
                'count': 0
            }
        
        # Memproses data
        import json
        for item in data:
            hour = item.timestamp.hour
            hourly_data[hour]['count'] += 1
            hourly_data[hour]['data'].append(item.to_dict())
            
            # Jika mode Counting Kendaraan, tambahkan statistik kendaraan
            if mode == 'Counting Kendaraan':
                try:
                    result = json.loads(item.result)
                    
                    # Update statistik total
                    vehicle_stats['total_car_up'] += result.get('car_up', 0)
                    vehicle_stats['total_car_down'] += result.get('car_down', 0)
                    vehicle_stats['total_bus_up'] += result.get('bus_up', 0)
                    vehicle_stats['total_bus_down'] += result.get('bus_down', 0)
                    vehicle_stats['total_truck_up'] += result.get('truck_up', 0)
                    vehicle_stats['total_truck_down'] += result.get('truck_down', 0)
                    vehicle_stats['total_person_motor_up'] += result.get('person_motor_up', 0)
                    vehicle_stats['total_person_motor_down'] += result.get('person_motor_down', 0)
                    
                    # Update statistik per jam
                    vehicle_stats['hourly'][hour]['car_up'] += result.get('car_up', 0)
                    vehicle_stats['hourly'][hour]['car_down'] += result.get('car_down', 0)
                    vehicle_stats['hourly'][hour]['bus_up'] += result.get('bus_up', 0)
                    vehicle_stats['hourly'][hour]['bus_down'] += result.get('bus_down', 0)
                    vehicle_stats['hourly'][hour]['truck_up'] += result.get('truck_up', 0)
                    vehicle_stats['hourly'][hour]['truck_down'] += result.get('truck_down', 0)
                    vehicle_stats['hourly'][hour]['person_motor_up'] += result.get('person_motor_up', 0)
                    vehicle_stats['hourly'][hour]['person_motor_down'] += result.get('person_motor_down', 0)
                    vehicle_stats['hourly'][hour]['count'] += 1
                except (json.JSONDecodeError, AttributeError):
                    logger.warning(f"Failed to parse result data for record ID {item.id}")
                    continue
        
        # Menyiapkan response
        response = {
            'date': date_str,
            'camera_name': camera_name if camera_name else 'all',
            'mode': mode,
            'total_records': len(data),
            'hourly_distribution': hourly_data
        }
        
        # Jika mode Counting Kendaraan, tambahkan statistik kendaraan
        if mode == 'Counting Kendaraan':
            # Hitung total kendaraan
            vehicle_stats['total_vehicles'] = (
                vehicle_stats['total_car_up'] + vehicle_stats['total_car_down'] +
                vehicle_stats['total_bus_up'] + vehicle_stats['total_bus_down'] +
                vehicle_stats['total_truck_up'] + vehicle_stats['total_truck_down'] +
                vehicle_stats['total_person_motor_up'] + vehicle_stats['total_person_motor_down']
            )
            
            # Konversi hourly dari dict ke list untuk lebih mudah digunakan di frontend
            hourly_list = []
            for hour, stats in vehicle_stats['hourly'].items():
                stats['hour'] = hour
                hourly_list.append(stats)
            
            vehicle_stats['hourly'] = hourly_list
            response['vehicle_stats'] = vehicle_stats
        
        logger.info(f"Generated daily stats for {date_str}, mode={mode}, camera={camera_name if camera_name else 'all'}")
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error generating daily stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/camera-settings/<int:id>/reset', methods=['POST'])
def reset_camera(id):
    try:
        camera = CameraSettings.query.get_or_404(id)
        camera.mode = None
        camera.enabled = False
        db.session.commit()
        logger.info(f"Camera {id} reset successfully")
        return jsonify({'message': 'Camera reset successful'})
    except Exception as e:
        logger.error(f"Error resetting camera {id}: {str(e)}")
        return jsonify({'error': str(e)}), 400

# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    socketio.emit('connect_response', {'data': 'Connected successfully!'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

# Main entry point
if __name__ == '__main__':
    try:
        # Inisialisasi database
        init_db()
        
        # Konfigurasi untuk akses jaringan
        host = '0.0.0.0'  # Mengizinkan akses dari semua interface jaringan
        port = 5000       # Port default
        
        logger.info(f"Starting application on {host}:{port}")
        socketio.run(
            app,
            host=host,
            port=port,
            debug=True,
            allow_unsafe_werkzeug=True
        )
    except Exception as e:
        logger.error(f"Error starting application: {str(e)}")