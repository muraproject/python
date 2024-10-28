import csv
import os
import json
from datetime import datetime, timedelta
import pandas as pd

class DataLogger:
    def __init__(self):
        self.csv_file = "counter_mobil.csv"
        self.summary_file = "daily_summary.csv"
        self.last_save_time = datetime.now()
        self.columns = [
            'timestamp',
            'car_up', 'car_down',
            'bus_up', 'bus_down',
            'truck_up', 'truck_down',
            'person_bike_up', 'person_bike_down'
        ]
        self.ensure_files_exist()
        
    def ensure_files_exist(self):
        """Create necessary files with headers if they don't exist"""
        # Main counting data file
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(self.columns)
        
        # Daily summary file
        if not os.path.exists(self.summary_file):
            with open(self.summary_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['date'] + self.columns[1:])  # Skip timestamp column

    def process_counts(self, counts):
        """Process raw counts to get maximum values for each category"""
        max_counts = {
            'car': {'up': 0, 'down': 0},
            'bus': {'up': 0, 'down': 0},
            'truck': {'up': 0, 'down': 0},
            'person_bike': {'up': 0, 'down': 0}
        }

        # Get maximum counts for vehicles
        for vehicle in ['car', 'bus', 'truck']:
            up_counts = [counts[vehicle][f'up{i}'] for i in range(1, 7)]
            down_counts = [counts[vehicle][f'down{i}'] for i in range(1, 7)]
            max_counts[vehicle]['up'] = max(up_counts)
            max_counts[vehicle]['down'] = max(down_counts)

        # Compare and get maximum between person and motorcycle
        person_up_max = max(counts['person'][f'up{i}'] for i in range(1, 7))
        motor_up_max = max(counts['motorcycle'][f'up{i}'] for i in range(1, 7))
        person_down_max = max(counts['person'][f'down{i}'] for i in range(1, 7))
        motor_down_max = max(counts['motorcycle'][f'down{i}'] for i in range(1, 7))

        max_counts['person_bike']['up'] = max(person_up_max, motor_up_max)
        max_counts['person_bike']['down'] = max(person_down_max, motor_down_max)

        return max_counts

    def save_interval_data(self, counts, interval_minutes):
        """Save data if interval has passed"""
        current_time = datetime.now()
        if (current_time - self.last_save_time).total_seconds() >= interval_minutes * 60:
            self.save_counts(counts)
            self.update_daily_summary(current_time.date())
            self.last_save_time = current_time
            return True
        return False

    def save_counts(self, counts):
        """Save counting data to CSV file"""
        max_counts = self.process_counts(counts)
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

        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)

        return row

    def update_daily_summary(self, date):
        """Update daily summary from main CSV data"""
        try:
            df = pd.read_csv(self.csv_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['date'] = df['timestamp'].dt.date
            
            # Filter for specific date and aggregate
            daily_data = df[df['date'] == date].sum().drop(['timestamp', 'date'])
            
            # Save to summary file
            summary_df = pd.read_csv(self.summary_file) if os.path.exists(self.summary_file) else pd.DataFrame()
            
            new_row = {'date': date.strftime("%Y-%m-%d")}
            new_row.update(daily_data.to_dict())
            
            if date.strftime("%Y-%m-%d") in summary_df['date'].values:
                summary_df.loc[summary_df['date'] == date.strftime("%Y-%m-%d")] = pd.Series(new_row)
            else:
                summary_df = pd.concat([summary_df, pd.DataFrame([new_row])], ignore_index=True)
            
            summary_df.to_csv(self.summary_file, index=False)
            
        except Exception as e:
            print(f"Error updating daily summary: {e}")

    def get_latest_counts(self, n=10):
        """Get the latest n counting records"""
        try:
            df = pd.read_csv(self.csv_file)
            return df.tail(n).values.tolist()
        except Exception:
            return []

    def get_daily_summary(self, date=None):
        """Get summary for a specific date or today"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
            
        try:
            df = pd.read_csv(self.summary_file)
            day_data = df[df['date'] == date]
            if not day_data.empty:
                return day_data.iloc[0].to_dict()
            return None
        except Exception:
            return None

    def get_period_summary(self, start_date, end_date):
        """Get summary for a specific period"""
        try:
            df = pd.read_csv(self.summary_file)
            df['date'] = pd.to_datetime(df['date'])
            mask = (df['date'] >= start_date) & (df['date'] <= end_date)
            period_data = df.loc[mask]
            
            summary = {
                'total': period_data.drop('date', axis=1).sum().to_dict(),
                'daily_average': period_data.drop('date', axis=1).mean().to_dict(),
                'max_day': period_data.drop('date', axis=1).max().to_dict(),
                'min_day': period_data.drop('date', axis=1).min().to_dict()
            }
            
            return summary
        except Exception as e:
            print(f"Error getting period summary: {e}")
            return None

    def export_data(self, start_date=None, end_date=None, format='csv'):
        """Export data for a specific period in various formats"""
        try:
            df = pd.read_csv(self.csv_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            if start_date:
                df = df[df['timestamp'].dt.date >= start_date]
            if end_date:
                df = df[df['timestamp'].dt.date <= end_date]
            
            filename = f"traffic_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if format == 'csv':
                export_file = f"{filename}.csv"
                df.to_csv(export_file, index=False)
            elif format == 'excel':
                export_file = f"{filename}.xlsx"
                df.to_excel(export_file, index=False)
            elif format == 'json':
                export_file = f"{filename}.json"
                df.to_json(export_file, orient='records', date_format='iso')
                
            return export_file
            
        except Exception as e:
            print(f"Error exporting data: {e}")
            return None

    def cleanup_old_data(self, days_to_keep=30):
        """Remove data older than specified days"""
        try:
            df = pd.read_csv(self.csv_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Filter and save recent data
            df_recent = df[df['timestamp'] >= cutoff_date]
            df_recent.to_csv(self.csv_file, index=False)
            
            # Update daily summary
            summary_df = pd.read_csv(self.summary_file)
            summary_df['date'] = pd.to_datetime(summary_df['date'])
            summary_df_recent = summary_df[summary_df['date'] >= cutoff_date]
            summary_df_recent.to_csv(self.summary_file, index=False)
            
            return True
        except Exception as e:
            print(f"Error cleaning up old data: {e}")
            return False

    def get_statistics(self, period='today'):
        """Get various statistics for different time periods"""
        try:
            df = pd.read_csv(self.csv_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            if period == 'today':
                today = datetime.now().date()
                df = df[df['timestamp'].dt.date == today]
            elif period == 'week':
                week_ago = datetime.now() - timedelta(days=7)
                df = df[df['timestamp'] >= week_ago]
            elif period == 'month':
                month_ago = datetime.now() - timedelta(days=30)
                df = df[df['timestamp'] >= month_ago]
            
            # Calculate statistics
            stats = {
                'total_vehicles': {
                    'up': df[['car_up', 'bus_up', 'truck_up']].sum().sum(),
                    'down': df[['car_down', 'bus_down', 'truck_down']].sum().sum()
                },
                'by_type': {
                    'car': {'up': df['car_up'].sum(), 'down': df['car_down'].sum()},
                    'bus': {'up': df['bus_up'].sum(), 'down': df['bus_down'].sum()},
                    'truck': {'up': df['truck_up'].sum(), 'down': df['truck_down'].sum()},
                    'person_bike': {'up': df['person_bike_up'].sum(), 'down': df['person_bike_down'].sum()}
                },
                'hourly_average': df.groupby(df['timestamp'].dt.hour).mean().to_dict(),
                'peak_hour': df.groupby(df['timestamp'].dt.hour).sum().sum(axis=1).idxmax()
            }
            
            return stats
        except Exception as e:
            print(f"Error calculating statistics: {e}")
            return None