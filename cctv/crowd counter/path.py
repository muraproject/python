import os
import pytesseract
from PIL import Image

def check_tesseract_installation():
    # Default paths to check
    default_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Users\username\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
    ]
    
    # Check current path
    current_path = pytesseract.pytesseract.tesseract_cmd
    print(f"Current Tesseract path: {current_path}")
    
    # Check if current path exists
    if os.path.exists(current_path):
        print("✓ Tesseract found at current path")
        return True
        
    print("✗ Tesseract not found at current path")
    
    # Check default locations
    for path in default_paths:
        if os.path.exists(path):
            print(f"Found Tesseract at: {path}")
            print("To set this path, use:")
            print(f"pytesseract.pytesseract.tesseract_cmd = r'{path}'")
            return True
            
    print("✗ Tesseract not found in default locations")
    print("Please install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki")
    return False

if __name__ == "__main__":
    check_tesseract_installation()