import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import numpy as np
import csv
from datetime import datetime
import threading
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier

class MuscleDataCollector:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Muscle Sensor Data Collector")
        self.root.geometry("1000x600")
        
        self.serial_port = None
        self.is_recording = False
        self.is_predicting = False
        self.current_gesture = "open"
        self.window_size = 100
        
        self.data_buffer = deque(maxlen=200)
        self.recording_buffer = []
        self.predict_buffer = deque(maxlen=self.window_size)
        
        # Model dan Scaler
        self.model = KNeighborsClassifier(n_neighbors=3)
        self.scaler = StandardScaler()
        self.is_model_trained = False
        
        self.setup_plot()
        self.setup_gui()
        
    def setup_plot(self):
        self.fig, self.ax = plt.subplots(figsize=(8, 4))
        self.line, = self.ax.plot([], [], 'b-')
        self.ax.set_title('Real-time Muscle Sensor Data')
        self.ax.set_xlabel('Samples')
        self.ax.set_ylabel('Value')
        self.ax.grid(True)
        
    def setup_gui(self):
        # Left Panel
        control_panel = ttk.Frame(self.root)
        control_panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)
        
        # Serial Connection Frame
        connection_frame = ttk.LabelFrame(control_panel, text="Serial Connection", padding=10)
        connection_frame.pack(fill="x", pady=5)
        
        ttk.Label(connection_frame, text="Port:").grid(row=0, column=0, padx=5)
        self.port_entry = ttk.Entry(connection_frame, width=15)
        self.port_entry.insert(0, "COM3")
        self.port_entry.grid(row=0, column=1, padx=5)
        
        self.connect_btn = ttk.Button(connection_frame, text="Connect", 
                                    command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=2, padx=5)

        # Recording Frame
        recording_frame = ttk.LabelFrame(control_panel, text="Data Recording", padding=10)
        recording_frame.pack(fill="x", pady=5)
        
        ttk.Label(recording_frame, text="Gesture:").pack(pady=5)
        self.gesture_var = tk.StringVar(value="open")
        ttk.Radiobutton(recording_frame, text="Open Hand", variable=self.gesture_var, 
                       value="open").pack()
        ttk.Radiobutton(recording_frame, text="Closed Hand", variable=self.gesture_var, 
                       value="closed").pack()
        
        self.record_btn = ttk.Button(recording_frame, text="Start Recording", 
                                   command=self.toggle_recording)
        self.record_btn.pack(pady=10)
        
        self.samples_label = ttk.Label(recording_frame, text="Recorded Windows: 0")
        self.samples_label.pack(pady=5)
        
        # Data Management Frame
        data_frame = ttk.LabelFrame(control_panel, text="Data Management", padding=10)
        data_frame.pack(fill="x", pady=5)
        
        self.save_btn = ttk.Button(data_frame, text="Save Data", command=self.save_data)
        self.save_btn.pack(pady=5)
        
        self.load_btn = ttk.Button(data_frame, text="Load & Train", command=self.load_and_train)
        self.load_btn.pack(pady=5)

        # Prediction Frame
        prediction_frame = ttk.LabelFrame(control_panel, text="Real-time Prediction", padding=10)
        prediction_frame.pack(fill="x", pady=5)
        
        self.predict_btn = ttk.Button(prediction_frame, text="Start Prediction", 
                                    command=self.toggle_prediction)
        self.predict_btn.pack(pady=5)
        
        self.prediction_label = ttk.Label(prediction_frame, text="Prediction: -",
                                        font=("Arial", 14, "bold"))
        self.prediction_label.pack(pady=5)

        # Statistics Frame
        stats_frame = ttk.LabelFrame(control_panel, text="Current Window Stats", padding=10)
        stats_frame.pack(fill="x", pady=5)
        
        self.min_label = ttk.Label(stats_frame, text="Min: -")
        self.min_label.pack(pady=2)
        self.max_label = ttk.Label(stats_frame, text="Max: -")
        self.max_label.pack(pady=2)
        self.mean_label = ttk.Label(stats_frame, text="Mean: -")
        self.mean_label.pack(pady=2)
        self.std_label = ttk.Label(stats_frame, text="Std: -")
        self.std_label.pack(pady=2)

        # Right Panel
        plot_panel = ttk.Frame(self.root)
        plot_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_panel)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Status Bar
        self.status_label = ttk.Label(self.root, text="Status: Not connected", 
                                    relief=tk.SUNKEN)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    def extract_features(self, window_data):
        features = [
            np.mean(window_data),
            np.std(window_data),
            np.max(window_data),
            np.min(window_data),
            np.median(window_data)
        ]
        return features

    def load_and_train(self):
        try:
            filename = filedialog.askopenfilename(
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
            if not filename:
                return
                
            X = []  # features
            y = []  # labels
            
            with open(filename, 'r') as f:
                reader = csv.reader(f)
                headers = next(reader)
                
                for row in reader:
                    gesture = row[0]
                    data = [float(x) for x in row[2:]]  # skip gesture and timestamp
                    features = self.extract_features(data)
                    X.append(features)
                    y.append(1 if gesture == 'closed' else 0)
            
            X = np.array(X)
            y = np.array(y)
            
            # Normalize features
            X_scaled = self.scaler.fit_transform(X)
            
            # Train model
            self.model.fit(X_scaled, y)
            self.is_model_trained = True
            
            messagebox.showinfo("Success", "Model trained successfully!")
            self.status_label.config(text="Status: Model trained and ready")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load and train: {str(e)}")

    def toggle_prediction(self):
        if not self.is_model_trained:
            messagebox.showerror("Error", "Please load and train model first")
            return
            
        if not self.is_predicting:
            if self.serial_port is None:
                messagebox.showerror("Error", "Please connect to Arduino first")
                return
                
            self.is_predicting = True
            self.predict_btn.config(text="Stop Prediction")
            self.predict_buffer.clear()
        else:
            self.is_predicting = False
            self.predict_btn.config(text="Start Prediction")
            self.prediction_label.config(text="Prediction: -")

    def make_prediction(self, window_data):
        try:
            features = self.extract_features(window_data)
            features_scaled = self.scaler.transform([features])
            prediction = self.model.predict(features_scaled)[0]
            gesture = "CLOSED" if prediction == 1 else "OPEN"
            self.prediction_label.config(
                text=f"Prediction: {gesture}",
                foreground='red' if gesture == "CLOSED" else 'green'
            )
        except Exception as e:
            print(f"Prediction error: {str(e)}")

    def toggle_connection(self):
        if self.serial_port is None:
            try:
                port = self.port_entry.get()
                self.serial_port = serial.Serial(port, 9600, timeout=1)
                self.connect_btn.config(text="Disconnect")
                self.status_label.config(text=f"Status: Connected to {port}")
                threading.Thread(target=self.read_serial, daemon=True).start()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to connect: {str(e)}")
        else:
            self.serial_port.close()
            self.serial_port = None
            self.connect_btn.config(text="Connect")
            self.status_label.config(text="Status: Not connected")

    def toggle_recording(self):
        if not self.is_recording:
            if self.serial_port is None:
                messagebox.showerror("Error", "Please connect to Arduino first")
                return
            
            self.is_recording = True
            self.record_btn.config(text="Stop Recording")
            self.current_gesture = self.gesture_var.get()
            self.status_label.config(text=f"Status: Recording {self.current_gesture} gesture")
        else:
            self.is_recording = False
            self.record_btn.config(text="Start Recording")
            self.status_label.config(text="Status: Recording stopped")

    def update_stats(self, window_data):
        if len(window_data) > 0:
            self.min_label.config(text=f"Min: {min(window_data):.2f}")
            self.max_label.config(text=f"Max: {max(window_data):.2f}")
            self.mean_label.config(text=f"Mean: {np.mean(window_data):.2f}")
            self.std_label.config(text=f"Std: {np.std(window_data):.2f}")

    def read_serial(self):
        current_window = []
        
        while self.serial_port is not None:
            try:
                if self.serial_port.in_waiting:
                    data = self.serial_port.readline().decode().strip()
                    if data:
                        value = float(data)
                        self.data_buffer.append(value)
                        
                        # Update plot
                        self.line.set_data(range(len(self.data_buffer)), self.data_buffer)
                        self.ax.relim()
                        self.ax.autoscale_view()
                        self.canvas.draw()
                        
                        # Handle recording
                        if self.is_recording:
                            current_window.append(value)
                            if len(current_window) >= self.window_size:
                                self.update_stats(current_window)
                                self.recording_buffer.append({
                                    'gesture': self.current_gesture,
                                    'data': current_window.copy(),
                                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                })
                                self.samples_label.config(
                                    text=f"Recorded Windows: {len(self.recording_buffer)}")
                                current_window = []
                        
                        # Handle prediction
                        if self.is_predicting:
                            self.predict_buffer.append(value)
                            if len(self.predict_buffer) >= self.window_size:
                                self.make_prediction(list(self.predict_buffer))
                                
                time.sleep(0.01)
            except Exception as e:
                print(f"Error reading serial: {str(e)}")
                break

    def save_data(self):
        if not self.recording_buffer:
            messagebox.showwarning("Warning", "No data to save!")
            return
            
        try:
            filename = f"muscle_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['gesture', 'timestamp'] + [f'sample_{i}' for i in range(self.window_size)])
                
                for record in self.recording_buffer:
                    writer.writerow([
                        record['gesture'],
                        record['timestamp']
                    ] + record['data'])
            
            messagebox.showinfo("Success", f"Data saved to {filename}")
            self.recording_buffer = []
            self.samples_label.config(text="Recorded Windows: 0")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save data: {str(e)}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = MuscleDataCollector()
    app.run()