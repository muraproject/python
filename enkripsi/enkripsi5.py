import wave
import struct
import os

def reduce_wav_size(input_file, output_file, target_sample_rate=22050, target_bit_depth=16):
    with wave.open(input_file, 'rb') as wf:
        n_channels, sampwidth, framerate, n_frames, _, _ = wf.getparams()
        
        # Baca semua frame
        frames = wf.readframes(n_frames)
    
    # Konversi bytes ke array of shorts
    samples = struct.unpack(f"{n_frames * n_channels}h", frames)
    
    # Kurangi sample rate (ambil setiap n-th sample)
    reduction_factor = int(framerate / target_sample_rate)
    reduced_samples = samples[::reduction_factor]
    
    # Kurangi bit depth jika perlu
    if target_bit_depth < 16:
        scale = (2 ** target_bit_depth) / (2 ** 16)
        reduced_samples = [int(sample * scale) for sample in reduced_samples]
    
    # Tulis ke file output
    with wave.open(output_file, 'wb') as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(target_bit_depth // 8)
        wf.setframerate(target_sample_rate)
        wf.writeframes(struct.pack(f"{len(reduced_samples)}h", *reduced_samples))

# Penggunaan
input_file = "rec.wav"
output_file = "reduced_output.wav"

reduce_wav_size(input_file, output_file)

# Tampilkan perbandingan ukuran file
original_size = os.path.getsize(input_file)
reduced_size = os.path.getsize(output_file)
print(f"Ukuran file asli: {original_size} bytes")
print(f"Ukuran file hasil: {reduced_size} bytes")
print(f"Pengurangan ukuran: {(1 - reduced_size/original_size)*100:.2f}%")