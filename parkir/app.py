from flask import Flask, render_template, request, jsonify, Response
import datetime
import random
import string
import json
import cv2
import base64
import threading
import time
import os

app = Flask(__name__)
app.secret_key = 'parking_system_secret_key'

# In-memory storage untuk demo (dalam production gunakan database)
parking_data = []
settings = {
    'camera_masuk': 'rtsp://192.168.1.100:554/stream1',
    'camera_keluar': 'rtsp://192.168.1.101:554/stream2'
}

# Camera management
cameras = {}
camera_locks = {}

class RTSPCamera:
    def __init__(self, rtsp_url):
        self.rtsp_url = rtsp_url
        self.cap = None
        self.is_connected = False
        self.last_frame = None
        self.last_update = None
        
    def connect(self):
        try:
            if self.cap:
                self.cap.release()
            
            self.cap = cv2.VideoCapture(self.rtsp_url)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer to get latest frame
            
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    self.is_connected = True
                    self.last_frame = frame
                    self.last_update = datetime.datetime.now()
                    return True
            
            self.is_connected = False
            return False
        except Exception as e:
            print(f"Error connecting to camera {self.rtsp_url}: {e}")
            self.is_connected = False
            return False
    
    def capture_frame(self):
        if not self.cap or not self.cap.isOpened():
            if not self.connect():
                return None
        
        try:
            ret, frame = self.cap.read()
            if ret:
                self.last_frame = frame
                self.last_update = datetime.datetime.now()
                return frame
            else:
                # Try to reconnect
                self.connect()
                return self.last_frame
        except Exception as e:
            print(f"Error capturing frame: {e}")
            return self.last_frame
    
    def get_base64_image(self):
        frame = self.capture_frame()
        if frame is not None:
            # Resize frame for web display (optional)
            height, width = frame.shape[:2]
            if width > 640:
                scale = 640 / width
                new_width = 640
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height))
            
            # Convert to JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                # Convert to base64
                img_base64 = base64.b64encode(buffer).decode('utf-8')
                return img_base64
        return None
    
    def save_photo(self, filename):
        frame = self.capture_frame()
        if frame is not None:
            # Create photos directory if not exists
            if not os.path.exists('photos'):
                os.makedirs('photos')
            
            filepath = os.path.join('photos', filename)
            cv2.imwrite(filepath, frame)
            return filepath
        return None
    
    def release(self):
        if self.cap:
            self.cap.release()
        self.is_connected = False

def get_camera(camera_type):
    camera_key = f'camera_{camera_type}'
    rtsp_url = settings.get(camera_key, '')
    
    if not rtsp_url:
        return None
    
    if camera_type not in cameras or cameras[camera_type].rtsp_url != rtsp_url:
        # Create new camera instance
        if camera_type in cameras:
            cameras[camera_type].release()
        
        cameras[camera_type] = RTSPCamera(rtsp_url)
        camera_locks[camera_type] = threading.Lock()
    
    return cameras[camera_type]

def generate_barcode():
    """Generate random barcode untuk simulasi"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def simulate_camera_capture(camera_type):
    """Capture foto real dari kamera RTSP"""
    camera = get_camera(camera_type)
    if camera:
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"photo_{camera_type}_{timestamp}.jpg"
        
        with camera_locks.get(camera_type, threading.Lock()):
            saved_path = camera.save_photo(filename)
            if saved_path:
                return filename
    
    # Fallback to simulation if camera not available
    return f"simulated_photo_{camera_type}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/masuk', methods=['POST'])
def pintu_masuk():
    """API untuk proses kendaraan masuk"""
    try:
        # Simulasi capture foto dari kamera masuk
        foto_masuk = simulate_camera_capture('masuk')
        
        # Generate barcode
        barcode = generate_barcode()
        
        # Data kendaraan masuk
        data_masuk = {
            'barcode': barcode,
            'tanggal_masuk': datetime.datetime.now().strftime('%Y-%m-%d'),
            'waktu_masuk': datetime.datetime.now().strftime('%H:%M:%S'),
            'foto_masuk': foto_masuk,
            'status': 'masuk',
            'tanggal_keluar': None,
            'waktu_keluar': None,
            'foto_keluar': None
        }
        
        parking_data.append(data_masuk)
        
        return jsonify({
            'success': True,
            'message': 'Kendaraan berhasil masuk',
            'data': data_masuk
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })

@app.route('/api/keluar', methods=['POST'])
def pintu_keluar():
    """API untuk proses kendaraan keluar"""
    try:
        barcode = request.json.get('barcode')
        
        if not barcode:
            return jsonify({
                'success': False,
                'message': 'Barcode tidak boleh kosong'
            })
        
        # Cari data kendaraan berdasarkan barcode
        kendaraan = None
        for data in parking_data:
            if data['barcode'] == barcode and data['status'] == 'masuk':
                kendaraan = data
                break
        
        if not kendaraan:
            return jsonify({
                'success': False,
                'message': 'Barcode tidak ditemukan atau kendaraan sudah keluar'
            })
        
        # Simulasi capture foto kamera keluar
        foto_keluar = simulate_camera_capture('keluar')
        
        # Update data kendaraan
        kendaraan['tanggal_keluar'] = datetime.datetime.now().strftime('%Y-%m-%d')
        kendaraan['waktu_keluar'] = datetime.datetime.now().strftime('%H:%M:%S')
        kendaraan['foto_keluar'] = foto_keluar
        kendaraan['status'] = 'keluar'
        
        # Hitung durasi parkir
        masuk = datetime.datetime.strptime(f"{kendaraan['tanggal_masuk']} {kendaraan['waktu_masuk']}", '%Y-%m-%d %H:%M:%S')
        keluar = datetime.datetime.strptime(f"{kendaraan['tanggal_keluar']} {kendaraan['waktu_keluar']}", '%Y-%m-%d %H:%M:%S')
        durasi = keluar - masuk
        
        kendaraan['durasi'] = str(durasi)
        
        return jsonify({
            'success': True,
            'message': 'Kendaraan berhasil keluar. Palang terbuka!',
            'data': kendaraan
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })

@app.route('/api/cek-barcode', methods=['POST'])
def cek_barcode():
    """API untuk cek detail kendaraan berdasarkan barcode"""
    try:
        barcode = request.json.get('barcode')
        
        if not barcode:
            return jsonify({
                'success': False,
                'message': 'Barcode tidak boleh kosong'
            })
        
        # Cari data kendaraan
        kendaraan = None
        for data in parking_data:
            if data['barcode'] == barcode and data['status'] == 'masuk':
                kendaraan = data
                break
        
        if not kendaraan:
            return jsonify({
                'success': False,
                'message': 'Barcode tidak ditemukan atau kendaraan sudah keluar'
            })
        
        return jsonify({
            'success': True,
            'data': kendaraan
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })

@app.route('/api/parking-list')
def parking_list():
    """API untuk mendapatkan daftar kendaraan yang sedang parkir"""
    kendaraan_parkir = [data for data in parking_data if data['status'] == 'masuk']
    return jsonify({
        'success': True,
        'data': kendaraan_parkir
    })

@app.route('/api/settings', methods=['GET', 'POST'])
def manage_settings():
    """API untuk manage settings kamera"""
    global settings
    
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'data': settings
        })
    
    try:
        new_settings = request.json
        settings_changed = False
        
        if 'camera_masuk' in new_settings and new_settings['camera_masuk'] != settings.get('camera_masuk'):
            settings['camera_masuk'] = new_settings['camera_masuk']
            settings_changed = True
            # Reconnect camera
            if 'masuk' in cameras:
                cameras['masuk'].release()
                del cameras['masuk']
        
        if 'camera_keluar' in new_settings and new_settings['camera_keluar'] != settings.get('camera_keluar'):
            settings['camera_keluar'] = new_settings['camera_keluar']
            settings_changed = True
            # Reconnect camera
            if 'keluar' in cameras:
                cameras['keluar'].release()
                del cameras['keluar']
        
        return jsonify({
            'success': True,
            'message': 'Settings berhasil disimpan' + (' dan kamera direstart' if settings_changed else ''),
            'data': settings
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })

def cleanup_cameras():
    """Cleanup camera resources"""
    for camera in cameras.values():
        camera.release()

# Register cleanup function
import atexit
atexit.register(cleanup_cameras)

@app.route('/api/simulate-camera/<camera_type>')
def simulate_camera_view(camera_type):
    """Get camera status dan latest frame"""
    camera = get_camera(camera_type)
    if camera:
        with camera_locks.get(camera_type, threading.Lock()):
            is_connected = camera.is_connected
            if not is_connected:
                is_connected = camera.connect()
            
            return jsonify({
                'success': True,
                'camera_url': settings.get(f'camera_{camera_type}', ''),
                'status': 'connected' if is_connected else 'disconnected',
                'last_update': camera.last_update.isoformat() if camera.last_update else None
            })
    
    return jsonify({
        'success': False,
        'camera_url': settings.get(f'camera_{camera_type}', ''),
        'status': 'not_configured',
        'last_update': None
    })

@app.route('/api/camera-frame/<camera_type>')
def get_camera_frame(camera_type):
    """Get latest frame dari kamera sebagai base64"""
    camera = get_camera(camera_type)
    if camera:
        with camera_locks.get(camera_type, threading.Lock()):
            base64_image = camera.get_base64_image()
            if base64_image:
                return jsonify({
                    'success': True,
                    'image': base64_image,
                    'timestamp': datetime.datetime.now().isoformat()
                })
    
    return jsonify({
        'success': False,
        'message': 'Camera not available or not configured'
    })

@app.route('/api/camera-stream/<camera_type>')
def camera_stream(camera_type):
    """Stream video dari kamera RTSP"""
    def generate():
        camera = get_camera(camera_type)
        if not camera:
            return
        
        while True:
            try:
                with camera_locks.get(camera_type, threading.Lock()):
                    frame = camera.capture_frame()
                    if frame is not None:
                        # Encode frame as JPEG
                        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        if ret:
                            frame_bytes = buffer.tobytes()
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
                time.sleep(0.1)  # ~10 FPS
            except Exception as e:
                print(f"Error in camera stream: {e}")
                time.sleep(1)
                break
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/test-camera/<camera_type>')
def test_camera_connection(camera_type):
    """Test koneksi kamera"""
    camera = get_camera(camera_type)
    if camera:
        with camera_locks.get(camera_type, threading.Lock()):
            success = camera.connect()
            if success:
                # Try to capture a frame to verify
                frame = camera.capture_frame()
                return jsonify({
                    'success': success and frame is not None,
                    'message': 'Camera connected successfully' if success and frame is not None else 'Camera connected but no frame captured',
                    'url': camera.rtsp_url
                })
    
    return jsonify({
        'success': False,
        'message': 'Failed to connect to camera',
        'url': settings.get(f'camera_{camera_type}', 'Not configured')
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9090, debug=True)