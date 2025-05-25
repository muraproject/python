import requests
import base64
import importlib.util
import sys
import os

def load_github_files():
    base_url = "https://raw.githubusercontent.com/muraproject/python/main/camera2/mobil%20gui5/"
    files = [
        'yolo_gui_mobil.py',
        'base_utils.py',
        'video_processor.py',
        'restart_helper.py'
    ]
    
    try:
        for file in files:
            response = requests.get(base_url + file)
            response.raise_for_status()
            
            # Eksekusi kode
            code = response.text
            spec = importlib.util.spec_from_loader(
                file[:-3],  # Hapus .py
                loader=None, 
                origin=file
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[file[:-3]] = module
            exec(code, module.__dict__)
            
        # Jalankan main program
        from yolo_gui_mobil import main
        main()
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    load_github_files()