import cv2
import threading
import time
from flask import Flask, Response, render_template

# Konfigurasi RTSP
rtsp_url = "rtsp://admin:Admin123@41.216.191.132:554/Streaming/Channels/101"

# Inisialisasi aplikasi Flask
app = Flask(__name__)

# Variabel global untuk menyimpan frame
frame = None
lock = threading.Lock()

def capture_video():
    global frame
    # Membuat koneksi ke kamera RTSP
    cap = cv2.VideoCapture(rtsp_url)
    
    # Periksa apakah koneksi berhasil
    if not cap.isOpened():
        print("Error: Tidak dapat membuka koneksi RTSP")
        return
    
    print("Koneksi RTSP berhasil dibuat")
    
    # Loop untuk membaca frame
    while True:
        ret, current_frame = cap.read()
        if not ret:
            print("Error: Tidak dapat membaca frame")
            # Mencoba menghubungkan kembali
            cap.release()
            time.sleep(1)
            cap = cv2.VideoCapture(rtsp_url)
            continue
        
        # Update frame global dengan thread lock untuk menghindari race condition
        with lock:
            frame = current_frame.copy()

def generate_frames():
    global frame
    while True:
        # Menunggu sampai frame tersedia
        if frame is None:
            time.sleep(0.1)
            continue
        
        # Mendapatkan frame dengan thread lock
        with lock:
            current_frame = frame.copy()
        
        # Encoding frame ke JPEG
        ret, buffer = cv2.imencode('.jpg', current_frame)
        if not ret:
            continue
        
        # Mengkonversi ke bytes dan mengirim sebagai respons multipart
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    # Halaman HTML sederhana dengan tampilan video
    return """
    <html>
    <head>
        <title>RTSP Stream</title>
    </head>
    <body>
        <h1>RTSP Streaming</h1>
        <img src="/video_feed" width="640" height="480" />
    </body>
    </html>
    """

@app.route('/video_feed')
def video_feed():
    # Endpoint untuk streaming video
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    # Memulai thread untuk capture video
    threading_cap = threading.Thread(target=capture_video)
    threading_cap.daemon = True
    threading_cap.start()
    
    # Menjalankan server Flask
    print("Server HTTP streaming dimulai di http://127.0.0.1:5000/")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)