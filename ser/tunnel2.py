import asyncio
import websockets
import socket
import json
import tkinter as tk
from tkinter import ttk
import threading
from datetime import datetime

# Konfigurasi
SERVER_IP = "103.130.16.22"
SERVER_WS_PORT = 5001
LOCAL_PORT = 80

class Stats:
    def __init__(self):
        self.bytes_received = 0
        self.bytes_sent = 0
        self.last_request = "-"
        self.connection_status = "Disconnected"
        self.total_requests = 0

class HomeClientGUI:
    def __init__(self):
        self.stats = Stats()
        self.setup_gui()
        
    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Home Tunnel Monitor")
        self.root.geometry("400x300")
        
        # Style
        style = ttk.Style()
        style.configure("Status.TLabel", padding=5)
        
        # Frame utama
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status koneksi
        self.status_label = ttk.Label(
            main_frame, 
            text="Status: Disconnected", 
            style="Status.TLabel"
        )
        self.status_label.grid(row=0, column=0, columnspan=2, sticky=tk.W)
        
        # Statistik
        ttk.Label(main_frame, text="Data Terkirim:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.sent_label = ttk.Label(main_frame, text="0 KB")
        self.sent_label.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(main_frame, text="Data Diterima:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.received_label = ttk.Label(main_frame, text="0 KB")
        self.received_label.grid(row=2, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(main_frame, text="Total Request:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.requests_label = ttk.Label(main_frame, text="0")
        self.requests_label.grid(row=3, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(main_frame, text="Request Terakhir:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.last_request_label = ttk.Label(main_frame, text="-")
        self.last_request_label.grid(row=4, column=1, sticky=tk.W, pady=2)
        
        # Update setiap 1 detik
        self.update_stats()
        
    def update_stats(self):
        # Update labels
        self.status_label.config(text=f"Status: {self.stats.connection_status}")
        self.sent_label.config(text=f"{self.stats.bytes_sent / 1024:.2f} KB")
        self.received_label.config(text=f"{self.stats.bytes_received / 1024:.2f} KB")
        self.requests_label.config(text=str(self.stats.total_requests))
        self.last_request_label.config(text=self.stats.last_request)
        
        # Schedule update berikutnya
        self.root.after(1000, self.update_stats)

    def start(self):
        # Start WebSocket client di thread terpisah
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
            # Update statistik
            self.stats.bytes_received += len(request_data)
            self.stats.total_requests += 1
            self.stats.last_request = datetime.now().strftime("%H:%M:%S")
            
            # Koneksi ke web server lokal
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('127.0.0.1', self.local_port))
            
            # Kirim request
            sock.send(request_data.encode())
            
            # Terima response
            response = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                if b"\r\n\r\n" in response and not (b"Transfer-Encoding: chunked" in response):
                    break
            
            sock.close()
            
            # Update statistik
            self.stats.bytes_sent += len(response)
            
            return response.decode()
            
        except Exception as e:
            error_resp = f"""HTTP/1.1 502 Bad Gateway
Content-Type: text/plain

Error: Cannot connect to local web server on port {self.local_port}
{str(e)}"""
            self.stats.bytes_sent += len(error_resp)
            return error_resp

    async def handle_server_messages(self):
        try:
            while True:
                message = await self.ws.recv()
                data = json.loads(message)
                
                if data['type'] == 'request':
                    response = await self.forward_request(data['data'])
                    await self.ws.send(json.dumps({
                        'type': 'response',
                        'id': data['id'],
                        'data': response
                    }))
                    
                elif data['type'] == 'heartbeat':
                    await self.ws.send(json.dumps({'type': 'heartbeat'}))

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