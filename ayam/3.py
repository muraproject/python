import cv2
from ultralytics import YOLO
import numpy as np
from scipy.spatial.distance import cdist

class ROIManager:
    def __init__(self, roi_points=None):
        self.roi_points = roi_points
        self.roi_polygon = None
        self.exit_count = 0
        self.tracked_exit_ids = set()  # ID objek yang sudah dihitung keluar
        
    def set_roi_rectangle(self, x, y, width, height):
        """Set ROI sebagai rectangle"""
        self.roi_points = [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
        self.roi_polygon = np.array(self.roi_points, np.int32)
        
    def set_roi_polygon(self, points):
        """Set ROI sebagai polygon dengan list of points"""
        self.roi_points = points
        self.roi_polygon = np.array(points, np.int32)
    
    def point_in_roi(self, point):
        """Cek apakah titik berada di dalam ROI"""
        if self.roi_polygon is None:
            return True
        return cv2.pointPolygonTest(self.roi_polygon, point, False) >= 0
    
    def bbox_in_roi(self, bbox):
        """Cek apakah bounding box berada di dalam ROI"""
        if self.roi_polygon is None:
            return True
        x1, y1, x2, y2 = bbox
        center = ((x1 + x2) // 2, (y1 + y2) // 2)
        return self.point_in_roi(center)
    
    def crop_to_roi(self, frame):
        """Crop frame hanya pada area ROI untuk optimasi"""
        if self.roi_polygon is None:
            return frame, (0, 0)
        
        # Dapatkan bounding rect dari ROI
        x, y, w, h = cv2.boundingRect(self.roi_polygon)
        
        # Crop frame
        cropped = frame[y:y+h, x:x+w]
        return cropped, (x, y)
    
    def adjust_detections_to_full_frame(self, detections, offset):
        """Sesuaikan koordinat deteksi dari cropped ke full frame"""
        offset_x, offset_y = offset
        adjusted_detections = []
        
        for detection in detections:
            x1, y1, x2, y2 = detection['bbox']
            adjusted_detection = detection.copy()
            adjusted_detection['bbox'] = (x1 + offset_x, y1 + offset_y, x2 + offset_x, y2 + offset_y)
            adjusted_detection['center'] = (detection['center'][0] + offset_x, detection['center'][1] + offset_y)
            adjusted_detections.append(adjusted_detection)
        
        return adjusted_detections
    
    def draw_roi(self, frame):
        """Gambar ROI di frame"""
        if self.roi_polygon is not None:
            # Gambar ROI polygon
            cv2.polylines(frame, [self.roi_polygon], True, (0, 255, 255), 3)
            # Fill dengan transparansi
            overlay = frame.copy()
            cv2.fillPoly(overlay, [self.roi_polygon], (0, 255, 255))
            cv2.addWeighted(frame, 0.8, overlay, 0.2, 0, frame)
            
            # Label ROI
            roi_center = np.mean(self.roi_polygon, axis=0).astype(int)
            cv2.putText(frame, "ROI", tuple(roi_center), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

class ObjectTracker:
    def __init__(self, roi_manager):
        self.trackers = []
        self.next_id = 1
        self.max_disappeared = 20  # Frame maksimum sebelum tracker dihapus
        self.max_distance = 10     # Jarak maksimum untuk mencocokkan deteksi
        self.roi_manager = roi_manager
    
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
        """Update tracker dengan deteksi baru (hanya yang di dalam ROI)"""
        # Filter deteksi hanya yang di dalam ROI
        roi_detections = []
        for detection in detections:
            if self.roi_manager.bbox_in_roi(detection['bbox']):
                roi_detections.append(detection)
        
        # Cek tracker yang keluar dari ROI
        self.check_exit_roi()
        
        if len(roi_detections) == 0:
            # Jika tidak ada deteksi di ROI, update semua tracker dengan prediksi saja
            for tracker in self.trackers:
                tracker['disappeared'] += 1
                prediction = tracker['kalman'].predict()
                tracker['center'] = (int(prediction[0]), int(prediction[1]))
            
            # Hapus tracker yang sudah terlalu lama menghilang
            self.trackers = [t for t in self.trackers if t['disappeared'] <= self.max_disappeared]
            return
        
        # Jika ada tracker dan deteksi ROI
        if len(self.trackers) == 0:
            # Buat tracker baru untuk semua deteksi ROI
            for detection in roi_detections:
                self.create_new_tracker(detection)
        else:
            # Cocokkan deteksi dengan tracker yang ada
            self.match_detections_to_trackers(roi_detections)
    
    def check_exit_roi(self):
        """Cek tracker yang keluar dari ROI dan tambah ke counter"""
        for tracker in self.trackers[:]:  # Gunakan slice copy untuk iterasi aman
            if not self.roi_manager.point_in_roi(tracker['center']):
                if tracker['id'] not in self.roi_manager.tracked_exit_ids:
                    self.roi_manager.exit_count += 1
                    self.roi_manager.tracked_exit_ids.add(tracker['id'])
                    print(f"  OBJEK KELUAR ROI - ID:{tracker['id']} {tracker['class']} | Total Keluar: {self.roi_manager.exit_count}")
                
                # Hapus tracker yang keluar dari ROI
                self.trackers.remove(tracker)
    
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
            'trail': [(cx, cy)],  # Untuk menggambar jejak
            'in_roi': True
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
    
    # Setup ROI - ATUR SESUAI KEBUTUHAN
    roi_manager = ROIManager()
    
    # Option 1: ROI Rectangle (x, y, width, height)
    # Contoh: ROI di tengah frame
    roi_x = width // 4
    roi_y = height // 4
    roi_width = width // 2
    roi_height = height // 2
    roi_manager.set_roi_rectangle(270, 100, 50, 200)
    
    # Option 2: ROI Polygon (uncomment untuk menggunakan)
    # roi_points = [(100, 100), (500, 100), (600, 400), (50, 400)]
    # roi_manager.set_roi_polygon(roi_points)
    
    print(f"ROI setup: Rectangle ({roi_x}, {roi_y}) size {roi_width}x{roi_height}")
    
    # Initialize object tracker dengan ROI
    tracker = ObjectTracker(roi_manager)
    
    print("Kalman Filter + ROI Tracking aktif!")
    print("Hanya objek di dalam ROI yang akan di-track")
    print("Objek yang keluar ROI akan dihitung")
    
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        
        if not ret:
            print("Video selesai atau error membaca frame")
            break
        
        frame_count += 1
        print(f"Memproses frame {frame_count}")
        
        # Crop frame untuk optimasi (hanya proses area ROI)
        cropped_frame, offset = roi_manager.crop_to_roi(frame)
        
        # Jalankan inferensi YOLOv8 hanya pada cropped frame
        if cropped_frame.size > 0:
            results = model(cropped_frame)
            
            # Konversi hasil deteksi ke format untuk tracker
            detections = []
            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        # Dapatkan koordinat bounding box (relative to cropped frame)
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = box.conf[0].cpu().numpy()
                        class_id = int(box.cls[0].cpu().numpy())
                        class_name = model.names[class_id]
                        
                        # Hitung center point (relative to cropped frame)
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
            
            # Adjust koordinat deteksi ke full frame
            detections = roi_manager.adjust_detections_to_full_frame(detections, offset)
        else:
            detections = []
        
        # Update tracker dengan deteksi baru
        tracker.update(detections)
        
        # Gambar ROI
        roi_manager.draw_roi(frame)
        
        # Gambar tracking results (hanya yang di dalam ROI)
        for tracked_obj in tracker.trackers:
            # Gambar bounding box
            x1, y1, x2, y2 = tracked_obj['bbox']
            
            # Warna berbeda untuk setiap ID
            colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), 
                     (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 165, 0)]
            color = colors[tracked_obj['id'] % len(colors)]
            
            # Gambar bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Gambar center point
            cx, cy = tracked_obj['center']
            cv2.circle(frame, (cx, cy), 4, color, -1)
            
            # Gambar trail (jejak) - hanya yang di dalam ROI
            if len(tracked_obj['trail']) > 1:
                roi_trail = [point for point in tracked_obj['trail'] 
                           if roi_manager.point_in_roi(point)]
                for i in range(1, len(roi_trail)):
                    thickness = max(1, int(3 * i / len(roi_trail)))
                    cv2.line(frame, roi_trail[i-1], roi_trail[i], color, thickness)
            
            # Label dengan ID dan informasi
            label = f"ID:{tracked_obj['id']} {tracked_obj['class']} {tracked_obj['confidence']:.2f}"
            
            # Background untuk label
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            cv2.rectangle(frame, (x1, y1-25), (x1 + label_size[0], y1), color, -1)
            cv2.putText(frame, label, (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2)
        
        # Tampilkan informasi tracking di console
        print(f"  Active Trackers in ROI: {len(tracker.trackers)}")
        print(f"  Total Exit Count: {roi_manager.exit_count}")
        for tracked_obj in tracker.trackers:
            status = "MISSING" if tracked_obj['disappeared'] > 0 else "ACTIVE"
            print(f"    ID {tracked_obj['id']}: {tracked_obj['class']} - {status}")
        
        # Tampilkan statistik di frame
        cv2.putText(frame, f"Frame: {frame_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        cv2.putText(frame, f"Tracked in ROI: {len(tracker.trackers)}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        cv2.putText(frame, f"Exit Count: {roi_manager.exit_count}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        
        # Tampilkan frame dengan ROI tracking secara live
        cv2.imshow('YOLOv8 + Kalman Filter + ROI - ayam.mp4', frame)
        
        # Kontrol kecepatan playback (sesuaikan delay untuk live feel)
        # Gunakan delay berdasarkan FPS video untuk playback natural
        delay = max(1, int(1000 / fps))
        key = cv2.waitKey(delay) & 0xFF
        if key == ord('q'):
            print("Menghentikan ROI tracking...")
            break
        elif key == ord('p'):
            print("Video dipause. Tekan sembarang tombol untuk melanjutkan...")
            cv2.waitKey(0)
        elif key == ord('r'):
            # Reset counter
            roi_manager.exit_count = 0
            roi_manager.tracked_exit_ids.clear()
            print("Exit counter direset!")
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    
    print("ROI tracking selesai!")
    print(f"Total frame yang diproses: {frame_count}")
    print(f"Total objek unik yang masuk ROI: {tracker.next_id - 1}")
    print(f"Total objek yang keluar ROI: {roi_manager.exit_count}")

if __name__ == "__main__":
    main()