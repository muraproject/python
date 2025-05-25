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
ffmpeg_output = []  # Store FFmpeg output for debugging

def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return "127.0.0.1"

def create_hls_dir():
    """Create HLS directory"""
    HLS_DIR.mkdir(exist_ok=True)
    logger.info(f"HLS directory: {HLS_DIR.absolute()}")

def test_ffmpeg_simple():
    """Test simple FFmpeg command first"""
    logger.info("🧪 Testing simple FFmpeg command...")
    
    cmd = [
        'ffmpeg', '-y',
        '-rtsp_transport', 'tcp',
        '-i', RTSP_URL,
        '-t', '5',  # Only 5 seconds test
        '-c', 'copy',
        'test_output.mp4'
    ]
    
    try:
        logger.info(f"📝 Test command: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Read output in real-time
        output_lines = []
        while True:
            line = process.stdout.readline()
            if not line:
                break
            
            line = line.strip()
            if line:
                print(f"FFmpeg: {line}")
                output_lines.append(line)
                
                # Check for success indicators
                if 'time=' in line:
                    logger.info(f"✅ Recording progress: {line}")
        
        process.wait()
        
        if process.returncode == 0:
            logger.info("✅ Simple FFmpeg test PASSED")
            return True
        else:
            logger.error(f"❌ Simple FFmpeg test FAILED with code: {process.returncode}")
            return False
            
    except Exception as e:
        logger.error(f"💥 Test failed: {e}")
        return False

def start_ffmpeg_hls_debug():
    """Start FFmpeg with detailed output"""
    global ffmpeg_process, ffmpeg_output
    
    create_hls_dir()
    
    logger.info("🚀 Starting FFmpeg RTSP to HLS (DEBUG MODE)...")
    
    # Clear old files
    for f in HLS_DIR.glob('*'):
        try:
            f.unlink()
            logger.info(f"🗑️ Deleted old file: {f.name}")
        except:
            pass
    
    cmd = [
        'ffmpeg', '-y',
        '-loglevel', 'verbose',  # More verbose output
        '-rtsp_transport', 'tcp',
        '-i', RTSP_URL,
        '-c:v', 'libx264',
        '-preset', 'ultrafast',  # Fastest preset
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
        logger.info(f"📝 Full command: {' '.join(cmd)}")
        
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
        logger.error(f"💥 Failed to start FFmpeg: {e}")
        return False

def monitor_ffmpeg_debug():
    """Monitor FFmpeg with detailed logging"""
    global connection_status, ffmpeg_process, server_running, ffmpeg_output
    
    logger.info("🔍 Starting FFmpeg monitor (DEBUG MODE)")
    
    while server_running and ffmpeg_process:
        try:
            # Check if process is still running
            if ffmpeg_process.poll() is not None:
                exit_code = ffmpeg_process.poll()
                logger.error(f"💥 FFmpeg process died with exit code: {exit_code}")
                connection_status = False
                
                # Read remaining output
                remaining = ffmpeg_process.stdout.read()
                if remaining:
                    for line in remaining.split('\n'):
                        if line.strip():
                            logger.info(f"FFmpeg final: {line.strip()}")
                            ffmpeg_output.append(line.strip())
                
                break
            
            # Read output line by line
            line = ffmpeg_process.stdout.readline()
            if line:
                line = line.strip()
                if line:
                    # Store for web interface
                    ffmpeg_output.append(line)
                    if len(ffmpeg_output) > 50:  # Keep only last 50 lines
                        ffmpeg_output.pop(0)
                    
                    # Log important lines
                    if any(keyword in line.lower() for keyword in 
                          ['error', 'failed', 'time=', 'opening', 'stream']):
                        logger.info(f"FFmpeg: {line}")
                    
                    # Update connection status based on output
                    if 'time=' in line:
                        connection_status = True
            
            # Also check HLS files
            playlist_path = HLS_DIR / 'stream.m3u8'
            if playlist_path.exists():
                try:
                    mtime = playlist_path.stat().st_mtime
                    age = time.time() - mtime
                    if age < 10:
                        connection_status = True
                    else:
                        connection_status = False
                except:
                    pass
            
        except Exception as e:
            logger.error(f"💥 Monitor error: {e}")
            
        time.sleep(0.5)  # Check more frequently

# Flask app
app = Flask(__name__)

@app.route('/')
def index():
    local_ip = get_local_ip()
    return f'''
<!DOCTYPE html>
<html>
<head>
    <title>RTSP to HLS Debug</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>
        body {{
            font-family: 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            background: #000;
            color: #0f0;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .section {{
            background: #111;
            border: 1px solid #333;
            border-radius: 5px;
            padding: 15px;
            margin: 10px 0;
        }}
        .video-container {{
            background: #000;
            text-align: center;
            padding: 10px;
        }}
        video {{
            width: 100%;
            max-width: 640px;
            height: auto;
        }}
        .status {{
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
            font-weight: bold;
        }}
        .connected {{ background: #004400; color: #0f0; }}
        .disconnected {{ background: #440000; color: #f00; }}
        .btn {{
            padding: 10px 15px;
            margin: 5px;
            background: #333;
            color: #0f0;
            border: 1px solid #666;
            cursor: pointer;
        }}
        .btn:hover {{ background: #444; }}
        .output {{
            background: #000;
            color: #0f0;
            padding: 10px;
            border: 1px solid #333;
            font-size: 12px;
            max-height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
        }}
        h2 {{ color: #0f0; border-bottom: 1px solid #333; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 RTSP to HLS Debug Console</h1>
        
        <div class="section">
            <h2>📊 Status</h2>
            <div id="status" class="status disconnected">❌ Not Connected</div>
            <div id="fileStatus">📁 Files: Loading...</div>
        </div>
        
        <div class="section">
            <h2>🎥 Video Player</h2>
            <div class="video-container">
                <video id="video" controls muted>
                    Your browser does not support video.
                </video>
            </div>
            <div>
                <button class="btn" onclick="initHLS()">🚀 Start HLS</button>
                <button class="btn" onclick="playVideo()">▶️ Play</button>
                <button class="btn" onclick="reloadStream()">🔄 Reload</button>
                <button class="btn" onclick="testFFmpeg()">🧪 Test FFmpeg</button>
            </div>
        </div>
        
        <div class="section">
            <h2>🖥️ FFmpeg Output</h2>
            <div id="ffmpegOutput" class="output">
                Waiting for FFmpeg output...
            </div>
        </div>
        
        <div class="section">
            <h2>📂 HLS Files</h2>
            <div id="filesList" class="output">
                Loading file list...
            </div>
        </div>
        
        <div class="section">
            <h2>ℹ️ Information</h2>
            <div>
                <strong>RTSP URL:</strong> {RTSP_URL}<br>
                <strong>Server:</strong> http://{local_ip}:{HTTP_PORT}<br>
                <strong>HLS Directory:</strong> {HLS_DIR.absolute()}<br>
                <strong>Playlist URL:</strong> /hls/stream.m3u8
            </div>
        </div>
    </div>

    <script>
        let hls;
        const video = document.getElementById('video');
        const statusEl = document.getElementById('status');
        const fileStatusEl = document.getElementById('fileStatus');
        const ffmpegOutputEl = document.getElementById('ffmpegOutput');
        const filesListEl = document.getElementById('filesList');

        function initHLS() {{
            const streamUrl = '/hls/stream.m3u8';
            
            if (Hls.isSupported()) {{
                if (hls) hls.destroy();
                
                hls = new Hls();
                hls.loadSource(streamUrl);
                hls.attachMedia(video);
                
                hls.on(Hls.Events.MANIFEST_PARSED, function() {{
                    console.log('✅ HLS loaded');
                    video.play().catch(e => console.log('Autoplay blocked'));
                }});
                
                hls.on(Hls.Events.ERROR, function(event, data) {{
                    console.error('❌ HLS error:', data);
                }});
            }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
                video.src = streamUrl;
            }}
        }}

        function playVideo() {{ video.play(); }}
        function reloadStream() {{ location.reload(); }}
        
        function testFFmpeg() {{
            fetch('/test-ffmpeg')
                .then(r => r.json())
                .then(data => {{
                    alert('Test result: ' + (data.success ? 'SUCCESS' : 'FAILED'));
                }});
        }}

        function updateStatus() {{
            fetch('/status')
                .then(r => r.json())
                .then(data => {{
                    if (data.connected) {{
                        statusEl.className = 'status connected';
                        statusEl.innerHTML = '✅ FFmpeg Running';
                    }} else {{
                        statusEl.className = 'status disconnected';
                        statusEl.innerHTML = '❌ FFmpeg Not Running';
                    }}
                    
                    fileStatusEl.innerHTML = 
                        '📁 Files: ' + data.hls_files_count + 
                        ' | 📄 Playlist: ' + (data.playlist_exists ? 'YES' : 'NO') +
                        ' | 📊 Size: ' + (data.playlist_size || 0) + ' bytes';
                }});
                
            // Get FFmpeg output
            fetch('/ffmpeg-output')
                .then(r => r.json())
                .then(data => {{
                    ffmpegOutputEl.textContent = data.output.join('\\n');
                    ffmpegOutputEl.scrollTop = ffmpegOutputEl.scrollHeight;
                }});
                
            // Get file list
            fetch('/files')
                .then(r => r.json())
                .then(data => {{
                    let html = '';
                    data.files.forEach(file => {{
                        html += file.name + ' (' + file.size + ' bytes)\\n';
                    }});
                    filesListEl.textContent = html || 'No files found';
                }});
        }}

        setInterval(updateStatus, 2000);
        updateStatus();
        
        // Auto-try HLS after 5 seconds
        setTimeout(initHLS, 5000);
    </script>
</body>
</html>
    '''

@app.route('/test-ffmpeg')
def test_ffmpeg_endpoint():
    success = test_ffmpeg_simple()
    return jsonify({'success': success})

@app.route('/ffmpeg-output')
def get_ffmpeg_output():
    return jsonify({'output': ffmpeg_output})

@app.route('/hls/<path:filename>')
def serve_hls(filename):
    return send_from_directory(HLS_DIR, filename)

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

@app.route('/files')
def list_files():
    files = []
    if HLS_DIR.exists():
        for file in HLS_DIR.iterdir():
            stat = file.stat()
            files.append({
                'name': file.name,
                'size': stat.st_size,
                'modified': time.strftime('%H:%M:%S', time.localtime(stat.st_mtime))
            })
    
    files.sort(key=lambda x: x['name'])
    return jsonify({'files': files})

if __name__ == "__main__":
    try:
        print("🔧 RTSP to HLS Debug Mode")
        print(f"📡 RTSP: {RTSP_URL}")
        
        # Test simple FFmpeg first
        print("\n🧪 Testing simple FFmpeg command first...")
        if not test_ffmpeg_simple():
            print("❌ Simple FFmpeg test failed - check RTSP connection")
            input("Press Enter to continue anyway or Ctrl+C to exit...")
        
        # Start FFmpeg HLS
        if not start_ffmpeg_hls_debug():
            print("❌ Failed to start FFmpeg HLS")
            exit(1)
        
        # Start monitoring
        monitor_thread = threading.Thread(target=monitor_ffmpeg_debug)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Start web server
        local_ip = get_local_ip()
        print(f"\n🌐 Debug Console: http://{local_ip}:{HTTP_PORT}")
        print("🔍 Check web interface for real-time FFmpeg output")
        
        app.run(host='0.0.0.0', port=HTTP_PORT, debug=False)
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
        server_running = False
        if ffmpeg_process:
            ffmpeg_process.terminate()