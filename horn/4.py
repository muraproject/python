import tkinter as tk
from tkinter import ttk
from serial import Serial
import pygame
import threading
import re
from datetime import datetime
import numpy as np

class HornSimulatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Horn MIDI Controller")
        
        # Initialize variables
        self.running = True
        self.connected = False
        self.horn_status = [False] * 6
        self.volume = 0.5
        self.tempo = 120
        self.octave = 4
        self.ser = None
        
        # Setup GUI
        self.setup_gui()
        
        # Initialize pygame
        pygame.mixer.init(44100, -16, 2, 512)
        pygame.init()

        # Generate beep sounds (frequencies untuk Do-La)
        self.horn_sounds = []
        frequencies = [262, 294, 330, 349, 392, 440]  # C4 to A4
        for freq in frequencies:
            sound = self.generate_beep(freq)
            sound.set_volume(self.volume)
            self.horn_sounds.append(sound)
                
    def setup_gui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Serial Connection Frame
        conn_frame = ttk.LabelFrame(main_frame, text="Serial Connection", padding="5")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, padx=5)
        self.port_entry = ttk.Entry(conn_frame, width=10)
        self.port_entry.insert(0, "COM3")
        self.port_entry.grid(row=0, column=1, padx=5)
        
        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=2, padx=5)
        
        # Control Frame
        ctrl_frame = ttk.LabelFrame(main_frame, text="Controls", padding="5")
        ctrl_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Volume Control
        ttk.Label(ctrl_frame, text="Volume:").grid(row=0, column=0, padx=5)
        self.volume_scale = ttk.Scale(ctrl_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                    command=self.update_volume)
        self.volume_scale.set(50)
        self.volume_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # Tempo Control
        ttk.Label(ctrl_frame, text="Tempo:").grid(row=1, column=0, padx=5)
        self.tempo_spinbox = ttk.Spinbox(ctrl_frame, from_=40, to=240, width=5,
                                       command=self.update_tempo)
        self.tempo_spinbox.set(120)
        self.tempo_spinbox.grid(row=1, column=1, sticky=tk.W, padx=5)
        
        # Octave Control
        ttk.Label(ctrl_frame, text="Octave:").grid(row=2, column=0, padx=5)
        self.octave_spinbox = ttk.Spinbox(ctrl_frame, values=(3,4,5), width=5,
                                         command=self.update_octave)
        self.octave_spinbox.set(4)
        self.octave_spinbox.grid(row=2, column=1, sticky=tk.W, padx=5)
        
        # Horn Status Frame
        status_frame = ttk.LabelFrame(main_frame, text="Horn Status", padding="5")
        status_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        notes = ['Do', 'Re', 'Mi', 'Fa', 'Sol', 'La']
        self.horn_indicators = []
        for i in range(6):
            indicator = ttk.Label(status_frame, text="●", foreground="gray")
            indicator.grid(row=0, column=i, padx=10)
            self.horn_indicators.append(indicator)
            ttk.Label(status_frame, text=f"Horn {i+1}").grid(row=1, column=i)
            ttk.Label(status_frame, text=notes[i]).grid(row=2, column=i)
        
        # Log Frame
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, width=50)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text['yscrollcommand'] = scrollbar.set
    
    def generate_beep(self, frequency, duration=0.1):
        sample_rate = 44100
        t = np.linspace(0, duration, int(duration * sample_rate), False)
        tone = np.sin(2 * np.pi * frequency * t)
        fade = 100
        tone[:fade] = tone[:fade] * np.linspace(0, 1, fade)
        tone[-fade:] = tone[-fade:] * np.linspace(1, 0, fade)
        scaled = np.int16(tone * 32767)
        stereo = np.vstack((scaled, scaled)).T
        return pygame.sndarray.make_sound(np.ascontiguousarray(stereo))

    def toggle_connection(self):
        if not self.connected:
            try:
                port = self.port_entry.get()
                self.ser = Serial(port, 115200)
                self.connected = True
                self.connect_btn.config(text="Disconnect")
                self.log("Connected to " + port)
                
                self.serial_thread = threading.Thread(target=self.read_serial)
                self.serial_thread.daemon = True
                self.serial_thread.start()
                
                # Send initial settings
                self.set_tempo(self.tempo)
                self.set_octave(self.octave)
            except Exception as e:
                self.log(f"Connection error: {str(e)}")
        else:
            self.connected = False
            if self.ser:
                self.ser.close()
            self.connect_btn.config(text="Connect")
            self.log("Disconnected")

    def read_serial(self):
        while self.connected and self.ser:
            if self.ser.in_waiting:
                try:
                    line = self.ser.readline().decode('utf-8').strip()
                    if line:
                        self.process_serial_data(line)
                except:
                    continue

    def process_serial_data(self, line):
        if "Horn" in line:
            match = re.search(r"Horn (\d) (ON|OFF)", line)
            if match:
                horn_num = int(match.group(1)) - 1
                state = match.group(2)
                
                self.horn_status[horn_num] = (state == "ON")
                self.root.after(0, self.update_indicator, horn_num)
                
                if state == "ON":
                    self.horn_sounds[horn_num].play()
                else:
                    self.horn_sounds[horn_num].stop()
                
                self.log(f"Horn {horn_num + 1} {state}")

    def update_indicator(self, horn_num):
        color = "green" if self.horn_status[horn_num] else "gray"
        self.horn_indicators[horn_num].config(foreground=color)

    def update_volume(self, value):
        self.volume = float(value) / 100
        for sound in self.horn_sounds:
            sound.set_volume(self.volume)

    def set_tempo(self, bpm):
        if self.ser and self.connected:
            microseconds = int(60000000 / bpm)
            tempo_bytes = [
                (microseconds >> 16) & 0xFF,
                (microseconds >> 8) & 0xFF,
                microseconds & 0xFF
            ]
            command = bytearray([ord('t')] + tempo_bytes)
            self.ser.write(command)
            self.log(f"Set tempo to {bpm} BPM")

    def update_tempo(self):
        try:
            new_tempo = int(self.tempo_spinbox.get())
            self.tempo = new_tempo
            self.set_tempo(new_tempo)
        except ValueError:
            self.log("Invalid tempo value")

    def set_octave(self, octave):
        if self.ser and self.connected:
            command = f'o{octave}'.encode()
            self.ser.write(command)
            self.log(f"Set octave to {octave}")

    def update_octave(self):
        try:
            new_octave = int(self.octave_spinbox.get())
            self.octave = new_octave
            self.set_octave(new_octave)
        except ValueError:
            self.log("Invalid octave value")

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)

    def on_closing(self):
        self.running = False
        if self.ser:
            self.ser.close()
        pygame.quit()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = HornSimulatorGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()