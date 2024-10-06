import cv2
import requests
from requests.auth import HTTPDigestAuth
import time

# Konfigurasi API
base_url = "http://8.215.44.249:3466/LAPI/V1.0"
auth = HTTPDigestAuth('admin', 'admin!123')

def get_stream_url():
    url = f"{base_url}/Channels/0/Media/Video/Streams/0/LiveStreamURL"
    response = requests.get(url, auth=auth)
    if response.status_code == 200:
        data = response.json()
        return data['Response']['Data']['URL']
    return None

def stream_with_opencv(stream_url):
    # Tambahkan parameter tambahan ke URL RTSP
    stream_url = f"{stream_url}?tcp"  # Gunakan TCP untuk streaming

    # Konfigurasi OpenCV untuk menggunakan FFMPEG backend
    cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
    
    # Set buffer size
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)

    if not cap.isOpened():
        print("Tidak dapat membuka video stream dengan OpenCV")
        return False

    retry_count = 0
    max_retries = 5

    while retry_count < max_retries:
        ret, frame = cap.read()
        if not ret:
            print(f"Tidak dapat menerima frame. Mencoba lagi... (Percobaan {retry_count + 1}/{max_retries})")
            retry_count += 1
            time.sleep(2)  # Tunggu 2 detik sebelum mencoba lagi
            continue
        
        cv2.imshow('RTSP Stream (OpenCV)', frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        retry_count = 0  # Reset counter jika frame berhasil dibaca

    cap.release()
    cv2.destroyAllWindows()
    return True

def main():
    stream_url = get_stream_url()
    if not stream_url:
        print("Tidak dapat mendapatkan URL stream")
        return

    print(f"Streaming dari URL: {stream_url}")

    print("Mencoba streaming dengan OpenCV...")
    opencv_success = stream_with_opencv(stream_url)

    if not opencv_success:
        print("Streaming gagal setelah beberapa percobaan.")

if __name__ == "__main__":
    main()