# app.py
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///monitoring.db'
app.config['SECRET_KEY'] = 'rahasia123'
db = SQLAlchemy(app)
socketio = SocketIO(app)

# Tabel untuk data monitoring
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

# Tabel untuk settings kamera
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

# Inisialisasi database
with app.app_context():
    db.create_all()
    # Inisialisasi 30 kamera jika belum ada
    if CameraSettings.query.count() == 0:
        for i in range(1, 31):
            camera = CameraSettings(
                name=f'Camera {i}',
                ip=f'192.168.1.{i}',
                enabled=False
            )
            db.session.add(camera)
        db.session.commit()

# Routes untuk monitoring
@app.route('/')
@app.route('/monitoring')
def monitoring():
    return render_template('layout.html', page='monitoring')

@app.route('/settings')
def settings():
    return render_template('layout.html', page='settings')

# API untuk monitoring
@app.route('/api/data/all')
def get_all_data():
    data = CameraData.query.order_by(CameraData.timestamp.desc()).all()
    return jsonify([item.to_dict() for item in data])

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
        
        socketio.emit('new_data', new_data.to_dict())
        return jsonify({'message': 'Data berhasil disimpan'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# API untuk settings
@app.route('/api/camera-settings')
def get_camera_settings():
    cameras = CameraSettings.query.all()
    return jsonify([camera.to_dict() for camera in cameras])

@app.route('/api/processor')
def get_processor_cameras():
    try:
        # Ambil parameter mode dari request
        mode = request.args.get('mode')
        if not mode:
            return jsonify({'error': 'Parameter mode harus diisi'}), 400

        # Query kamera yang aktif dengan mode yang sesuai
        cameras = CameraSettings.query.filter_by(
            mode=mode,
            enabled=True
        ).all()

        # Format response
        camera_list = [{
            'id': camera.id,
            'name': camera.name,
            'ip': camera.ip,
            'mode': camera.mode
        } for camera in cameras]

        return jsonify({
            'total': len(camera_list),
            'cameras': camera_list
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/camera-settings/<int:id>', methods=['PATCH'])
def update_camera_settings(id):
    camera = CameraSettings.query.get_or_404(id)
    data = request.json
    
    if 'mode' in data:
        new_mode = data['mode']
        if new_mode:
            # Hitung penggunaan mode saat ini
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
            elif new_mode == 'Api dan Asap' and mode_usage.get('Api dan Asap', 0) >= 6:
                return jsonify({'error': 'Maksimal 6 kamera untuk Api dan Asap'}), 400
    
    try:
        for field, value in data.items():
            setattr(camera, field, value)
        db.session.commit()
        return jsonify(camera.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/camera-settings/<int:id>/reset', methods=['POST'])
def reset_camera(id):
    camera = CameraSettings.query.get_or_404(id)
    camera.mode = None
    camera.enabled = False
    db.session.commit()
    return jsonify({'message': 'Camera reset successful'})

if __name__ == '__main__':
    socketio.run(app, debug=True)