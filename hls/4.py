#!/usr/bin/env python3
import subprocess
import time
import threading
import logging
import os
import signal
import sys
from pathlib import Path
from flask import Flask, send_from_directory, jsonify
import psutil

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration  
RTSP_URL = "rtsp://admin:VGOUNZ@103.122.66.243:8088/stream2"
HTTP_PORT = 5003
HLS_DIR = Path("hls")

# HLS Configuration - More conservative settings
HLS_TIME = 4  # 4 second segments (more stable)
HLS_LIST_SIZE = 6  # Keep 6 segments (24 seconds buffer)
DELETE_THRESHOLD = 10  # Keep 10 segments before deleting old ones

# Global variables
ffmpeg_process = None
server_running = True
connection_status = False
ffmpeg_output = []
restart_count = 0
last_restart_time = 0
process_lock = threading.Lock()

def setup_signal_handlers():
    """Setup graceful shutdown handlers"""
    def signal_handler(signum, frame):
        global server_running
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        server_running = False
        cleanup_and_exit()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def cleanup_and_exit():
    """Clean shutdown"""
    global ffmpeg_process, server_running
    server_running = False
    
    if ffmpeg_process:
        try:
            logger.info("Terminating FFmpeg process...")
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.info("Force killing FFmpeg process...")
            ffmpeg_process.kill()
            ffmpeg_process.wait()
        except Exception as e:
            logger.error(f"Error stopping FFmpeg: {e}")
    
    logger.info("Server stopped gracefully")
    sys.exit(0)

def create_hls_dir():
    """Create HLS directory and clean old files"""
    HLS_DIR.mkdir(exist_ok=True)
    logger.info(f"HLS directory: {HLS_DIR.absolute()}")

def test_ffmpeg():
    """Test if FFmpeg is available and working"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info("FFmpeg is available")
            logger.debug(f"FFmpeg version: {result.stdout.split('ffmpeg version')[1].split('\\n')[0]}")
            return True
        else:
            logger.error("FFmpeg not working properly")
            return False
    except FileNotFoundError:
        logger.error("FFmpeg not found in PATH")
        return False
    except Exception as e:
        logger.error(f"Error testing FFmpeg: {e}")
        return False

def test_rtsp_connection():
    """Test RTSP connection"""
    logger.info(f"Testing RTSP connection to: {RTSP_URL}")
    
    cmd = [
        'ffmpeg', '-y',
        '-rtsp_transport', 'tcp',
        '-i', RTSP_URL,
        '-t', '5',  # Test for 5 seconds only
        '-f', 'null',
        '-'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            logger.info("RTSP connection test: SUCCESS")
            return True
        else:
            logger.error(f"RTSP connection test: FAILED")
            logger.error(f"FFmpeg stderr: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("RTSP connection test: TIMEOUT")
        return False
    except Exception as e:
        logger.error(f"RTSP connection test error: {e}")
        return False

def start_ffmpeg_hls():
    """Start FFmpeg process with basic, stable settings"""
    global ffmpeg_process
    
    with process_lock:
        if ffmpeg_process and ffmpeg_process.poll() is None:
            logger.info("FFmpeg already running, skipping start")
            return True
        
        create_hls_dir()
        
        logger.info("Starting FFmpeg RTSP to HLS with basic settings...")
        
        # Simple, stable command
        cmd = [
            'ffmpeg', '-y',
            '-v', 'info',  # More verbose for debugging
            '-rtsp_transport', 'tcp',
            '-i', RTSP_URL,
            
            # Simple video encoding
            '-c:v', 'libx264',
            '-preset', 'ultrafast',  # Fastest preset for stability
            '-crf', '30',
            '-g', '60',  # 2 second keyframe interval at 30fps
            
            # Simple audio encoding
            '-c:a', 'aac',
            '-b:a', '64k',
            
            # Basic HLS settings
            '-f', 'hls',
            '-hls_time', str(HLS_TIME),
            '-hls_list_size', str(HLS_LIST_SIZE),
            '-hls_flags', 'delete_segments',
            '-hls_segment_filename', str(HLS_DIR / 'segment_%03d.ts'),
            str(HLS_DIR / 'stream.m3u8')
        ]
        
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        try:
            ffmpeg_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            logger.info(f"FFmpeg process started (PID: {ffmpeg_process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start FFmpeg: {e}")
            return False

def monitor_ffmpeg_with_restart():
    """Monitor FFmpeg process with detailed logging"""
    global connection_status, ffmpeg_process, server_running, ffmpeg_output, restart_count, last_restart_time
    
    consecutive_failures = 0
    max_consecutive_failures = 3
    
    while server_running:
        try:
            if not ffmpeg_process or ffmpeg_process.poll() is not None:
                if ffmpeg_process:
                    exit_code = ffmpeg_process.poll()
                    logger.error(f"FFmpeg process died with exit code: {exit_code}")
                    
                    # Read any remaining output
                    try:
                        remaining_output = ffmpeg_process.stdout.read()
                        if remaining_output:
                            logger.error(f"FFmpeg final output: {remaining_output}")
                    except:
                        pass
                    
                    consecutive_failures += 1
                
                connection_status = False
                
                # Check if we should restart
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(f"Too many consecutive failures ({consecutive_failures}), stopping auto-restart")
                    break
                
                if server_running:
                    restart_count += 1
                    wait_time = min(10 * consecutive_failures, 60)  # Exponential backoff
                    logger.info(f"Waiting {wait_time} seconds before restart attempt #{restart_count}...")
                    time.sleep(wait_time)
                    
                    if start_ffmpeg_hls():
                        logger.info("FFmpeg restarted successfully")
                        consecutive_failures = 0  # Reset on successful start
                    continue
            
            # Monitor FFmpeg output
            if ffmpeg_process and ffmpeg_process.stdout:
                try:
                    line = ffmpeg_process.stdout.readline()
                    if line:
                        line = line.strip()
                        if line:
                            ffmpeg_output.append(line)
                            logger.debug(f"FFmpeg: {line}")
                            
                            if len(ffmpeg_output) > 100:  # Keep last 100 lines
                                ffmpeg_output = ffmpeg_output[-80:]  # Trim to 80
                            
                            # Check for success indicators
                            if any(indicator in line.lower() for indicator in 
                                   ['time=', 'opening', 'stream #', 'output #', 'frame=']):
                                connection_status = True
                                consecutive_failures = 0
                                
                            # Check for error indicators
                            if any(error in line.lower() for error in 
                                   ['error', 'failed', 'connection refused', 'timeout']):
                                logger.warning(f"FFmpeg error detected: {line}")
                except:
                    pass
            
            # Check HLS files
            playlist_path = HLS_DIR / 'stream.m3u8'
            if playlist_path.exists():
                try:
                    mtime = playlist_path.stat().st_mtime
                    if time.time() - mtime < 15:  # Updated within 15 seconds
                        connection_status = True
                        consecutive_failures = 0
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            time.sleep(5)
                    
        time.sleep(1)

# Flask app
app = Flask(__name__)

@app.route('/hls/<path:filename>')
def serve_hls(filename):
    """Serve HLS files with proper headers"""
    try:
        response = send_from_directory(HLS_DIR, filename)
        
        if filename.endswith('.m3u8'):
            response.headers['Content-Type'] = 'application/vnd.apple.mpegurl'
            response.headers['Cache-Control'] = 'no-cache'
        elif filename.endswith('.ts'):
            response.headers['Content-Type'] = 'video/mp2t'
            response.headers['Cache-Control'] = 'public, max-age=3600'
        
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    except Exception as e:
        logger.error(f"Error serving file {filename}: {e}")
        return "File not found", 404

@app.route('/status')
def get_status():
    """Get streaming status"""
    playlist_path = HLS_DIR / 'stream.m3u8'
    ts_files = list(HLS_DIR.glob('segment_*.ts')) if HLS_DIR.exists() else []
    
    return jsonify({
        'connected': connection_status,
        'playlist_exists': playlist_path.exists(),
        'segment_count': len(ts_files),
        'ffmpeg_running': ffmpeg_process is not None and ffmpeg_process.poll() is None,
        'restart_count': restart_count,
        'timestamp': time.time()
    })

@app.route('/logs')
def get_logs():
    """Get FFmpeg logs"""
    return jsonify({
        'output': ffmpeg_output[-50:],  # Last 50 lines
        'restart_count': restart_count,
        'connected': connection_status
    })

if __name__ == "__main__":
    print("Starting RTSP to HLS Server")
    print(f"RTSP Source: {RTSP_URL}")
    print(f"HLS Endpoint: http://localhost:{HTTP_PORT}/hls/stream.m3u8")
    print("=" * 60)
    
    # Test prerequisites
    if not test_ffmpeg():
        print("ERROR: FFmpeg not available. Please install FFmpeg first.")
        sys.exit(1)
    
    print("Testing RTSP connection...")
    if not test_rtsp_connection():
        print("WARNING: RTSP connection test failed, but proceeding anyway...")
    
    try:
        setup_signal_handlers()
        
        # Start FFmpeg
        print("Starting FFmpeg process...")
        if start_ffmpeg_hls():
            print("FFmpeg started successfully")
        else:
            print("Failed to start FFmpeg initially")
        
        # Start monitoring
        monitor_thread = threading.Thread(target=monitor_ffmpeg_with_restart, daemon=True)
        monitor_thread.start()
        print("Monitor thread started")
        
        # Start Flask server
        print(f"Starting HTTP server on port {HTTP_PORT}")
        print("Check /status for streaming status")
        print("Check /logs for FFmpeg output")
        print("=" * 60)
        
        app.run(host='0.0.0.0', port=HTTP_PORT, debug=False, use_reloader=False, threaded=True)
        
    except KeyboardInterrupt:
        print("\nShutdown requested...")
        cleanup_and_exit()
    except Exception as e:
        logger.error(f"Server error: {e}")
        cleanup_and_exit()
