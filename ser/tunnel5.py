import asyncio
import websockets
import socket
import json
import time
import errno

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
        self.chunk_size = 8192
        self.active_sockets = {}

    async def handle_local_response(self, local_socket, socket_id, start=False):
        try:
            while True:
                try:
                    chunk = await self.loop.sock_recv(local_socket, self.chunk_size)
                    if not chunk:
                        break

                    # Forward chunk ke server
                    await self.ws.send(json.dumps({
                        'type': 'response',
                        'socket_id': socket_id,
                        'chunk': chunk.decode(),
                        'start': start
                    }))
                    start = False

                except (BlockingIOError, errno.EAGAIN, errno.EWOULDBLOCK):
                    await asyncio.sleep(0.01)
                    continue
                except Exception as e:
                    print(f"[-] Error reading response: {e}")
                    break

            # Sinyal akhir response
            await self.ws.send(json.dumps({
                'type': 'response',
                'socket_id': socket_id,
                'chunk': '',
                'end': True
            }))

        finally:
            try:
                local_socket.close()
            except:
                pass
            if socket_id in self.active_sockets:
                del self.active_sockets[socket_id]

    async def handle_server_messages(self):
        try:
            while True:
                message = await self.ws.recv()
                data = json.loads(message)
                
                if data['type'] == 'request':
                    socket_id = data['socket_id']
                    
                    if data.get('start', False):
                        # Buat koneksi baru ke web server lokal
                        try:
                            local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            local_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                            local_socket.setblocking(False)
                            
                            await self.loop.sock_connect(local_socket, ('127.0.0.1', self.local_port))
                            self.active_sockets[socket_id] = local_socket
                            
                            # Start membaca response dalam task terpisah
                            asyncio.create_task(self.handle_local_response(local_socket, socket_id, True))
                            
                        except Exception as e:
                            print(f"[-] Error connecting to local server: {e}")
                            continue
                    
                    if socket_id in self.active_sockets:
                        local_socket = self.active_sockets[socket_id]
                        # Forward chunk ke web server lokal
                        if data['chunk']:
                            try:
                                await self.loop.sock_sendall(local_socket, data['chunk'].encode())
                            except Exception as e:
                                print(f"[-] Error forwarding to local: {e}")
                        
                        # Tutup koneksi jika ini chunk terakhir
                        if data.get('end', False):
                            try:
                                await self.loop.sock_shutdown(local_socket, socket.SHUT_WR)
                            except:
                                pass

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
                    compression=None,
                    max_size=None
                ) as websocket:
                    self.ws = websocket
                    print("[+] Connected!")
                    
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
            finally:
                # Cleanup active sockets
                for sock in self.active_sockets.values():
                    try:
                        sock.close()
                    except:
                        pass
                self.active_sockets.clear()

    async def start(self):
        self.loop = asyncio.get_event_loop()
        await self.connect()

if __name__ == "__main__":
    client = HomeClient()
    asyncio.run(client.start())