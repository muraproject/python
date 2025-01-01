import wave
import struct
import numpy as np
from midiutil import MIDIFile
import pygame
from math import log2

class AudioToMIDIConverter:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        
    def read_wav(self, wav_path):
        with wave.open(wav_path, 'rb') as wav_file:
            # Get basic info
            n_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            framerate = wav_file.getframerate()
            n_frames = wav_file.getnframes()
            
            # Read raw data
            raw_data = wav_file.readframes(n_frames)
            
            # Convert raw data to numpy array
            if sample_width == 1:
                fmt = "%iB" % n_frames * n_channels
                data = np.array(struct.unpack(fmt, raw_data))
            elif sample_width == 2:
                fmt = "%ih" % n_frames * n_channels
                data = np.array(struct.unpack(fmt, raw_data))
            else:
                raise ValueError("Unsupported sample width")
                
            # Convert to mono if stereo
            if n_channels == 2:
                data = np.mean(data.reshape(-1, 2), axis=1)
                
            return data, framerate
            
    def detect_notes(self, data, sample_rate, chunk_size=2048, threshold=1000):
        notes = []
        times = []
        
        # Process audio in chunks
        for i in range(0, len(data) - chunk_size, chunk_size // 2):
            chunk = data[i:i + chunk_size]
            
            # Calculate RMS amplitude
            rms = np.sqrt(np.mean(chunk ** 2))
            
            if rms > threshold:
                # Simple frequency detection using zero crossings
                zero_crossings = np.where(np.diff(np.signbit(chunk)))[0]
                if len(zero_crossings) > 1:
                    # Estimate frequency from zero crossings
                    avg_dist = np.mean(np.diff(zero_crossings))
                    freq = sample_rate / (2 * avg_dist) if avg_dist > 0 else 440
                    
                    # Convert frequency to MIDI note
                    if 20 <= freq <= 20000:  # Valid frequency range
                        midi_note = int(round(69 + 12 * log2(freq/440.0)))
                        if 0 <= midi_note <= 127:  # Valid MIDI note range
                            notes.append(midi_note)
                            times.append(i / sample_rate)
        
        return notes, times
        
    def create_midi(self, notes, times, output_file="output.mid", bpm=120):
        midi = MIDIFile(1)
        midi.addTempo(0, 0, bpm)
        
        # Set instrument to piano (program 0)
        midi.addProgramChange(0, 0, 0, 0)
        
        # Add notes
        last_note = None
        last_time = 0
        
        for i, (note, time) in enumerate(zip(notes, times)):
            # Avoid repeated notes
            if note != last_note:
                # Calculate duration
                if i < len(notes) - 1:
                    duration = min(times[i + 1] - time, 0.5)  # Max duration 0.5 seconds
                else:
                    duration = 0.25  # Default duration for last note
                
                # Add note with varying velocity based on position in melody
                velocity = np.random.randint(80, 100)
                midi.addNote(0, 0, note, time, duration, velocity)
                
                last_note = note
                last_time = time
        
        # Write MIDI file
        with open(output_file, "wb") as f:
            midi.writeFile(f)
    
    def play_midi(self, midi_path):
        pygame.mixer.music.load(midi_path)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
    
    def process_and_play(self, wav_path, output_midi_path="output.mid"):
        print("Reading WAV file...")
        data, sample_rate = self.read_wav(wav_path)
        
        print("Detecting notes...")
        notes, times = self.detect_notes(data, sample_rate)
        
        print(f"Found {len(notes)} notes")
        print("Creating MIDI file...")
        self.create_midi(notes, times, output_midi_path)
        
        print("Playing MIDI...")
        self.play_midi(output_midi_path)
        print("Finished playback")

# Usage example
if __name__ == "__main__":
    converter = AudioToMIDIConverter()
    converter.process_and_play("garuda.wav")