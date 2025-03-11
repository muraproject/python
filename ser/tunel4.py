import asyncio
import websockets
import socket
import json
import time
import zlib
from concurrent.futures import ThreadPoolExecutor

# Konfigurasi
SERVER_IP = "103.130.16.22"
SERVER_WS_PORT = 5001
LOCAL_PORT = 80

class HomeClient:
    def __init__(self):
        self.ws = None
        self.reconnect = True
        self.local_port = LOCAL_PORT
        self.ws_url = f"ws://{SERVER_IP}:{SERVER_WS_PORT}"
        self.compression_level = 6
        self.executor = ThreadPoolExecutor(max_workers=20)
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.last_print = time.time()
        self.response_cache = {}
        self.cache_timeout = 300  # 5 menit cache
        
    def compress_data(self, data):
        return zlib.compress(data.encode(), self.compression_level)
        
    def decompress_data(self, data):
        return zlib.decompress(data).decode()

    def calculate_speed(self):
        current_time = time.time()
        time_diff = current_time - self.last_print
        
        if time_diff >= 1:  # Print setiap detik
            up_speed = self.total_bytes_sent / time_diff / 1024  # KB/s
            down_speed = self.total_bytes_received / time_diff / 1024  # KB/s
            
            print(f"[+] Speed - Up: {up_speed:.2f} KB/s, Down: {down_speed:.2f} KB/s")
            
            self.total_bytes_sent = 0
            self.total_bytes_received = 0
            self.last_print = current_time

    def forward_request(self, request_data):
        try:
            # Cache check (untuk GET requests)
            if request_data.startswith("GET "):
                cache_key = request_data.split("\r\n\r\n")[0]
                if cache_key in self.response_cache:
                    cache_time, response = self.response_cache[cache_key]
                    if time.time() - cache_time < self.cache_timeout:
                        print(f"[+] Cache hit for {cache_key[:50]}")
                        return response

            # Connect to local server
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(10)
            sock.connect(('127.0.0.1', self.local_port))
            
            # Send request
            sock.send(request_data.encode())
            
            # Receive response with optimal buffer
            response = bytearray()
            while True:
                try:
                    chunk = sock.recv(8192)
                    if not chunk:
                        break
                    response.extend(chunk)
                    if b"\r\n\r\n" in response and not (b"Transfer-Encoding: chunked" in response):
                        break
                except socket.timeout:
                    break
            
            sock.close()
            response_str = response.decode()
            
            # Cache response untuk GET requests
            if request_data.startswith("GET "):
                self.response_cache[cache_key] = (time.time(), response_str)
            
            return response_str
            
        except Exception as e:
            print(f"[-] Forward error: {e}")
            return f"HTTP/1.1 502 Bad Gateway\r\n\r\nError: {str(e)}"

    async def clean_cache(self):
        while True:
            try:
                current_time = time.time()
                expired = [k for k, (t, _) in self.response_cache.items() 
                          if current_time - t > self.cache_timeout]
                
                for key in expired:
                    del self.response_cache[key]
                    
                if expired:
                    print(f"[-] Cleaned {len(expired)} cached responses")
                    
            except Exception as e:
                print(f"[-] Cache cleaning error: {e}")
                
            await asyncio.sleep(60)

    async def handle_server_messages(self):
        try:
            while True:
                compressed_data = await self.ws.recv()
                self.total_bytes_received += len(compressed_data)
                
                data = json.loads(self.decompress_data(compressed_data))
                
                if data['type'] == 'request':
                    # Forward request in thread pool
                    response = await asyncio.get_event_loop().run_in_executor(
                        self.executor,
                        self.forward_request,
                        data['data']
                    )
                    
                    # Compress and send response
                    response_data = json.dumps({
                        'type': 'response',
                        'id': data['id'],
                        'data': response
                    })
                    
                    compressed_response = self.compress_data(response_data)
                    await self.ws.send(compressed_response)
                    self.total_bytes_sent += len(compressed_response)
                    
                    print(f"[+] Response {len(response)} bytes -> {len(compressed_response)} bytes")
                
                self.calculate_speed()

        except websockets.exceptions.ConnectionClosed:
            print("[-] Connection closed")
        except Exception as e:
            print(f"[-] Error: {e}")

    async def connect(self):
        while self.reconnect:
            try:
                print(f"[+] Connecting to {self.ws_url}")
                
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    compression=None,  # Manual compression
                    max_size=None  # Unlimited message size
                ) as websocket:
                    self.ws = websocket
                    print("[+] Connected!")
                    
                    # Start cache cleaner
                    asyncio.create_task(self.clean_cache())
                    
                    await self.handle_server_messages()
                    
            except (websockets.exceptions.ConnectionClosed, 
                    websockets.exceptions.InvalidStatusCode,
                    ConnectionRefusedError) as e:
                print(f"[-] Connection error: {e}")
                print("[*] Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
                continue
                
            except Exception as e:
                print(f"[-] Unexpected error: {e}")
                print("[*] Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
                continue

    async def start(self):
        await self.connect()

if __name__ == "__main__":
    client = HomeClient()
    asyncio.run(client.start())