import json
import csv
from datetime import datetime
import os

class Settings:
    def __init__(self):
        self.settings_file = "settings_mobil.json"
        self.csv_file = "counter_mobil.csv"
        self.default_settings = {
            'lines': {
                'up1': 100,
                'up2': 150,
                'up3': 200,
                'up4': 250,
                'up5': 300,
                'up6': 350,
                'down1': 120,
                'down2': 170,
                'down3': 220,
                'down4': 270,
                'down5': 320,
                'down6': 370
            },
            'interval': 5,  # minutes
            'video_source': 'https://cctvjss.jogjakota.go.id/kotabaru/ANPR-Jl-Ahmad-Jazuli.stream/playlist.m3u8',
            'detection_threshold': 0.3,
            'max_trajectory_points': 30
        }
        self.settings = self.load_settings()

    def load_settings(self):
        """Load settings from JSON file or create with defaults"""
        try:
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
                # Update with any missing default settings
                for key, value in self.default_settings.items():
                    if key not in settings:
                        settings[key] = value
                return settings
        except FileNotFoundError:
            self.save_settings(self.default_settings)
            return self.default_settings

    def save_settings(self, settings=None):
        """Save settings to JSON file"""
        if settings is not None:
            self.settings = settings
        with open(self.settings_file, 'w') as f:
            json.dump(self.settings, f, indent=4)

    def get_line_positions(self):
        """Get all line positions"""
        return self.settings['lines']

    def set_line_positions(self, positions):
        """Update line positions"""
        self.settings['lines'] = positions
        self.save_settings()

    def get_interval(self):
        """Get saving interval in minutes"""
        return self.settings['interval']

    def set_interval(self, minutes):
        """Set saving interval"""
        self.settings['interval'] = minutes
        self.save_settings()

    def get_video_source(self):
        """Get video source URL"""
        return self.settings['video_source']

    def get_detection_settings(self):
        """Get detection related settings"""
        return {
            'threshold': self.settings['detection_threshold'],
            'max_trajectory_points': self.settings['max_trajectory_points']
        }

class DataLogger:
    def __init__(self, csv_file="counter_mobil.csv"):
        self.csv_file = csv_file
        self.columns = [
            'timestamp',
            'car_up', 'car_down',
            'bus_up', 'bus_down',
            'truck_up', 'truck_down',
            'person_bike_up', 'person_bike_down'
        ]
        self.ensure_csv_exists()

    def ensure_csv_exists(self):
        """Create CSV file with headers if it doesn't exist"""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(self.columns)

    def save_counts(self, counts):
        """Save counting data to CSV file"""
        # Process the counts to get maximum values
        max_counts = self.process_counts(counts)
        
        # Prepare row data
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [
            timestamp,
            max_counts['car']['up'],
            max_counts['car']['down'],
            max_counts['bus']['up'],
            max_counts['bus']['down'],
            max_counts['truck']['up'],
            max_counts['truck']['down'],
            max_counts['person_bike']['up'],
            max_counts['person_bike']['down']
        ]

        # Append to CSV
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def process_counts(self, counts):
        """Process raw counts to get maximum values for each category"""
        max_counts = {
            'car': {'up': 0, 'down': 0},
            'bus': {'up': 0, 'down': 0},
            'truck': {'up': 0, 'down': 0},
            'person_bike': {'up': 0, 'down': 0}
        }

        # Get max counts for vehicles
        for vehicle in ['car', 'bus', 'truck']:
            up_counts = [counts[vehicle][f'up{i}'] for i in range(1, 7)]
            down_counts = [counts[vehicle][f'down{i}'] for i in range(1, 7)]
            max_counts[vehicle]['up'] = max(up_counts)
            max_counts[vehicle]['down'] = max(down_counts)

        # Compare person and motorcycle counts
        person_up = max(counts['person'][f'up{i}'] for i in range(1, 7))
        motor_up = max(counts['motorcycle'][f'up{i}'] for i in range(1, 7))
        person_down = max(counts['person'][f'down{i}'] for i in range(1, 7))
        motor_down = max(counts['motorcycle'][f'down{i}'] for i in range(1, 7))

        max_counts['person_bike']['up'] = max(person_up, motor_up)
        max_counts['person_bike']['down'] = max(person_down, motor_down)

        return max_counts

    def read_latest_counts(self, n=10):
        """Read the latest n entries from the CSV file"""
        try:
            with open(self.csv_file, 'r') as f:
                reader = list(csv.reader(f))
                if len(reader) <= 1:  # Only header or empty
                    return []
                # Get last n rows (excluding header)
                return reader[-n:] if len(reader) > n else reader[1:]
        except FileNotFoundError:
            return []

    def get_daily_summary(self, date=None):
        """Get summary of counts for a specific date"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        daily_counts = {
            'car': {'up': 0, 'down': 0},
            'bus': {'up': 0, 'down': 0},
            'truck': {'up': 0, 'down': 0},
            'person_bike': {'up': 0, 'down': 0}
        }

        try:
            with open(self.csv_file, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    if row[0].startswith(date):
                        # Add counts from each row
                        daily_counts['car']['up'] += int(row[1])
                        daily_counts['car']['down'] += int(row[2])
                        daily_counts['bus']['up'] += int(row[3])
                        daily_counts['bus']['down'] += int(row[4])
                        daily_counts['truck']['up'] += int(row[5])
                        daily_counts['truck']['down'] += int(row[6])
                        daily_counts['person_bike']['up'] += int(row[7])
                        daily_counts['person_bike']['down'] += int(row[8])

        except FileNotFoundError:
            pass

        return daily_counts

def get_settings_handler():
    """Factory function to create Settings instance"""
    return Settings()

def get_data_logger():
    """Factory function to create DataLogger instance"""
    return DataLogger()