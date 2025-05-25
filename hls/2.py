#!/usr/bin/env python3
import subprocess
import time
import threading
import logging
import os
import socket
import sys
from pathlib import Path
from flask import Flask, send_from_directory, jsonify

# Setup logging dengan file backup
log_file = Path("rtsp_debug.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
RTSP_URL = "rtsp://admin:VGOUNZ@103.122.66.243:8088/stream2"
HTTP_PORT = 5003
HLS_DIR = Path("hls")

# Global variables
ffmpeg_process = None
server_running = False
connection_status = False
ffmpeg_output = []
startup_error = None

def safe_execute(func, description, critical=False):
    """Safely execute function with error handling"""
    try:
        logger.info(f"🔄 {description}...")
        result = func()
        logger.info(f"✅ {description} - SUCCESS")
        return result
    except Exception as e:
        error_msg = f"❌ {description} - FAILED: {str(e)}"
        logger.error(error_msg)
        if critical:
            global startup_error
            startup_error = error_msg
        return None

def check_system_requirements():
    """Check all system requirements"""
    logger.info("🔍 Checking system requirements...")
    
    issues = []
    
    # Check FFmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.info("✅ FFmpeg found")
        else:
            issues.append("FFmpeg installation issue")
    except FileNotFoundError:
        issues.append("FFmpeg not found in PATH")
    except Exception as e:
        issues.append(f"FFmpeg check failed: {e}")
    
    # Check port availability
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', HTTP_PORT))
        logger.info(f"✅ Port {HTTP_PORT} available")
    except OSError:
        issues.append(f"Port {HTTP_PORT} already in use")
    
    # Check write permissions
    try:
        test_file = Path("test_write.tmp")
        test_file.write_text("test")
        test_file.unlink()
        logger.info("✅ Write permissions OK")
    except Exception:
        issues.append("No write permissions in current directory")
    
    return issues

def get_local_ip():
    """Get local IP with fallback"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return "127.0.0.1"

def create_hls_dir():
    """Create HLS directory with error handling"""
    try:
        HLS_DIR.mkdir(exist_ok=True)
        logger.info(f"✅ HLS directory ready: {HLS_DIR.absolute()}")
        
        # Test write to directory
        test_file = HLS_DIR / "test.tmp"
        test_file.write_text("test")
        test_file.unlink()
        
        return True
    except Exception as e:
        logger.error(f"❌ Cannot create/write to HLS directory: {e}")
        return False

def test_rtsp_connection():
    """Test RTSP connection with multiple methods"""
    logger.info("🧪 Testing RTSP connection...")
    
    methods = [
        ('TCP', ['-rtsp_transport', 'tcp']),
        ('UDP', ['-rtsp_transport', 'udp']),
        ('Default', [])
    ]
    
    for name, options in methods:
        try:
            cmd = ['ffprobe', '-v', 'quiet'] + options + ['-i', RTSP_URL]
            logger.info(f"   Testing {name}: {' '.join(cmd[:4])}...")
            
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            
            if result.returncode == 0:
                logger.info(f"✅ {name} transport works")
                return options
            else:
                logger.warning(f"❌ {name} transport failed")
                
        except subprocess.TimeoutExpired:
            logger.warning(f"⏰ {name} transport timeout")
        except Exception as e:
            logger.warning(f"💥 {name} transport error: {e}")
    
    logger.error("🚫 All RTSP connection methods failed")
    return None

def start_ffmpeg_hls():
    """Start FFmpeg with robust error handling"""
    global ffmpeg_process, ffmpeg_output
    
    # Clear old files
    if HLS_DIR.exists():
        for f in HLS_DIR.glob('*'):
            try:
                f.unlink()
            except:
                pass
    
    # Test RTSP first
    transport_options = test_rtsp_connection()
    if not transport_options:
        logger.error("❌ Cannot connect to RTSP - aborting FFmpeg start")
        return False
    
    logger.info(f"🚀 Starting FFmpeg with {transport_options or 'default'} transport...")
    
    cmd = [
        'ffmpeg', '-y',
        '-loglevel', 'info',
        '-hide_banner'
    ]
    
    if transport_options:
        cmd.extend(transport_options)
    
    cmd.extend([
        '-i', RTSP_URL,
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '28',
        '-g', '50',
        '-c:a', 'aac',
        '-b:a', '64k',
        '-f', 'hls',
        '-hls_time', '6',
        '-hls_list_size', '5',
        '-hls_flags', 'delete_segments',
        '-hls_segment_filename', str(HLS_DIR / 'seg_%03d.ts'),
        str(HLS_DIR / 'stream.m3u8')
    ])
    
    try:
        logger.info(f"📝 Command: {' '.join(cmd[:6])}... (truncated)")
        
        ffmpeg_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Wait a bit and check if it started successfully
        time.sleep(2)
        if ffmpeg_process.poll() is None:
            logger.info("✅ FFmpeg process started successfully")
            return True
        else:
            exit_code = ffmpeg_process.poll()
            logger.error(f"❌ FFmpeg failed to start, exit code: {exit_code}")
            
            # Read error output
            try:
                output = ffmpeg_process.stdout.read()
                if output:
                    logger.error(f"FFmpeg error: {output}")
                    ffmpeg_output.extend(output.split('\n'))
            except:
                pass
            
            return False
            
    except Exception as e:
        logger.error(f"💥 Exception starting FFmpeg: {e}")
        return False

def monitor_ffmpeg():
    """Monitor FFmpeg with robust error handling"""
    global connection_status, ffmpeg_process, server_running, ffmpeg_output
    
    logger.info("🔍 Starting FFmpeg monitor...")
    
    while server_running and ffmpeg_process:
        try:
            if ffmpeg_process.poll() is not None:
                # Process died
                exit_code = ffmpeg_process.poll()
                logger.warning(f"⚠️ FFmpeg process died with code: {exit_code}")
                connection_status = False
                
                # Read final output
                try:
                    remaining = ffmpeg_process.stdout.read()
                    if remaining:
                        lines = remaining.strip().split('\n')
                        for line in lines:
                            if line.strip():
                                ffmpeg_output.append(line.strip())
                                logger.info(f"FFmpeg final: {line.strip()}")
                except:
                    pass
                
                break
            
            # Read output
            try:
                line = ffmpeg_process.stdout.readline()
                if line:
                    line = line.strip()
                    if line:
                        ffmpeg_output.append(line)
                        # Keep only last 100 lines
                        if len(ffmpeg_output) > 100:
                            ffmpeg_output.pop(0)
                        
                        # Log important lines
                        if any(keyword in line.lower() for keyword in 
                              ['error', 'failed', 'time=', 'opening', 'stream mapping']):
                            logger.info(f"FFmpeg: {line}")
                        
                        # Update status
                        if 'time=' in line:
                            connection_status = True
            except:
                pass
            
            # Check HLS files
            try:
                playlist_path = HLS_DIR / 'stream.m3u8'
                if playlist_path.exists():
                    mtime = playlist_path.stat().st_mtime
                    if time.time() - mtime < 15:
                        connection_status = True
            except:
                pass
                
        except Exception as e:
            logger.error(f"💥 Monitor error: {e}")
            
        time.sleep(0.5)
    
    logger.info("🏁 FFmpeg monitor stopped")

# Flask app with error handling
app = Flask(__name__)

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Flask error: {e}")
    return f"Server error: {e}", 500

@app.route('/')
def index():
    local_ip = get_local_ip()
    
    # Show startup error if any
    error_section = ""
    if startup_error:
        error_section = f'''
        <div class="section error">
            <h2>⚠️ Startup Error</h2>
            <div>{startup_error}</div>
        </div>
        '''
    
    return f'''
<!DOCTYPE html>
<html>
<head>
    <title>RTSP to HLS - Robust Version</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>
        body {{
            font-family: 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            background: #001122;
            color: #00ff00;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .section {{
            background: #002244;
            border: 1px solid #004466;
            border-radius: 5px;
            padding: 15px;
            margin: 10px 0;
        }}
        .error {{
            background: #440000;
            border-color: #880000;
            color: #ff6666;
        }}
        .video-container {{
            background: #000;
            text-align: center;
            padding: 10px;
        }}
        video {{ width: 100%; max-width: 640px; }}
        .status {{
            padding: 10px;
            border-radius: 5px;
            margin: 5px 0;
            font-weight: bold;
        }}
        .connected {{ background: #004400; }}
        .disconnected {{ background: #440000; }}
        .btn {{
            padding: 8px 12px;
            margin: 3px;
            background: #004466;
            color: #00ff00;
            border: 1px solid #006688;
            cursor: pointer;
            border-radius: 3px;
        }}
        .btn:hover {{ background: #006688; }}
        .output {{
            background: #000011;
            color: #00ff00;
            padding: 10px;
            border: 1px solid #004466;
            font-size: 11px;
            max-height: 200px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        h2 {{ 
            color: #00ffff; 
            border-bottom: 1px solid #004466; 
            font-size: 16px;
        }}
        .info {{ font-size: 12px; line-height: 1.4; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ RTSP to HLS - Robust Version</h1>
        
        {error_section}
        
        <div class="section">
            <h2>📊 System Status</h2>
            <div id="status" class="status disconnected">❌ Not Connected</div>
            <div id="systemInfo" class="info">Loading system info...</div>
        </div>
        
        <div class="section">
            <h2>🎥 Video Player</h2>
            <div class="video-container">
                <video id="video" controls muted>No video</video>
            </div>
            <div>
                <button class="btn" onclick="initHLS()">🚀 Start HLS</button>
                <button class="btn" onclick="playVideo()">▶️ Play</button>
                <button class="btn" onclick="testConnection()">🧪 Test RTSP</button>
                <button class="btn" onclick="restartFFmpeg()">🔄 Restart</button>
            </div>
        </div>
        
        <div class="section">
            <h2>🖥️ FFmpeg Output</h2>
            <div id="ffmpegOutput" class="output">Waiting for output...</div>
        </div>
        
        <div class="section">
            <h2>📂 Files & Debug</h2>
            <div id="debugInfo" class="output">Loading debug info...</div>
        </div>
    </div>

    <script>
        let hls;
        const video = document.getElementById('video');
        
        function initHLS() {{
            fetch('/hls/stream.m3u8', {{method: 'HEAD'}})
                .then(response => {{
                    if (response.ok) {{
                        if (Hls.isSupported()) {{
                            if (hls) hls.destroy();
                            hls = new Hls();
                            hls.loadSource('/hls/stream.m3u8');
                            hls.attachMedia(video);
                            hls.on(Hls.Events.MANIFEST_PARSED, () => {{
                                video.play().catch(e => console.log('Autoplay blocked'));
                            }});
                        }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
                            video.src = '/hls/stream.m3u8';
                        }}
                    }} else {{
                        alert('HLS playlist not ready yet');
                    }}
                }})
                .catch(() => alert('Cannot access HLS playlist'));
        }}
        
        function playVideo() {{ video.play(); }}
        
        function testConnection() {{
            fetch('/test-rtsp')
                .then(r => r.json())
                .then(data => alert('RTSP Test: ' + (data.success ? 'SUCCESS' : 'FAILED')))
                .catch(() => alert('Test request failed'));
        }}
        
        function restartFFmpeg() {{
            if (confirm('Restart FFmpeg process?')) {{
                fetch('/restart-ffmpeg', {{method: 'POST'}})
                    .then(r => r.json())
                    .then(data => alert(data.success ? 'Restarted' : 'Failed to restart'));
            }}
        }}
        
        function updateStatus() {{
            // Update main status
            fetch('/status')
                .then(r => r.json())
                .then(data => {{
                    const statusEl = document.getElementById('status');
                    const systemInfoEl = document.getElementById('systemInfo');
                    
                    if (data.connected) {{
                        statusEl.className = 'status connected';
                        statusEl.innerHTML = '✅ FFmpeg Running';
                    }} else {{
                        statusEl.className = 'status disconnected';
                        statusEl.innerHTML = '❌ FFmpeg Not Running';
                    }}
                    
                    systemInfoEl.innerHTML = 
                        'Files: ' + data.hls_files_count + 
                        ' | Playlist: ' + (data.playlist_exists ? 'YES' : 'NO') +
                        ' | FFmpeg PID: ' + (data.ffmpeg_running ? 'Running' : 'Stopped') +
                        ' | Last check: ' + new Date().toLocaleTimeString();
                }})
                .catch(() => {{
                    document.getElementById('status').innerHTML = '⚠️ Server Error';
                }});
            
            // Update FFmpeg output
            fetch('/ffmpeg-output')
                .then(r => r.json())
                .then(data => {{
                    const outputEl = document.getElementById('ffmpegOutput');
                    outputEl.textContent = data.output.slice(-30).join('\\n');
                    outputEl.scrollTop = outputEl.scrollHeight;
                }})
                .catch(() => {{}});
            
            // Update debug info
            fetch('/debug')
                .then(r => r.json())
                .then(data => {{
                    const debugEl = document.getElementById('debugInfo');
                    let html = '';
                    if (data.files.length > 0) {{
                        html += 'HLS Files:\\n';
                        data.files.forEach(f => {{
                            html += f.name + ' (' + f.size + ' bytes)\\n';
                        }});
                    }} else {{
                        html += 'No HLS files found\\n';
                    }}
                    html += '\\nServer uptime: ' + Math.round(data.uptime) + 's';
                    debugEl.textContent = html;
                }})
                .catch(() => {{}});
        }}
        
        setInterval(updateStatus, 2000);
        updateStatus();
        setTimeout(initHLS, 8000);
    </script>
</body>
</html>
    '''

@app.route('/test-rtsp')
def test_rtsp_endpoint():
    options = test_rtsp_connection()
    return jsonify({'success': options is not None, 'transport': options})

@app.route('/restart-ffmpeg', methods=['POST'])
def restart_ffmpeg():
    global ffmpeg_process
    try:
        if ffmpeg_process:
            ffmpeg_process.terminate()
            time.sleep(2)
        
        success = start_ffmpeg_hls()
        if success:
            # Restart monitor
            monitor_thread = threading.Thread(target=monitor_ffmpeg)
            monitor_thread.daemon = True
            monitor_thread.start()
        
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/ffmpeg-output')
def get_ffmpeg_output():
    return jsonify({'output': ffmpeg_output})

@app.route('/debug')
def get_debug():
    files = []
    if HLS_DIR.exists():
        for f in HLS_DIR.iterdir():
            files.append({
                'name': f.name,
                'size': f.stat().st_size
            })
    
    return jsonify({
        'files': files,
        'uptime': time.time() - start_time,
        'ffmpeg_running': ffmpeg_process is not None and ffmpeg_process.poll() is None
    })

@app.route('/hls/<path:filename>')
def serve_hls(filename):
    return send_from_directory(HLS_DIR, filename)

@app.route('/status')
def get_status():
    playlist_path = HLS_DIR / 'stream.m3u8'
    return jsonify({
        'connected': connection_status,
        'playlist_exists': playlist_path.exists(),
        'hls_files_count': len(list(HLS_DIR.glob('*'))) if HLS_DIR.exists() else 0,
        'ffmpeg_running': ffmpeg_process is not None and ffmpeg_process.poll() is None,
        'timestamp': time.time()
    })

def main():
    global server_running, start_time
    start_time = time.time()
    
    print("🛡️ RTSP to HLS Server - Robust Version")
    print("=" * 50)
    
    # Check system requirements
    issues = check_system_requirements()
    if issues:
        print("⚠️ System issues found:")
        for issue in issues:
            print(f"   • {issue}")
        
        if not input("\nContinue anyway? (y/N): ").lower().startswith('y'):
            return
    
    # Setup
    if not safe_execute(create_hls_dir, "Creating HLS directory", critical=True):
        print("❌ Cannot create HLS directory")
        return
    
    # Start FFmpeg
    if not safe_execute(start_ffmpeg_hls, "Starting FFmpeg", critical=False):
        print("⚠️ FFmpeg failed to start - will run in debug mode")
    else:
        # Start monitor
        monitor_thread = threading.Thread(target=monitor_ffmpeg)
        monitor_thread.daemon = True
        monitor_thread.start()
    
    # Start web server
    try:
        server_running = True
        local_ip = get_local_ip()
        
        print(f"\n✅ Server starting...")
        print(f"🌐 URL: http://{local_ip}:{HTTP_PORT}")
        print(f"📁 HLS: {HLS_DIR.absolute()}")
        print(f"📋 Log: {log_file.absolute()}")
        print("\n🔄 Press Ctrl+C to stop")
        
        app.run(host='0.0.0.0', port=HTTP_PORT, debug=False, threaded=True)
        
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
    finally:
        server_running = False
        if ffmpeg_process:
            ffmpeg_process.terminate()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Stopped by user")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        logger.exception("Unexpected error")