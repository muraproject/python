#!/usr/bin/env python3
"""
Comprehensive Pixhawk Telemetry Reader

This script reads and displays multiple telemetry parameters from a Pixhawk
flight controller via MAVLink communication.

Requirements:
- Python 3.7+
- pymavlink library
- pyserial library

Installation:
pip install pymavlink pyserial

Features:
- Establishes MAVLink connection
- Reads multiple telemetry parameters:
  * Acceleration (X, Y, Z)
  * Ground Speed
  * Altitude
  * Heading
  * Battery Status
  * GPS Data
- Provides error handling and connection management
- Supports continuous data reading
"""

import time
import serial
from pymavlink import mavutil

class PixhawkTelemetryReader:
    def __init__(self, 
                 port='COM3', 
                 baud=57600, 
                 connection_timeout=10, 
                 read_interval=0.5):
        """
        Initialize Pixhawk connection parameters.
        
        :param port: Serial port to connect (default: COM3)
        :param baud: Baud rate for serial communication
        :param connection_timeout: Maximum time to attempt connection
        :param read_interval: Time between telemetry data reads
        """
        self.port = port
        self.baud = baud
        self.connection_timeout = connection_timeout
        self.read_interval = read_interval
        
        self.mavlink_connection = None
        self.is_connected = False
        
        # Telemetry data cache
        self.telemetry_data = {
            'acceleration': (0, 0, 0),
            'ground_speed': 0,
            'altitude': 0,
            'heading': 0,
            'battery': {
                'voltage': 0,
                'current': 0,
                'remaining': 0
            },
            'gps': {
                'lat': 0,
                'lon': 0,
                'alt': 0,
                'fix_type': 0,
                'satellites_visible': 0
            }
        }

    def connect(self):
        """
        Establish connection with Pixhawk via MAVLink.
        
        :return: True if connection successful, False otherwise
        """
        try:
            print(f"Attempting to connect to Pixhawk on {self.port} at {self.baud} baud...")
            
            # Create MAVLink connection
            self.mavlink_connection = mavutil.mavlink_connection(
                self.port, 
                baud=self.baud,
                timeout=self.connection_timeout
            )
            
            # Wait for heartbeat from Pixhawk
            print("Waiting for heartbeat...")
            self.mavlink_connection.wait_heartbeat()
            
            self.is_connected = True
            print("Pixhawk connected successfully!")
            return True
        
        except serial.SerialException as serial_err:
            print(f"Serial Connection Error: {serial_err}")
            print("Check:")
            print("1. Correct COM port")
            print("2. Port is not in use by another application")
            print("3. Physical connection")
        
        except mavutil.MAVError as mav_err:
            print(f"MAVLink Connection Error: {mav_err}")
            print("Verify Pixhawk is powered and configured correctly")
        
        except Exception as e:
            print(f"Unexpected connection error: {e}")
        
        self.is_connected = False
        return False

    def read_telemetry(self):
        """
        Read comprehensive telemetry data from Pixhawk.
        
        :return: Dictionary of telemetry data or None if reading fails
        """
        if not self.is_connected:
            print("Not connected to Pixhawk. Attempting to reconnect...")
            self.connect()
            return None
        
        try:
            # Request data streams
            self.mavlink_connection.mav.request_data_stream_send(
                self.mavlink_connection.target_system,
                self.mavlink_connection.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                10,  # 10 Hz
                1    # Start streaming
            )
            
            # Read messages with timeout
            start_time = time.time()
            while time.time() - start_time < 1:  # 1-second window to collect messages
                msg = self.mavlink_connection.recv_msg()
                
                if not msg:
                    time.sleep(0.01)
                    continue
                
                # Process different message types
                if msg.get_type() == 'RAW_IMU':
                    # Acceleration data (convert from millig to m/s²)
                    self.telemetry_data['acceleration'] = (
                        msg.xacc / 1000.0,
                        msg.yacc / 1000.0,
                        msg.zacc / 1000.0
                    )
                
                elif msg.get_type() == 'GPS_RAW_INT':
                    # GPS data
                    self.telemetry_data['gps'] = {
                        'lat': msg.lat / 10000000.0,  # Convert to degrees
                        'lon': msg.lon / 10000000.0,
                        'alt': msg.alt / 1000.0,      # Convert to meters
                        'fix_type': msg.fix_type,
                        'satellites_visible': msg.satellites_visible
                    }
                
                elif msg.get_type() == 'VFR_HUD':
                    # Speed and altitude
                    self.telemetry_data['ground_speed'] = msg.groundspeed
                    self.telemetry_data['altitude'] = msg.alt
                    self.telemetry_data['heading'] = msg.heading
                
                elif msg.get_type() == 'BATTERY_STATUS':
                    # Battery information
                    self.telemetry_data['battery'] = {
                        'voltage': msg.voltages[0] / 1000.0,  # Convert to volts
                        'current': msg.current_battery / 100.0,  # Convert to amps
                        'remaining': msg.battery_remaining
                    }
            
            return self.telemetry_data
        
        except mavutil.MAVError as mav_err:
            print(f"MAVLink Reading Error: {mav_err}")
            self.is_connected = False
        
        except Exception as e:
            print(f"Unexpected reading error: {e}")
            self.is_connected = False
        
        return None

    def print_telemetry(self, telemetry):
        """
        Print formatted telemetry data.
        
        :param telemetry: Dictionary of telemetry data
        """
        if not telemetry:
            print("No telemetry data available.")
            return
        
        print("\n--- Pixhawk Telemetry Data ---")
        
        # Acceleration
        x, y, z = telemetry['acceleration']
        print(f"Acceleration (m/s²): X: {x:.3f}, Y: {y:.3f}, Z: {z:.3f}")
        
        # Speed and Altitude
        print(f"Ground Speed: {telemetry['ground_speed']:.2f} m/s")
        print(f"Altitude: {telemetry['altitude']:.2f} m")
        print(f"Heading: {telemetry['heading']:.2f}°")
        
        # GPS Data
        gps = telemetry['gps']
        print(f"GPS: Lat {gps['lat']:.6f}, Lon {gps['lon']:.6f}, Alt {gps['alt']:.2f} m")
        print(f"GPS Fix Type: {gps['fix_type']}, Satellites: {gps['satellites_visible']}")
        
        # Battery Status
        battery = telemetry['battery']
        print(f"Battery: {battery['voltage']:.2f}V, {battery['current']:.2f}A, {battery['remaining']}% Remaining")

    def continuous_read(self, duration=60):
        """
        Continuously read and print telemetry data.
        
        :param duration: Total reading duration in seconds
        """
        print(f"Starting continuous telemetry data reading for {duration} seconds...")
        start_time = time.time()
        
        while time.time() - start_time < duration:
            telemetry = self.read_telemetry()
            
            if telemetry:
                self.print_telemetry(telemetry)
            
            time.sleep(self.read_interval)
        
        print("Continuous reading completed.")

def main():
    """
    Main function to demonstrate Pixhawk telemetry reading.
    """
    # Create Pixhawk telemetry reader
    pixhawk = PixhawkTelemetryReader(
        port='COM3',         # Adjust as needed
        baud=57600,          # Standard Pixhawk baud rate
        read_interval=0.5    # Read every 0.5 seconds
    )
    
    # Attempt connection
    if pixhawk.connect():
        # Read telemetry data continuously for 1 minute
        pixhawk.continuous_read(duration=60)
    else:
        print("Failed to establish Pixhawk connection.")

if __name__ == "__main__":
    main()