import cv2
from ultralytics import YOLO
import numpy as np
import math

def calculate_distance(box1, box2):
    """Hitung jarak antara center point dua bounding box"""
    center1 = ((box1[0] + box1[2]) / 2, (box1[1] + box1[3]) / 2)
    center2 = ((box2[0] + box2[2]) / 2, (box2[1] + box2[3]) / 2)
    return math.sqrt((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)

def calculate_iou(box1, box2):
    """Hitung Intersection over Union (IoU) antara dua bounding box"""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    if x2 <= x1 or y2 <= y1:
        return 0
    
    intersection = (x2 - x1) * (y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection
    
    return intersection / union if union > 0 else 0

def is_overlap_or_nearby(person_box, safety_box, distance_threshold=100, iou_threshold=0.1):
    """Cek apakah safety equipment berada dekat atau overlap dengan person"""
    # Cek IoU overlap
    iou = calculate_iou(person_box, safety_box)
    if iou > iou_threshold:
        return True
    
    # Cek jarak center point
    distance = calculate_distance(person_box, safety_box)
    if distance < distance_threshold:
        return True
    
    # Cek apakah safety equipment berada di area atas person (untuk helm)
    person_center_x = (person_box[0] + person_box[2]) / 2
    person_top = person_box[1]
    safety_center_x = (safety_box[0] + safety_box[2]) / 2
    safety_bottom = safety_box[3]
    
    # Untuk helm, cek apakah berada di area kepala (bagian atas person)
    if abs(person_center_x - safety_center_x) < 50 and safety_bottom <= person_top + 80:
        return True
    
    return False

def check_safety_compliance(persons, hardhats, safety_vests):
    """Cek compliance safety untuk setiap person"""
    compliance_results = []
    
    for person in persons:
        person_box = person['bbox']
        has_hardhat = False
        has_safety_vest = False
        
        # Cek apakah person memiliki hardhat
        for hardhat in hardhats:
            if is_overlap_or_nearby(person_box, hardhat['bbox']):
                has_hardhat = True
                break
        
        # Cek apakah person memiliki safety vest
        for vest in safety_vests:
            if is_overlap_or_nearby(person_box, vest['bbox'], distance_threshold=80):
                has_safety_vest = True
                break
        
        compliance_results.append({
            'person': person,
            'has_hardhat': has_hardhat,
            'has_safety_vest': has_safety_vest,
            'compliant': has_hardhat and has_safety_vest
        })
    
    return compliance_results

def main():
    # Load YOLOv8 model
    model = YOLO('best.pt')
    
    # Buka video
    video_path = 'hse1.mp4'
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"Error: Tidak dapat membuka video {video_path}")
        return
    
    # Dapatkan informasi video
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"Video Info: {width}x{height} @ {fps} FPS")
    print("Safety Compliance Detection Started...")
    print("Hijau = Compliant, Merah = Non-Compliant")
    
    frame_count = 0
    total_violations = 0
    
    while True:
        ret, frame = cap.read()
        
        if not ret:
            print("Video selesai atau error membaca frame")
            break
        
        frame_count += 1
        
        # Jalankan inferensi YOLOv8
        results = model(frame)
        
        # Pisahkan deteksi berdasarkan kelas
        persons = []
        hardhats = []
        safety_vests = []
        
        for r in results:
            boxes = r.boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0]
                    confidence = box.conf[0]
                    class_id = box.cls[0]
                    class_name = model.names[int(class_id)]
                    
                    # Filter berdasarkan confidence minimum
                    if confidence < 0.5:
                        continue
                    
                    detection = {
                        'bbox': (int(x1), int(y1), int(x2), int(y2)),
                        'confidence': float(confidence),
                        'class_name': class_name
                    }
                    
                    if class_name == 'Person':
                        persons.append(detection)
                    elif class_name == 'Hardhat':
                        hardhats.append(detection)
                    elif class_name == 'Safety Vest':
                        safety_vests.append(detection)
        
        # Cek compliance untuk setiap person
        compliance_results = check_safety_compliance(persons, hardhats, safety_vests)
        
        # Buat frame annotated
        annotated_frame = frame.copy()
        
        # Gambar semua deteksi safety equipment dengan warna abu-abu
        for hardhat in hardhats:
            x1, y1, x2, y2 = hardhat['bbox']
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (128, 128, 128), 1)
            cv2.putText(annotated_frame, f"Helmet {hardhat['confidence']:.2f}", 
                       (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 128), 1)
        
        for vest in safety_vests:
            x1, y1, x2, y2 = vest['bbox']
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (128, 128, 128), 1)
            cv2.putText(annotated_frame, f"Vest {vest['confidence']:.2f}", 
                       (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 128), 1)
        
        # Gambar person dengan status compliance
        violations_this_frame = 0
        
        for result in compliance_results:
            person = result['person']
            x1, y1, x2, y2 = person['bbox']
            
            # Tentukan warna berdasarkan compliance
            if result['compliant']:
                color = (0, 255, 0)  # Hijau - Compliant
                status = "COMPLIANT"
            else:
                color = (0, 0, 255)  # Merah - Non-Compliant
                status = "VIOLATION"
                violations_this_frame += 1
            
            # Gambar bounding box person
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 3)
            
            # Buat label detail
            missing_items = []
            if not result['has_hardhat']:
                missing_items.append("HELM")
            if not result['has_safety_vest']:
                missing_items.append("VEST")
            
            if missing_items:
                detail = f"Missing: {', '.join(missing_items)}"
            else:
                detail = "Complete Safety"
            
            # Label utama
            label = f"{status} {person['confidence']:.2f}"
            cv2.putText(annotated_frame, label, 
                       (x1, y1-25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # Detail missing items
            cv2.putText(annotated_frame, detail, 
                       (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        total_violations += violations_this_frame
        
        # Informasi di layar
        info_lines = [
            f"Frame: {frame_count}",
            f"Persons: {len(persons)} | Violations: {violations_this_frame}",
            f"Total Violations: {total_violations}",
            f"Compliance Rate: {((frame_count * len(persons) - total_violations) / max(frame_count * len(persons), 1) * 100):.1f}%" if persons else "No persons detected"
        ]
        
        for i, line in enumerate(info_lines):
            cv2.putText(annotated_frame, line, 
                       (10, 30 + i*25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 
                       (255, 255, 255), 2)
        
        # Console output untuk violations
        if violations_this_frame > 0:
            print(f"\nFrame {frame_count}: {violations_this_frame} VIOLATIONS detected!")
            for i, result in enumerate(compliance_results):
                if not result['compliant']:
                    missing = []
                    if not result['has_hardhat']:
                        missing.append("Helmet")
                    if not result['has_safety_vest']:
                        missing.append("Safety Vest")
                    print(f"  Person {i+1}: Missing {', '.join(missing)}")
        
        # Tampilkan frame
        cv2.imshow('Safety Compliance Detection System', annotated_frame)
        
        # Kontrol
        delay = max(1, int(1000 / fps))
        key = cv2.waitKey(delay) & 0xFF
        if key == ord('q'):
            print("Menghentikan deteksi...")
            break
        elif key == ord('p'):
            print("Video dipause. Tekan sembarang tombol untuk melanjutkan...")
            cv2.waitKey(0)
        elif key == ord('s'):
            screenshot_name = f"compliance_frame_{frame_count}.jpg"
            cv2.imwrite(screenshot_name, annotated_frame)
            print(f"Screenshot disimpan: {screenshot_name}")
    
    # Cleanup dan summary
    cap.release()
    cv2.destroyAllWindows()
    
    print(f"\n=== SUMMARY ===")
    print(f"Total frames processed: {frame_count}")
    print(f"Frames actually detected: {(frame_count + detection_interval - 1) // detection_interval}")
    print(f"Detection rate: 2x per second (every {detection_interval} frames)")
    print(f"Performance gain: {((1 - (1/detection_interval)) * 100):.1f}% faster")
    print(f"Total violations detected: {total_violations}")
    if frame_count > 0:
        avg_compliance = ((frame_count * len(persons) - total_violations) / max(frame_count * len(persons), 1) * 100) if persons else 100
        print(f"Overall compliance rate: {avg_compliance:.1f}%")

if __name__ == "__main__":
    main()