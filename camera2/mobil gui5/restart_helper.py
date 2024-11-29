import os
import sys
import subprocess
import time

def restart_app():
    try:
        print("Restarting application...")
        # Gunakan path absolut dari temporary directory
        main_script = os.path.join(os.path.dirname(sys.argv[0]), "yolo_gui_mobil.py")
        python = sys.executable
        subprocess.Popen([python, main_script])
        sys.exit(0)
    except Exception as e:
        print(f"Error during restart: {e}")
        time.sleep(3)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restart":
        restart_app()