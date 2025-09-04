import cv2
import numpy as np
import os
import glob

class OrangeBallDetector:
    def __init__(self):
        # Nilai HSV default untuk warna orange
        self.lower_h = 10
        self.lower_s = 100
        self.lower_v = 100
        self.upper_h = 25
        self.upper_s = 255
        self.upper_v = 255
        
        # Setup trackbars
        self.setup_trackbars()
        
    def setup_trackbars(self):
        """Setup trackbars untuk kalibrasi HSV"""
        cv2.namedWindow('HSV Calibration', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('HSV Calibration', 400, 300)
        
        # Trackbars untuk Lower HSV
        cv2.createTrackbar('Lower H', 'HSV Calibration', self.lower_h, 179, self.on_trackbar)
        cv2.createTrackbar('Lower S', 'HSV Calibration', self.lower_s, 255, self.on_trackbar)
        cv2.createTrackbar('Lower V', 'HSV Calibration', self.lower_v, 255, self.on_trackbar)
        
        # Trackbars untuk Upper HSV
        cv2.createTrackbar('Upper H', 'HSV Calibration', self.upper_h, 179, self.on_trackbar)
        cv2.createTrackbar('Upper S', 'HSV Calibration', self.upper_s, 255, self.on_trackbar)
        cv2.createTrackbar('Upper V', 'HSV Calibration', self.upper_v, 255, self.on_trackbar)
        
        # Trackbar untuk morphology
        cv2.createTrackbar('Erosion', 'HSV Calibration', 2, 10, self.on_trackbar)
        cv2.createTrackbar('Dilation', 'HSV Calibration', 2, 10, self.on_trackbar)
        
    def on_trackbar(self, val):
        """Callback function untuk trackbars"""
        self.lower_h = cv2.getTrackbarPos('Lower H', 'HSV Calibration')
        self.lower_s = cv2.getTrackbarPos('Lower S', 'HSV Calibration')
        self.lower_v = cv2.getTrackbarPos('Lower V', 'HSV Calibration')
        self.upper_h = cv2.getTrackbarPos('Upper H', 'HSV Calibration')
        self.upper_s = cv2.getTrackbarPos('Upper S', 'HSV Calibration')
        self.upper_v = cv2.getTrackbarPos('Upper V', 'HSV Calibration')
    
    def get_video_files(self, folder_path):
        """Ambil semua file video dari folder"""
        video_extensions = ['*.mp4', '*.avi', '*.mov', '*.mkv', '*.wmv', '*.flv']
        video_files = []
        
        for extension in video_extensions:
            video_files.extend(glob.glob(os.path.join(folder_path, extension)))
        
        return video_files
    
    def process_frame(self, frame):
        """Proses frame untuk deteksi HSV"""
        # Convert BGR ke HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Buat range HSV
        lower_orange = np.array([self.lower_h, self.lower_s, self.lower_v])
        upper_orange = np.array([self.upper_h, self.upper_s, self.upper_v])
        
        # Buat mask
        mask = cv2.inRange(hsv, lower_orange, upper_orange)
        
        # Morphological operations untuk mengurangi noise
        erosion_size = cv2.getTrackbarPos('Erosion', 'HSV Calibration')
        dilation_size = cv2.getTrackbarPos('Dilation', 'HSV Calibration')
        
        if erosion_size > 0:
            kernel_erosion = np.ones((erosion_size, erosion_size), np.uint8)
            mask = cv2.erode(mask, kernel_erosion, iterations=1)
        
        if dilation_size > 0:
            kernel_dilation = np.ones((dilation_size, dilation_size), np.uint8)
            mask = cv2.dilate(mask, kernel_dilation, iterations=1)
        
        # Apply mask ke frame original
        result = cv2.bitwise_and(frame, frame, mask=mask)
        
        return mask, result
    
    def display_info(self, frame):
        """Tampilkan informasi HSV values di frame"""
        info_text = [
            f"Lower HSV: ({self.lower_h}, {self.lower_s}, {self.lower_v})",
            f"Upper HSV: ({self.upper_h}, {self.upper_s}, {self.upper_v})",
            "Press 'q' to quit, 'n' for next video, 'r' to restart"
        ]
        
        for i, text in enumerate(info_text):
            cv2.putText(frame, text, (10, 30 + i*25), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, text, (10, 30 + i*25), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
    
    def run(self, folder_path="videos"):
        """Jalankan program deteksi"""
        # Ambil daftar video files
        video_files = self.get_video_files(folder_path)
        
        if not video_files:
            print(f"Tidak ada file video ditemukan di folder '{folder_path}'")
            print("Silakan masukkan file video (.mp4, .avi, .mov, dll) ke dalam folder tersebut")
            return
        
        print(f"Ditemukan {len(video_files)} file video:")
        for i, video in enumerate(video_files):
            print(f"{i+1}. {os.path.basename(video)}")
        
        current_video_idx = 0
        
        while current_video_idx < len(video_files):
            video_path = video_files[current_video_idx]
            print(f"\nMemulai video: {os.path.basename(video_path)}")
            
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                print(f"Error: Tidak dapat membuka video {video_path}")
                current_video_idx += 1
                continue
            
            # Dapatkan properties video
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            frame_delay = int(1000 / fps) if fps > 0 else 30
            
            while True:
                ret, frame = cap.read()
                
                if not ret:
                    print("Video selesai atau error membaca frame")
                    break
                
                # Resize frame jika terlalu besar
                height, width = frame.shape[:2]
                if width > 640:
                    scale = 640 / width
                    new_width = 640
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))
                
                # Proses frame
                mask, result = self.process_frame(frame)
                
                # Buat frame untuk display info
                info_frame = frame.copy()
                self.display_info(info_frame)
                
                # Convert mask ke 3 channel untuk display
                mask_colored = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                
                # Gabungkan display: kiri = original, kanan = result
                left_display = np.hstack([info_frame, mask_colored])
                right_display = np.hstack([result, mask_colored])
                final_display = np.vstack([left_display, right_display])
                
                # Tambahkan label
                cv2.putText(final_display, "Original + Mask", (10, 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(final_display, "Filtered + Mask", (10, final_display.shape[0]//2 + 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                # Tampilkan hasil
                cv2.imshow('Orange Ball Detection', final_display)
                
                # Handle keyboard input
                key = cv2.waitKey(frame_delay) & 0xFF
                if key == ord('q'):
                    cap.release()
                    cv2.destroyAllWindows()
                    return
                elif key == ord('n'):  # Next video
                    break
                elif key == ord('r'):  # Restart current video
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                elif key == ord(' '):  # Pause/resume
                    cv2.waitKey(0)
            
            cap.release()
            current_video_idx += 1
        
        print("Semua video selesai diproses")
        cv2.destroyAllWindows()

def main():
    # Buat folder videos jika belum ada
    if not os.path.exists("videos"):
        os.makedirs("videos")
        print("Folder 'videos' telah dibuat. Silakan masukkan file video ke dalamnya.")
        return
    
    # Inisialisasi detector
    detector = OrangeBallDetector()
    
    print("=== Orange Ball HSV Detector ===")
    print("Kontrol:")
    print("- Gunakan slider di window 'HSV Calibration' untuk menyesuaikan range HSV")
    print("- 'q': Keluar")
    print("- 'n': Video berikutnya") 
    print("- 'r': Restart video saat ini")
    print("- 'space': Pause/Resume")
    print("\nMencari file video di folder 'videos'...")
    
    # Jalankan detector
    detector.run("videos")

if __name__ == "__main__":
    main()