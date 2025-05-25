import os
import random
import shutil
from pathlib import Path
import cv2
import numpy as np
import yaml
from tqdm import tqdm
import albumentations as A

def create_dataset_structure(base_path):
    """Membuat struktur folder dataset untuk YOLO."""
    folders = [
        'images/train', 'images/val', 'images/test',
        'labels/train', 'labels/val', 'labels/test'
    ]
    
    for folder in folders:
        os.makedirs(os.path.join(base_path, folder), exist_ok=True)
    
    print(f"Struktur folder dataset dibuat di {base_path}")

def generate_yolo_labels(input_folder, output_folder, class_id):
    """Membuat label YOLO untuk gambar dalam folder tertentu."""
    os.makedirs(output_folder, exist_ok=True)
    
    image_files = [f for f in os.listdir(input_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
    
    for img_file in tqdm(image_files, desc=f"Generating labels for class {class_id}"):
        img_path = os.path.join(input_folder, img_file)
        img = cv2.imread(img_path)
        
        if img is None:
            print(f"Couldn't read image: {img_path}")
            continue
            
        height, width = img.shape[:2]
        
        # Membuat label yang mencakup seluruh gambar dengan class_id
        # Format YOLO: <class_id> <x_center> <y_center> <width> <height>
        # Dimana semua nilai dinormalisasi ke [0,1]
        label_content = f"{class_id} 0.5 0.5 1.0 1.0\n"
        
        # Simpan label
        label_filename = os.path.splitext(img_file)[0] + '.txt'
        with open(os.path.join(output_folder, label_filename), 'w') as f:
            f.write(label_content)
    
    return image_files

def prepare_dataset(container_folder, full_folder, output_path, temp_labels_path, 
                    train_ratio=0.7, val_ratio=0.2, test_ratio=0.1):
    """Menyiapkan dataset dari folder container dan full."""
    # Buat temporary folder untuk label
    os.makedirs(temp_labels_path, exist_ok=True)
    container_labels = os.path.join(temp_labels_path, 'container')
    full_labels = os.path.join(temp_labels_path, 'full')
    
    # Buat label untuk kedua kelas
    print("Membuat label untuk kelas container (0)...")
    container_files = generate_yolo_labels(container_folder, container_labels, 0)
    
    print("Membuat label untuk kelas full/sampah_overload (1)...")
    full_files = generate_yolo_labels(full_folder, full_labels, 1)
    
    # Gabungkan data dari kedua kelas
    all_files = []
    for img_file in container_files:
        all_files.append({
            'image': os.path.join(container_folder, img_file),
            'label': os.path.join(container_labels, os.path.splitext(img_file)[0] + '.txt'),
            'class': 'container'
        })
    
    for img_file in full_files:
        all_files.append({
            'image': os.path.join(full_folder, img_file),
            'label': os.path.join(full_labels, os.path.splitext(img_file)[0] + '.txt'),
            'class': 'full'
        })
    
    # Acak dataset
    random.shuffle(all_files)
    
    # Split dataset
    total = len(all_files)
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)
    
    splits = {
        'train': all_files[:train_end],
        'val': all_files[train_end:val_end],
        'test': all_files[val_end:]
    }
    
    # Copy file ke folder yang sesuai
    for split_name, files in splits.items():
        for file_info in tqdm(files, desc=f"Copying {split_name} files"):
            img_file = os.path.basename(file_info['image'])
            label_file = os.path.basename(file_info['label'])
            
            # Copy gambar
            shutil.copy2(
                file_info['image'],
                os.path.join(output_path, f"images/{split_name}", img_file)
            )
            
            # Copy label
            shutil.copy2(
                file_info['label'],
                os.path.join(output_path, f"labels/{split_name}", label_file)
            )
    
    print(f"Dataset dibagi: {len(splits['train'])} train, {len(splits['val'])} validation, {len(splits['test'])} test")
    return splits

def augment_images(output_path, aug_factor=3):
    """Melakukan augmentasi data pada train dataset."""
    # Definisikan augmentasi
    augmentations = A.Compose([
        A.HorizontalFlip(p=0.5),
        A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.5),
        A.Rotate(limit=30, p=0.5),
        A.RandomScale(scale_limit=0.2, p=0.5),
        A.Transpose(p=0.3)
    ], bbox_params=A.BboxParams(format='yolo', label_fields=['class_labels']))

    # Path untuk train images dan labels
    train_images_path = os.path.join(output_path, "images/train")
    train_labels_path = os.path.join(output_path, "labels/train")
    
    image_files = [f for f in os.listdir(train_images_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
    
    # Augment setiap gambar
    for img_file in tqdm(image_files, desc="Augmenting images"):
        # Load gambar
        img_path = os.path.join(train_images_path, img_file)
        img = cv2.imread(img_path)
        
        if img is None:
            print(f"Couldn't read image for augmentation: {img_path}")
            continue
            
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Load label
        base_name = os.path.splitext(img_file)[0]
        label_path = os.path.join(train_labels_path, f"{base_name}.txt")
        
        if os.path.exists(label_path):
            # Baca label dalam format YOLO
            bboxes = []
            class_labels = []
            
            with open(label_path, 'r') as f:
                for line in f:
                    data = line.strip().split()
                    if len(data) == 5:  # kelas, x, y, w, h
                        class_id = int(data[0])
                        x, y, w, h = map(float, data[1:])
                        bboxes.append([x, y, w, h])
                        class_labels.append(class_id)
            
            # Lakukan augmentasi beberapa kali
            for i in range(aug_factor):
                if len(bboxes) > 0:  # Hanya augment jika ada bounding box
                    transformed = augmentations(image=img, bboxes=bboxes, class_labels=class_labels)
                    
                    # Simpan gambar dan label baru
                    aug_img = transformed['image']
                    aug_bboxes = transformed['bboxes']
                    aug_labels = transformed['class_labels']
                    
                    # Nama file baru
                    new_img_name = f"{base_name}_aug{i}.jpg"
                    new_label_name = f"{base_name}_aug{i}.txt"
                    
                    # Simpan gambar
                    aug_img_rgb = cv2.cvtColor(aug_img, cv2.COLOR_RGB2BGR)
                    cv2.imwrite(os.path.join(train_images_path, new_img_name), aug_img_rgb)
                    
                    # Simpan label
                    with open(os.path.join(train_labels_path, new_label_name), 'w') as f:
                        for bbox, class_id in zip(aug_bboxes, aug_labels):
                            f.write(f"{class_id} {' '.join(map(str, bbox))}\n")
    
    # Hitung jumlah gambar setelah augmentasi
    total_images = len(os.listdir(train_images_path))
    print(f"Augmentation selesai. Total {total_images} gambar di training set.")

def create_data_yaml(output_path, classes):
    """Membuat file data.yaml untuk YOLO."""
    data = {
        'train': './images/train',
        'val': './images/val',
        'test': './images/test',
        'nc': len(classes),
        'names': classes
    }
    
    yaml_path = os.path.join(output_path, 'data.yaml')
    with open(yaml_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)
    
    print(f"File data.yaml dibuat di {yaml_path}")

def main():
    # Konfigurasi path
    container_folder = input("Masukkan path folder container: ")
    full_folder = input("Masukkan path folder full/sampah_overload: ")
    output_dataset_folder = input("Masukkan path untuk dataset output: ")
    
    # Temporary folder untuk label
    temp_labels_folder = os.path.join(output_dataset_folder, 'temp_labels')
    
    # Rasio split dataset
    train_ratio = float(input("Masukkan rasio untuk train (default 0.7): ") or 0.7)
    val_ratio = float(input("Masukkan rasio untuk validation (default 0.2): ") or 0.2)
    test_ratio = float(input("Masukkan rasio untuk test (default 0.1): ") or 0.1)
    
    # Faktor augmentasi
    aug_factor = int(input("Masukkan jumlah augmentasi per gambar (default 3): ") or 3)
    
    # Nama kelas
    class_names = ['container', 'sampah_overload']
    
    # Buat struktur dataset
    create_dataset_structure(output_dataset_folder)
    
    # Persiapkan dataset
    splits = prepare_dataset(
        container_folder, 
        full_folder, 
        output_dataset_folder,
        temp_labels_folder,
        train_ratio, 
        val_ratio, 
        test_ratio
    )
    
    # Lakukan augmentasi
    augment_images(output_dataset_folder, aug_factor)
    
    # Buat file data.yaml
    create_data_yaml(output_dataset_folder, class_names)
    
    # Bersihkan temporary folder
    shutil.rmtree(temp_labels_folder, ignore_errors=True)
    
    print("\nPenyiapan dataset selesai. Anda dapat menggunakan dataset ini untuk melatih model YOLO.")
    print(f"Struktur dataset ada di: {output_dataset_folder}")
    print(f"\nUntuk melatih model YOLOv8, jalankan perintah:")
    print(f"pip install ultralytics")
    print(f"python -c \"from ultralytics import YOLO; YOLO('yolov8n.pt').train(data='{os.path.join(output_dataset_folder, 'data.yaml')}', epochs=100, imgsz=640)\"")

if __name__ == "__main__":
    main()