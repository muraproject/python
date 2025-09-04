import cv2
from ultralytics import YOLO
import numpy as np
from scipy.spatial.distance import cdist

class ROICounter:
    def __init__(self, roi_points):
        self.roi_points = np.array(roi_points, dtype=np.int32)
        self.exit_counter = 0
        self.counted_objects = set()  # Track objek yang sudah dihitung
    
    def is_inside_roi(self, point):
        """Cek apakah titik berada di dalam ROI"""
        result = cv2.pointPolygonTest(self.roi_points, point, False)
        return result >= 0
    
    def draw_roi(self, frame):
        """Gambar ROI di frame"""
        # Gambar ROI polygon
        cv2.polylines(frame, [self.roi_points], True, (0, 255, 255), 3)
        # Fill ROI dengan transparansi
        overlay = frame.copy()
        cv2.fillPoly(overlay, [self.roi_points], (0, 255, 255))
        cv2.addWeighted(overlay, 0.1, frame, 0.9, 0, frame)
        
        # Label ROI
        cv2.putText(frame, "ROI ZONE", 
                   tuple(self.roi_points[0]), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    
    def update_counter(self, tracked_objects):
        """Update counter berdasarkan objek yang keluar ROI"""
        for obj in tracked_objects:
            obj_id = obj['id']
            center = obj['center']
            
            # Cek status objek terhadap ROI
            inside_roi = self.is_inside_roi(center)
            
            # Jika objek di luar ROI dan belum dihitung
            if not inside_roi and obj_id not in self.counted_objects:
                self.exit_counter += 1
                self.counted_objects.add(obj_id)
                print(f"🚀 OBJEK KELUAR ROI! ID:{obj_id} | Total Count: {self.exit_counter}")
                return True
            
            # Reset jika objek kembali ke ROI (optional)
            elif inside_roi and obj_id in self.counted_objects:
                # Uncomment baris ini jika ingin reset counter ketika objek kembali ke ROI
                # self.counted_objects.discard(obj_id)
                pass
        
        return False

class ObjectTracker:
    def __init__(self):
        self.trackers = []
        self.next_id = 1
        self.max_disappeared = 30  # Frame maksimum sebelum tracker dihapus
        self.max_distance = 50     # Jarak maksimum untuk mencocokkan deteksi
    
    def create_kalman_filter(self):
        """Membuat Kalman Filter untuk tracking posisi objek"""
        kf = cv2.KalmanFilter(4, 2)
        kf.measurementMatrix = np.array([[1, 0, 0, 0],
                                       [0, 1, 0, 0]], np.float32)
        kf.transitionMatrix = np.array([[1, 0, 1, 0],
                                      [0, 1, 0, 1],
                                      [0, 0, 1, 0],
                                      [0, 0, 0, 1]], np.float32)
        kf.processNoiseCov = 0.03 * np.eye(4, dtype=np.float32)
        kf.measurementNoiseCov = 0.1 * np.eye(2, dtype=np.float32)
        return kf
    
    def update(self, detections):
        """Update tracker dengan deteksi baru"""
        if len(detections) == 0:
            # Jika tidak ada deteksi, update semua tracker dengan prediksi saja
            for tracker in self.trackers:
                tracker['disappeared'] += 1
                prediction = tracker['kalman'].predict()
                tracker['center'] = (int(prediction[0]), int(prediction[1]))
            
            # Hapus tracker yang sudah terlalu lama menghilang
            self.trackers = [t for t in self.trackers if t['disappeared'] <= self.max_disappeared]
            return
        
        # Jika ada tracker dan deteksi
        if len(self.trackers) == 0:
            # Buat tracker baru untuk semua deteksi
            for detection in detections:
                self.create_new_tracker(detection)
        else:
            # Cocokkan deteksi dengan tracker yang ada
            self.match_detections_to_trackers(detections)
    
    def create_new_tracker(self, detection):
        """Membuat tracker baru untuk deteksi"""
        cx, cy = detection['center']
        tracker = {
            'id': self.next_id,
            'kalman': self.create_kalman_filter(),
            'center': (cx, cy),
            'disappeared': 0,
            'class': detection['class'],
            'confidence': detection['confidence'],
            'bbox': detection['bbox'],
            'trail': [(cx, cy)]  # Untuk menggambar jejak
        }
        
        # Initialize Kalman filter
        tracker['kalman'].statePre = np.array([cx, cy, 0, 0], dtype=np.float32)
        tracker['kalman'].statePost = np.array([cx, cy, 0, 0], dtype=np.float32)
        
        self.trackers.append(tracker)
        self.next_id += 1
    
    def match_detections_to_trackers(self, detections):
        """Mencocokkan deteksi dengan tracker yang sudah ada"""
        if len(self.trackers) == 0:
            for detection in detections:
                self.create_new_tracker(detection)
            return
        
        # Hitung jarak antara deteksi dan tracker
        tracker_centers = np.array([t['center'] for t in self.trackers])
        detection_centers = np.array([d['center'] for d in detections])
        
        distances = cdist(tracker_centers, detection_centers)
        
        # Assign deteksi ke tracker terdekat
        used_detection_indices = set()
        used_tracker_indices = set()
        
        # Sort berdasarkan jarak terdekat
        tracker_indices, detection_indices = np.unravel_index(
            np.argsort(distances, axis=None), distances.shape)
        
        for tracker_idx, detection_idx in zip(tracker_indices, detection_indices):
            if (tracker_idx in used_tracker_indices or 
                detection_idx in used_detection_indices):
                continue
            
            if distances[tracker_idx, detection_idx] <= self.max_distance:
                # Update tracker dengan deteksi
                detection = detections[detection_idx]
                self.update_tracker(self.trackers[tracker_idx], detection)
                used_tracker_indices.add(tracker_idx)
                used_detection_indices.add(detection_idx)
        
        # Tandai tracker yang tidak cocok sebagai menghilang
        for i, tracker in enumerate(self.trackers):
            if i not in used_tracker_indices:
                tracker['disappeared'] += 1
                # Prediksi posisi berdasarkan Kalman filter
                prediction = tracker['kalman'].predict()
                tracker['center'] = (int(prediction[0]), int(prediction[1]))
        
        # Buat tracker baru untuk deteksi yang tidak cocok
        for i, detection in enumerate(detections):
            if i not in used_detection_indices:
                self.create_new_tracker(detection)
        
        # Hapus tracker yang sudah terlalu lama menghilang
        self.trackers = [t for t in self.trackers if t['disappeared'] <= self.max_disappeared]
    
    def update_tracker(self, tracker, detection):
        """Update tracker dengan deteksi baru"""
        cx, cy = detection['center']
        
        # Update Kalman filter
        measurement = np.array([[np.float32(cx)], [np.float32(cy)]])
        tracker['kalman'].correct(measurement)
        prediction = tracker['kalman'].predict()
        
        # Update tracker properties
        tracker['center'] = (int(prediction[0]), int(prediction[1]))
        tracker['disappeared'] = 0
        tracker['class'] = detection['class']
        tracker['confidence'] = detection['confidence']
        tracker['bbox'] = detection['bbox']
        
        # Tambah ke trail (maksimal 20 titik)
        tracker['trail'].append((cx, cy))
        if len(tracker['trail']) > 20:
            tracker['trail'].pop(0)

def main():
    # Load YOLOv8 model
    model = YOLO('best.pt')  # Pastikan file best.pt ada di folder yang sama
    
    # Buka video untuk mendapatkan dimensi
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
    
    # Setup ROI (Region of Interest) - sesuaikan dengan video Anda
    # Contoh ROI: area tengah-bawah video sebagai zona keluar
    roi_points = [
        (int(width*0.2), int(height*0.6)),    # Top-left
        (int(width*0.8), int(height*0.6)),    # Top-right  
        (int(width*0.9), int(height*0.9)),    # Bottom-right
        (int(width*0.1), int(height*0.9))     # Bottom-left
    ]
    
    # Anda bisa mengubah ROI sesuai kebutuhan, misalnya:
    # roi_points = [(100, 200), (500, 200), (600, 400), (50, 400)]  # Custom ROI
    
    # Initialize tracker dan ROI counter
    tracker = ObjectTracker()
    roi_counter = ROICounter(roi_points)
    
    print("🎯 ROI Counter System aktif!")
    print("📍 ROI Zone telah diatur")
    print("🔄 Kalman Filter Tracking aktif!")
    
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        
        if not ret:
            print("Video selesai atau error membaca frame")
            break
        
        frame_count += 1
        
        # Jalankan inferensi YOLOv8
        results = model(frame)
        
        # Konversi hasil deteksi ke format untuk tracker
        detections = []
        for r in results:
            boxes = r.boxes
            if boxes is not None:
                for box in boxes:
                    # Dapatkan koordinat bounding box
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = box.conf[0].cpu().numpy()
                    class_id = int(box.cls[0].cpu().numpy())
                    class_name = model.names[class_id]
                    
                    # Hitung center point
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    
                    detection = {
                        'bbox': (int(x1), int(y1), int(x2), int(y2)),
                        'center': (cx, cy),
                        'confidence': confidence,
                        'class': class_name,
                        'class_id': class_id
                    }
                    detections.append(detection)
        
        # Update tracker dengan deteksi baru
        tracker.update(detections)
        
        # Update ROI counter
        object_exited = roi_counter.update_counter(tracker.trackers)
        
        # Gambar ROI
        roi_counter.draw_roi(frame)
        
        # Gambar tracking results
        for tracked_obj in tracker.trackers:
            # Gambar bounding box
            x1, y1, x2, y2 = tracked_obj['bbox']
            
            # Warna berbeda untuk setiap ID
            colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), 
                     (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 165, 0)]
            color = colors[tracked_obj['id'] % len(colors)]
            
            # Cek apakah objek di dalam atau luar ROI
            inside_roi = roi_counter.is_inside_roi(tracked_obj['center'])
            
            # Gambar bounding box dengan border berbeda untuk objek di luar ROI
            thickness = 3 if not inside_roi else 2
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            
            # Gambar center point
            cx, cy = tracked_obj['center']
            cv2.circle(frame, (cx, cy), 4, color, -1)
            
            # Gambar trail (jejak)
            if len(tracked_obj['trail']) > 1:
                for i in range(1, len(tracked_obj['trail'])):
                    thickness = max(1, int(3 * i / len(tracked_obj['trail'])))
                    cv2.line(frame, tracked_obj['trail'][i-1], tracked_obj['trail'][i], color, thickness)
            
            # Label dengan ID dan informasi + status ROI
            roi_status = "OUT" if not inside_roi else "IN"
            label = f"ID:{tracked_obj['id']} {tracked_obj['class']} {tracked_obj['confidence']:.2f} [{roi_status}]"
            
            # Background untuk label
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            bg_color = (0, 0, 255) if not inside_roi else color  # Red background for OUT objects
            cv2.rectangle(frame, (x1, y1-25), (x1 + label_size[0], y1), bg_color, -1)
            cv2.putText(frame, label, (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2)
        
        # Tampilkan counter dan statistik
        # Background untuk counter
        cv2.rectangle(frame, (10, 10), (400, 120), (0, 0, 0), -1)
        cv2.rectangle(frame, (10, 10), (400, 120), (255, 255, 255), 2)
        
        # Counter utama
        cv2.putText(frame, f"EXIT COUNTER: {roi_counter.exit_counter}", (20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # Informasi lainnya
        cv2.putText(frame, f"Frame: {frame_count}", (20, 65), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(frame, f"Active Trackers: {len(tracker.trackers)}", (20, 85), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(frame, f"Objects Counted: {len(roi_counter.counted_objects)}", (20, 105), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Efek visual saat ada objek yang keluar ROI
        if object_exited:
            cv2.putText(frame, "OBJECT EXITED ROI!", (width//2-100, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
        
        # Tampilkan informasi tracking di console (simplified)
        if frame_count % 30 == 0:  # Print setiap 30 frame untuk mengurangi spam
            print(f"Frame {frame_count}: EXIT COUNT = {roi_counter.exit_counter}, Active Trackers = {len(tracker.trackers)}")
        
        # Tampilkan frame dengan tracking secara live
        cv2.imshow('YOLOv8 + Kalman Filter + ROI Counter - ayam.mp4', frame)
        
        # Kontrol kecepatan playback (sesuaikan delay untuk live feel)
        # Gunakan delay berdasarkan FPS video untuk playback natural
        delay = max(1, int(1000 / fps))
        key = cv2.waitKey(delay) & 0xFF
        if key == ord('q'):
            print("Menghentikan tracking...")
            break
        elif key == ord('p'):
            print("Video dipause. Tekan sembarang tombol untuk melanjutkan...")
            cv2.waitKey(0)
        elif key == ord('r'):
            # Reset counter
            roi_counter.exit_counter = 0
            roi_counter.counted_objects.clear()
            print("🔄 Counter di-reset!")
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    
    # Final report
    print("\n" + "="*50)
    print("📊 FINAL REPORT")
    print("="*50)
    print(f"🎬 Total frame yang diproses: {frame_count}")
    print(f"🎯 Total objek yang keluar ROI: {roi_counter.exit_counter}")
    print(f"🔢 Total objek unik yang di-track: {tracker.next_id - 1}")
    print(f"📋 ID objek yang sudah keluar ROI: {sorted(list(roi_counter.counted_objects))}")
    print("="*50)

if __name__ == "__main__":
    main()