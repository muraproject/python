# processor/video_processor.py

import cv2
import numpy as np
from datetime import datetime
from ultralytics import YOLO

class VideoDisplay:
    """
    Class untuk mengelola tampilan video
    """
    def __init__(self, width=1280, height=720):
        self.display_width = width
        self.display_height = height
        
    def resize_frame(self, frame):
        """Resize frame ke ukuran tetap"""
        return cv2.resize(frame, (self.display_width, self.display_height))

class Monitor:
    """
    Class untuk menampilkan statistik monitoring
    """
    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.stats_height = 200
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.line_height = 20
        self.padding = 10
        self.colors = {
            'car': (255, 100, 0),      # Orange
            'bus': (0, 255, 100),      # Green
            'truck': (100, 100, 255),  # Blue
            'person': (255, 255, 0),   # Yellow
            'motorcycle': (255, 0, 255),# Magenta
            'bicycle': (0, 255, 255)    # Cyan
        }

    def create_stats_frame(self, width):
        """Membuat frame untuk statistik"""
        stats_frame = np.zeros((self.stats_height, width, 3), dtype=np.uint8)
        stats_frame[:] = (40, 40, 40)  # Dark gray background
        return stats_frame

    def draw_fps_info(self, frame, fps, num_objects):
        """Menampilkan FPS dan jumlah objek"""
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30), 
                   self.font, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"Objects: {num_objects}", (10, 60), 
                   self.font, 0.6, (255, 255, 255), 2)

    def draw_current_stats(self, frame, counts):
        """Menampilkan statistik lengkap"""
        height, width = frame.shape[:2]
        stats_frame = self.create_stats_frame(width)
        
        y_pos = self.padding
        x_pos_labels = [10, width//4, width//2, 3*width//4]
        
        # Headers
        headers = ['Vehicle Type', 'Up Lines', 'Down Lines', 'Total']
        for i, header in enumerate(headers):
            cv2.putText(stats_frame, header, (x_pos_labels[i], y_pos), 
                       self.font, 0.5, (255, 255, 255), 1)
        
        y_pos += self.line_height
        cv2.line(stats_frame, (0, y_pos), (width, y_pos), (100, 100, 100), 1)
        y_pos += 5
        
        # Draw detailed counts for each vehicle type
        for vehicle_type, color in self.colors.items():
            # Vehicle type name
            cv2.putText(stats_frame, vehicle_type.capitalize(), 
                       (x_pos_labels[0], y_pos), self.font, 0.5, color, 1)
            
            # Up lines detailed counts
            up_counts = [counts[vehicle_type][f'up{i}'] for i in range(1, 7)]
            up_text = f"1:{up_counts[0]} 2:{up_counts[1]} 3:{up_counts[2]} 4:{up_counts[3]} 5:{up_counts[4]} 6:{up_counts[5]}"
            cv2.putText(stats_frame, up_text, (x_pos_labels[1], y_pos), 
                       self.font, 0.5, color, 1)
            
            # Down lines detailed counts
            down_counts = [counts[vehicle_type][f'down{i}'] for i in range(1, 7)]
            down_text = f"1:{down_counts[0]} 2:{down_counts[1]} 3:{down_counts[2]} 4:{down_counts[3]} 5:{down_counts[4]} 6:{down_counts[5]}"
            cv2.putText(stats_frame, down_text, (x_pos_labels[2], y_pos), 
                       self.font, 0.5, color, 1)
            
            # Totals for this vehicle type
            total_up = sum(up_counts)
            total_down = sum(down_counts)
            cv2.putText(stats_frame, f"Up:{total_up} Down:{total_down}", 
                       (x_pos_labels[3], y_pos), self.font, 0.5, color, 1)
            
            y_pos += self.line_height
        
        # Add timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cv2.putText(stats_frame, f"Time: {timestamp}", 
                   (width - 200, self.stats_height - 10), 
                   self.font, 0.5, (255, 255, 255), 1)
        
        return np.vstack((frame, stats_frame))

class VideoProcessor:
    """
    Class utama untuk pemrosesan video
    """
    def __init__(self, settings_manager, data_manager):
        self.settings_manager = settings_manager
        self.data_manager = data_manager
        self.model = YOLO('yolov8n.pt')
        self.gpu_processor = settings_manager.gpu_processor
        self.tracker = settings_manager.tracker
        self.monitor = Monitor(data_manager)
        self.video_display = VideoDisplay(
            settings_manager.settings['display']['width'],
            settings_manager.settings['display']['height']
        )
        
        self.prev_centroids = {}
        self.tracking_id = 0
        self.crossed_ids = {
            f'{direction}{i}': set() 
            for direction in ['up', 'down'] 
            for i in range(1, 7)
        }
        
        # Performance metrics
        self.frame_count = 0
        self.fps = 0
        self.processing_time = 0

    def initialize_video_capture(self):
        """Inisialisasi video capture dengan settings yang sesuai"""
        video_source = self.settings_manager.settings['video_source']
        cap = cv2.VideoCapture(video_source, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 30)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        if video_source.startswith(('rtsp://', 'http://', 'https://')):
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        return cap

    def calculate_line_positions(self, height):
        """Menghitung posisi garis berdasarkan settings"""
        settings = self.settings_manager.settings['lines']
        return {
            'up_lines': [int(height * settings[f'up{i}']) for i in range(1, 7)],
            'down_lines': [int(height * settings[f'down{i}']) for i in range(1, 7)]
        }

    def track_object(self, centroid_x, centroid_y):
        """Track objek berdasarkan posisi centroid"""
        if self.prev_centroids:
            prev_points = np.array([[p[0], p[1]] for p in self.prev_centroids.values()])
            curr_point = np.array([centroid_x, centroid_y])
            distances = np.linalg.norm(prev_points - curr_point, axis=1)
            min_distance_idx = np.argmin(distances)
            min_distance = distances[min_distance_idx]
            matched_id = list(self.prev_centroids.keys())[min_distance_idx] if min_distance <= 50 else None
        else:
            matched_id = None

        if matched_id is None:
            matched_id = self.tracking_id
            self.tracking_id += 1

        return matched_id

    def draw_object_info(self, frame, matched_id, x1, y1, x2, y2, 
                        centroid_x, centroid_y, class_name):
        """Menggambar informasi objek pada frame"""
        color = self.monitor.colors.get(class_name, (255, 255, 255))
        
        # Bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        
        # Centroid
        cv2.circle(frame, (centroid_x, centroid_y), 4, color, -1)
        
        # ID dan class
        label = f"ID:{matched_id} {class_name}"
        cv2.putText(frame, label, (x1, y1-10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Trajectory
        points = list(self.tracker.trajectories[matched_id])
        for i in range(1, len(points)):
            cv2.line(frame, points[i-1], points[i], color, 2)

    def check_line_crossings(self, matched_id, centroid_y, class_name, line_positions):
        """Memeriksa crossing pada garis deteksi"""
        if matched_id in self.prev_centroids:
            prev_y = self.prev_centroids[matched_id][1]
            
            # Check up lines
            for i, up_y in enumerate(line_positions['up_lines']):
                direction = f'up{i+1}'
                if prev_y > up_y and centroid_y <= up_y and matched_id not in self.crossed_ids[direction]:
                    self.data_manager.update_count(class_name, direction)
                    self.crossed_ids[direction].add(matched_id)
            
            # Check down lines
            for i, down_y in enumerate(line_positions['down_lines']):
                direction = f'down{i+1}'
                if prev_y < down_y and centroid_y >= down_y and matched_id not in self.crossed_ids[direction]:
                    self.data_manager.update_count(class_name, direction)
                    self.crossed_ids[direction].add(matched_id)

    def draw_detection_lines(self, frame, line_positions):
        """Menggambar garis deteksi"""
        height, width = frame.shape[:2]
        
        # Draw up lines
        for i, y in enumerate(line_positions['up_lines']):
            cv2.line(frame, (0, y), (width, y), (0, 255, 0), 2)
            cv2.putText(frame, f"UP {i+1}", (10, y-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Draw down lines
        for i, y in enumerate(line_positions['down_lines']):
            cv2.line(frame, (0, y), (width, y), (0, 0, 255), 2)
            cv2.putText(frame, f"DOWN {i+1}", (10, y+20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    def process_frame(self, frame):
        """Memproses satu frame video"""
        # Resize frame ke ukuran tetap
        frame = self.video_display.resize_frame(frame)
        
        # Calculate line positions
        height, width = frame.shape[:2]
        line_positions = self.calculate_line_positions(height)
        
        # Process with YOLO
        results = self.model(frame)
        
        # Create overlay for visualization
        overlay = frame.copy()
        
        # Draw detection lines
        self.draw_detection_lines(overlay, line_positions)
        
        # Process detections
        current_centroids = {}
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                class_name = self.model.names[cls]
                
                if conf > 0.3 and class_name in ['car', 'person', 'truck', 'bus', 'bicycle', 'motorcycle']:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    centroid_x = (x1 + x2) // 2
                    centroid_y = (y1 + y2) // 2
                    
                    # Track object
                    matched_id = self.track_object(centroid_x, centroid_y)
                    current_centroids[matched_id] = (centroid_x, centroid_y, class_name)
                    
                    # Update visualization
                    self.tracker.update_trajectory(matched_id, (centroid_x, centroid_y))
                    self.draw_object_info(overlay, matched_id, x1, y1, x2, y2, 
                                       centroid_x, centroid_y, class_name)
                    
                    # Check line crossings
                    self.check_line_crossings(matched_id, centroid_y, class_name, 
                                           line_positions)
        
        # Update tracking info
        self.prev_centroids = current_centroids
        self.tracker.clear_old_trajectories(current_centroids.keys())
        
        # Add overlay with transparency
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Add monitoring stats
        self.monitor.draw_fps_info(frame, self.fps, len(current_centroids))
        frame = self.monitor.draw_current_stats(frame, self.data_manager.current_counts)
        
        # Update performance metrics
        self.frame_count += 1
        
        return frame