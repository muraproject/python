#!/usr/bin/env python3
import subprocess
import time
import threading
import logging
import os
import socket
from pathlib import Path
from flask import Flask, send_from_directory, jsonify

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration  
RTSP_URL = "rtsp://admin:VGOUNZ@103.122.66.243:8088/stream2"
HTTP_PORT = 5003
HLS_DIR = Path("hls")

# Global variables
ffmpeg_process = None
server_running = True
connection_status = False
ffmpeg_output = []

def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return "127.0.0.1"

def create_hls_dir():
    HLS_DIR.mkdir(exist_ok=True)
    logger.info(f"HLS directory: {HLS_DIR.absolute()}")

def start_ffmpeg_hls():
    global ffmpeg_process
    
    create_hls_dir()
    
    logger.info("🚀 Starting FFmpeg RTSP to HLS...")
    
    cmd = [
        'ffmpeg', '-y',
        '-loglevel', 'info',  # Less verbose
        '-rtsp_transport', 'tcp',
        '-i', RTSP_URL,
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '30',
        '-g', '30',
        '-c:a', 'aac',
        '-b:a', '64k',
        '-f', 'hls',
        '-hls_time', '4',
        '-hls_list_size', '6',
        '-hls_flags', 'delete_segments',
        '-hls_segment_filename', str(HLS_DIR / 'seg_%03d.ts'),
        str(HLS_DIR / 'stream.m3u8')
    ]
    
    try:
        ffmpeg_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        logger.info("✅ FFmpeg process started")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start FFmpeg: {e}")
        return False

def monitor_ffmpeg_with_restart():
    global connection_status, ffmpeg_process, server_running, ffmpeg_output
    
    restart_count = 0
    
    while server_running:
        if ffmpeg_process:
            if ffmpeg_process.poll() is not None:
                exit_code = ffmpeg_process.poll()
                
                if exit_code == 0:
                    logger.info("ℹ️ FFmpeg finished normally - restarting...")
                else:
                    logger.warning(f"⚠️ FFmpeg died with code: {exit_code} - restarting...")
                
                connection_status = False
                restart_count += 1
                
                # Read final output
                try:
                    remaining = ffmpeg_process.stdout.read()
                    if remaining:
                        lines = remaining.strip().split('\n')[-5:]  # Last 5 lines
                        for line in lines:
                            if line.strip():
                                ffmpeg_output.append(line.strip())
                except:
                    pass
                
                # Auto-restart after short delay
                if server_running:
                    logger.info(f"🔄 Auto-restarting FFmpeg (restart #{restart_count})...")
                    time.sleep(3)  # Wait 3 seconds before restart
                    start_ffmpeg_hls()
                    continue
            
            # Read FFmpeg output
            try:
                line = ffmpeg_process.stdout.readline()
                if line:
                    line = line.strip()
                    if line:
                        ffmpeg_output.append(line)
                        if len(ffmpeg_output) > 30:  # Keep last 30 lines
                            ffmpeg_output.pop(0)
                        
                        # Update connection status
                        if 'time=' in line or 'Opening' in line:
                            connection_status = True
            except:
                pass
            
            # Check HLS files existence
            playlist_path = HLS_DIR / 'stream.m3u8'
            if playlist_path.exists():
                try:
                    mtime = playlist_path.stat().st_mtime
                    if time.time() - mtime < 15:  # Updated within 15 seconds
                        connection_status = True
                except:
                    pass
        else:
            connection_status = False
                    
        time.sleep(0.5)

# Flask app
app = Flask(__name__)

@app.route('/')
def index():
    local_ip = get_local_ip()
    return f'''
<!DOCTYPE html>
<html>
<head>
    <title>RTSP HLS Live Stream</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #1a1a1a;
            color: white;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            margin-bottom: 20px;
        }}
        video {{
            width: 100%;
            height: auto;
            background: #000;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }}
        .status-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: #2d2d2d;
            border-radius: 8px;
            margin: 15px 0;
        }}
        .status {{
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 14px;
        }}
        .connected {{ background: #4CAF50; }}
        .disconnected {{ background: #f44336; }}
        .controls {{
            text-align: center;
            margin: 20px 0;
        }}
        .btn {{
            padding: 12px 24px;
            margin: 8px;
            background: #4285f4;
            color: white;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            transition: background 0.3s;
        }}
        .btn:hover {{
            background: #3367d6;
        }}
        .info-panel {{
            background: #2d2d2d;
            border-radius: 8px;
            padding: 15px;
            margin: 15px 0;
        }}
        .debug {{
            background: #000;
            color: #0f0;
            padding: 15px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            max-height: 200px;
            overflow-y: auto;
            white-space: pre-wrap;
            border: 1px solid #333;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎥 RTSP HLS Live Stream</h1>
            <p>Real-time RTSP to HLS conversion with auto-restart</p>
        </div>
        
        <div class="status-bar">
            <div id="status" class="status disconnected">⏳ Starting...</div>
            <div id="stats" style="font-size: 12px;">
                Files: 0 | Size: 0 KB
            </div>
        </div>
        
        <video id="video" controls autoplay muted playsinline>
            <p>Your browser does not support HTML5 video.</p>
        </video>
        
        <div class="controls">
            <button class="btn" onclick="startStream()">🚀 Start Stream</button>
            <button class="btn" onclick="playVideo()">▶️ Play</button>
            <button class="btn" onclick="pauseVideo()">⏸️ Pause</button>
            <button class="btn" onclick="toggleMute()">🔊 Mute</button>
        </div>
        
        <div class="info-panel">
            <h3>📡 Stream Information</h3>
            <p><strong>RTSP Source:</strong> {RTSP_URL}</p>
            <p><strong>HLS Playlist:</strong> http://{local_ip}:{HTTP_PORT}/hls/stream.m3u8</p>
            <p><strong>Status:</strong> Auto-restart enabled</p>
        </div>
        
        <div class="debug" id="debug">
            🖥️ FFmpeg output will appear here...
        </div>
    </div>

    <script>
        const video = document.getElementById('video');
        const statusEl = document.getElementById('status');
        const statsEl = document.getElementById('stats');
        const debugEl = document.getElementById('debug');
        let hls = null;
        let streamStarted = false;

        function startStream() {{
            console.log('🚀 Initializing HLS stream...');
            
            const streamUrl = '/hls/stream.m3u8';
            
            if (Hls.isSupported()) {{
                if (hls) {{
                    hls.destroy();
                }}
                
                hls = new Hls({{
                    debug: false,
                    lowLatencyMode: true,
                    backBufferLength: 30,
                    maxBufferLength: 60,
                    autoStartLoad: true
                }});
                
                hls.loadSource(streamUrl);
                hls.attachMedia(video);
                
                hls.on(Hls.Events.MANIFEST_PARSED, function() {{
                    console.log('✅ Stream ready');
                    video.play().catch(e => console.log('Autoplay blocked'));
                    streamStarted = true;
                }});
                
                hls.on(Hls.Events.ERROR, function(event, data) {{
                    if (data.fatal) {{
                        console.log('🔄 Stream error - retrying...');
                        setTimeout(startStream, 3000);
                    }}
                }});
                
            }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
                video.src = streamUrl;
                video.play().catch(e => console.log('Autoplay blocked'));
                streamStarted = true;
            }} else {{
                alert('❌ HLS not supported in this browser');
            }}
        }}

        function playVideo() {{
            if (!streamStarted) startStream();
            video.play();
        }}

        function pauseVideo() {{
            video.pause();
        }}

        function toggleMute() {{
            video.muted = !video.muted;
        }}

        function updateStatus() {{
            fetch('/status')
                .then(r => r.json())
                .then(data => {{
                    if (data.connected && data.playlist_exists) {{
                        statusEl.className = 'status connected';
                        statusEl.innerHTML = '✅ Live Streaming';
                        
                        // Auto-start when ready
                        if (!streamStarted && data.hls_files_count > 1) {{
                            setTimeout(startStream, 1000);
                        }}
                    }} else {{
                        statusEl.className = 'status disconnected';
                        statusEl.innerHTML = '⏳ Connecting...';
                    }}
                    
                    statsEl.innerHTML = 
                        'Files: ' + data.hls_files_count + 
                        ' | Size: ' + Math.round(data.playlist_size / 1024) + ' KB';
                }})
                .catch(() => {{
                    statusEl.className = 'status disconnected';
                    statusEl.innerHTML = '❌ Server Error';
                }});
                
            // Update FFmpeg output
            fetch('/ffmpeg-output')
                .then(r => r.json())
                .then(data => {{
                    if (data.output.length > 0) {{
                        debugEl.textContent = data.output.slice(-15).join('\\n');
                        debugEl.scrollTop = debugEl.scrollHeight;
                    }}
                }})
                .catch(() => {{}});
        }}

        // Start monitoring
        updateStatus();
        setInterval(updateStatus, 2000);
        
        // Auto-start after 8 seconds
        setTimeout(() => {{
            if (!streamStarted) {{
                startStream();
            }}
        }}, 8000);
    </script>
</body>
</html>
    '''

@app.route('/ffmpeg-output')
def get_ffmpeg_output():
    return jsonify({'output': ffmpeg_output})

@app.route('/hls/<path:filename>')
def serve_hls(filename):
    response = send_from_directory(HLS_DIR, filename)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'no-cache'
    return response

@app.route('/status')
def get_status():
    playlist_path = HLS_DIR / 'stream.m3u8'
    hls_files_count = len(list(HLS_DIR.glob('*'))) if HLS_DIR.exists() else 0
    
    playlist_size = 0
    if playlist_path.exists():
        playlist_size = playlist_path.stat().st_size
    
    return jsonify({
        'connected': connection_status,
        'playlist_exists': playlist_path.exists(),
        'hls_files_count': hls_files_count,
        'playlist_size': playlist_size,
        'ffmpeg_running': ffmpeg_process is not None and ffmpeg_process.poll() is None,
        'timestamp': time.time()
    })

if __name__ == "__main__":
    print("🚀 Starting RTSP to HLS Server with Auto-Restart")
    print(f"📡 RTSP: {RTSP_URL}")
    
    try:
        # Start FFmpeg
        start_ffmpeg_hls()
        
        # Start monitoring with auto-restart
        monitor_thread = threading.Thread(target=monitor_ffmpeg_with_restart, daemon=True)
        monitor_thread.start()
        
        # Start Flask server
        local_ip = get_local_ip()
        print(f"🌐 Server: http://{local_ip}:{HTTP_PORT}")
        print("✅ Auto-restart enabled - stream will continue even if FFmpeg stops")
        
        app.run(host='0.0.0.0', port=HTTP_PORT, debug=False, use_reloader=False, threaded=True)
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping server...")
        server_running = False
    except Exception as e:
        print(f"❌ Server error: {e}")
    finally:
        if ffmpeg_process:
            try:
                ffmpeg_process.terminate()
            except:
                pass
        print("👋 Server stopped")