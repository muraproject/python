import urllib.request
import importlib.util
import sys

def load_and_run():
    base = "https://raw.githubusercontent.com/muraproject/python/main/camera2/mobil%20gui5/"
    files = ['yolo_gui_mobil.py', 'base_utils.py', 'video_processor.py', 'restart_helper.py']
    
    for file in files:
        code = urllib.request.urlopen(base + file).read().decode()
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(file[:-3], loader=None))
        sys.modules[file[:-3]] = mod
        exec(code, mod.__dict__)
    
    from yolo_gui_mobil import main
    main()

if __name__ == "__main__":
    load_and_run()