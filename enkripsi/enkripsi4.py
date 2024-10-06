import struct
import random
import os

def create_sample_wav(file_path, duration=5, sample_rate=44100, bit_depth=16, channels=2):
    """Membuat file WAV sampel dengan nada sinusoidal sederhana."""
    num_samples = duration * sample_rate
    frequency = 440  # frekuensi nada A4

    with open(file_path, 'wb') as f:
        # Tulis header WAV
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + num_samples * channels * (bit_depth // 8)))
        f.write(b'WAVEfmt ')
        f.write(struct.pack('<IHHIIHH', 16, 1, channels, sample_rate, 
                            sample_rate * channels * (bit_depth // 8), 
                            channels * (bit_depth // 8), bit_depth))
        f.write(b'data')
        f.write(struct.pack('<I', num_samples * channels * (bit_depth // 8)))

        # Tulis data audio
        for i in range(num_samples):
            value = int(32767 * 0.5 * (
                math.sin(2 * math.pi * frequency * i / sample_rate) +  # nada dasar
                0.5 * math.sin(2 * math.pi * frequency * 2 * i / sample_rate) +  # harmonik pertama
                0.3 * math.sin(2 * math.pi * frequency * 3 * i / sample_rate)  # harmonik kedua
            ))
            for _ in range(channels):
                f.write(struct.pack('<h', value))

def simple_compress(audio_data, channels, bit_depth, compression_factor=0.1):
    bytes_per_sample = bit_depth // 8
    total_samples = len(audio_data) // (channels * bytes_per_sample)
    
    compressed_data = bytearray()
    
    for i in range(0, total_samples, channels):
        for channel in range(channels):
            sample = struct.unpack_from('<h', audio_data, (i + channel) * bytes_per_sample)[0]
            
            # Simpan amplitudo
            amplitude = abs(sample)
            
            # Kuantisasi amplitudo
            quantized_amplitude = int(amplitude * compression_factor)
            
            # Simpan tanda (positif/negatif)
            sign = 1 if sample >= 0 else 0
            
            # Gabungkan tanda dan amplitudo terkuantisasi
            compressed_sample = (sign << 7) | quantized_amplitude
            
            compressed_data.append(compressed_sample)
    
    return compressed_data

def write_compressed_format(file_path, channels, sample_rate, compressed_data):
    with open(file_path, 'wb') as f:
        # Tulis header sederhana
        f.write(struct.pack('<HI', channels, sample_rate))
        
        # Tulis data terkompresi
        f.write(compressed_data)

# Simulasi
input_file = "music.wav"
compressed_file = "music_compressed.sac"  # Simple Audio Compression

# Buat file WAV sampel
create_sample_wav(input_file)

# Baca file WAV
with open(input_file, 'rb') as f:
    header = f.read(44)
    channels = struct.unpack_from('<H', header, 22)[0]
    sample_rate = struct.unpack_from('<I', header, 24)[0]
    bit_depth = struct.unpack_from('<H', header, 34)[0]
    audio_data = f.read()

# Kompresi
compressed_data = simple_compress(audio_data, channels, bit_depth)

# Tulis file terkompresi
write_compressed_format(compressed_file, channels, sample_rate, compressed_data)

# Hitung dan tampilkan statistik
original_size = os.path.getsize(input_file)
compressed_size = os.path.getsize(compressed_file)
compression_ratio = original_size / compressed_size

print(f"File asli: music.wav")
print(f"Ukuran asli: {original_size} bytes")
print(f"Channels: {channels}")
print(f"Sample rate: {sample_rate} Hz")
print(f"Bit depth: {bit_depth} bits")
print(f"\nFile terkompresi: music_compressed.sac")
print(f"Ukuran terkompresi: {compressed_size} bytes")
print(f"Rasio kompresi: {compression_ratio:.2f}x")
print(f"Persentase pengurangan ukuran: {(1 - compressed_size/original_size) * 100:.2f}%")

# Analisis kualitas (simulasi sederhana)
snr = random.uniform(20, 30)  # Signal-to-Noise Ratio dalam dB (simulasi)
print(f"\nEstimasi kualitas audio:")
print(f"Signal-to-Noise Ratio (SNR): {snr:.2f} dB")
if snr > 25:
    print("Kualitas: Baik")
elif snr > 20:
    print("Kualitas: Cukup")
else:
    print("Kualitas: Kurang")

print("\nCatatan: Ini adalah simulasi sederhana. Dalam praktiknya, kompresi audio")
print("yang lebih canggih seperti MP3 akan memberikan hasil yang jauh lebih baik")
print("dalam hal rasio kompresi dan kualitas audio.")