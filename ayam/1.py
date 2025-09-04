import cv2
from ultralytics import YOLO
import numpy as np

def main():
    # Load YOLOv8 model
    model = YOLO('best.pt')  # Pastikan file best.pt ada di folder yang sama
    
    # Buka video
    video_path = 'ayam.mp4'  # Pastikan file ayam.mp4 ada di folder yang sama
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"Error: Tidak dapat membuka video {video_path}")
        return
    
    # Dapatkan informasi video
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"Video Info: {width}x{height} @ {fps} FPS")
    
    # Hanya live detection, tanpa menyimpan output
    
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        
        if not ret:
            print("Video selesai atau error membaca frame")
            break
        
        frame_count += 1
        print(f"Memproses frame {frame_count}")
        
        # Jalankan inferensi YOLOv8
        results = model(frame)
        
        # Gambar bounding box pada frame
        annotated_frame = results[0].plot()
        
        # Tampilkan informasi deteksi di console
        for r in results:
            boxes = r.boxes
            if boxes is not None:
                for box in boxes:
                    # Dapatkan koordinat bounding box
                    x1, y1, x2, y2 = box.xyxy[0]
                    confidence = box.conf[0]
                    class_id = box.cls[0]
                    class_name = model.names[int(class_id)]
                    
                    print(f"  Deteksi: {class_name} - Confidence: {confidence:.2f}")
        
        # Tampilkan frame dengan deteksi secara live
        cv2.imshow('YOLOv8 Live Detection - ayam.mp4', annotated_frame)
        
        # Kontrol kecepatan playback (sesuaikan delay untuk live feel)
        # Gunakan delay berdasarkan FPS video untuk playback natural
        delay = max(1, int(1000 / fps))
        key = cv2.waitKey(delay) & 0xFF
        if key == ord('q'):
            print("Menghentikan deteksi...")
            break
        elif key == ord('p'):
            print("Video dipause. Tekan sembarang tombol untuk melanjutkan...")
            cv2.waitKey(0)
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    
    print("Live detection selesai!")
    print(f"Total frame yang diproses: {frame_count}")

if __name__ == "__main__":
    main()