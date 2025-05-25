# enhanced_video_processor.py

import cv2
import numpy as np
from datetime import datetime
import time
import threading
import logging
from collections import deque
from ultralytics import YOLO

# Setup logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import necessary classes directly instead of importing VideoProcessor
# This avoids the import error
class VideoDisplay:
    """
    Class untuk mengelola tampilan video
    """
    def __init__(self, width=1280, height=720):
        self.display_width = width
        self.display_height = height
        logger.info(f"Initialized VideoDisplay with size {width}x{height}")
        
    def resize_frame(self, frame):
        """Resize frame ke ukuran tetap"""
        try:
            return cv2.resize(frame, (self.display_width, self.display_height))
        except Exception as e:
            logger.error(f"Error resizing frame: {e}")
            return frame

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
        logger.info("Monitor initialized with default settings")

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

    def draw_camera_info(self, frame, camera_name, camera_mode):
        """Menampilkan informasi kamera aktif"""
        cv2.putText(frame, f"Camera: {camera_name}", (10, 90),
                   self.font, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"Mode: {camera_mode}", (10, 120),
                   self.font, 0.6, (255, 255, 255), 2)

    def draw_current_stats(self, frame, counts, camera_info=None):
        """Menampilkan statistik lengkap"""
        try:
            height, width = frame.shape[:2]
            stats_frame = self.create_stats_frame(width)
            
            # Draw camera info if available
            if camera_info:
                self.draw_camera_info(stats_frame, 
                                    camera_info.get('name', 'Unknown'),
                                    camera_info.get('mode', 'Unknown'))
            
            y_pos = self.padding + 50  # Adjusted for camera info
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
            
        except Exception as e:
            logger.error(f"Error drawing stats: {e}")
            return frame

class EnhancedStreamReader:
    """
    Improved video stream reading system with error recovery
    """
    def __init__(self, video_source, buffer_size=30, target_fps=30.0, resize_width=None, resize_height=None):
        self.video_source = video_source
        self.buffer_size = buffer_size
        self.target_fps = target_fps
        self.resize_width = resize_width
        self.resize_height = resize_height
        
        # Thread management
        self.thread = None
        self.stopped = False
        self.lock = threading.Lock()
        
        # Frame buffer for dropped frame protection
        self.frame_buffer = deque(maxlen=buffer_size)
        self.current_frame = None
        
        # Performance metrics
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()
        self.last_frame_time = 0
        
        # Connect to video source
        self._initialize_capture()
        
    def _initialize_capture(self):
        """Initialize video capture with appropriate settings"""
        try:
            logger.info(f"Initializing video capture from: {self.video_source}")
            
            # Use FFMPEG backend for better streaming performance
            self.cap = cv2.VideoCapture(self.video_source, cv2.CAP_FFMPEG)
            
            if not self.cap.isOpened():
                raise ValueError(f"Failed to open video source: {self.video_source}")
                
            # Get original properties
            self.original_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.original_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.original_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            # Fix invalid FPS values
            if self.original_fps <= 0 or self.original_fps > 120:
                logger.warning(f"Unusual FPS detected ({self.original_fps}), defaulting to 30 FPS")
                self.original_fps = 30.0
                
            # Set buffer size
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
            
            # Apply specific settings for network streams
            if self._is_network_stream():
                self._configure_network_stream()
                
            # Read first frame
            ret, frame = self.cap.read()
            if not ret:
                raise ValueError("Failed to read initial frame")
                
            # Apply resize if needed
            if self.resize_width and self.resize_height:
                frame = cv2.resize(frame, (self.resize_width, self.resize_height))
                
            # Store frame properties
            self.width = frame.shape[1]
            self.height = frame.shape[0]
            
            # Initialize frame buffer
            with self.lock:
                self.current_frame = frame.copy()
                self.frame_buffer.append(frame.copy())
                
            self.last_frame_time = time.time()
            logger.info(f"Video capture initialized: {self.width}x{self.height} @ {self.original_fps:.1f} FPS")
            
            return True
            
        except Exception as e:
            logger.error(f"Error initializing video capture: {e}")
            return False
            
    def _is_network_stream(self):
        """Check if source is a network stream"""
        if isinstance(self.video_source, str):
            return any(self.video_source.startswith(prefix) 
                      for prefix in ['rtsp://', 'http://', 'https://', 'rtmp://'])
        return False
        
    def _configure_network_stream(self):
        """Apply specific settings for network streams"""
        logger.info("Applying network stream optimizations")
        
        # Use H264 codec for better streaming
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
        
        # Smaller buffer for lower latency
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
    def start(self):
        """Start the reader thread"""
        if self.thread is not None and self.thread.is_alive():
            logger.warning("Reader thread already running")
            return self
            
        self.stopped = False
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()
        logger.info("Reader thread started")
        return self
        
    def _update(self):
        """Background thread to continuously read frames"""
        reconnect_count = 0
        max_reconnects = 5
        consecutive_failures = 0
        max_consecutive_failures = 30
        frame_interval = 1.0 / self.target_fps
        
        while not self.stopped:
            try:
                # Calculate time to wait for target FPS
                current_time = time.time()
                time_since_last = current_time - self.last_frame_time
                
                # If we need to wait to maintain target FPS
                if time_since_last < frame_interval:
                    sleep_time = frame_interval - time_since_last
                    time.sleep(sleep_time * 0.8)  # Sleep slightly less to account for processing
                    continue
                
                # Read frame
                ret, frame = self.cap.read()
                
                if not ret:
                    consecutive_failures += 1
                    logger.warning(f"Failed to read frame ({consecutive_failures}/{max_consecutive_failures})")
                    
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(f"Too many consecutive failures: {consecutive_failures}")
                        
                        # Try to reconnect for network streams
                        if self._is_network_stream() and reconnect_count < max_reconnects:
                            logger.info(f"Attempting reconnection ({reconnect_count+1}/{max_reconnects})")
                            self.cap.release()
                            time.sleep(2)  # Wait before reconnecting
                            
                            # Reinitialize
                            if self._initialize_capture():
                                reconnect_count += 1
                                consecutive_failures = 0
                                logger.info("Reconnection successful")
                            else:
                                logger.error("Reconnection failed")
                                
                        else:
                            # For local files that reach the end
                            if self._is_network_stream():
                                logger.error("Max reconnection attempts reached")
                            else:
                                logger.info("End of local file reached")
                                
                            if self.frame_buffer:
                                # Use last frame from buffer
                                with self.lock:
                                    last_frame = self.frame_buffer[-1].copy()
                                    self.current_frame = last_frame
                            else:
                                logger.error("No frames in buffer")
                                
                    time.sleep(0.1)  # Small delay on failure
                    continue
                    
                # Reset failure counter on successful read
                consecutive_failures = 0
                
                # Apply resize if needed
                if self.resize_width and self.resize_height:
                    frame = cv2.resize(frame, (self.resize_width, self.resize_height))
                
                # Update frame data with thread lock
                with self.lock:
                    self.current_frame = frame.copy()
                    self.frame_buffer.append(frame.copy())
                
                # Update FPS calculation
                self.frame_count += 1
                self.last_frame_time = time.time()
                elapsed = self.last_frame_time - self.start_time
                
                if elapsed >= 1.0:
                    self.fps = self.frame_count / elapsed
                    self.frame_count = 0
                    self.start_time = self.last_frame_time
                    
            except Exception as e:
                logger.error(f"Error in reader thread: {e}")
                time.sleep(0.1)
                
        # Cleanup on thread stop
        if hasattr(self, 'cap') and self.cap is not None:
            self.cap.release()
            logger.info("Released video capture")
            
    def read(self):
        """Read the current frame safely"""
        with self.lock:
            if self.current_frame is None:
                return None
            return self.current_frame.copy()
            
    def get_buffered_frame(self, index=-1):
        """Get a specific frame from buffer (default: latest)"""
        with self.lock:
            if not self.frame_buffer:
                return None
                
            if index < 0:
                return self.frame_buffer[-1].copy()
                
            if index < len(self.frame_buffer):
                return self.frame_buffer[index].copy()
                
            return None
            
    def is_running(self):
        """Check if reader is still active"""
        return self.thread is not None and self.thread.is_alive()
        
    def get_fps(self):
        """Get current actual FPS"""
        return self.fps
        
    def get_dimensions(self):
        """Get frame dimensions"""
        return (self.width, self.height)
        
    def stop(self):
        """Stop reader thread"""
        self.stopped = True
        if self.thread is not None:
            self.thread.join(timeout=1.0)
        if hasattr(self, 'cap') and self.cap is not None:
            self.cap.release()
        logger.info("Stream reader stopped")

class EnhancedVideoProcessor:
    """
    Enhanced video processor with improved streaming and error handling
    """
    def __init__(self, settings_manager, data_manager):
        try:
            self.settings_manager = settings_manager
            self.data_manager = data_manager
            
            # Load YOLO model
            logger.info("Loading YOLO model...")
            self.model = YOLO('yolov8n.pt')
            
            # Get GPU and tracker from settings manager
            self.gpu_processor = settings_manager.gpu_processor
            self.tracker = settings_manager.tracker
            
            # Setup monitoring and display
            self.monitor = Monitor(data_manager)
            self.video_display = VideoDisplay(
                settings_manager.settings['display']['width'],
                settings_manager.settings['display']['height']
            )
            
            # Tracking variables
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
            
            # Error recovery
            self.last_valid_frame = None
            self.recovery_mode = False
            self.recovery_attempts = 0
            self.max_recovery_attempts = 5
            
            # Processing status
            self.running = False
            
            logger.info("Enhanced VideoProcessor initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Enhanced VideoProcessor: {e}")
            raise
            
    def initialize_video_capture(self):
        """Initialize enhanced video capture with better reliability"""
        try:
            video_source = self.settings_manager.settings['video_source']
            if not video_source:
                raise ValueError("No video source configured")
            
            logger.info(f"Initializing enhanced video capture from source: {video_source}")
            
            # Get display settings
            display_width = self.settings_manager.settings['display']['width']
            display_height = self.settings_manager.settings['display']['height']
            
            # Create and start enhanced reader
            reader = EnhancedStreamReader(
                video_source=video_source,
                buffer_size=30,
                target_fps=30.0,
                resize_width=display_width,
                resize_height=display_height
            ).start()
            
            if not reader.is_running():
                raise Exception(f"Failed to start video reader for source: {video_source}")
                
            return reader
            
        except Exception as e:
            logger.error(f"Error initializing enhanced video capture: {e}")
            raise
            
    def calculate_line_positions(self, height):
        """Calculate detection line positions"""
        try:
            settings = self.settings_manager.settings['lines']
            return {
                'up_lines': [int(height * settings[f'up{i}']) for i in range(1, 7)],
                'down_lines': [int(height * settings[f'down{i}']) for i in range(1, 7)]
            }
        except Exception as e:
            logger.error(f"Error calculating line positions: {e}")
            raise
            
    def track_object(self, centroid_x, centroid_y):
        """Track object based on centroid position"""
        try:
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
            
        except Exception as e:
            logger.error(f"Error tracking object: {e}")
            return self.tracking_id + 1
            
    def draw_object_info(self, frame, matched_id, x1, y1, x2, y2, 
                        centroid_x, centroid_y, class_name):
        """Draw object information on frame"""
        try:
            color = self.monitor.colors.get(class_name, (255, 255, 255))
            
            # Bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Centroid
            cv2.circle(frame, (centroid_x, centroid_y), 4, color, -1)
            
            # ID and class
            label = f"ID:{matched_id} {class_name}"
            cv2.putText(frame, label, (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            # Trajectory
            if matched_id in self.tracker.trajectories:
                points = list(self.tracker.trajectories[matched_id])
                for i in range(1, len(points)):
                    cv2.line(frame, points[i-1], points[i], color, 2)
                    
        except Exception as e:
            logger.error(f"Error drawing object info: {e}")
            
    def check_line_crossings(self, matched_id, centroid_y, class_name, line_positions):
        """Check if object crosses detection lines"""
        try:
            if matched_id in self.prev_centroids:
                prev_y = self.prev_centroids[matched_id][1]
                
                # Check up lines
                for i, up_y in enumerate(line_positions['up_lines']):
                    direction = f'up{i+1}'
                    if prev_y > up_y and centroid_y <= up_y and matched_id not in self.crossed_ids[direction]:
                        self.data_manager.update_count(class_name, direction)
                        self.crossed_ids[direction].add(matched_id)
                        logger.debug(f"Object {matched_id} crossed up line {i+1}")
                
                # Check down lines
                for i, down_y in enumerate(line_positions['down_lines']):
                    direction = f'down{i+1}'
                    if prev_y < down_y and centroid_y >= down_y and matched_id not in self.crossed_ids[direction]:
                        self.data_manager.update_count(class_name, direction)
                        self.crossed_ids[direction].add(matched_id)
                        logger.debug(f"Object {matched_id} crossed down line {i+1}")
                        
        except Exception as e:
            logger.error(f"Error checking line crossings: {e}")
            
    def draw_detection_lines(self, frame, line_positions):
        """Draw detection lines on frame"""
        try:
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
                           
        except Exception as e:
            logger.error(f"Error drawing detection lines: {e}")
            
    def process_frame(self, frame):
        """Process a single video frame"""
        try:
            # Store last valid frame for dropout protection
            if frame is not None:
                self.last_valid_frame = frame.copy()
            elif self.last_valid_frame is not None:
                # Use last valid frame if current is None
                logger.warning("Using last valid frame as fallback")
                frame = self.last_valid_frame.copy()
            else:
                logger.error("No valid frame available")
                return np.zeros((480, 640, 3), dtype=np.uint8)  # Return blank frame
            
            # Resize frame to consistent size
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
            self.prev_centroids = {
                id_: (cent[0], cent[1]) for id_, cent in current_centroids.items()
            }
            self.tracker.clear_old_trajectories(current_centroids.keys())
            
            # Add overlay with transparency
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
            
            # Add monitoring stats
            self.monitor.draw_fps_info(frame, self.fps, len(current_centroids))
            
            # Get camera info
            camera_info = {
                'name': self.settings_manager.settings.get('camera_name', 'Unknown'),
                'mode': self.settings_manager.settings.get('camera_mode', 'Unknown')
            }
            
            # Add full stats with camera info
            frame = self.monitor.draw_current_stats(
                frame, 
                self.data_manager.current_counts,
                camera_info
            )
            
            # Update performance metrics
            self.frame_count += 1
            if self.frame_count % 30 == 0:
                current_time = time.time()
                if hasattr(self, 'last_time'):
                    self.fps = 30 / (current_time - self.last_time)
                self.last_time = current_time
            
            return frame
            
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            
            # Return original frame or blank frame on error
            if frame is not None:
                return frame
            elif self.last_valid_frame is not None:
                return self.last_valid_frame
            else:
                return np.zeros((480, 640, 3), dtype=np.uint8)
                
    def process_video_stream(self, reader, frame_callback=None):
        """Process video stream with error handling"""
        self.running = True
        error_count = 0
        max_errors = 30
        
        logger.info("Starting enhanced video processing loop")
        
        try:
            while self.running and reader.is_running():
                try:
                    # Read frame
                    frame = reader.read()
                    
                    if frame is None:
                        error_count += 1
                        logger.warning(f"Failed to read frame ({error_count}/{max_errors})")
                        
                        if error_count >= max_errors:
                            if not self._attempt_recovery(reader):
                                logger.error("Stream recovery failed")
                                break
                            error_count = 0
                            
                        time.sleep(0.1)
                        continue
                        
                    # Reset error count on successful read
                    error_count = 0
                    
                    # Process frame
                    processed_frame = self.process_frame(frame)
                    
                    # Call callback if provided
                    if frame_callback and processed_frame is not None:
                        frame_callback(processed_frame)
                        
                except Exception as e:
                    logger.error(f"Error in processing loop: {e}")
                    time.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Video stream processing error: {e}")
        finally:
            self.running = False
            if reader:
                reader.stop()
            logger.info("Video processing loop ended")
            
    def _attempt_recovery(self, reader):
        """Try to recover from stream failure"""
        if self.recovery_mode or self.recovery_attempts >= self.max_recovery_attempts:
            logger.error(f"Recovery limit reached: {self.recovery_attempts}/{self.max_recovery_attempts}")
            return False
            
        self.recovery_mode = True
        self.recovery_attempts += 1
        
        try:
            logger.info(f"Attempting stream recovery ({self.recovery_attempts}/{self.max_recovery_attempts})")
            
            # Stop current reader
            if reader:
                reader.stop()
                
            # Wait before reconnecting
            time.sleep(3)
            
            # Force refresh settings from API
            if hasattr(self.settings_manager, 'update_video_source'):
                logger.info("Updating video source from API")
                self.settings_manager.update_video_source()
                
            # Initialize new reader
            new_reader = self.initialize_video_capture()
            
            if new_reader and new_reader.is_running():
                logger.info("Stream recovery successful")
                self.recovery_mode = False
                return True
                
            logger.error("Failed to initialize new reader")
            self.recovery_mode = False
            return False
            
        except Exception as e:
            logger.error(f"Recovery attempt failed: {e}")
            self.recovery_mode = False
            return False
            
    def cleanup(self):
        """Cleanup resources"""
        try:
            # Clear any stored data
            self.prev_centroids.clear()
            self.crossed_ids.clear()
            self.tracker.trajectories.clear()
            self.tracker.colors.clear()
            
            # Reset counters
            self.tracking_id = 0
            self.frame_count = 0
            self.fps = 0
            self.recovery_attempts = 0
            self.running = False
            
            logger.info("Enhanced VideoProcessor cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")