# app.py
from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from datetime import datetime
from sqlalchemy import and_, or_  # Tambahkan or_

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///monitoring.db'
app.config['SECRET_KEY'] = 'rahasia123'
db = SQLAlchemy(app)
socketio = SocketIO(app)

# Model database (tidak berubah)
class CameraData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    camera_name = db.Column(db.String(100), nullable=False)
    mode = db.Column(db.String(50), nullable=False)
    result = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'camera_name': self.camera_name,
            'mode': self.mode,
            'result': self.result,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }

with app.app_context():
    db.create_all()

# API untuk mendapatkan semua data
@app.route('/api/data/all')
def get_all_data():
    try:
        data = CameraData.query.order_by(CameraData.timestamp.desc()).all()
        return jsonify([item.to_dict() for item in data])
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# API save (tidak berubah)
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

# API filters (tidak berubah)
@app.route('/api/filters')
def get_filters():
    try:
        camera_names = db.session.query(CameraData.camera_name.distinct()).all()
        modes = db.session.query(CameraData.mode.distinct()).all()
        
        min_date = db.session.query(db.func.min(CameraData.timestamp)).scalar()
        max_date = db.session.query(db.func.max(CameraData.timestamp)).scalar()
        
        return jsonify({
            'camera_names': [x[0] for x in camera_names],
            'modes': [x[0] for x in modes],
            'date_range': {
                'min': min_date.strftime('%Y-%m-%d %H:%M:%S') if min_date else None,
                'max': max_date.strftime('%Y-%m-%d %H:%M:%S') if max_date else None
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/')
def monitoring():
    return render_template('monitoring_tailwind.html')

if __name__ == '__main__':
    socketio.run(app, debug=True)