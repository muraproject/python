import asyncio
import websockets
import socket
import json
import tkinter as tk
from tkinter import ttk
import threading
from datetime import datetime
import time

# Konfigurasi
SERVER_IP = "103.130.16.22"
SERVER_WS_PORT = 5001
LOCAL_PORT = 80

class Stats:
    def __init__(self):
        # HTTP Stats
        self.http_bytes_received = 0
        self.http_bytes_sent = 0
        self.total_http_requests = 0
        self.last_http_request = "-"
        
        # WebSocket Stats
        self.ws_bytes_received = 0
        self.ws_bytes_sent = 0
        self.total_ws_messages = 0
        self.last_ws_message = "-"
        
        # Speed Stats
        self.last_update_time = time.time()
        self.speed_up = 0  # bytes per second
        self.speed_down = 0  # bytes per second
        self.prev_total_sent = 0
        self.prev_total_received = 0
        
        # Connection Status
        self.connection_status = "Disconnected"

    def update_speeds(self):
        current_time = time.time()
        time_diff = current_time - self.last_update_time
        
        if time_diff > 0:
            total_sent = self.http_bytes_sent + self.ws_bytes_sent
            total_received = self.http_bytes_received + self.ws_bytes_received
            
            self.speed_up = (total_sent - self.prev_total_sent) / time_diff
            self.speed_down = (total_received - self.prev_total_received) / time_diff
            
            self.prev_total_sent = total_sent
            self.prev_total_received = total_received
            self.last_update_time = current_time

class HomeClientGUI:
    def __init__(self):
        self.stats = Stats()
        self.setup_gui()
        
    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Home Tunnel Monitor")
        self.root.geometry("500x400")
        
        # Style
        style = ttk.Style()
        style.configure("Header.TLabel", font=('Helvetica', 10, 'bold'))
        style.configure("Status.TLabel", padding=5)
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status koneksi
        self.status_label = ttk.Label(
            main_frame, 
            text="Status: Disconnected", 
            style="Status.TLabel"
        )
        self.status_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0,10))
        
        # HTTP Statistics
        ttk.Label(main_frame, text="HTTP Traffic", style="Header.TLabel").grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=(10,5))
            
        ttk.Label(main_frame, text="Data Terkirim:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.http_sent_label = ttk.Label(main_frame, text="0 KB")
        self.http_sent_label.grid(row=2, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(main_frame, text="Data Diterima:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.http_received_label = ttk.Label(main_frame, text="0 KB")
        self.http_received_label.grid(row=3, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(main_frame, text="Total Request:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.http_requests_label = ttk.Label(main_frame, text="0")
        self.http_requests_label.grid(row=4, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(main_frame, text="Request Terakhir:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.http_last_request_label = ttk.Label(main_frame, text="-")
        self.http_last_request_label.grid(row=5, column=1, sticky=tk.W, pady=2)
        
        # WebSocket Statistics
        ttk.Label(main_frame, text="WebSocket Traffic", style="Header.TLabel").grid(
            row=6, column=0, columnspan=2, sticky=tk.W, pady=(10,5))
            
        ttk.Label(main_frame, text="Data Terkirim:").grid(row=7, column=0, sticky=tk.W, pady=2)
        self.ws_sent_label = ttk.Label(main_frame, text="0 KB")
        self.ws_sent_label.grid(row=7, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(main_frame, text="Data Diterima:").grid(row=8, column=0, sticky=tk.W, pady=2)
        self.ws_received_label = ttk.Label(main_frame, text="0 KB")
        self.ws_received_label.grid(row=8, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(main_frame, text="Total Messages:").grid(row=9, column=0, sticky=tk.W, pady=2)
        self.ws_messages_label = ttk.Label(main_frame, text="0")
        self.ws_messages_label.grid(row=9, column=1, sticky=tk.W, pady=2)
        
        # Speed Statistics
        ttk.Label(main_frame, text="Network Speed", style="Header.TLabel").grid(
            row=10, column=0, columnspan=2, sticky=tk.W, pady=(10,5))
            
        ttk.Label(main_frame, text="Upload:").grid(row=11, column=0, sticky=tk.W, pady=2)
        self.speed_up_label = ttk.Label(main_frame, text="0 KB/s")
        self.speed_up_label.grid(row=11, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(main_frame, text="Download:").grid(row=12, column=0, sticky=tk.W, pady=2)
        self.speed_down_label = ttk.Label(main_frame, text="0 KB/s")
        self.speed_down_label.grid(row=12, column=1, sticky=tk.W, pady=2)
        
        # Update setiap 1 detik
        self.update_stats()
        
    def format_bytes(self, bytes_value):
        if bytes_value < 1024:
            return f"{bytes_value:.0f} B"
        elif bytes_value < 1024*1024:
            return f"{bytes_value/1024:.2f} KB"
        else:
            return f"{bytes_value/(1024*1024):.2f} MB"
            
    def format_speed(self, bytes_per_sec):
        if bytes_per_sec < 1024:
            return f"{bytes_per_sec:.0f} B/s"
        elif bytes_per_sec < 1024*1024:
            return f"{bytes_per_sec/1024:.2f} KB/s"
        else:
            return f"{bytes_per_sec/(1024*1024):.2f} MB/s"
        
    def update_stats(self):
        # Update speeds
        self.stats.update_speeds()
        
        # Update labels
        self.status_label.config(text=f"Status: {self.stats.connection_status}")
        
        # HTTP Stats
        self.http_sent_label.config(text=self.format_bytes(self.stats.http_bytes_sent))
        self.http_received_label.config(text=self.format_bytes(self.stats.http_bytes_received))
        self.http_requests_label.config(text=str(self.stats.total_http_requests))
        self.http_last_request_label.config(text=self.stats.last_http_request)
        
        # WebSocket Stats
        self.ws_sent_label.config(text=self.format_bytes(self.stats.ws_bytes_sent))
        self.ws_received_label.config(text=self.format_bytes(self.stats.ws_bytes_received))
        self.ws_messages_label.config(text=str(self.stats.total_ws_messages))
        
        # Speed Stats
        self.speed_up_label.config(text=self.format_speed(self.stats.speed_up))
        self.speed_down_label.config(text=self.format_speed(self.stats.speed_down))
        
        # Schedule next update
        self.root.after(1000, self.update_stats)

    def start(self):
        # Start WebSocket client in separate thread
        client = HomeClient(self.stats)
        ws_thread = threading.Thread(target=lambda: asyncio.run(client.start()))
        ws_thread.daemon = True
        ws_thread.start()
        
        # Start GUI
        self.root.mainloop()

class HomeClient:
    def __init__(self, stats):
        self.stats = stats
        self.ws = None
        self.reconnect = True
        self.local_port = LOCAL_PORT
        self.ws_url = f"ws://{SERVER_IP}:{SERVER_WS_PORT}"

    async def forward_request(self, request_data):
        try:
            # Update HTTP stats
            request_size = len(request_data)
            self.stats.http_bytes_received += request_size
            self.stats.total_http_requests += 1
            self.stats.last_http_request = datetime.now().strftime("%H:%M:%S")
            
            # Connect to local web server
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('127.0.0.1', self.local_port))
            
            # Send request
            sock.send(request_data.encode())
            
            # Receive response
            response = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                if b"\r\n\r\n" in response and not (b"Transfer-Encoding: chunked" in response):
                    break
            
            sock.close()
            
            # Update HTTP stats
            response_size = len(response)
            self.stats.http_bytes_sent += response_size
            
            return response.decode()
            
        except Exception as e:
            error_resp = f"""HTTP/1.1 502 Bad Gateway
Content-Type: text/plain

Error: Cannot connect to local web server on port {self.local_port}
{str(e)}"""
            self.stats.http_bytes_sent += len(error_resp)
            return error_resp

    async def handle_server_messages(self):
        try:
            while True:
                message = await self.ws.recv()
                msg_size = len(message)
                self.stats.ws_bytes_received += msg_size
                self.stats.total_ws_messages += 1
                
                data = json.loads(message)
                
                if data['type'] == 'request':
                    response = await self.forward_request(data['data'])
                    response_data = json.dumps({
                        'type': 'response',
                        'id': data['id'],
                        'data': response
                    })
                    await self.ws.send(response_data)
                    self.stats.ws_bytes_sent += len(response_data)
                    
                elif data['type'] == 'heartbeat':
                    response_data = json.dumps({'type': 'heartbeat'})
                    await self.ws.send(response_data)
                    self.stats.ws_bytes_sent += len(response_data)

        except websockets.exceptions.ConnectionClosed:
            self.stats.connection_status = "Disconnected"
        except Exception as e:
            print(f"Error: {e}")
            self.stats.connection_status = f"Error: {str(e)}"

    async def connect(self):
        while self.reconnect:
            try:
                self.stats.connection_status = "Connecting..."
                
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=30,
                    ping_timeout=10
                ) as websocket:
                    self.ws = websocket
                    self.stats.connection_status = "Connected"
                    
                    await self.handle_server_messages()
                    
            except (websockets.exceptions.ConnectionClosed, 
                    websockets.exceptions.InvalidStatusCode,
                    ConnectionRefusedError) as e:
                self.stats.connection_status = "Reconnecting..."
                await asyncio.sleep(5)
                continue
                
            except Exception as e:
                self.stats.connection_status = f"Error: {str(e)}"
                await asyncio.sleep(5)
                continue

    async def start(self):
        await self.connect()

if __name__ == "__main__":
    gui = HomeClientGUI()
    gui.start()