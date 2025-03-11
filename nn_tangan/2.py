import tkinter as tk
from tkinter import ttk, messagebox
import serial
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import threading
import time

class MuscleSlopeLearner:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Muscle Slope Pattern Learner")
        self.root.geometry("1000x600")
        
        # Parameters
        self.serial_port = None
        self.window_size = 20
        self.data_buffer = deque(maxlen=200)  # untuk display
        self.slope_buffer = deque(maxlen=200)  # untuk display slope
        self.analysis_buffer = deque(maxlen=self.window_size)  # untuk analisis
        
        self.is_recording = False
        self.current_gesture = None
        self.gesture_data = {
            'open': {'slopes': [], 'max_slopes': [], 'threshold': None},
            'close': {'slopes': [], 'max_slopes': [], 'threshold': None}
        }
        self.is_predicting = False
        self.slope_history = deque(maxlen=5)  # untuk stabilitas prediksi
        
        self.setup_gui()
        
    def setup_gui(self):
        # Control Panel
        control_frame = ttk.Frame(self.root)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)
        
        # Connection
        conn_frame = ttk.LabelFrame(control_frame, text="Connection", padding=10)
        conn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, padx=5)
        self.port_entry = ttk.Entry(conn_frame, width=10)
        self.port_entry.insert(0, "COM3")
        self.port_entry.grid(row=0, column=1, padx=5)
        
        self.connect_btn = ttk.Button(conn_frame, text="Connect", 
                                    command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=2, padx=5)
        
        # Recording Controls
        record_frame = ttk.LabelFrame(control_frame, text="Record Gesture", padding=10)
        record_frame.pack(fill=tk.X, pady=5)
        
        self.gesture_var = tk.StringVar(value="open")
        ttk.Radiobutton(record_frame, text="Open Hand", variable=self.gesture_var,
                       value="open").pack()
        ttk.Radiobutton(record_frame, text="Close Hand", variable=self.gesture_var,
                       value="close").pack()
        
        self.record_btn = ttk.Button(record_frame, text="Start Recording",
                                   command=self.toggle_recording)
        self.record_btn.pack(pady=5)
        
        # Training Controls
        train_frame = ttk.LabelFrame(control_frame, text="Training & Prediction", padding=10)
        train_frame.pack(fill=tk.X, pady=5)
        
        self.train_btn = ttk.Button(train_frame, text="Train Model",
                                  command=self.train_model)
        self.train_btn.pack(pady=5)
        
        self.predict_btn = ttk.Button(train_frame, text="Start Prediction",
                                    command=self.toggle_prediction)
        self.predict_btn.pack(pady=5)
        
        self.prediction_label = ttk.Label(train_frame, text="Prediction: -",
                                        font=("Arial", 12, "bold"))
        self.prediction_label.pack(pady=5)
        
        # Analysis Display
        analysis_frame = ttk.LabelFrame(control_frame, text="Pattern Analysis", padding=10)
        analysis_frame.pack(fill=tk.X, pady=5)
        
        self.open_label = ttk.Label(analysis_frame, text="Open Pattern:\nNo data")
        self.open_label.pack(pady=5)
        
        self.close_label = ttk.Label(analysis_frame, text="Close Pattern:\nNo data")
        self.close_label.pack(pady=5)
        
        # Current Values
        values_frame = ttk.LabelFrame(control_frame, text="Current Values", padding=10)
        values_frame.pack(fill=tk.X, pady=5)
        
        self.value_label = ttk.Label(values_frame, text="Value: -")
        self.value_label.pack(pady=2)
        
        self.slope_label = ttk.Label(values_frame, text="Slope: -")
        self.slope_label.pack(pady=2)
        
        # Plot Area
        plot_frame = ttk.Frame(self.root)
        plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(8, 6))
        
        # Raw signal plot
        self.line1, = self.ax1.plot([], [], 'b-', label='Raw Signal')
        self.ax1.set_title('Raw Signal')
        self.ax1.set_ylabel('Value')
        self.ax1.grid(True)
        self.ax1.legend()
        
        # Slope plot
        self.line2, = self.ax2.plot([], [], 'r-', label='Slope')
        self.ax2.set_title('Slope Pattern')
        self.ax2.set_ylabel('Slope')
        self.ax2.grid(True)
        self.ax2.legend()
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Status Bar
        self.status_bar = ttk.Label(self.root, text="Not Connected", relief=tk.SUNKEN)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=2)
        
    def calculate_slope(self, data):
        if len(data) < 2:
            return 0
        x = np.arange(len(data))
        slope = np.polyfit(x, data, 1)[0]
        return slope
        
    def train_model(self):
        if not self.gesture_data['open']['slopes'] or not self.gesture_data['close']['slopes']:
            messagebox.showerror("Error", "Please record both open and close gestures first")
            return
            
        try:
            # Calculate thresholds based on recorded data
            for gesture in ['open', 'close']:
                max_slopes = np.abs(self.gesture_data[gesture]['max_slopes'])
                mean_max = np.mean(max_slopes)
                std_max = np.std(max_slopes)
                self.gesture_data[gesture]['threshold'] = mean_max - std_max
            
            messagebox.showinfo("Success", "Model trained! You can start prediction")
            self.update_pattern_analysis()
            
        except Exception as e:
            messagebox.showerror("Error", f"Training failed: {str(e)}")
    
    def toggle_prediction(self):
        if not all(self.gesture_data[g]['threshold'] is not None for g in ['open', 'close']):
            messagebox.showerror("Error", "Please train model first")
            return
            
        if not self.is_predicting:
            self.is_predicting = True
            self.predict_btn.config(text="Stop Prediction")
            self.slope_history.clear()
        else:
            self.is_predicting = False
            self.predict_btn.config(text="Start Prediction")
            self.prediction_label.config(text="Prediction: -")
    
    def predict_gesture(self, slope):
        self.slope_history.append(abs(slope))
        if len(self.slope_history) < 3:  # Tunggu minimal 3 data
            return None
            
        avg_slope = np.mean(self.slope_history)
        
        # Cek threshold untuk masing-masing gerakan
        close_match = avg_slope > self.gesture_data['close']['threshold']
        open_match = avg_slope > self.gesture_data['open']['threshold']
        
        if close_match and not open_match:
            return "CLOSE"
        elif open_match and not close_match:
            return "OPEN"
        else:
            return "STABLE"
    
    def update_pattern_analysis(self):
        for gesture in ['open', 'close']:
            slopes = self.gesture_data[gesture]['slopes']
            max_slopes = self.gesture_data[gesture]['max_slopes']
            
            if slopes:
                avg_slope = np.mean(slopes)
                max_slope = np.mean(max_slopes)
                std_slope = np.std(slopes)
                
                label_text = f"{gesture.capitalize()} Pattern:\n"
                label_text += f"Avg Slope: {avg_slope:.2f}\n"
                label_text += f"Max Slope: {max_slope:.2f}\n"
                label_text += f"Std Dev: {std_slope:.2f}"
                
                if gesture == 'open':
                    self.open_label.config(text=label_text)
                else:
                    self.close_label.config(text=label_text)
        
    def toggle_connection(self):
        if self.serial_port is None:
            try:
                port = self.port_entry.get()
                self.serial_port = serial.Serial(port, 9600, timeout=1)
                self.connect_btn.config(text="Disconnect")
                self.status_bar.config(text=f"Connected to {port}")
                threading.Thread(target=self.read_serial, daemon=True).start()
            except Exception as e:
                messagebox.showerror("Error", f"Connection failed: {str(e)}")
        else:
            self.serial_port.close()
            self.serial_port = None
            self.connect_btn.config(text="Connect")
            self.status_bar.config(text="Not Connected")
            
    def toggle_recording(self):
        if not self.is_recording:
            if self.serial_port is None:
                messagebox.showerror("Error", "Please connect first")
                return
                
            self.is_recording = True
            self.current_gesture = self.gesture_var.get()
            self.record_btn.config(text="Stop Recording")
            self.status_bar.config(text=f"Recording {self.current_gesture} gesture")
            
            # Reset buffers for new recording
            self.analysis_buffer.clear()
            current_slopes = []
        else:
            self.is_recording = False
            self.record_btn.config(text="Start Recording")
            self.status_bar.config(text="Recording stopped")
            self.current_gesture = None
            
    def read_serial(self):
        last_plot_update = time.time()
        current_slopes = []
        
        while self.serial_port is not None:
            try:
                if self.serial_port.in_waiting:
                    data = self.serial_port.readline().decode().strip()
                    if data:
                        value = float(data)
                        current_time = time.time()
                        
                        # Update data buffers
                        self.data_buffer.append(value)
                        self.analysis_buffer.append(value)
                        
                        # Calculate slope
                        if len(self.analysis_buffer) >= 2:
                            slope = self.calculate_slope(list(self.analysis_buffer))
                            self.slope_buffer.append(slope)
                            self.slope_label.config(text=f"Slope: {slope:.2f}")
                            
                            # Record slopes if recording
                            if self.is_recording:
                                current_slopes.append(slope)
                                if len(current_slopes) > 5:  # Minimal data points
                                    gesture_data = self.gesture_data[self.current_gesture]
                                    gesture_data['slopes'] = current_slopes
                                    gesture_data['max_slopes'].append(max(abs(np.array(current_slopes))))
                                    self.update_pattern_analysis()
                                    
                            # Make prediction if active
                            if self.is_predicting:
                                prediction = self.predict_gesture(slope)
                                if prediction:
                                    self.prediction_label.config(
                                        text=f"Prediction: {prediction}",
                                        foreground='red' if prediction == "CLOSE" else 
                                                  'green' if prediction == "OPEN" else 'blue'
                                    )
                        
                        # Update value display
                        self.value_label.config(text=f"Value: {value:.1f}")
                        
                        # Update plots every 100ms
                        if current_time - last_plot_update > 0.1:
                            # Update raw signal plot
                            self.line1.set_data(range(len(self.data_buffer)), 
                                              self.data_buffer)
                            self.ax1.relim()
                            self.ax1.autoscale_view()
                            
                            # Update slope plot
                            if len(self.slope_buffer) > 0:
                                self.line2.set_data(range(len(self.slope_buffer)), 
                                                  self.slope_buffer)
                                self.ax2.relim()
                                self.ax2.autoscale_view()
                            
                            self.canvas.draw()
                            last_plot_update = current_time
                            
            except Exception as e:
                print(f"Serial error: {str(e)}")
                break

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = MuscleSlopeLearner()
    app.run()