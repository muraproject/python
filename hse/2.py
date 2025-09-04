import cv2
from ultralytics import YOLO
import numpy as np

def main():
    # Load YOLOv8 model
    model = YOLO('best.pt')  # Pastikan file best.pt ada di folder yang sama
    
    # Daftar kelas yang ingin ditampilkan
    allowed_classes = ['Person', 'Hardhat', 'Safety Vest']
    
    # Buka video
    video_path = 'hse1.mp4'  # Pastikan file hse1.mp4 ada di folder yang sama
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"Error: Tidak dapat membuka video {video_path}")
        return
    
    # Dapatkan informasi video
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"Video Info: {width}x{height} @ {fps} FPS")
    print(f"Menampilkan hanya: {', '.join(allowed_classes)}")
    
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        
        if not ret:
            print("Video selesai atau error membaca frame")
            break
        
        frame_count += 1
        print(f"\nMemproses frame {frame_count}")
        
        # Jalankan inferensi YOLOv8
        results = model(frame)
        
        # Buat frame kosong untuk annotasi manual
        annotated_frame = frame.copy()
        
        # Proses hasil deteksi dengan filter
        detected_objects = []
        for r in results:
            boxes = r.boxes
            if boxes is not None:
                for box in boxes:
                    # Dapatkan informasi deteksi
                    x1, y1, x2, y2 = box.xyxy[0]
                    confidence = box.conf[0]
                    class_id = box.cls[0]
                    class_name = model.names[int(class_id)]
                    
                    # Filter hanya kelas yang diinginkan
                    if class_name in allowed_classes:
                        detected_objects.append({
                            'bbox': (int(x1), int(y1), int(x2), int(y2)),
                            'confidence': float(confidence),
                            'class_name': class_name,
                            'class_id': int(class_id)
                        })
                        
                        print(f"  Deteksi: {class_name} - Confidence: {confidence:.2f}")
        
        # Gambar bounding box hanya untuk objek yang difilter
        for obj in detected_objects:
            x1, y1, x2, y2 = obj['bbox']
            class_name = obj['class_name']
            confidence = obj['confidence']
            
            # Tentukan warna berdasarkan kelas
            if class_name == 'Person':
                color = (0, 255, 0)  # Hijau
            elif class_name == 'Hardhat':
                color = (255, 0, 0)  # Biru
            elif class_name == 'Safety Vest':
                color = (0, 165, 255)  # Orange
            else:
                color = (255, 255, 255)  # Putih (default)
            
            # Gambar bounding box
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
            
            # Gambar label dengan background
            label = f"{class_name} {confidence:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            
            # Background untuk text
            cv2.rectangle(annotated_frame, 
                         (x1, y1 - label_size[1] - 10), 
                         (x1 + label_size[0], y1), 
                         color, -1)
            
            # Text label
            cv2.putText(annotated_frame, label, 
                       (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                       (255, 255, 255), 2)
        
        # Tampilkan jumlah deteksi di pojok kiri atas
        info_text = f"Frame: {frame_count} | Deteksi: {len(detected_objects)}"
        cv2.putText(annotated_frame, info_text, 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                   (255, 255, 255), 2)
        
        # Tampilkan frame dengan deteksi secara live
        cv2.imshow('YOLOv8 Filtered Detection - HSE Safety', annotated_frame)
        
        # Kontrol kecepatan playback
        delay = max(1, int(1000 / fps))
        key = cv2.waitKey(delay) & 0xFF
        if key == ord('q'):
            print("Menghentikan deteksi...")
            break
        elif key == ord('p'):
            print("Video dipause. Tekan sembarang tombol untuk melanjutkan...")
            cv2.waitKey(0)
        elif key == ord('s'):
            # Simpan screenshot frame saat ini
            screenshot_name = f"frame_{frame_count}_detections.jpg"
            cv2.imwrite(screenshot_name, annotated_frame)
            print(f"Screenshot disimpan: {screenshot_name}")
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    
    print("Live detection selesai!")
    print(f"Total frame yang diproses: {frame_count}")

if __name__ == "__main__":
    main()