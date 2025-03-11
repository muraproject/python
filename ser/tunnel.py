import asyncio
import websockets
import socket
import json
import time
from concurrent.futures import ThreadPoolExecutor

# Konfigurasi
SERVER_IP = "103.130.16.22"  # IP server Anda
SERVER_WS_PORT = 5001        # Port WebSocket server
LOCAL_PORT = 80             # Port web server lokal
MAX_CONNECTIONS = 5         # Jumlah maksimal koneksi paralel

class HomeClient:
    def __init__(self):
        self.ws_connections = []
        self.reconnect = True
        self.local_port = LOCAL_PORT
        self.ws_url = f"ws://{SERVER_IP}:{SERVER_WS_PORT}"
        self.executor = ThreadPoolExecutor(max_workers=10)

    def receive_full_response(self, sock):
        response = b""
        content_length = None
        chunked = False
        header_end = False
        
        while True:
            chunk = sock.recv(8192)
            if not chunk:
                break
            
            response += chunk
            
            if not header_end and b"\r\n\r\n" in response:
                header_end = True
                headers = response.split(b"\r\n\r\n")[0].decode('utf-8', 'ignore')
                
                # Check content length
                for line in headers.split('\r\n'):
                    if line.lower().startswith('content-length:'):
                        content_length = int(line.split(':')[1].strip())
                    elif line.lower().startswith('transfer-encoding:') and 'chunked' in line.lower():
                        chunked = True
            
            if header_end:
                if content_length is not None:
                    if len(response) >= response.find(b"\r\n\r\n") + 4 + content_length:
                        break
                elif chunked:
                    if response.endswith(b"0\r\n\r\n"):
                        break
                elif response.endswith(b"\r\n0\r\n\r\n"):
                    break
        
        return response

    async def forward_request(self, request_data):
        try:
            # Koneksi ke web server lokal
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)  # 30 detik timeout
            sock.connect(('127.0.0.1', self.local_port))
            
            # Kirim request
            sock.send(request_data.encode())
            
            # Gunakan thread pool untuk membaca response
            response = await asyncio.get_event_loop().run_in_executor(
                self.executor, 
                self.receive_full_response,
                sock
            )
            
            sock.close()
            return response.decode('utf-8', 'ignore')
            
        except Exception as e:
            return f"""HTTP/1.1 502 Bad Gateway
Content-Type: text/plain

Error: Cannot connect to local web server on port {self.local_port}
{str(e)}"""

    async def handle_server_messages(self, ws):
        try:
            while True:
                message = await ws.recv()
                data = json.loads(message)
                
                if data['type'] == 'request':
                    # Forward request ke web server lokal
                    response = await self.forward_request(data['data'])
                    
                    # Kirim response balik ke server
                    await ws.send(json.dumps({
                        'type': 'response',
                        'id': data['id'],
                        'data': response
                    }))
                    
                elif data['type'] == 'heartbeat':
                    await ws.send(json.dumps({'type': 'heartbeat'}))

        except websockets.exceptions.ConnectionClosed:
            print("Koneksi terputus")
            if ws in self.ws_connections:
                self.ws_connections.remove(ws)
        except Exception as e:
            print(f"Error: {e}")
            if ws in self.ws_connections:
                self.ws_connections.remove(ws)

    async def maintain_connections(self):
        while self.reconnect:
            try:
                # Buat koneksi baru jika jumlah koneksi kurang
                while len(self.ws_connections) < MAX_CONNECTIONS:
                    ws = await websockets.connect(
                        self.ws_url,
                        ping_interval=30,
                        ping_timeout=10
                    )
                    print(f"Koneksi baru dibuat (total: {len(self.ws_connections) + 1})")
                    self.ws_connections.append(ws)
                    asyncio.create_task(self.handle_server_messages(ws))
                
                await asyncio.sleep(5)  # Check setiap 5 detik
                
            except Exception as e:
                print(f"Error saat membuat koneksi: {e}")
                await asyncio.sleep(5)

    async def start(self):
        await self.maintain_connections()

if __name__ == "__main__":
    client = HomeClient()
    asyncio.run(client.start())