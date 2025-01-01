from midiutil import MIDIFile

def create_garuda_pancasila():
    # Buat object MIDI dengan 1 track
    midi = MIDIFile(1)
    
    # Setup track dan timing
    track = 0
    channel = 0
    tempo = 120  # BPM
    time_start = 0
    
    # Set tempo
    midi.addTempo(track, time_start, tempo)
    
    # Definisi nada (middle C = 60)
    notes = {
        'do': 60,  # C4
        're': 62,  # D4
        'mi': 64,  # E4
        'fa': 65,  # F4
        'so': 67,  # G4
        'la': 69   # A4
    }
    
    # Durasi dan volume
    duration = 1  # 1 beat
    volume = 100  # 0-127
    
    # Melodi Garuda Pancasila (bait pertama)
    # "Ga-ru-da Pan-ca-si-la"
    melody = [
        ('do', 0),    # Ga
        ('do', 1),    # ru
        ('re', 2),    # da
        ('mi', 3),    # Pan
        ('so', 4),    # ca
        ('so', 5),    # si
        ('la', 6),    # la
        ('so', 7),    # -
        
        # "A-ku-lah peng-ka-li-ma mu"
        ('mi', 8),    # A
        ('mi', 9),    # ku
        ('fa', 10),   # lah
        ('mi', 11),   # peng
        ('re', 12),   # ka
        ('do', 13),   # li
        ('re', 14),   # ma
        ('do', 15),   # mu
    ]
    
    # Tambahkan nada ke file MIDI
    for note_name, time in melody:
        midi.addNote(track, channel, notes[note_name], time, duration, volume)
    
    # Simpan file
    with open("garuda_pancasila.mid", "wb") as output_file:
        midi.writeFile(output_file)

if __name__ == "__main__":
    create_garuda_pancasila()