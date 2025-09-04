import cv2
import numpy as np
import os
import glob
import json

class OrangeBallDetector:
    def __init__(self):
        # File untuk menyimpan settings
        self.settings_file = "hsv_settings.json"
        
        # Load settings yang tersimpan atau gunakan default
        self.load_settings()
        
        # Setup trackbars
        self.setup_trackbars()
        
    def load_settings(self):
        """Load settings HSV yang tersimpan"""
        default_settings = {
            "lower_h": 10,
            "lower_s": 100, 
            "lower_v": 100,
            "upper_h": 25,
            "upper_s": 255,
            "upper_v": 255,
            "erosion": 2,
            "dilation": 2,
            "min_area": 100,
            "max_area": 100000
        }
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                print(f"Settings loaded from {self.settings_file}")
            else:
                settings = default_settings
                print("Menggunakan default settings")
        except:
            settings = default_settings
            print("Error loading settings, menggunakan default")
        
        # Assign settings ke variables
        self.lower_h = settings.get("lower_h", 10)
        self.lower_s = settings.get("lower_s", 100)
        self.lower_v = settings.get("lower_v", 100)
        self.upper_h = settings.get("upper_h", 25)
        self.upper_s = settings.get("upper_s", 255)
        self.upper_v = settings.get("upper_v", 255)
        self.erosion = settings.get("erosion", 2)
        self.dilation = settings.get("dilation", 2)
        self.min_area = settings.get("min_area", 100)
        self.max_area = settings.get("max_area", 100000)
        
    def save_settings(self):
        """Simpan settings HSV saat ini"""
        settings = {
            "lower_h": self.lower_h,
            "lower_s": self.lower_s,
            "lower_v": self.lower_v,
            "upper_h": self.upper_h,
            "upper_s": self.upper_s,
            "upper_v": self.upper_v,
            "erosion": self.erosion,
            "dilation": self.dilation,
            "min_area": self.min_area,
            "max_area": self.max_area
        }
        
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
            print(f"Settings disimpan ke {self.settings_file}")
        except Exception as e:
            print(f"Error saving settings: {e}")
        
    def setup_trackbars(self):
        """Setup trackbars untuk kalibrasi HSV"""
        cv2.namedWindow('HSV Calibration', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('HSV Calibration', 450, 400)
        
        # Trackbars untuk Lower HSV
        cv2.createTrackbar('Lower H', 'HSV Calibration', self.lower_h, 179, self.on_trackbar)
        cv2.createTrackbar('Lower S', 'HSV Calibration', self.lower_s, 255, self.on_trackbar)
        cv2.createTrackbar('Lower V', 'HSV Calibration', self.lower_v, 255, self.on_trackbar)
        
        # Trackbars untuk Upper HSV
        cv2.createTrackbar('Upper H', 'HSV Calibration', self.upper_h, 179, self.on_trackbar)
        cv2.createTrackbar('Upper S', 'HSV Calibration', self.upper_s, 255, self.on_trackbar)
        cv2.createTrackbar('Upper V', 'HSV Calibration', self.upper_v, 255, self.on_trackbar)
        
        # Trackbars untuk morphology
        cv2.createTrackbar('Erosion', 'HSV Calibration', self.erosion, 10, self.on_trackbar)
        cv2.createTrackbar('Dilation', 'HSV Calibration', self.dilation, 10, self.on_trackbar)
        
        # Trackbars untuk filter area (dengan range yang lebih luas)
        cv2.createTrackbar('Min Area', 'HSV Calibration', self.min_area//10, 500, self.on_trackbar)
        cv2.createTrackbar('Max Area', 'HSV Calibration', self.max_area//1000, 200, self.on_trackbar)
        
    def on_trackbar(self, val):
        """Callback function untuk trackbars"""
        self.lower_h = cv2.getTrackbarPos('Lower H', 'HSV Calibration')
        self.lower_s = cv2.getTrackbarPos('Lower S', 'HSV Calibration')
        self.lower_v = cv2.getTrackbarPos('Lower V', 'HSV Calibration')
        self.upper_h = cv2.getTrackbarPos('Upper H', 'HSV Calibration')
        self.upper_s = cv2.getTrackbarPos('Upper S', 'HSV Calibration')
        self.upper_v = cv2.getTrackbarPos('Upper V', 'HSV Calibration')
        self.erosion = cv2.getTrackbarPos('Erosion', 'HSV Calibration')
        self.dilation = cv2.getTrackbarPos('Dilation', 'HSV Calibration')
        self.min_area = cv2.getTrackbarPos('Min Area', 'HSV Calibration') * 10
        self.max_area = cv2.getTrackbarPos('Max Area', 'HSV Calibration') * 1000
        
        # Auto save setiap perubahan
        self.save_settings()
    
    def get_video_files(self, folder_path):
        """Ambil semua file video dari folder"""
        video_extensions = ['*.mp4', '*.avi', '*.mov', '*.mkv', '*.wmv', '*.flv']
        video_files = []
        
        for extension in video_extensions:
            video_files.extend(glob.glob(os.path.join(folder_path, extension)))
        
        return video_files
    
    def detect_balls(self, mask):
        """Deteksi objek orange dari mask dan return koordinat center + size"""
        objects = []
        debug_info = []
        
        # Cari contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        debug_info.append(f"Total contours found: {len(contours)}")
        
        for i, contour in enumerate(contours):
            # Hitung area
            area = cv2.contourArea(contour)
            
            # Gunakan bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            
            # Hitung center
            center_x = x + w // 2
            center_y = y + h // 2
            center = (center_x, center_y)
            
            debug_info.append(f"Contour {i}: area={int(area)}, size={w}x{h}")
            
            # Filter yang lebih permissive
            if area > self.min_area and area < self.max_area:
                if w > 5 and h > 5:  # Sangat permissive size filter
                    objects.append({
                        'center': center,
                        'bbox': (x, y, w, h),
                        'area': area,
                        'contour': contour
                    })
                    debug_info.append(f"  -> ACCEPTED!")
                else:
                    debug_info.append(f"  -> REJECTED (size too small)")
            else:
                debug_info.append(f"  -> REJECTED (area filter: {self.min_area}-{self.max_area})")
        
        return objects, debug_info
    
    def process_frame(self, frame):
        """Proses frame untuk deteksi HSV dan tracking"""
        # Convert BGR ke HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Buat range HSV
        lower_orange = np.array([self.lower_h, self.lower_s, self.lower_v])
        upper_orange = np.array([self.upper_h, self.upper_s, self.upper_v])
        
        # Buat mask
        mask = cv2.inRange(hsv, lower_orange, upper_orange)
        
        # Morphological operations untuk mengurangi noise
        if self.erosion > 0:
            kernel_erosion = np.ones((self.erosion, self.erosion), np.uint8)
            mask = cv2.erode(mask, kernel_erosion, iterations=1)
        
        if self.dilation > 0:
            kernel_dilation = np.ones((self.dilation, self.dilation), np.uint8)
            mask = cv2.dilate(mask, kernel_dilation, iterations=1)
        
        # Deteksi objek orange
        objects, debug_info = self.detect_balls(mask)
        
        # Buat frame dengan tracking visualization
        tracked_frame = frame.copy()
        
        for obj in objects:
            center = obj['center']
            bbox = obj['bbox']  # (x, y, w, h)
            area = obj['area']
            contour = obj['contour']
            
            x, y, w, h = bbox
            
            # Gambar rectangle/kotak hijau
            cv2.rectangle(tracked_frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
            
            # Gambar titik tengah merah
            cv2.circle(tracked_frame, center, 6, (0, 0, 255), -1)
            
            # Gambar crosshair merah
            cv2.line(tracked_frame, (center[0]-15, center[1]), (center[0]+15, center[1]), (0, 0, 255), 2)
            cv2.line(tracked_frame, (center[0], center[1]-15), (center[0], center[1]+15), (0, 0, 255), 2)
            
            # Gambar contour untuk detail shape (optional, warna cyan)
            cv2.drawContours(tracked_frame, [contour], -1, (255, 255, 0), 2)
            
            # Tambahkan info text
            info_text = f"Area: {int(area)}"
            size_text = f"Size: {w}x{h}"
            
            # Text dengan background untuk readability
            cv2.putText(tracked_frame, info_text, (x, y-25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            cv2.putText(tracked_frame, info_text, (x, y-25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            cv2.putText(tracked_frame, size_text, (x, y-5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            cv2.putText(tracked_frame, size_text, (x, y-5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        return mask, tracked_frame, len(objects), debug_info
    
    def display_info(self, frame, object_count):
        """Tampilkan informasi di frame"""
        info_text = [
            f"HSV Range: H({self.lower_h}-{self.upper_h}) S({self.lower_s}-{self.upper_s}) V({self.lower_v}-{self.upper_v})",
            f"Objects Detected: {object_count}",
            f"Area Filter: {self.min_area}-{self.max_area}",
            "Controls: 'q'=quit 'n'=next 'r'=restart 's'=save"
        ]
        
        for i, text in enumerate(info_text):
            y_pos = 25 + i*20
            cv2.putText(frame, text, (10, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            cv2.putText(frame, text, (10, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    
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
                if width > 480:
                    scale = 480 / width
                    new_width = 480
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))
                
                # Proses frame
                mask, tracked_frame, object_count, debug_info = self.process_frame(frame)
                
                # Print debug info ke console (opsional)
                if object_count == 0 and len(debug_info) > 1:  # Print hanya jika tidak ada deteksi
                    print("DEBUG:", " | ".join(debug_info[:3]))  # Print beberapa debug info
                
                # Buat frame dengan info
                info_frame = frame.copy()
                self.display_info(info_frame, object_count)
                
                # Convert mask ke 3 channel untuk display
                mask_colored = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                
                # Layout 3 gambar horizontal
                # Gambar 1: Original + info
                # Gambar 2: Mask (hitam putih)
                # Gambar 3: Tracked (original + bulatan)
                
                # Tambahkan label di setiap gambar
                cv2.putText(info_frame, "1. Original", (10, 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(mask_colored, "2. HSV Mask", (10, 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(tracked_frame, "3. Tracking", (10, 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                
                # Gabungkan 3 gambar secara horizontal
                combined_display = np.hstack([info_frame, mask_colored, tracked_frame])
                
                # Tampilkan hasil
                cv2.imshow('Orange Ball Detection - 3 Views', combined_display)
                
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
                elif key == ord('s'):  # Manual save
                    self.save_settings()
                    print("Settings disimpan manual")
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
    
    print("=== Orange Object HSV Detector dengan Auto-Save Settings ===")
    print("Fitur:")
    print("- Settings HSV otomatis tersimpan di 'hsv_settings.json'")
    print("- 3 tampilan: Original | HSV Mask | Tracking")
    print("- Deteksi otomatis dengan kotak hijau, contour cyan, dan titik merah")
    print("- Lebih toleran untuk objek orange yang tidak sempurna bulat")
    print("\nKontrol:")
    print("- Gunakan slider di window 'HSV Calibration'")
    print("- 'q': Keluar")
    print("- 'n': Video berikutnya") 
    print("- 'r': Restart video saat ini")
    print("- 's': Save settings manual")
    print("- 'space': Pause/Resume")
    print("\nMencari file video di folder 'videos'...")
    
    # Jalankan detector
    detector.run("videos")

if __name__ == "__main__":
    main()