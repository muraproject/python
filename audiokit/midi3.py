from midiutil import MIDIFile
import pygame
import tempfile
import os

def play_indonesia_pusaka():
    pygame.mixer.init()
    midi = MIDIFile(1)
    
    track = 0
    channel = 0
    tempo = 85  # Tempo yang lebih lambat dan khidmat
    time_start = 0
    
    midi.addTempo(track, time_start, tempo)
    
    # Nada dasar C (do=C)
    notes = {
        '0': 60,  # C4 (Do)
        '1': 62,  # D4 (Re)
        '2': 64,  # E4 (Mi)
        '3': 65,  # F4 (Fa)
        '4': 67,  # G4 (So)
        '5': 69,  # A4 (La)
        '6': 71,  # B4 (Si)
        '7': 72   # C5 (Do tinggi)
    }
    
    # Melodi dengan timing yang tepat
    # Format: (nada, waktu_mulai, durasi)
    melody = [
        # "In-do-ne-sia"
        ('3', 0, 1),      # In
        ('1', 1, 0.5),    # do
        ('2', 1.5, 0.5),  # ne
        ('3', 2, 1),      # sia
        
        # "Ta-nah A-ir-ku"
        ('2', 3, 0.5),    # Ta
        ('1', 3.5, 0.5),  # nah
        ('2', 4, 0.5),    # A
        ('3', 4.5, 0.5),  # ir
        ('4', 5, 1),      # ku
        
        # "Pu-sa-ka"
        ('3', 6, 1),      # Pu
        ('2', 7, 0.5),    # sa
        ('1', 7.5, 0.5),  # ka
        
        # "A-ba-di"
        ('2', 8, 1),      # A
        ('1', 9, 0.5),    # ba
        ('7', 9.5, 0.5),  # di
        
        # "Nan-ja-ya"
        ('1', 10, 1),     # Nan
        ('2', 11, 0.5),   # ja
        ('3', 11.5, 0.5), # ya
        
        # "In-do-ne-sia"
        ('3', 12, 1),     # In
        ('1', 13, 0.5),   # do
        ('2', 13.5, 0.5), # ne
        ('3', 14, 1),     # sia
        
        # "Ta-nah Pu-sa-ka"
        ('2', 15, 0.5),   # Ta
        ('1', 15.5, 0.5), # nah
        ('2', 16, 0.5),   # Pu
        ('3', 16.5, 0.5), # sa
        ('4', 17, 1),     # ka
        
        # "In-dah" "Ra-ya"
        ('3', 18, 1),     # In
        ('2', 19, 1),     # dah
        ('1', 20, 2),     # Ra
                          # ya
    ]
    
    # Volume dinamis
    volume_accent = 110  # Untuk nada penting/ketukan kuat
    volume_normal = 95   # Untuk nada lainnya
    
    for note_name, time, duration in melody:
        # Beri aksen pada ketukan pertama di setiap bar dan nada panjang
        is_accent = time % 4 == 0 or duration >= 1
        volume = volume_accent if is_accent else volume_normal
        midi.addNote(track, channel, notes[note_name], time, duration, volume)
    
    # Mainkan MIDI
    temp = tempfile.NamedTemporaryFile(delete=False)
    midi.writeFile(temp)
    temp.close()
    
    try:
        pygame.mixer.music.load(temp.name)
        pygame.mixer.music.play()
        
        print("Playing Indonesia Pusaka... Press Ctrl+C to stop")
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            
    except KeyboardInterrupt:
        print("\nPlayback stopped by user")
    finally:
        pygame.mixer.music.stop()
        pygame.mixer.quit()
        os.unlink(temp.name)

if __name__ == "__main__":
    print("Indonesia Pusaka")
    print("Tempo: 85 BPM")
    print("Time Signature: 4/4")
    play_indonesia_pusaka()