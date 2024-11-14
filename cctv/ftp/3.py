import socket
import threading
import logging
import json
import time
import struct
import binascii
import sys
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Constants for commands
COMMAND_MAPPING = {
    0x0001: "HANDSHAKE",
    0x0002: "HEARTBEAT",
    0x0003: "LOGIN",
    0x0004: "STREAM_START", 
    0x0005: "STREAM_STOP",
    0x0006: "PTZ_CONTROL",
    0x0007: "GET_PARAMS",
    0x0008: "SET_PARAMS",
    0x0009: "DISCONNECT",
    0x000A: "STATUS",
    0x000B: "ERROR"
}

class Logger:
    @staticmethod
    def setup():
        log_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        # File handler with rotation
        file_handler = RotatingFileHandler(
            filename=f'logs/camera_server_{datetime.now().strftime("%Y%m%d")}.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(log_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        
        # Root logger setup
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        return root_logger

class ProtocolException(Exception):
    pass

class UVV2Protocol:
    HEADER_SIZE = 8
    MAGIC_NUMBERS = [0xAA55, 0xAA77]  # Support multiple magic numbers
    VERSION = 0x01
    
    @staticmethod
    def debug_hex(data, max_length=32):
        hex_str = binascii.hexlify(data[:max_length]).decode('utf-8')
        return ' '.join(hex_str[i:i+2] for i in range(0, len(hex_str), 2))
        
    @staticmethod
    def validate_magic(magic):
        return magic in UVV2Protocol.MAGIC_NUMBERS
        
    @staticmethod
    def parse_message(data, logger):
        try:
            if len(data) < UVV2Protocol.HEADER_SIZE:
                raise ProtocolException(f"Message too short: {len(data)} bytes")
                
            magic, length, cmd, version = struct.unpack('<HHHH', data[:UVV2Protocol.HEADER_SIZE])
            logger.debug(f"Parsed header - Magic: 0x{magic:04X}, Length: {length}, Command: 0x{cmd:04X} ({COMMAND_MAPPING.get(cmd, 'UNKNOWN')})")
            
            if not UVV2Protocol.validate_magic(magic):
                raise ProtocolException(f"Invalid magic number: 0x{magic:04X}")
                
            if length < UVV2Protocol.HEADER_SIZE:
                raise ProtocolException(f"Invalid length: {length}")
                
            return magic, length, cmd, version, data[UVV2Protocol.HEADER_SIZE:length]
            
        except struct.error as e:
            raise ProtocolException(f"Failed to parse message: {str(e)}")
            
    @staticmethod
    def create_message(cmd, payload=b'', magic=0xAA55):
        try:
            total_length = UVV2Protocol.HEADER_SIZE + len(payload)
            header = struct.pack('<HHHH', magic, total_length, cmd, UVV2Protocol.VERSION)
            return header + payload
        except struct.error as e:
            raise ProtocolException(f"Failed to create message: {str(e)}")

class CameraDevice:
    def __init__(self, device_id, camera_id):
        self.device_id = device_id
        self.camera_id = camera_id
        self.logger = logging.getLogger(f'Camera_{device_id}')
        self.status = "READY"
        self.streaming = False
        self.ptz = {"pan": 0, "tilt": 0, "zoom": 1}
        self.settings = {
            "resolution": "1920x1080",
            "framerate": 30,
            "bitrate": 4000000,
            "quality": "high"
        }
        
    def handle_ptz(self, command_data):
        try:
            params = json.loads(command_data.decode())
            self.logger.info(f"PTZ control: {params}")
            self.ptz.update(params)
            return json.dumps({"status": "success", "ptz": self.ptz}).encode()
        except Exception as e:
            raise ProtocolException(f"PTZ control failed: {str(e)}")
            
    def get_status(self):
        return json.dumps({
            "device_id": self.device_id,
            "camera_id": self.camera_id,
            "status": self.status,
            "streaming": self.streaming,
            "ptz": self.ptz,
            "settings": self.settings
        }).encode()

class ClientHandler:
    def __init__(self, socket, address, camera):
        self.socket = socket
        self.address = address
        self.camera = camera
        self.authenticated = False
        self.running = True
        self.buffer = bytearray()
        self.last_heartbeat = time.time()
        self.current_magic = 0xAA55  # Default magic number
        self.logger = logging.getLogger(f'Client_{address[0]}:{address[1]}')
        
    def handle(self):
        self.logger.info(f"New connection established")
        self.socket.settimeout(1.0)
        
        while self.running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break
                    
                self.buffer.extend(data)
                self.process_buffer()
                
            except socket.timeout:
                self.check_heartbeat()
            except Exception as e:
                self.logger.error(f"Connection error: {str(e)}")
                break
                
        self.cleanup()
        
    def process_buffer(self):
        while len(self.buffer) >= UVV2Protocol.HEADER_SIZE:
            try:
                magic, length, cmd, version, payload = UVV2Protocol.parse_message(self.buffer, self.logger)
                
                if len(self.buffer) < length:
                    break
                    
                self.current_magic = magic  # Remember client's magic number
                self.handle_command(cmd, payload)
                self.buffer = self.buffer[length:]
                
            except ProtocolException as e:
                self.logger.error(f"Protocol error: {str(e)}")
                self.recover_buffer()
                
    def recover_buffer(self):
        """Try to recover from protocol errors by finding next valid magic number"""
        for i in range(1, len(self.buffer)-1):
            for magic in UVV2Protocol.MAGIC_NUMBERS:
                if self.buffer[i:i+2] == struct.pack('<H', magic):
                    self.logger.info(f"Recovered at position {i} with magic 0x{magic:04X}")
                    self.buffer = self.buffer[i:]
                    return
        self.buffer.clear()
        
    def handle_command(self, cmd, payload):
        try:
            if cmd == 0x0001:  # HANDSHAKE
                response = {
                    "status": "ok",
                    "timestamp": int(time.time()),
                    "version": UVV2Protocol.VERSION
                }
                
            elif cmd == 0x0002:  # HEARTBEAT
                self.last_heartbeat = time.time()
                response = {"status": "ok"}
                
            elif cmd == 0x0003:  # LOGIN
                if not self.authenticated:
                    # Here you would validate credentials
                    self.authenticated = True
                    response = {"status": "authenticated"}
                else:
                    response = {"status": "already_authenticated"}
                    
            elif not self.authenticated:
                response = {"status": "error", "message": "Not authenticated"}
                
            elif cmd == 0x0004:  # STREAM_START
                self.camera.streaming = True
                response = {"status": "streaming"}
                
            elif cmd == 0x0005:  # STREAM_STOP
                self.camera.streaming = False
                response = {"status": "stopped"}
                
            elif cmd == 0x0006:  # PTZ_CONTROL
                result = self.camera.handle_ptz(payload)
                response = json.loads(result.decode())
                
            elif cmd == 0x0007:  # GET_PARAMS
                response = self.camera.settings
                
            elif cmd == 0x0008:  # SET_PARAMS
                new_settings = json.loads(payload.decode())
                self.camera.settings.update(new_settings)
                response = {"status": "ok", "settings": self.camera.settings}
                
            elif cmd == 0x0009:  # DISCONNECT
                self.running = False
                response = {"status": "disconnecting"}
                
            elif cmd == 0x000A:  # STATUS
                response = json.loads(self.camera.get_status().decode())
                
            else:
                response = {"status": "error", "message": f"Unknown command: 0x{cmd:04X}"}
                
            # Send response
            response_payload = json.dumps(response).encode()
            response_message = UVV2Protocol.create_message(cmd, response_payload, self.current_magic)
            self.socket.send(response_message)
            
        except Exception as e:
            self.logger.error(f"Command handling error: {str(e)}")
            error_response = json.dumps({"status": "error", "message": str(e)}).encode()
            error_message = UVV2Protocol.create_message(0x000B, error_response, self.current_magic)
            self.socket.send(error_message)
            
    def check_heartbeat(self):
        if time.time() - self.last_heartbeat > 30:
            self.logger.warning("Heartbeat timeout")
            self.running = False
            
    def cleanup(self):
        try:
            self.socket.close()
        except:
            pass
        self.logger.info("Connection closed")

class CameraServer:
    def __init__(self, host, port=5196):
        self.host = host
        self.port = port
        self.running = False
        self.server_socket = None
        self.clients = []
        self.camera = CameraDevice("EZIPC0", "ZP4BV-BP")
        self.logger = logging.getLogger('CameraServer')
        
    def start(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1)
            
            self.running = True
            self.logger.info(f"Server started on {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    self.handle_new_client(client_socket, address)
                except socket.timeout:
                    continue
                except Exception as e:
                    self.logger.error(f"Accept error: {str(e)}")
                    
        except Exception as e:
            self.logger.error(f"Server error: {str(e)}")
        finally:
            self.cleanup()
            
    def handle_new_client(self, client_socket, address):
        client = ClientHandler(client_socket, address, self.camera)
        self.clients.append(client)
        
        client_thread = threading.Thread(target=client.handle)
        client_thread.daemon = True
        client_thread.start()
        
    def stop(self):
        self.running = False
        
    def cleanup(self):
        self.running = False
        
        for client in self.clients[:]:
            try:
                client.running = False
            except:
                pass
            
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
                
        self.logger.info("Server stopped")

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        return None

def main():
    # Setup logging
    logger = Logger.setup()
    
    # Get local IP
    host_ip = get_local_ip()
    if not host_ip:
        logger.error("Failed to get local IP address")
        return
        
    logger.info(f"Starting server on {host_ip}:5196")
    
    # Create and start server
    server = CameraServer(host_ip)
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    finally:
        server.stop()

if __name__ == "__main__":
    main()