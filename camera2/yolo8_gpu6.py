import cv2
import numpy as np
import time
from ultralytics import YOLO
from collections import deque
import os
from datetime import datetime
import threading
import argparse

# Kelas untuk tracking objek
class ObjectTracker:
    def __init__(self, max_trajectory_points=10):
        self.trajectories = {}
        self.max_points = max_trajectory_points
        self.colors = {}

    def get_color(self, track_id):
        if track_id not in self.colors:
            self.colors[track_id] = tuple(np.random.randint(0, 255, 3).tolist())
        return self.colors[track_id]

    def update_trajectory(self, track_id, centroid):
        if track_id not in self.trajectories:
            self.trajectories[track_id] = deque(maxlen=self.max_points)
        self.trajectories[track_id].append(centroid)

# Thread untuk mengambil frame dari video source dengan kontrol framerate
class FramerateControlledCapture:
    def __init__(self, video_source, resize_factor=0.5, target_fps=None):
        self.video_source = video_source
        self.resize_factor = resize_factor
        
        # Inisialisasi video capture
        self.cap = cv2.VideoCapture(video_source)
        if video_source.startswith(('rtsp://', 'http://', 'https://')):
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Dapatkan framerate asli video
        self.original_fps = self.cap.get(cv2.CAP_PROP_FPS)
        print(f"Video original FPS: {self.original_fps}")
        
        # Set target framerate (gunakan original jika tidak ditentukan)
        self.target_fps = target_fps if target_fps is not None else self.original_fps
        
        # Baca frame pertama
        self.grabbed, frame = self.cap.read()
        if self.grabbed and self.resize_factor != 1.0:
            frame = cv2.resize(frame, (0, 0), fx=self.resize_factor, fy=self.resize_factor)
        
        self.frame = frame
        self.last_frame_time = time.time()
        self.stopped = False
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()
        self.height, self.width = frame.shape[:2] if self.grabbed else (0, 0)
        
        # Variabel untuk kontrol framerate
        self.frame_interval = 1.0 / self.target_fps
        
    def start(self):
        threading.Thread(target=self.update, daemon=True).start()
        return self
        
    def update(self):
        """Threading function untuk mengambil frame dengan kontrol framerate"""
        while not self.stopped:
            if not self.grabbed:
                self.stop()
                break
            
            # Waktu yang dibutuhkan untuk setiap frame berdasarkan target FPS
            current_time = time.time()
            elapsed = current_time - self.last_frame_time
            
            # Hanya ambil frame baru jika sudah waktunya
            if elapsed >= self.frame_interval:
                self.grabbed, frame = self.cap.read()
                
                if not self.grabbed:
                    self.stop()
                    break
                
                if self.resize_factor != 1.0:
                    frame = cv2.resize(frame, (0, 0), fx=self.resize_factor, fy=self.resize_factor)
                    
                self.frame = frame
                self.last_frame_time = current_time
                
                # Calculate actual FPS
                self.frame_count += 1
                total_elapsed = current_time - self.start_time
                if total_elapsed >= 1.0:
                    self.fps = self.frame_count / total_elapsed
                    self.frame_count = 0
                    self.start_time = current_time
            else:
                # Sleep untuk mengurangi penggunaan CPU 
                time.sleep(max(0, self.frame_interval - elapsed) * 0.8)  # Sleep sedikit kurang dari interval untuk kompensasi jitter
    
    def read(self):
        return self.frame
    
    def get_fps(self):
        return self.fps
    
    def get_dimensions(self):
        return (self.width, self.height)
        
    def stop(self):
        self.stopped = True
        if self.cap is not None:
            self.cap.release()

# Periodic Screenshot Manager - lebih efisien, tanpa thread terpisah
class ScreenshotManager:
    def __init__(self, save_dir, interval=5.0, prefix="tracking"):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        self.interval = interval
        self.prefix = prefix
        self.last_save_time = 0
        self.enabled = True
        
    def maybe_save(self, frame, current_time):
        """Ambil screenshot saat interval waktu tercapai"""
        if not self.enabled or self.interval <= 0:
            return False

        if current_time - self.last_save_time >= self.interval:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.save_dir}/{self.prefix}_{timestamp}.jpg"
            
            # Spawn thread khusus untuk I/O operasi 
            # agar tidak menghambat thread utama
            threading.Thread(
                target=lambda f, fn: cv2.imwrite(fn, f), 
                args=(frame.copy(), filename),
                daemon=True
            ).start()
            
            self.last_save_time = current_time
            return True
        return False

def run_tracker(
    video_source='https://cctvjss.jogjakota.go.id/atcs/ATCS_Glagahsari_PTZ.stream/playlist.m3u8',
    output_dir='output',
    display_mode='single',
    resize_factor=0.5,
    confidence_threshold=0.4,
    screenshot_interval=5.0,
    yolo_model='yolov8n.pt',
    show_ui=True,
    target_fps=None,
    detection_fps=5.0  # Target 5 FPS untuk deteksi
):
    # Buat directory output jika belum ada
    os.makedirs(output_dir, exist_ok=True)
    
    # Inisialisasi screenshot manager
    screenshot_mgr = ScreenshotManager(
        save_dir=output_dir, 
        interval=screenshot_interval
    )
    
    # Load YOLO model di thread utama untuk menghindari masalah
    try:
        print(f"Loading {yolo_model}...")
        model = YOLO(yolo_model)
        print("Model loaded successfully")
    except Exception as e:
        print(f"Failed to load model: {e}")
        return
    
    # Inisialisasi tracker
    tracker = ObjectTracker(max_trajectory_points=10)

    # Inisialisasi variabel tracking
    object_counts = {
        'car': {'up': 0, 'down': 0},
        'motorcycle': {'up': 0, 'down': 0},
        'truck': {'up': 0, 'down': 0},
        'bus': {'up': 0, 'down': 0},
        'person': {'up': 0, 'down': 0},
        'bicycle': {'up': 0, 'down': 0}
    }
    prev_centroids = {}
    tracking_id = 0
    crossed_ids = {'up': set(), 'down': set()}
    
    # Start video capture in threaded mode with framerate control
    print(f"Opening video: {video_source}")
    video_capture = FramerateControlledCapture(
        video_source=video_source,
        resize_factor=resize_factor,
        target_fps=target_fps
    ).start()
    
    if not video_capture.grabbed:
        print("Failed to open video source")
        return
    
    # Get frame dimensions
    width, height = video_capture.get_dimensions()
    
    # Define detection lines
    up_line_y = int(height * 0.4)
    down_line_y = int(height * 0.6)
    
    # Display setup
    if show_ui:
        if display_mode == 'dual':
            cv2.namedWindow("Live View", cv2.WINDOW_NORMAL)
        cv2.namedWindow("Tracking", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Tracking", 800, 600)
        
    print(f"Starting video processing...")
    print(f"Video playback FPS: {video_capture.target_fps:.1f}")
    print(f"Detection FPS: {detection_fps}")
    
    # Untuk pengukuran FPS
    tracking_fps = 0
    tracking_frame_count = 0
    tracking_start_time = time.time()
    
    # Variabel untuk last detection time
    last_detection_time = 0
    detection_interval = 1.0 / detection_fps  # Interval untuk 5 FPS (0.2 detik)
    
    # Untuk tracking hasil terakhir
    last_results = None
    last_tracking_frame = None
    
    try:
        while not video_capture.stopped:
            current_time = time.time()
            
            # Get latest frame
            frame = video_capture.read()
            if frame is None:
                print("End of video stream")
                break
                
            # Show original frame if in dual mode
            if show_ui and display_mode == 'dual':
                live_frame = frame.copy()
                cv2.putText(live_frame, "LIVE VIEW", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                cv2.putText(live_frame, f"FPS: {video_capture.get_fps():.1f}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                cv2.imshow("Live View", live_frame)
            
            # Buat copy dari frame untuk tracking view
            if show_ui or screenshot_interval > 0:
                tracking_frame = frame.copy()
            else:
                tracking_frame = None
                
            # Hanya lakukan deteksi setiap interval (sesuai detection_fps)
            do_detection = current_time - last_detection_time >= detection_interval
                
            if do_detection:
                # Catat waktu mulai proses
                process_start = time.time()
                last_detection_time = current_time
                
                # Detect objects with YOLO
                try:
                    results = model(frame, verbose=False)
                    last_results = results  # Simpan hasil untuk frame berikutnya
                    
                    # Process detection results
                    current_centroids = {}
                    detected_objects = []  # Lista untuk menyimpan data tracking
                    
                    for r in results:
                        boxes = r.boxes
                        for box in boxes:
                            cls = int(box.cls[0])
                            conf = float(box.conf[0])
                            class_name = model.names[cls]
                            
                            if conf > confidence_threshold and class_name in object_counts:
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                centroid_x = (x1 + x2) // 2
                                centroid_y = (y1 + y2) // 2
                                
                                # Tracking with simple algorithm
                                matched_id = None
                                min_distance = float('inf')
                                
                                for prev_id, prev_data in prev_centroids.items():
                                    prev_x, prev_y, _ = prev_data
                                    distance = ((prev_x - centroid_x) ** 2 + (prev_y - centroid_y) ** 2) ** 0.5
                                    if distance < min_distance and distance <= 50:
                                        min_distance = distance
                                        matched_id = prev_id
                                        
                                if matched_id is None:
                                    matched_id = tracking_id
                                    tracking_id += 1
                                    
                                current_centroids[matched_id] = (centroid_x, centroid_y, class_name)
                                tracker.update_trajectory(matched_id, (centroid_x, centroid_y))
                                color = tracker.get_color(matched_id)
                                
                                # Check line crossing
                                direction = ""
                                if matched_id in prev_centroids:
                                    prev_y = prev_centroids[matched_id][1]
                                    
                                    # Check up crossing
                                    if prev_y > up_line_y and centroid_y <= up_line_y and matched_id not in crossed_ids['up']:
                                        object_counts[class_name]['up'] += 1
                                        crossed_ids['up'].add(matched_id)
                                        direction = "↑ UP"
                                        
                                    # Check down crossing
                                    if prev_y < down_line_y and centroid_y >= down_line_y and matched_id not in crossed_ids['down']:
                                        object_counts[class_name]['down'] += 1
                                        crossed_ids['down'].add(matched_id)
                                        direction = "↓ DOWN"
                                        
                                # Save object data for visualization
                                detected_objects.append({
                                    'id': matched_id,
                                    'class': class_name,
                                    'box': (x1, y1, x2, y2),
                                    'centroid': (centroid_x, centroid_y),
                                    'color': color,
                                    'direction': direction
                                })
                    
                    # Update tracking data
                    prev_centroids = current_centroids
                    
                    # Update crossed IDs
                    crossed_ids['up'] = {id for id in crossed_ids['up'] if id in current_centroids}
                    crossed_ids['down'] = {id for id in crossed_ids['down'] if id in current_centroids}
                    
                    # Calculate tracking FPS
                    tracking_frame_count += 1
                    elapsed_time = time.time() - tracking_start_time
                    if elapsed_time >= 1.0:
                        tracking_fps = tracking_frame_count / elapsed_time
                        tracking_frame_count = 0
                        tracking_start_time = time.time()
                    
                    # Hitung waktu proses
                    process_time = time.time() - process_start
                    
                    # Simpan object untuk visualisasi
                    last_detected_objects = detected_objects
                    
                except Exception as e:
                    print(f"Detection error: {e}")
                    continue
            else:
                # Gunakan hasil deteksi sebelumnya
                detected_objects = last_detected_objects if 'last_detected_objects' in locals() else []
                process_time = 0
            
            # Only render visualization if UI is enabled or screenshot is needed
            if (show_ui or screenshot_mgr.maybe_save(tracking_frame, current_time)) and tracking_frame is not None:
                # Draw detection lines
                cv2.line(tracking_frame, (0, up_line_y), (width, up_line_y), (0, 255, 0), 2)
                cv2.putText(tracking_frame, "UP", (10, up_line_y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                cv2.line(tracking_frame, (0, down_line_y), (width, down_line_y), (0, 0, 255), 2)
                cv2.putText(tracking_frame, "DOWN", (10, down_line_y + 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
                # Draw detected objects if available
                if 'detected_objects' in locals() and detected_objects:
                    for obj in detected_objects:
                        x1, y1, x2, y2 = obj['box']
                        centroid_x, centroid_y = obj['centroid']
                        color = obj['color']
                        
                        # Draw bounding box and centroid
                        cv2.rectangle(tracking_frame, (x1, y1), (x2, y2), color, 2)
                        cv2.circle(tracking_frame, (centroid_x, centroid_y), 4, color, -1)
                        
                        # Draw trajectory
                        if obj['id'] in tracker.trajectories:
                            points = list(tracker.trajectories[obj['id']])
                            for i in range(1, len(points)):
                                cv2.line(tracking_frame, points[i-1], points[i], color, 2)
                        
                        # Draw label
                        label = f"{obj['class']} {obj['direction']}"
                        cv2.putText(tracking_frame, label, (x1, y1-10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                # Display counts
                y_pos = 30
                for obj_type, counts in object_counts.items():
                    text = f"{obj_type}: UP:{counts['up']} DN:{counts['down']}"
                    cv2.putText(tracking_frame, text, (width - 250, y_pos), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                    y_pos += 20
                
                # Display FPS info
                cv2.putText(tracking_frame, f"Video: {video_capture.get_fps():.1f} FPS", 
                            (10, height - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                cv2.putText(tracking_frame, f"Detection: {detection_fps:.1f} FPS", 
                            (10, height - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                
                detection_status = "Active" if do_detection else "Waiting"
                cv2.putText(tracking_frame, f"Detection: {detection_status}", 
                            (10, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                            (0, 255, 0) if do_detection else (0, 165, 255), 2)
                
                # Take screenshot if needed
                screenshot_mgr.maybe_save(tracking_frame, current_time)
                
                # Display tracking view
                if show_ui:
                    cv2.putText(tracking_frame, "TRACKING VIEW", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                    cv2.imshow("Tracking", tracking_frame)
                    last_tracking_frame = tracking_frame
            
            # Check for exit key
            if show_ui and cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up
        video_capture.stop()
        if show_ui:
            cv2.destroyAllWindows()
        
        # Print results
        print("\nFinal Object Counts:")
        for obj_type, counts in object_counts.items():
            print(f"{obj_type}: UP: {counts['up']}, DOWN: {counts['down']}")

def main():
    parser = argparse.ArgumentParser(description='Object Tracking with YOLO')
    parser.add_argument('--source', type=str, default='https://cctvjss.jogjakota.go.id/atcs/ATCS_Glagahsari_PTZ.stream/playlist.m3u8', help='Video source')
    parser.add_argument('--output', type=str, default='output', help='Output directory')
    parser.add_argument('--display', type=str, default='single', choices=['single', 'dual', 'none'], 
                        help='Display mode: single (tracking only), dual (live + tracking), none (headless)')
    parser.add_argument('--resize', type=float, default=0.5, help='Resize factor for input frames')
    parser.add_argument('--confidence', type=float, default=0.4, help='Detection confidence threshold')
    parser.add_argument('--screenshot', type=float, default=5.0, 
                        help='Screenshot interval in seconds (0 to disable)')
    parser.add_argument('--model', type=str, default='yolov8n.pt', help='YOLO model to use')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode (no UI)')
    parser.add_argument('--fps', type=float, default=None, 
                        help='Target FPS (default is original video FPS)')
    parser.add_argument('--detection-fps', type=float, default=5.0,
                        help='Target FPS for object detection (default is 5 FPS)')
    
    args = parser.parse_args()
    
    # Determine display mode
    show_ui = not args.headless
    display_mode = 'none' if args.headless else args.display
    
    print(f"Starting tracker with settings:")
    print(f"- Video source: {args.source}")
    print(f"- Display mode: {display_mode}")
    print(f"- Resize factor: {args.resize}x")
    print(f"- Detection FPS: {args.detection_fps}")
    print(f"- Screenshot interval: {args.screenshot}s")
    print(f"- Target Video FPS: {args.fps if args.fps else 'Original video FPS'}")
    
    run_tracker(
        video_source=args.source,
        output_dir=args.output,
        display_mode=display_mode,
        resize_factor=args.resize,
        confidence_threshold=args.confidence,
        screenshot_interval=args.screenshot,
        yolo_model=args.model,
        show_ui=show_ui,
        target_fps=args.fps,
        detection_fps=args.detection_fps
    )

if __name__ == "__main__":
    main()