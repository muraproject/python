import cv2
import numpy as np
import torch
from ultralytics import YOLO
from collections import defaultdict
import math
from scipy.optimize import linear_sum_assignment
from filterpy.kalman import KalmanFilter

# Implementasi SORT (Simple Online and Realtime Tracking)
def linear_assignment(cost_matrix):
    x, y = linear_sum_assignment(cost_matrix)
    return np.array(list(zip(x, y)))

def iou_batch(bb_test, bb_gt):
    """
    Computes IOU between two bboxes in the form [x1,y1,x2,y2]
    """
    bb_gt = np.expand_dims(bb_gt, 0)
    bb_test = np.expand_dims(bb_test, 1)
    
    xx1 = np.maximum(bb_test[..., 0], bb_gt[..., 0])
    yy1 = np.maximum(bb_test[..., 1], bb_gt[..., 1])
    xx2 = np.minimum(bb_test[..., 2], bb_gt[..., 2])
    yy2 = np.minimum(bb_test[..., 3], bb_gt[..., 3])
    w = np.maximum(0., xx2 - xx1)
    h = np.maximum(0., yy2 - yy1)
    wh = w * h
    o = wh / ((bb_test[..., 2] - bb_test[..., 0]) * (bb_test[..., 3] - bb_test[..., 1])                                      
        + (bb_gt[..., 2] - bb_gt[..., 0]) * (bb_gt[..., 3] - bb_gt[..., 1]) - wh)                                              
    return(o)  

def convert_bbox_to_z(bbox):
    """
    Takes a bounding box in the form [x1,y1,x2,y2] and returns z in the form
    [x,y,s,r] where x,y is the centre of the box and s is the scale/area and r is
    the aspect ratio
    """
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = bbox[0] + w/2.
    y = bbox[1] + h/2.
    s = w * h    # scale is just area
    r = w / float(h)
    return np.array([x, y, s, r]).reshape((4, 1))

def convert_x_to_bbox(x, score=None):
    """
    Takes a bounding box in the centre form [x,y,s,r] and returns it in the form
    [x1,y1,x2,y2] where x1,y1 is the top left and x2,y2 is the bottom right
    """
    w = np.sqrt(x[2] * x[3])
    h = x[2] / w
    if(score==None):
        return np.array([x[0]-w/2.,x[1]-h/2.,x[0]+w/2.,x[1]+h/2.]).reshape((1,4))
    else:
        return np.array([x[0]-w/2.,x[1]-h/2.,x[0]+w/2.,x[1]+h/2.,score]).reshape((1,5))

class KalmanBoxTracker(object):
    """
    This class represents the internal state of individual tracked objects observed as bbox.
    """
    count = 0
    def __init__(self, bbox):
        """
        Initialises a tracker using initial bounding box.
        """
        # define constant velocity model
        self.kf = KalmanFilter(dim_x=7, dim_z=4) 
        self.kf.F = np.array([[1,0,0,0,1,0,0],[0,1,0,0,0,1,0],[0,0,1,0,0,0,1],[0,0,0,1,0,0,0],  [0,0,0,0,1,0,0],[0,0,0,0,0,1,0],[0,0,0,0,0,0,1]])
        self.kf.H = np.array([[1,0,0,0,0,0,0],[0,1,0,0,0,0,0],[0,0,1,0,0,0,0],[0,0,0,1,0,0,0]])

        self.kf.R[2:,2:] *= 10.
        self.kf.P[4:,4:] *= 1000. # give high uncertainty to the unobservable initial velocities
        self.kf.P *= 10.
        self.kf.Q[-1,-1] *= 0.01
        self.kf.Q[4:,4:] *= 0.01

        self.kf.x[:4] = convert_bbox_to_z(bbox)
        self.time_since_update = 0
        self.id = KalmanBoxTracker.count
        KalmanBoxTracker.count += 1
        self.history = []
        self.hits = 0
        self.hit_streak = 0
        self.age = 0
        self.centroid_positions = []  # Menyimpan posisi centroid untuk garis tracking

    def update(self, bbox):
        """
        Updates the state vector with observed bbox.
        """
        self.time_since_update = 0
        self.history = []
        self.hits += 1
        self.hit_streak += 1
        self.kf.update(convert_bbox_to_z(bbox))
        
        # Tambahkan centroid saat ini ke history
        x1, y1, x2, y2 = bbox[:4]
        centroid_x = int((x1 + x2) / 2)
        centroid_y = int((y1 + y2) / 2)
        self.centroid_positions.append((centroid_x, centroid_y))
        
        # Batasi panjang history centroid (maksimal 20 posisi terakhir)
        if len(self.centroid_positions) > 20:
            self.centroid_positions = self.centroid_positions[-20:]

    def predict(self):
        """
        Advances the state vector and returns the predicted bounding box estimate.
        """
        if((self.kf.x[6]+self.kf.x[2])<=0):
            self.kf.x[6] *= 0.0
        self.kf.predict()
        self.age += 1
        if(self.time_since_update>0):
            self.hit_streak = 0
        self.time_since_update += 1
        self.history.append(convert_x_to_bbox(self.kf.x))
        return self.history[-1]

    def get_state(self):
        """
        Returns the current bounding box estimate.
        """
        return convert_x_to_bbox(self.kf.x)

def associate_detections_to_trackers(detections, trackers, iou_threshold=0.3):
    """
    Assigns detections to tracked object (both represented as bounding boxes)
    Returns 3 lists of matches, unmatched_detections and unmatched_trackers
    """
    if len(trackers) == 0:
        return np.empty((0, 2), dtype=int), np.arange(len(detections)), np.empty((0, 5), dtype=int)

    iou_matrix = iou_batch(detections, trackers)

    if min(iou_matrix.shape) > 0:
        a = (iou_matrix > iou_threshold).astype(np.int32)
        if a.sum(1).max() == 1 and a.sum(0).max() == 1:
            matched_indices = np.stack(np.where(a), axis=1)
        else:
            matched_indices = linear_assignment(-iou_matrix)
    else:
        matched_indices = np.empty(shape=(0, 2))

    unmatched_detections = []
    for d, det in enumerate(detections):
        if d not in matched_indices[:, 0]:
            unmatched_detections.append(d)
    
    unmatched_trackers = []
    for t, trk in enumerate(trackers):
        if t not in matched_indices[:, 1]:
            unmatched_trackers.append(t)

    # filter out matched with low IOU
    matches = []
    for m in matched_indices:
        if iou_matrix[m[0], m[1]] < iou_threshold:
            unmatched_detections.append(m[0])
            unmatched_trackers.append(m[1])
        else:
            matches.append(m.reshape(1, 2))
    
    if len(matches) == 0:
        matches = np.empty((0, 2), dtype=int)
    else:
        matches = np.concatenate(matches, axis=0)

    return matches, np.array(unmatched_detections), np.array(unmatched_trackers)

class Sort(object):
    def __init__(self, max_age=1, min_hits=3, iou_threshold=0.3):
        """
        Sets key parameters for SORT
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.trackers = []
        self.frame_count = 0
        self.colors = {}  # Dictionary untuk menyimpan warna untuk setiap ID

    def update(self, dets=np.empty((0, 5))):
        """
        Params:
          dets - a numpy array of detections in the format [[x1,y1,x2,y2,score],[x1,y1,x2,y2,score],...]
        Requires: this method must be called once for each frame even with empty detections.
        Returns the a similar array, where the last column is the object ID.
        """
        self.frame_count += 1
        
        # get predicted locations from existing trackers.
        trks = np.zeros((len(self.trackers), 5))
        to_del = []
        ret = []
        
        for t, trk in enumerate(trks):
            pos = self.trackers[t].predict()[0]
            trk[:] = [pos[0], pos[1], pos[2], pos[3], 0]
            if np.any(np.isnan(pos)):
                to_del.append(t)
        
        trks = np.ma.compress_rows(np.ma.masked_invalid(trks))
        for t in reversed(to_del):
            self.trackers.pop(t)
        
        matched, unmatched_dets, unmatched_trks = associate_detections_to_trackers(dets, trks, self.iou_threshold)

        # update matched trackers with assigned detections
        for m in matched:
            self.trackers[m[1]].update(dets[m[0], :])

        # create and initialise new trackers for unmatched detections
        for i in unmatched_dets:
            trk = KalmanBoxTracker(dets[i, :])
            # Buat warna random untuk ID baru
            if trk.id not in self.colors:
                self.colors[trk.id] = (
                    np.random.randint(0, 255),
                    np.random.randint(0, 255),
                    np.random.randint(0, 255)
                )
            self.trackers.append(trk)
        
        i = len(self.trackers)
        for trk in reversed(self.trackers):
            d = trk.get_state()[0]
            if (trk.time_since_update < 1) and (trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits):
                ret.append(np.concatenate((d, [trk.id])).reshape(1, -1))  # ID tanpa +1
            i -= 1
            
            # remove dead tracklet
            if trk.time_since_update > self.max_age:
                self.trackers.pop(i)
        
        if len(ret) > 0:
            return np.concatenate(ret)
        return np.empty((0, 5))

    def get_trackers(self):
        """
        Returns the current trackers for drawing trajectory lines
        """
        return self.trackers
    
    def get_color(self, track_id):
        """
        Returns the color for a given track ID
        """
        if track_id not in self.colors:
            self.colors[track_id] = (
                np.random.randint(0, 255),
                np.random.randint(0, 255),
                np.random.randint(0, 255)
            )
        return self.colors[track_id]

# Main program
def main():
    print("Memulai sistem deteksi dan tracking orang...")
    
    # Inisialisasi model YOLOv8n
    model = YOLO('yolov8n.pt')
    print("Model YOLOv8n berhasil dimuat")
    
    # Class yang ingin kita deteksi (orang = 0 dalam COCO dataset)
    target_class = 0  # 0 = orang/person
    
    # Inisialisasi SORT tracker
    mot_tracker = Sort(max_age=20, min_hits=3, iou_threshold=0.3)
    
    # Counter untuk orang
    person_counter = 0
    counted_ids = set()
    
    # Buka video
    video_path = 'mobil2.mp4'
    cap = cv2.VideoCapture(video_path)
    
    # Cek apakah video berhasil dibuka
    if not cap.isOpened():
        print(f"Error: Tidak dapat membuka video {video_path}")
        return
    
    print(f"Video {video_path} berhasil dibuka")
    
    # Dapatkan dimensi frame
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    
    # Setup garis penghitungan (tengah frame)
    counting_line_y = int(frame_height * 0.5)
    
    # Setup video writer
    output_path = 'output.mp4'
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
    
    if not out.isOpened():
        print(f"Error: Tidak dapat membuat file output {output_path}")
        cap.release()
        return
    
    print(f"File output akan disimpan ke {output_path}")
    
    # Tracking posisi sebelumnya
    previous_positions = {}
    frame_count = 0
    
    print("Memulai proses deteksi dan tracking...")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Selesai membaca video")
                break
            
            frame_count += 1
            if frame_count % 30 == 0:  # Tampilkan progress setiap 30 frame
                print(f"Memproses frame ke-{frame_count}")
                
            # Deteksi objek menggunakan YOLOv8
            results = model(frame, verbose=False)
            
            # Extract deteksi dan filter hanya orang
            detections = []
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls = int(box.cls[0].item())
                    
                    # Filter hanya orang (class 0)
                    if cls == target_class:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = box.conf[0].item()
                        
                        # Format deteksi untuk SORT [x1, y1, x2, y2, confidence]
                        detections.append([x1, y1, x2, y2, conf])
            
            # Jalankan SORT tracking
            if len(detections) > 0:
                detections_array = np.array(detections)
                track_bbs_ids = mot_tracker.update(detections_array)
            else:
                track_bbs_ids = np.empty((0, 5))
            
            # Gambar garis penghitungan
            cv2.line(frame, (0, counting_line_y), (frame_width, counting_line_y), (0, 255, 255), 2)
            
            # Ambil semua trackers untuk menggambar garis tracking
            trackers = mot_tracker.get_trackers()
            
            # Proses hasil tracking
            for track in track_bbs_ids:
                x1, y1, x2, y2, track_id = track.astype(int)
                
                # Tentukan posisi tengah orang
                center_y = (y1 + y2) // 2
                
                # Cek arah dan hitung jika melintasi garis
                if track_id in previous_positions:
                    prev_center_y = previous_positions[track_id]
                    
                    # Jika orang melintasi garis penghitungan dari atas ke bawah
                    if prev_center_y < counting_line_y and center_y >= counting_line_y:
                        if track_id not in counted_ids:
                            person_counter += 1
                            counted_ids.add(track_id)
                            print(f"Orang ID:{track_id} dihitung (total: {person_counter})")
                
                # Simpan posisi saat ini untuk perbandingan berikutnya
                previous_positions[track_id] = center_y
                
                # Dapatkan warna untuk ID ini
                color = mot_tracker.get_color(track_id)
                
                # Gambar bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # Label dengan ID
                label = f"Person ID:{track_id}"
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                # Hitung centroid untuk garis tracking
                centroid_x = int((x1 + x2) / 2)
                centroid_y = int((y1 + y2) / 2)
                
                # Tambahkan titik centroid ke dalam frame
                cv2.circle(frame, (centroid_x, centroid_y), 4, color, -1)
            
            # Gambar garis tracking untuk setiap tracker
            for tracker in trackers:
                if len(tracker.centroid_positions) > 1:
                    # Ambil warna untuk tracker ini
                    color = mot_tracker.get_color(tracker.id)
                    
                    # Gambar garis yang menghubungkan centroid positions
                    for i in range(1, len(tracker.centroid_positions)):
                        # Dapatkan posisi sebelumnya dan saat ini
                        prev_pos = tracker.centroid_positions[i-1]
                        curr_pos = tracker.centroid_positions[i]
                        
                        # Gambar garis
                        thickness = 2
                        cv2.line(frame, prev_pos, curr_pos, color, thickness)
            
            # Tampilkan counter di kanan atas
            text = f"Jumlah Orang: {person_counter}"
            cv2.putText(frame, text, (frame_width - 200, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            # Tulis frame ke file output
            out.write(frame)
            
    except Exception as e:
        print(f"Error terjadi: {str(e)}")
    finally:
        # Tutup semua
        cap.release()
        out.release()
        
        # Tampilkan hasil akhir
        print("\nHasil Penghitungan Akhir:")
        print(f"Total Orang: {person_counter}")
        
        print(f"\nVideo hasil telah disimpan ke {output_path}")

if __name__ == "__main__":
    main()