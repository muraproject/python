from midiutil import MIDIFile

def create_garuda_pancasila_fixed():
    midi = MIDIFile(1)
    
    track = 0
    channel = 0
    tempo = 120
    time_start = 0
    
    midi.addTempo(track, time_start, tempo)
    
    # Menggunakan notasi angka, dimana:
    # 1 = Do, 2 = Re, 3 = Mi, 4 = Fa, 5 = So, 6 = La, 7 = Si
    # Sesuai dengan partitur, lagu ini dimulai dari Do = F
    notes = {
        '0': 65,  # F4 (Do)
        '1': 65,  # F4 (Do)
        '2': 67,  # G4 (Re)
        '3': 69,  # A4 (Mi)
        '4': 70,  # Bb4 (Fa)
        '5': 72,  # C5 (So)
        '6': 74,  # D5 (La)
        '7': 76   # E5 (Si)
    }
    
    # Melodi sesuai partitur (menggunakan notasi angka)
    melody = [
        # Garuda Pancasila
        ('0', 0, 0.5),
        ('5', 0.5, 0.5),
        ('5', 1, 0.5),
        ('1', 1.5, 0.5),
        ('1', 2, 0.5),
        ('2', 2.5, 0.5),
        ('2', 3, 0.5),
        ('3', 3.5, 0.5),
        ('0', 4, 0.5),
        ('3', 4.5, 0.5),
        ('4', 5, 0.5),
        ('5', 5.5, 0.5),
        
        # Akulah pengkalimamu
        ('1', 6, 0.5),
        ('2', 6.5, 0.5),
        ('3', 7, 0.5),
        ('4', 7.5, 0.5),
        ('2', 8, 0.5),
        ('0', 8.5, 1),
        
        # Patriot proklamasi
        ('5', 9.5, 0.5),
        ('5', 10, 0.5),
        ('2', 10.5, 0.5),
        ('2', 11, 0.5),
        ('3', 11.5, 0.5),
        ('3', 12, 0.5),
        ('4', 12.5, 0.5),
        ('0', 13, 0.5),
        
        # Sedia berkorban untukmu
        ('3', 13.5, 0.5),
        ('2', 14, 0.5),
        ('1', 14.5, 0.5),
        ('5', 15, 0.5),
        ('5', 15.5, 0.5),
        ('5', 16, 0.5),
        ('6', 16.5, 0.5),
        ('7', 17, 0.5),
        ('1', 17.5, 0.5),
        ('0', 18, 1),
    ]
    
    # Volume dinamis untuk ekspresi musikal yang lebih baik
    volume_normal = 100
    volume_accent = 110
    
    for note_name, time, duration in melody:
        # Berikan aksen pada ketukan kuat
        volume = volume_accent if int(time) % 4 == 0 else volume_normal
        midi.addNote(track, channel, notes[note_name], time, duration, volume)
    
    with open("garuda_pancasila_fixed.mid", "wb") as output_file:
        midi.writeFile(output_file)

if __name__ == "__main__":
    create_garuda_pancasila_fixed()