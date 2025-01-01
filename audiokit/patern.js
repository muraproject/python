// FL Studio MIDI Pattern Script
// Untuk melodi sederhana do re mi fa so la

// Definisi note MIDI (Middle C = 60)
const DO = 60;  // C4
const RE = 62;  // D4
const MI = 64;  // E4
const FA = 65;  // F4
const SO = 67;  // G4
const LA = 69;  // A4

// Pattern data
const pattern = {
  name: "Simple Melody",
  length: 8, // bars
  notes: [
    {
      note: DO,
      position: 0,
      length: 1,
      velocity: 100
    },
    {
      note: RE,
      position: 1,
      length: 1,
      velocity: 100
    },
    {
      note: MI,
      position: 2,
      length: 1,
      velocity: 100
    },
    {
      note: FA,
      position: 3,
      length: 1,
      velocity: 100
    },
    {
      note: SO,
      position: 4,
      length: 1,
      velocity: 100
    },
    {
      note: LA,
      position: 5,
      length: 1,
      velocity: 100
    }
  ]
};

// Export sebagai file MIDI
function exportMIDI(pattern) {
  // Konversi ke format MIDI
  let midiData = [];
  
  // Header MIDI
  midiData.push(0x4D); // 'M'
  midiData.push(0x54); // 'T'
  midiData.push(0x68); // 'h'
  midiData.push(0x64); // 'd'
  
  // Tambahkan note events
  pattern.notes.forEach(note => {
    // Note ON
    midiData.push(0x90); // Note ON command
    midiData.push(note.note); // MIDI note number
    midiData.push(note.velocity); // Velocity
    
    // Note OFF
    midiData.push(0x80); // Note OFF command
    midiData.push(note.note); // MIDI note number
    midiData.push(0x00); // Release velocity
  });
  
  return midiData;
}