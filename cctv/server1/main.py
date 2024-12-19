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