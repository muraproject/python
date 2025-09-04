import cv2
import numpy as np
import os
import glob
import json

class HSVColorTracker:
    def __init__(self):
        # Default HSV values
        self.lower_h = 0
        self.lower_s = 0
        self.lower_v = 0
        self.upper_h = 179
        self.upper_s = 255
        self.upper_v = 255
        
        # Click point variables
        self.click_point = None
        self.point_is_green = False
        self.counter = 0
        self.previous_point_was_green = False
        self.settings_file = "tracker_settings.json"
        
        self.load_settings()
        self.setup_trackbars()
        
    def load_settings(self):
        """Load saved settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.click_point = settings.get('click_point')
                    self.counter = settings.get('counter', 0)
                    print(f"✅ Settings loaded: Point={self.click_point}, Counter={self.counter}")
        except Exception as e:
            print(f"⚠️  Could not load settings: {e}")
    
    def save_settings(self):
        """Save current settings to file"""
        try:
            settings = {
                'click_point': self.click_point,
                'counter': self.counter
            }
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            print(f"⚠️  Could not save settings: {e}")
        
    def setup_trackbars(self):
        """Setup window dan trackbars untuk kontrol HSV"""
        cv2.namedWindow('HSV Controls', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('HSV Controls', 500, 400)
        
        # Buat trackbars
        cv2.createTrackbar('Lower H', 'HSV Controls', self.lower_h, 179, self.nothing)
        cv2.createTrackbar('Lower S', 'HSV Controls', self.lower_s, 255, self.nothing)
        cv2.createTrackbar('Lower V', 'HSV Controls', self.lower_v, 255, self.nothing)
        cv2.createTrackbar('Upper H', 'HSV Controls', self.upper_h, 179, self.nothing)
        cv2.createTrackbar('Upper S', 'HSV Controls', self.upper_s, 255, self.nothing)
        cv2.createTrackbar('Upper V', 'HSV Controls', self.upper_v, 255, self.nothing)
        
        # Preset buttons
        cv2.createTrackbar('PRESET: WHITE', 'HSV Controls', 0, 1, self.preset_white)
        cv2.createTrackbar('PRESET: BRIGHT WHITE', 'HSV Controls', 0, 1, self.preset_bright_white)
        cv2.createTrackbar('PRESET: RESET ALL', 'HSV Controls', 0, 1, self.preset_reset)
        
        print("✅ HSV Controls window created with 6 trackbars")
        
    def nothing(self, val):
        """Callback function untuk trackbars (tidak perlu melakukan apa-apa)"""
        pass
    
    def mouse_callback(self, event, x, y, flags, param):
        """Mouse callback untuk menangkap klik"""
        if event == cv2.EVENT_LBUTTONDOWN:
            # Adjust x coordinate karena kita menampilkan 2 frame bersamaan
            # Hanya ambil klik di frame kiri (original video)
            frame_width = param.shape[1] // 2 if param is not None else 640
            if x < frame_width:
                self.click_point = (x, y)
                self.point_is_green = False  # Reset ke merah saat klik baru
                self.previous_point_was_green = False
                print(f"🖱️  Point clicked at: ({x}, {y})")
                self.save_settings()
    
    def preset_white(self, val):
        """Preset untuk tracking warna putih/abu-abu terang"""
        if val == 1:
            cv2.setTrackbarPos('Lower H', 'HSV Controls', 0)
            cv2.setTrackbarPos('Lower S', 'HSV Controls', 0)
            cv2.setTrackbarPos('Lower V', 'HSV Controls', 180)
            cv2.setTrackbarPos('Upper H', 'HSV Controls', 179)
            cv2.setTrackbarPos('Upper S', 'HSV Controls', 50)
            cv2.setTrackbarPos('Upper V', 'HSV Controls', 255)
            print("🤍 PRESET WHITE: H(0-179) S(0-50) V(180-255)")
            cv2.setTrackbarPos('PRESET: WHITE', 'HSV Controls', 0)
    
    def preset_bright_white(self, val):
        """Preset untuk tracking warna putih sangat terang"""
        if val == 1:
            cv2.setTrackbarPos('Lower H', 'HSV Controls', 0)
            cv2.setTrackbarPos('Lower S', 'HSV Controls', 0)
            cv2.setTrackbarPos('Lower V', 'HSV Controls', 220)
            cv2.setTrackbarPos('Upper H', 'HSV Controls', 179)
            cv2.setTrackbarPos('Upper S', 'HSV Controls', 30)
            cv2.setTrackbarPos('Upper V', 'HSV Controls', 255)
            print("⚪ PRESET BRIGHT WHITE: H(0-179) S(0-30) V(220-255)")
            cv2.setTrackbarPos('PRESET: BRIGHT WHITE', 'HSV Controls', 0)
    
    def preset_reset(self, val):
        """Reset ke semua warna"""
        if val == 1:
            cv2.setTrackbarPos('Lower H', 'HSV Controls', 0)
            cv2.setTrackbarPos('Lower S', 'HSV Controls', 0)
            cv2.setTrackbarPos('Lower V', 'HSV Controls', 0)
            cv2.setTrackbarPos('Upper H', 'HSV Controls', 179)
            cv2.setTrackbarPos('Upper S', 'HSV Controls', 255)
            cv2.setTrackbarPos('Upper V', 'HSV Controls', 255)
            print("🔄 RESET: Menampilkan semua warna")
            cv2.setTrackbarPos('PRESET: RESET ALL', 'HSV Controls', 0)
        
    def update_hsv_values(self):
        """Update HSV values dari trackbars"""
        self.lower_h = cv2.getTrackbarPos('Lower H', 'HSV Controls')
        self.lower_s = cv2.getTrackbarPos('Lower S', 'HSV Controls')
        self.lower_v = cv2.getTrackbarPos('Lower V', 'HSV Controls')
        self.upper_h = cv2.getTrackbarPos('Upper H', 'HSV Controls')
        self.upper_s = cv2.getTrackbarPos('Upper S', 'HSV Controls')
        self.upper_v = cv2.getTrackbarPos('Upper V', 'HSV Controls')
        
    def get_video_files(self, folder_path):
        """Dapatkan list file video dari folder"""
        extensions = ['*.mp4', '*.avi', '*.mov', '*.mkv', '*.wmv', '*.flv', '*.m4v']
        video_files = []
        
        for ext in extensions:
            video_files.extend(glob.glob(os.path.join(folder_path, ext)))
            
        return video_files
        
    def create_hsv_mask(self, frame):
        """Buat HSV mask dari frame"""
        # Convert BGR ke HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Update HSV values dari trackbars
        self.update_hsv_values()
        
        # Buat lower dan upper range
        lower_range = np.array([self.lower_h, self.lower_s, self.lower_v])
        upper_range = np.array([self.upper_h, self.upper_s, self.upper_v])
        
        # Buat mask
        mask = cv2.inRange(hsv, lower_range, upper_range)
        
        # Hitung statistik
        white_pixels = cv2.countNonZero(mask)
        total_pixels = mask.shape[0] * mask.shape[1]
        coverage_percent = (white_pixels / total_pixels) * 100
        
        return mask, coverage_percent
    
    def check_point_in_mask(self, mask):
        """Check if click point is in black area of mask and update counter"""
        if self.click_point is None:
            return
        
        x, y = self.click_point
        if 0 <= x < mask.shape[1] and 0 <= y < mask.shape[0]:
            # Check pixel value at point location
            pixel_value = mask[y, x]
            
            # If pixel is black (0), point should be green
            # If pixel is white (255), point should be red
            current_point_should_be_green = (pixel_value == 0)
            
            # Count transition from red to green (when point enters black area)
            if current_point_should_be_green and not self.previous_point_was_green:
                self.counter += 1
                print(f"🎯 Counter: {self.counter}")
                self.save_settings()
            
            self.point_is_green = current_point_should_be_green
            self.previous_point_was_green = current_point_should_be_green
    
    def draw_click_point(self, frame):
        """Draw the click point on frame"""
        if self.click_point is None:
            return
        
        x, y = self.click_point
        
        # Choose color: green if in black area, red if in white area
        color = (0, 255, 0) if self.point_is_green else (0, 0, 255)  # Green or Red
        
        # Draw bold circle
        cv2.circle(frame, (x, y), 8, color, -1)  # Filled circle
        cv2.circle(frame, (x, y), 10, (255, 255, 255), 2)  # White border
        
        # Draw small cross in center
        cv2.line(frame, (x-4, y), (x+4, y), (255, 255, 255), 2)
        cv2.line(frame, (x, y-4), (x, y+4), (255, 255, 255), 2)
        
    def add_text_info(self, frame, coverage_percent):
        """Tambahkan informasi text ke frame"""
        info_lines = [
            f"HSV Range: H({self.lower_h}-{self.upper_h}) S({self.lower_s}-{self.upper_s}) V({self.lower_v}-{self.upper_v})",
            f"Tracked Area: {coverage_percent:.1f}%",
            f"Counter: {self.counter} | Point: {'GREEN' if self.point_is_green else 'RED'} | Click to set point",
            "WHITE area in mask = Your target color",
            "For WHITE objects: Low S(0-50) + High V(180-255)",
            "Use PRESET buttons for quick white tracking"
        ]
        
        # Tambahkan background gelap untuk text
        overlay = frame.copy()
        cv2.rectangle(overlay, (5, 5), (650, 165), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Tambahkan text
        for i, line in enumerate(info_lines):
            y_pos = 30 + i * 25
            cv2.putText(frame, line, (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
    def run(self, video_folder="videos"):
        """Jalankan HSV color tracker"""
        # Cari video files
        video_files = self.get_video_files(video_folder)
        
        if not video_files:
            print(f"❌ Tidak ada video ditemukan di folder '{video_folder}'")
            print("📁 Letakkan file video (.mp4, .avi, dll) di folder tersebut")
            return
            
        print(f"🎥 Ditemukan {len(video_files)} video:")
        for i, video in enumerate(video_files, 1):
            print(f"  {i}. {os.path.basename(video)}")
            
        print("\n🚀 Memulai HSV Color Tracker...")
        print("🎛️  Gunakan trackbars di window 'HSV Controls' untuk adjust warna")
        print("⚪ Area PUTIH di mask = warna yang ditrack")
        print("⚫ Area HITAM di mask = warna yang diabaikan")
        print("🖱️  KLIK di video untuk set point tracking")
        print("🔴 Point MERAH = di area putih mask")  
        print("🟢 Point HIJAU = di area hitam mask")
        print("🎯 Counter bertambah saat point berubah dari merah ke hijau")
        print()
        
        # Process each video
        for video_path in video_files:
            print(f"▶️  Memulai: {os.path.basename(video_path)}")
            
            # Buka video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"❌ Tidak bisa membuka: {video_path}")
                continue
                
            # Dapatkan FPS
            fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
            frame_delay = max(1, int(1000 / fps))
            
            # Flag untuk setup mouse callback sekali saja
            mouse_callback_set = False
            
            # Main loop untuk video
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("✅ Video selesai")
                    break
                    
                # Resize frame jika terlalu besar
                height, width = frame.shape[:2]
                if width > 640:
                    scale = 640 / width
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (640, new_height))
                    
                # Buat HSV mask
                mask, coverage_percent = self.create_hsv_mask(frame)
                
                # Check point status in mask
                self.check_point_in_mask(mask)
                
                # Siapkan frame untuk display
                display_frame = frame.copy()
                self.add_text_info(display_frame, coverage_percent)
                
                # Draw click point on original frame
                self.draw_click_point(display_frame)
                
                # Convert mask ke BGR untuk display
                mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                
                # Draw click point on mask frame too
                self.draw_click_point(mask_bgr)
                
                # Tambahkan label pada masing-masing panel
                cv2.putText(display_frame, "ORIGINAL VIDEO - CLICK TO SET POINT", (10, frame.shape[0] - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(mask_bgr, "HSV MASK (WHITE = TRACKED COLOR)", (10, frame.shape[0] - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # Gabungkan frame secara horizontal
                combined_frame = np.hstack([display_frame, mask_bgr])
                
                # Tampilkan hasil
                cv2.imshow('HSV Color Tracker - Original | Mask (White = Tracked)', combined_frame)
                
                # Set mouse callback hanya sekali setelah window dibuat
                if not mouse_callback_set:
                    cv2.setMouseCallback('HSV Color Tracker - Original | Mask (White = Tracked)', self.mouse_callback, combined_frame)
                    mouse_callback_set = True
                
                # Handle keyboard input
                key = cv2.waitKey(frame_delay) & 0xFF
                
                if key == ord('q'):
                    print("🛑 Quit - Program dihentikan")
                    cap.release()
                    cv2.destroyAllWindows()
                    return
                elif key == ord(' '):
                    print("⏸️  Paused - Press any key to continue...")
                    cv2.waitKey(0)
                elif key == ord('r'):
                    print("🔄 Reset - Menampilkan semua warna")
                    cv2.setTrackbarPos('Lower H', 'HSV Controls', 0)
                    cv2.setTrackbarPos('Lower S', 'HSV Controls', 0) 
                    cv2.setTrackbarPos('Lower V', 'HSV Controls', 0)
                    cv2.setTrackbarPos('Upper H', 'HSV Controls', 179)
                    cv2.setTrackbarPos('Upper S', 'HSV Controls', 255)
                    cv2.setTrackbarPos('Upper V', 'HSV Controls', 255)
                elif key == ord('n'):
                    print("⏭️  Next - Lanjut ke video berikutnya")
                    break
                elif key == ord('c'):
                    print(f"🎯 Reset Counter - Counter reset dari {self.counter} ke 0")
                    self.counter = 0
                    self.save_settings()
                    
            cap.release()
            
        print("🎉 Semua video selesai diproses!")
        cv2.destroyAllWindows()

def main():
    # Buat folder videos jika belum ada
    if not os.path.exists("videos"):
        os.makedirs("videos")
        print("📁 Folder 'videos' telah dibuat")
        print("🎥 Silakan letakkan file video di folder tersebut")
        return
        
    print("=" * 60)
    print("🎯 HSV COLOR TRACKER with CLICK POINT COUNTER")
    print("=" * 60)
    print()
    print("📖 PENJELASAN:")
    print("• Program ini menampilkan video asli dan HSV mask secara bersamaan")
    print("• Area PUTIH di mask = warna yang berhasil ditrack")
    print("• Area HITAM di mask = warna yang diabaikan")
    print("• KLIK di video kiri untuk set point tracking")
    print()
    print("🎯 FITUR CLICK POINT:")
    print("• 🔴 Point MERAH = berada di area putih mask")
    print("• 🟢 Point HIJAU = berada di area hitam mask") 
    print("• Counter bertambah +1 setiap point berubah dari MERAH ke HIJAU")
    print("• Setting point dan counter tersimpan otomatis")
    print()
    print("🎛️  CARA MENGGUNAKAN TRACKBARS:")
    print("• Lower H/S/V: Batas bawah range warna")
    print("• Upper H/S/V: Batas atas range warna")
    print("• Semakin sempit range = semakin spesifik warna yang ditrack")
    print()
    print("🌈 PANDUAN WARNA HSV:")
    print("• PUTIH:   H(0-179)   S(0-50)     V(180-255)  ← WARNA ANDA!")
    print("• Putih Terang: H(0-179) S(0-30)   V(220-255)  ← Sangat terang")
    print("• Merah:   H(0-10)    S(120-255)  V(70-255)")
    print("• Orange:  H(10-25)   S(100-255)  V(100-255)")  
    print("• Kuning:  H(25-35)   S(100-255)  V(100-255)")
    print("• Hijau:   H(40-80)   S(100-255)  V(50-255)")
    print("• Biru:    H(100-130) S(100-255)  V(50-255)")
    print()
    print("🤍 KHUSUS TRACKING PUTIH:")
    print("• H (Hue): Tidak penting untuk putih (0-179 OK)")
    print("• S (Saturation): RENDAH (0-50) - putih tidak jenuh")
    print("• V (Value): TINGGI (180-255) - putih sangat terang")
    print("• Gunakan preset 'WHITE' atau 'BRIGHT WHITE' untuk mudah!")
    print()
    print("⌨️  KONTROL:")
    print("• 🖱️  Left Click = Set tracking point")
    print("• Trackbars: Manual adjustment HSV")
    print("• Preset buttons: Klik preset untuk auto-set")
    print("• 'q' = Quit (keluar)")
    print("• 'space' = Pause/Resume")  
    print("• 'r' = Reset trackbars (tampilkan semua warna)")
    print("• 'n' = Next video")
    print("• 'c' = Reset counter ke 0")
    print()
    print("💡 TIPS TRACKING PUTIH:")
    print("• Gunakan preset 'WHITE' sebagai starting point")
    print("• Jika background hijau/biru ikut ketrack → turunkan Upper V")
    print("• Jika objek putih hilang → naikkan Lower V atau Upper S") 
    print("• Pencahayaan penting: area terang bisa kedeteksi sebagai putih")
    print("• Background hijau/biru tidak akan ketrack karena S tinggi")
    print()
    print("🎛️  PRESET BUTTONS:")
    print("• 'PRESET: WHITE' = Setting umum untuk putih")
    print("• 'PRESET: BRIGHT WHITE' = Hanya putih sangat terang")
    print("• 'PRESET: RESET ALL' = Reset ke semua warna")
    print("=" * 60)
    
    # Jalankan tracker
    tracker = HSVColorTracker()
    tracker.run("videos")

if __name__ == "__main__":
    main()