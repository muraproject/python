import os
import sys
import subprocess
import time

def restart_app():
    """Helper function to restart the main application"""
    try:
        print("Restarting application...")
        
        # Get current script path
        main_script = os.path.abspath("camera2/mobil gui5/yolo_gui_mobil.py")
        
        # Start new process
        python = sys.executable
        subprocess.Popen([python, main_script])
        
        # Exit current process
        sys.exit(0)
        
    except Exception as e:
        print(f"Error during restart: {e}")
        time.sleep(3)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restart":
        restart_app()