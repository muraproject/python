import cv2
import requests
from requests.auth import HTTPDigestAuth
import time

# Konfigurasi API
base_url = "http://192.168.1.13/LAPI/V1.0"
auth = HTTPDigestAuth('admin', 'admin!123')

def get_stream_url():
    url = f"{base_url}/Channels/0/Media/Video/Streams/0/LiveStreamURL"
    try:
        response = requests.get(url, auth=auth)
        response.raise_for_status()
        data = response.json()
        print("API Response:", data)
        if 'Response' in data and 'Data' in data['Response'] and 'URL' in data['Response']['Data']:
            rtsp_url = data['Response']['Data']['URL']
            # Tambahkan kredensial ke URL RTSP
            return f"rtsp://admin:admin!123@{rtsp_url.split('//')[1]}"
        else:
            print("URL tidak ditemukan dalam respons")
            return None
    except requests.RequestException as e:
        print(f"Error saat mengambil URL stream: {e}")
        return None

def stream_with_opencv(stream_url):
    cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
    
    # Tambahkan timeout
    timeout = time.time() + 10  # 10 detik timeout
    while not cap.isOpened() and time.time() < timeout:
        time.sleep(0.5)
    
    if not cap.isOpened():
        print("Tidak dapat membuka video stream dalam waktu yang ditentukan")
        return False

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Tidak dapat menerima frame")
                break
            
            cv2.imshow('IP Camera Live Stream', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    
    return True

def main():
    stream_url = get_stream_url()
    if stream_url:
        print(f"Streaming dari URL: {stream_url}")
        success = stream_with_opencv(stream_url)
        if not success:
            print("Gagal melakukan streaming video")
    else:
        print("Tidak dapat mendapatkan URL stream")

if __name__ == "__main__":
    main()
