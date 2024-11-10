import os

def search_text_in_files(search_path, search_text, output_file):
    """
    Mencari teks dalam file .cpp dan .h di folder yang ditentukan
    mengabaikan besar kecil huruf (case-insensitive)
    
    Args:
        search_path (str): Path folder yang akan dicari
        search_text (str): Teks yang ingin dicari
        output_file (str): Path file output txt
    """
    # Mengecek apakah folder exist
    if not os.path.exists(search_path):
        print(f"Error: Folder '{search_path}' tidak ditemukan!")
        return
    
    # Ubah search_text ke lowercase untuk perbandingan case-insensitive
    search_text_lower = search_text.lower()
    
    # Counter untuk statistik
    total_files = 0
    files_with_text = 0
    total_occurrences = 0
    
    # Hapus file hasil pencarian lama jika ada
    if os.path.exists(output_file):
        os.remove(output_file)
    
    # Buka file untuk menulis hasil
    with open(output_file, 'w', encoding='utf-8') as output:
        output.write(f"Hasil Pencarian '{search_text}' di folder: {search_path}\n")
        output.write("(Pencarian mengabaikan besar kecil huruf)\n")
        output.write("-" * 50 + "\n")
        
        # Berjalan recursive di semua folder
        for root, dirs, files in os.walk(search_path):
            # Filter hanya file .cpp dan .h
            cpp_files = [f for f in files if f.endswith(('.cpp', '.h'))]
            
            for filename in cpp_files:
                total_files += 1
                file_path = os.path.join(root, filename)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        line_number = 0
                        found_in_file = False
                        
                        for line in file:
                            line_number += 1
                            # Bandingkan dalam lowercase untuk case-insensitive
                            if search_text_lower in line.lower():
                                if not found_in_file:
                                    output.write(f"\nDitemukan di file: {file_path}\n")
                                    found_in_file = True
                                    files_with_text += 1
                                
                                # Tulis baris original (dengan format asli) yang mengandung teks
                                output.write(f"Baris {line_number}: {line.strip()}\n")
                                total_occurrences += 1
                                
                except UnicodeDecodeError:
                    output.write(f"Warning: Tidak dapat membaca file {file_path} (encoding error)\n")
                except Exception as e:
                    output.write(f"Error saat membaca file {file_path}: {str(e)}\n")
        
        # Tulis statistik pencarian
        output.write("\n" + "=" * 50 + "\n")
        output.write("Statistik Pencarian:\n")
        output.write(f"Total file diperiksa: {total_files}\n")
        output.write(f"File yang mengandung teks: {files_with_text}\n")
        output.write(f"Total kemunculan teks: {total_occurrences}\n")

    print(f"Pencarian selesai. Hasil telah disimpan ke '{output_file}'")

# Konfigurasi pencarian
FOLDER_PATH = "C:\OpenCPN\gui\src"           # Path folder yang akan dicari
SEARCH_TEXT = "SetIcon"        # Text yang akan dicari
OUTPUT_FILE = "hasil_pencarian.txt"  # Nama file output

# Jalankan fungsi pencarian
search_text_in_files(FOLDER_PATH, SEARCH_TEXT, OUTPUT_FILE)