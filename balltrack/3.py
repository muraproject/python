import cv2
import numpy as np
import os
import glob

class SimpleHSVTracker:
    def __init__(self):
        # Default HSV values - lebih toleran
        self.lower_h = 0
        self.lower_s = 0
        self.lower_v = 0
        self.upper_h = 179
        self.upper_s = 255
        self.upper_v = 255
        
        # Setup trackbars
        self.setup_trackbars()
        
    def setup_trackbars(self):
        """Setup trackbars untuk kontrol HSV"""
        cv2.namedWindow('HSV Controls', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('HSV Controls', 400, 300)
        
        # Trackbars untuk HSV range
        cv2.createTrackbar('Lower H', 'HSV Controls', self.lower_h, 179, self.on_trackbar)
        cv2.createTrackbar('Lower S', 'HSV Controls', self.lower_s, 255, self.on_trackbar)
        cv2.createTrackbar('Lower V', 'HSV Controls', self.lower_v, 255, self.on_trackbar)
        cv2.createTrackbar('Upper H', 'HSV Controls', self.upper_h, 179, self.on_trackbar)
        cv2.createTrackbar('Upper S', 'HSV Controls', self.upper_s, 255, self.on_trackbar)
        cv2.createTrackbar('Upper V', 'HSV Controls', self.upper_v, 255, self.on_trackbar)
        
        print("Trackbars setup complete. Adjust sliders to filter colors.")
        
    def on_trackbar(self, val):
        """Update HSV values dari trackbars"""
        self.lower_h = cv2.getTrackbarPos('Lower H', 'HSV Controls')
        self.lower_s = cv2.getTrackbarPos('Lower S', 'HSV Controls')
        self.lower_v = cv2.getTrackbarPos('Lower V', 'HSV Controls')
        self.upper_h = cv2.getTrackbarPos('Upper H', 'HSV Controls')
        self.upper_s = cv2.getTrackbarPos('Upper S', 'HSV Controls')
        self.upper_v = cv2.getTrackbarPos('Upper V', 'HSV Controls')
        
    def get_video_files(self, folder_path):
        """Ambil file video dari folder"""
        video_extensions = ['*.mp4', '*.avi', '*.mov', '*.mkv', '*.wmv', '*.flv']
        video_files = []
        
        for extension in video_extensions:
            video_files.extend(glob.glob(os.path.join(folder_path, extension)))
        
        return video_files
    
    def process_frame(self, frame):
        """Proses frame untuk HSV filtering"""
        # Convert ke HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Buat HSV range
        lower_range = np.array([self.lower_h, self.lower_s, self.lower_v])
        upper_range = np.array([self.upper_h, self.upper_s, self.upper_v])
        
        # Buat mask
        mask = cv2.inRange(hsv, lower_range, upper_range)
        
        # Hitung statistik untuk debugging
        white_pixels = cv2.countNonZero(mask)
        total_pixels = mask.shape[0] * mask.shape[1]
        white_percentage = (white_pixels / total_pixels) * 100
        
        return mask, white_percentage
    
    def add_info_to_frame(self, frame, white_percentage):
        """Tambahkan info ke frame"""
        info_text = [
            f"HSV Range: H({self.lower_h}-{self.upper_h}) S({self.lower_s}-{self.upper_s}) V({self.lower_v}-{self.upper_v})",
            f"Mask Coverage: {white_percentage:.1f}%",
            "Adjust sliders in 'HSV Controls' window",
            "Press 'q' to quit, 'space' to pause"
        ]
        
        for i, text in enumerate(info_text):
            y_pos = 25 + i * 25
            # Background putih untuk text
            cv2.putText(frame, text, (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 3)
            # Text hitam di atas
            cv2.putText(frame, text, (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
    
    def run(self, folder_path="videos"):
        """Jalankan tracker"""
        # Cari file video
        video_files = self.get_video_files(folder_path)
        
        if not video_files:
            print(f"Tidak ada video ditemukan di folder '{folder_path}'")
            print("Letakkan file video (.mp4, .avi, dll) di folder tersebut")
            return
            
        print(f"Ditemukan {len(video_files)} video:")
        for i, video in enumerate(video_files):
            print(f"{i+1}. {os.path.basename(video)}")
            
        # Proses setiap video
        for video_path in video_files:
            print(f"\nMemulai video: {os.path.basename(video_path)}")
            
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"Error: Tidak bisa buka {video_path}")
                continue
                
            # Get FPS untuk timing
            fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
            frame_delay = int(1000 / fps)
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("Video selesai")
                    break
                
                # Resize jika terlalu besar
                height, width = frame.shape[:2]
                if width > 640:
                    scale = 640 / width
                    new_width = 640
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))
                
                # Proses frame untuk HSV mask
                mask, white_percentage = self.process_frame(frame)
                
                # Tambahkan info ke frame original
                info_frame = frame.copy()
                self.add_info_to_frame(info_frame, white_percentage)
                
                # Convert mask ke 3 channel untuk display
                mask_colored = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                
                # Gabung frame original dan mask secara horizontal
                combined = np.hstack([info_frame, mask_colored])
                
                # Tampilkan
                cv2.imshow('Original Video | HSV Mask', combined)
                
                # Handle keyboard
                key = cv2.waitKey(frame_delay) & 0xFF
                if key == ord('q'):
                    cap.release()
                    cv2.destroyAllWindows()
                    return
                elif key == ord(' '):  # Pause
                    print("Paused. Press any key to continue...")
                    cv2.waitKey(0)
                elif key == ord('r'):  # Reset HSV
                    print("Reset HSV to show all colors")
                    cv2.setTrackbarPos('Lower H', 'HSV Controls', 0)
                    cv2.setTrackbarPos('Lower S', 'HSV Controls', 0)
                    cv2.setTrackbarPos('Lower V', 'HSV Controls', 0)
                    cv2.setTrackbarPos('Upper H', 'HSV Controls', 179)
                    cv2.setTrackbarPos('Upper S', 'HSV Controls', 255)
                    cv2.setTrackbarPos('Upper V', 'HSV Controls', 255)
            
            cap.release()
            
        print("Semua video selesai")
        cv2.destroyAllWindows()

def main():
    # Buat folder videos jika belum ada
    if not os.path.exists("videos"):
        os.makedirs("videos")
        print("Folder 'videos' dibuat. Masukkan file video ke dalamnya.")
        return
    
    print("=== Simple HSV Color Tracker ===")
    print("Fitur:")
    print("- Video player dengan HSV mask")
    print("- 6 slider untuk kontrol HSV range")
    print("- Real-time filtering")
    print("- Statistik coverage mask")
    print()
    print("Cara pakai:")
    print("1. Jalankan program")
    print("2. Adjust slider di window 'HSV Controls':")
    print("   - Lower H/S/V: Batas bawah warna")
    print("   - Upper H/S/V: Batas atas warna")
    print("3. Lihat hasilnya real-time!")
    print()
    print("Tips HSV:")
    print("- H (Hue): Jenis warna (Red=0-10, Orange=10-25, Yellow=25-35, Green=35-85, Blue=85-130)")
    print("- S (Saturation): Intensitas warna (0=abu-abu, 255=warna cerah)")  
    print("- V (Value): Kecerahan (0=gelap, 255=terang)")
    print()
    print("Kontrol:")
    print("- 'q': Quit")
    print("- 'space': Pause/Resume")
    print("- 'r': Reset HSV (tampilkan semua warna)")
    print()
    
    # Jalankan tracker
    tracker = SimpleHSVTracker()
    tracker.run("videos")

if __name__ == "__main__":
    main()