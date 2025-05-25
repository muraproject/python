import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, Label, Button, Frame, Scale, DoubleVar
from PIL import Image, ImageTk
import cv2
import numpy as np
from ultralytics import YOLO
import threading

class WasteDetectionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Aplikasi Deteksi Sampah")
        self.root.geometry("1000x700")
        self.root.configure(bg="#f0f0f0")
        
        # Variabel untuk menyimpan jalur model
        self.model_path = tk.StringVar()
        self.model_path.set("model/best.pt")  # Default path model
        self.model = None
        
        # Variabel untuk menyimpan jalur gambar
        self.image_path = None
        self.current_image = None
        self.detection_results = None
        
        # Variabel untuk threshold confidence
        self.conf_threshold = DoubleVar()
        self.conf_threshold.set(0.25)  # Default threshold 0.25
        self.iou_threshold = DoubleVar()
        self.iou_threshold.set(0.45)  # Default IoU threshold
        
        # Membuat frame utama
        main_frame = Frame(root, bg="#f0f0f0")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Membuat frame untuk kontrol
        control_frame = Frame(main_frame, bg="#f0f0f0")
        control_frame.pack(side=tk.TOP, fill=tk.X, pady=10)
        
        # Tombol untuk memilih model
        self.model_button = Button(
            control_frame, 
            text="Pilih Model", 
            command=self.select_model,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 12),
            padx=10,
            pady=5
        )
        self.model_button.pack(side=tk.LEFT, padx=5)
        
        # Label untuk menampilkan jalur model
        self.model_label = Label(
            control_frame, 
            textvariable=self.model_path,
            bg="#f0f0f0",
            font=("Arial", 10)
        )
        self.model_label.pack(side=tk.LEFT, padx=5)
        
        # Tombol untuk memuat model
        self.load_model_button = Button(
            control_frame, 
            text="Muat Model", 
            command=self.load_model,
            bg="#2196F3",
            fg="white",
            font=("Arial", 12),
            padx=10,
            pady=5
        )
        self.load_model_button.pack(side=tk.LEFT, padx=5)
        
        # Frame untuk threshold settings
        threshold_frame = Frame(main_frame, bg="#f0f0f0")
        threshold_frame.pack(side=tk.TOP, fill=tk.X, pady=10)
        
        # Label untuk confidence threshold
        conf_label = Label(
            threshold_frame,
            text="Confidence Threshold:",
            bg="#f0f0f0",
            font=("Arial", 12)
        )
        conf_label.pack(side=tk.LEFT, padx=5)
        
        # Slider untuk confidence threshold
        conf_slider = Scale(
            threshold_frame,
            variable=self.conf_threshold,
            from_=0.01,
            to=1.0,
            resolution=0.01,
            orient=tk.HORIZONTAL,
            length=200,
            bg="#f0f0f0",
            font=("Arial", 10)
        )
        conf_slider.pack(side=tk.LEFT, padx=5)
        
        # Label untuk IoU threshold
        iou_label = Label(
            threshold_frame,
            text="IoU Threshold:",
            bg="#f0f0f0",
            font=("Arial", 12)
        )
        iou_label.pack(side=tk.LEFT, padx=15)
        
        # Slider untuk IoU threshold
        iou_slider = Scale(
            threshold_frame,
            variable=self.iou_threshold,
            from_=0.1,
            to=1.0,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            length=200,
            bg="#f0f0f0",
            font=("Arial", 10)
        )
        iou_slider.pack(side=tk.LEFT, padx=5)
        
        # Frame untuk tombol gambar
        image_control_frame = Frame(main_frame, bg="#f0f0f0")
        image_control_frame.pack(side=tk.TOP, fill=tk.X, pady=10)
        
        # Tombol untuk memilih gambar
        self.image_button = Button(
            image_control_frame, 
            text="Pilih Gambar", 
            command=self.select_image,
            bg="#FF9800",
            fg="white",
            font=("Arial", 12),
            padx=10,
            pady=5
        )
        self.image_button.pack(side=tk.LEFT, padx=5)
        
        # Tombol untuk prediksi
        self.predict_button = Button(
            image_control_frame, 
            text="Deteksi Sampah", 
            command=self.predict_image,
            bg="#E91E63",
            fg="white",
            font=("Arial", 12),
            padx=10,
            pady=5,
            state=tk.DISABLED
        )
        self.predict_button.pack(side=tk.LEFT, padx=5)
        
        # Frame untuk gambar
        self.image_frame = Frame(main_frame, bg="black", width=800, height=500)
        self.image_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=10)
        self.image_frame.pack_propagate(False)
        
        # Label untuk menampilkan gambar
        self.image_label = Label(self.image_frame, bg="black")
        self.image_label.pack(fill=tk.BOTH, expand=True)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Status: Siap")
        self.status_bar = Label(
            root, 
            textvariable=self.status_var, 
            bd=1, 
            relief=tk.SUNKEN, 
            anchor=tk.W,
            font=("Arial", 10)
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Informasi kelas
        self.class_info_var = tk.StringVar()
        self.class_info_var.set("Kelas Terdeteksi: -")
        self.class_info = Label(
            main_frame, 
            textvariable=self.class_info_var,
            bg="#f0f0f0",
            font=("Arial", 12, "bold")
        )
        self.class_info.pack(side=tk.BOTTOM, pady=10)
    
    def select_model(self):
        """Fungsi untuk memilih file model"""
        model_file = filedialog.askopenfilename(
            title="Pilih File Model",
            filetypes=[("PyTorch Model", "*.pt"), ("All Files", "*.*")]
        )
        if model_file:
            self.model_path.set(model_file)
            self.status_var.set(f"Status: Model dipilih: {os.path.basename(model_file)}")
    
    def load_model(self):
        """Fungsi untuk memuat model YOLOv8"""
        try:
            model_path = self.model_path.get()
            if not os.path.exists(model_path):
                messagebox.showerror("Error", f"File model tidak ditemukan: {model_path}")
                return
            
            self.status_var.set("Status: Memuat model...")
            self.root.update()
            
            # Memuat model di thread terpisah
            threading.Thread(target=self._load_model_thread, args=(model_path,)).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Gagal memuat model: {str(e)}")
            self.status_var.set("Status: Error memuat model")
    
    def _load_model_thread(self, model_path):
        """Loading model in a separate thread"""
        try:
            self.model = YOLO(model_path)
            
            # Update UI dari thread utama
            self.root.after(0, self._model_loaded_callback)
        except Exception as e:
            # Update error di thread utama
            self.root.after(0, lambda: self._model_error_callback(str(e)))
    
    def _model_loaded_callback(self):
        """Callback setelah model berhasil dimuat"""
        self.predict_button.config(state=tk.NORMAL)
        self.status_var.set(f"Status: Model berhasil dimuat: {os.path.basename(self.model_path.get())}")
        messagebox.showinfo("Info", "Model berhasil dimuat!")
    
    def _model_error_callback(self, error_msg):
        """Callback jika terjadi error saat memuat model"""
        messagebox.showerror("Error", f"Gagal memuat model: {error_msg}")
        self.status_var.set("Status: Error memuat model")
    
    def select_image(self):
        """Fungsi untuk memilih gambar"""
        image_file = filedialog.askopenfilename(
            title="Pilih Gambar",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"),
                ("All Files", "*.*")
            ]
        )
        
        if image_file:
            self.image_path = image_file
            self.load_and_display_image(image_file)
            self.status_var.set(f"Status: Gambar dipilih: {os.path.basename(image_file)}")
            self.class_info_var.set("Kelas Terdeteksi: -")
    
    def load_and_display_image(self, image_path, with_detections=False):
        """Fungsi untuk memuat dan menampilkan gambar"""
        try:
            if with_detections and self.detection_results is not None:
                # Ambil gambar dengan hasil deteksi
                img = self.detection_results[0].plot()
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            else:
                # Muat gambar asli
                img = cv2.imread(image_path)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Konversi ke format PIL
            self.current_image = Image.fromarray(img)
            
            # Resize gambar agar sesuai dengan frame
            img_width, img_height = self.current_image.size
            frame_width = self.image_frame.winfo_width()
            frame_height = self.image_frame.winfo_height()
            
            # Hitung rasio untuk mempertahankan aspek rasio
            ratio = min(frame_width/img_width, frame_height/img_height)
            new_width = int(img_width * ratio)
            new_height = int(img_height * ratio)
            
            resized_image = self.current_image.resize((new_width, new_height), Image.LANCZOS)
            
            # Konversi ke PhotoImage untuk tkinter
            photo = ImageTk.PhotoImage(resized_image)
            
            # Update label dengan gambar baru
            self.image_label.config(image=photo)
            self.image_label.image = photo  # Simpan referensi
            
        except Exception as e:
            messagebox.showerror("Error", f"Gagal memuat gambar: {str(e)}")
    
    def predict_image(self):
        """Fungsi untuk melakukan prediksi pada gambar"""
        if self.model is None:
            messagebox.showwarning("Peringatan", "Model belum dimuat!")
            return
        
        if self.image_path is None or not os.path.exists(self.image_path):
            messagebox.showwarning("Peringatan", "Pilih gambar terlebih dahulu!")
            return
        
        try:
            self.status_var.set(f"Status: Melakukan deteksi dengan threshold {self.conf_threshold.get():.2f}...")
            self.root.update()
            
            # Lakukan prediksi di thread terpisah
            threading.Thread(target=self._predict_thread).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Gagal melakukan prediksi: {str(e)}")
            self.status_var.set("Status: Error saat prediksi")
    
    def _predict_thread(self):
        """Thread terpisah untuk prediksi"""
        try:
            # Ambil nilai threshold
            conf_threshold = self.conf_threshold.get()
            iou_threshold = self.iou_threshold.get()
            
            # Lakukan prediksi dengan threshold yang disesuaikan
            results = self.model(self.image_path, conf=conf_threshold, iou=iou_threshold)
            self.detection_results = results
            
            # Update UI dari thread utama
            self.root.after(0, self._prediction_complete_callback)
        except Exception as e:
            # Update error di thread utama
            self.root.after(0, lambda: self._prediction_error_callback(str(e)))
    
    def _prediction_complete_callback(self):
        """Callback setelah prediksi selesai"""
        if self.detection_results:
            # Tampilkan gambar dengan hasil deteksi
            self.load_and_display_image(self.image_path, with_detections=True)
            
            # Dapatkan informasi tentang objek terdeteksi
            result = self.detection_results[0]
            class_counts = {}
            
            # Hitung jumlah objek per kelas
            if hasattr(result, 'boxes') and len(result.boxes) > 0:
                for box in result.boxes:
                    class_id = int(box.cls.item())
                    class_name = result.names[class_id]
                    conf = box.conf.item()
                    
                    if class_name in class_counts:
                        class_counts[class_name] += 1
                    else:
                        class_counts[class_name] = 1
            
            # Tampilkan informasi kelas
            if class_counts:
                class_info = "Kelas Terdeteksi: "
                for cls_name, count in class_counts.items():
                    class_info += f"{cls_name} ({count}), "
                class_info = class_info.rstrip(", ")
                self.class_info_var.set(class_info)
            else:
                self.class_info_var.set("Kelas Terdeteksi: Tidak ada objek terdeteksi")
            
            self.status_var.set(f"Status: Deteksi selesai! [Confidence: {self.conf_threshold.get():.2f}, IoU: {self.iou_threshold.get():.2f}]")
        else:
            self.status_var.set("Status: Tidak ada objek terdeteksi")
    
    def _prediction_error_callback(self, error_msg):
        """Callback jika terjadi error saat prediksi"""
        messagebox.showerror("Error", f"Gagal melakukan prediksi: {error_msg}")
        self.status_var.set("Status: Error saat prediksi")


if __name__ == "__main__":
    # Cek apakah pustaka yang diperlukan tersedia
    try:
        import ultralytics
    except ImportError:
        print("ERROR: Pustaka ultralytics tidak ditemukan.")
        print("Silakan instal dengan perintah: pip install ultralytics")
        sys.exit(1)
    
    # Membuat jendela utama
    root = tk.Tk()
    app = WasteDetectionApp(root)
    
    # Menjalankan aplikasi
    root.mainloop()