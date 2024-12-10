import os

def process_file(file_path):
    """
    Memproses file dengan mengganti:
    1. <br> menjadi ";" (dengan tanda petik dua)
    2. ; menjadi ,
    3. )"," menjadi )","' (persis sesuai spesifikasi)
    """
    try:
        # Baca isi file
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Lakukan penggantian sesuai urutan
        content = content.replace('<br>', '";')
        content = content.replace(';', ',')
        content = content.replace(')","', ')","\'')
        
        # Tulis kembali ke file
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
            
        print(f"Berhasil memproses: {file_path}")
        
    except Exception as e:
        print(f"Error saat memproses {file_path}: {str(e)}")

def process_folder(folder_path):
    """
    Memproses semua file dalam folder yang diberikan
    """
    try:
        # Pastikan folder ada
        if not os.path.exists(folder_path):
            print(f"Folder tidak ditemukan: {folder_path}")
            return
            
        # Hitung jumlah file yang akan diproses
        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        total_files = len(files)
        
        print(f"Ditemukan {total_files} file untuk diproses")
        
        # Proses setiap file
        for filename in files:
            file_path = os.path.join(folder_path, filename)
            process_file(file_path)
            
        print("\nSelesai memproses semua file!")
        
    except Exception as e:
        print(f"Error: {str(e)}")

# Contoh penggunaan
if __name__ == "__main__":
    folder_path = input("Masukkan path folder yang akan diproses: ")
    process_folder(folder_path)