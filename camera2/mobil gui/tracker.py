import numpy as np
from collections import deque

class ObjectTracker:
    def __init__(self, max_points=30):
        self.trajectories = {}  # Store object trajectories
        self.prev_centroids = {}  # Store previous centroids
        self.current_centroids = {}  # Store current centroids
        self.tracking_id = 0  # Unique ID counter
        self.max_points = max_points  # Maximum trajectory points
        self.colors = {}  # Store colors for each track
        self.crossed_ids = self.init_crossed_ids()  # Store IDs that crossed lines
        self.counts = self.init_counters()  # Initialize counters

    def init_crossed_ids(self):
        """Initialize sets to store IDs that have crossed each line"""
        return {
            'up1': set(), 'up2': set(), 'up3': set(), 'up4': set(), 'up5': set(), 'up6': set(),
            'down1': set(), 'down2': set(), 'down3': set(), 'down4': set(), 'down5': set(), 'down6': set()
        }

    def init_counters(self):
        """Initialize counters for each object type and line"""
        vehicle_types = ['car', 'motorcycle', 'truck', 'bus', 'person']
        counts = {}
        
        for vehicle in vehicle_types:
            counts[vehicle] = {
                'up1': 0, 'up2': 0, 'up3': 0, 'up4': 0, 'up5': 0, 'up6': 0,
                'down1': 0, 'down2': 0, 'down3': 0, 'down4': 0, 'down5': 0, 'down6': 0
            }
        
        return counts

    def get_color(self, track_id):
        """Get or create a unique color for a track ID"""
        if track_id not in self.colors:
            self.colors[track_id] = tuple(np.random.randint(0, 255, 3).tolist())
        return self.colors[track_id]

    def update_trajectory(self, track_id, centroid):
        """Update trajectory for a given track ID"""
        if track_id not in self.trajectories:
            self.trajectories[track_id] = deque(maxlen=self.max_points)
        self.trajectories[track_id].append(centroid)

    def match_detections(self, detections, max_distance=50):
        """Match new detections with existing tracks"""
        matched_tracks = {}
        new_tracks = []
        
        # Convert previous centroids to numpy array for vectorized distance calculation
        if self.prev_centroids:
            prev_points = np.array([[p[0], p[1]] for p in self.prev_centroids.values()])
            prev_ids = list(self.prev_centroids.keys())
            
            for det in detections:
                x, y, class_name = det
                curr_point = np.array([x, y])
                
                # Calculate distances to all previous points
                distances = np.linalg.norm(prev_points - curr_point, axis=1)
                min_distance_idx = np.argmin(distances)
                min_distance = distances[min_distance_idx]
                
                if min_distance <= max_distance:
                    # Match found
                    matched_id = prev_ids[min_distance_idx]
                    matched_tracks[matched_id] = (x, y, class_name)
                else:
                    # New track needed
                    new_tracks.append(det)
        else:
            # All detections are new tracks
            new_tracks = detections
            
        return matched_tracks, new_tracks

    def update(self, detections, line_positions):
        """Update tracker with new detections and check line crossings"""
        # Match detections with existing tracks
        matched_tracks, new_tracks = self.match_detections(detections)
        
        # Update current centroids
        self.current_centroids.clear()
        
        # Process matched tracks
        for track_id, (x, y, class_name) in matched_tracks.items():
            self.current_centroids[track_id] = (x, y, class_name)
            self.update_trajectory(track_id, (x, y))
            
            # Check line crossings if we have previous position
            if track_id in self.prev_centroids:
                prev_y = self.prev_centroids[track_id][1]
                self.check_line_crossings(track_id, prev_y, y, class_name, line_positions)
        
        # Create new tracks
        for x, y, class_name in new_tracks:
            new_id = self.tracking_id
            self.tracking_id += 1
            self.current_centroids[new_id] = (x, y, class_name)
            self.update_trajectory(new_id, (x, y))
        
        # Clean up crossed_ids for tracks that are no longer active
        self.cleanup_crossed_ids()
        
        # Update previous centroids for next frame
        self.prev_centroids = {k: (v[0], v[1]) for k, v in self.current_centroids.items()}
        
        return self.current_centroids

    def check_line_crossings(self, track_id, prev_y, curr_y, class_name, line_positions):
        """Check if object has crossed any counting lines"""
        # Check UP lines
        for i in range(1, 7):
            line_y = line_positions[f'up{i}']
            if prev_y > line_y and curr_y <= line_y and track_id not in self.crossed_ids[f'up{i}']:
                self.counts[class_name][f'up{i}'] += 1
                self.crossed_ids[f'up{i}'].add(track_id)
                
        # Check DOWN lines
        for i in range(1, 7):
            line_y = line_positions[f'down{i}']
            if prev_y < line_y and curr_y >= line_y and track_id not in self.crossed_ids[f'down{i}']:
                self.counts[class_name][f'down{i}'] += 1
                self.crossed_ids[f'down{i}'].add(track_id)

    def cleanup_crossed_ids(self):
        """Remove crossed IDs for tracks that are no longer active"""
        active_tracks = set(self.current_centroids.keys())
        for direction in self.crossed_ids:
            self.crossed_ids[direction] = self.crossed_ids[direction].intersection(active_tracks)

    def get_counts(self):
        """Get current counts"""
        return self.counts.copy()

    def get_trajectory(self, track_id):
        """Get trajectory for a specific track"""
        return list(self.trajectories.get(track_id, []))

    def get_all_trajectories(self):
        """Get all current trajectories"""
        return {k: list(v) for k, v in self.trajectories.items() if k in self.current_centroids}

    def get_max_counts(self):
        """Get maximum counts across all lines for each direction"""
        max_counts = {}
        for vehicle_type in self.counts:
            max_counts[vehicle_type] = {
                'up': max(self.counts[vehicle_type][f'up{i}'] for i in range(1, 7)),
                'down': max(self.counts[vehicle_type][f'down{i}'] for i in range(1, 7))
            }
        return max_counts

    def reset_counts(self):
        """Reset all counters to zero"""
        self.counts = self.init_counters()
        self.crossed_ids = self.init_crossed_ids()