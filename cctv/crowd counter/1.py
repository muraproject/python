import cv2
import pytesseract
import time
import os

# Set Tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def process_video(video_path, roi, interval=5):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(fps * interval)
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        if frame_count % frame_interval != 0:
            continue
            
        # Extract ROI
        x, y, w, h = roi
        roi_frame = frame[y:y+h, x:x+w]
        
        # Process ROI
        gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        
        # OCR
        text = pytesseract.image_to_string(thresh).strip()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {text}")
        
        # Display
        cv2.rectangle(frame, (x,y), (x+w,y+h), (0,255,0), 2)
        cv2.imshow('Frame', frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

# Example usage
roi = (100, 100, 200, 50)  # Adjust coordinates as needed
process_video("jalan.mp4", roi, interval=5)  # Process every 5 seconds