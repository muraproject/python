import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sys
import os
from datetime import datetime

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    messagebox.showerror("Import Error", "Pyserial is not installed. Please install it using 'pip install pyserial'")
    sys.exit(1)

class ESPRecorderTester:
    def __init__(self, master):
        self.master = master
        master.title("ESP Recorder Tester")
        master.geometry("600x500")

        self.ser = None
        self.current_path = "/"

        self.create_widgets()

    def create_widgets(self):
        # COM Port selection
        tk.Label(self.master, text="COM Port:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.com_port = ttk.Combobox(self.master, values=self.get_serial_ports())
        self.com_port.grid(row=0, column=1, padx=5, pady=5)

        # Baud Rate selection
        tk.Label(self.master, text="Baud Rate:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.baud_rate = ttk.Combobox(self.master, values=['9600', '115200'])
        self.baud_rate.set('115200')
        self.baud_rate.grid(row=1, column=1, padx=5, pady=5)

        # Connect and Disconnect buttons
        self.connect_button = tk.Button(self.master, text="Connect", command=self.connect)
        self.connect_button.grid(row=2, column=0, padx=5, pady=5)
        self.disconnect_button = tk.Button(self.master, text="Disconnect", command=self.disconnect, state=tk.DISABLED)
        self.disconnect_button.grid(row=2, column=1, padx=5, pady=5)

        # Command input
        tk.Label(self.master, text="Command:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.command_entry = tk.Entry(self.master, width=40)
        self.command_entry.grid(row=3, column=1, padx=5, pady=5)
        tk.Button(self.master, text="Send", command=self.send_command).grid(row=3, column=2, padx=5, pady=5)

        # Action buttons
        actions_frame = ttk.Frame(self.master)
        actions_frame.grid(row=4, column=0, columnspan=3, padx=5, pady=5)

        tk.Button(actions_frame, text="Record", command=self.record).grid(row=0, column=0, padx=2, pady=2)
        tk.Button(actions_frame, text="Stop Record", command=self.stop_record).grid(row=0, column=1, padx=2, pady=2)
        tk.Button(actions_frame, text="Play", command=self.play).grid(row=0, column=2, padx=2, pady=2)
        tk.Button(actions_frame, text="Stop Play", command=self.stop_play).grid(row=0, column=3, padx=2, pady=2)
        tk.Button(actions_frame, text="List Files", command=self.list_files).grid(row=1, column=0, padx=2, pady=2)
        tk.Button(actions_frame, text="Delete File", command=self.delete_file).grid(row=1, column=1, padx=2, pady=2)
        tk.Button(actions_frame, text="Check Memory", command=self.check_memory).grid(row=1, column=2, padx=2, pady=2)

        # Response area
        tk.Label(self.master, text="Response:").grid(row=5, column=0, sticky="nw", padx=5, pady=5)
        self.response_text = tk.Text(self.master, height=10, width=60)
        self.response_text.grid(row=5, column=1, columnspan=2, padx=5, pady=5)

        # Current path and file list
        tk.Label(self.master, text="Current Path:").grid(row=6, column=0, sticky="e", padx=5, pady=5)
        self.path_var = tk.StringVar(value=self.current_path)
        tk.Entry(self.master, textvariable=self.path_var, state='readonly', width=40).grid(row=6, column=1, padx=5, pady=5)
        tk.Button(self.master, text="Up", command=self.go_up_folder).grid(row=6, column=2, padx=5, pady=5)

        self.file_listbox = tk.Listbox(self.master, height=10, width=60)
        self.file_listbox.grid(row=7, column=0, columnspan=3, padx=5, pady=5)
        self.file_listbox.bind('<Double-1>', self.on_item_double_click)

    def get_serial_ports(self):
        return [port.device for port in list_ports.comports()]

    def connect(self):
        try:
            self.ser = serial.Serial(self.com_port.get(), int(self.baud_rate.get()), timeout=1)
            self.connect_button.config(state=tk.DISABLED)
            self.disconnect_button.config(state=tk.NORMAL)
            self.update_response("Connected to " + self.com_port.get())
            self.list_files()
        except serial.SerialException as e:
            self.update_response(f"Error: {str(e)}")

    def disconnect(self):
        if self.ser:
            self.ser.close()
            self.ser = None
            self.connect_button.config(state=tk.NORMAL)
            self.disconnect_button.config(state=tk.DISABLED)
            self.update_response("Disconnected")

    def send_command(self):
        if self.ser:
            command = self.command_entry.get()
            response = self.send_and_receive(command)
            self.update_response(response)

    def send_and_receive(self, command):
        if not self.ser:
            return "Not connected to any port"
        try:
            self.ser.write((command + '\n').encode())
            response = ""
            while True:
                line = self.ser.readline().decode().strip()
                if line == "END_OF_LIST" or line == "":
                    break
                response += line + "\n"
            return response
        except serial.SerialException as e:
            return f"Error: {str(e)}"

    def record(self):
        now = datetime.now()
        folder_name = now.strftime("%Y%m%d")
        file_name = now.strftime("%H%M%S.wav")
        full_path = f"/{folder_name}/{file_name}"
        response = self.send_and_receive(f"RECORD_{full_path}")
        self.update_response(response)

    def stop_record(self):
        response = self.send_and_receive("STOP_RECORD")
        self.update_response(response)
        self.list_files()  # Refresh the file list after stopping recording

    def play(self):
        selected = self.file_listbox.get(tk.ACTIVE)
        if selected:
            if selected.endswith('/'):  # It's a folder
                self.current_path = os.path.join(self.current_path, selected[:-1]).replace("\\", "/")
                self.path_var.set(self.current_path)
                self.list_files()
            else:  # It's a file
                full_path = os.path.join(self.current_path, selected).replace("\\", "/")
                response = self.send_and_receive(f"PLAY_{full_path}")
                print(full_path)
                self.update_response(response)

    def stop_play(self):
        response = self.send_and_receive("STOP_PLAY")
        self.update_response(response)

    def list_files(self):
        response = self.send_and_receive(f"LIST_{self.current_path}")
        items = response.strip().split('\n')
        self.file_listbox.delete(0, tk.END)
        for item in items:
            if item.endswith('/'):  # It's a folder
                self.file_listbox.insert(tk.END, f"📁 {item}")
            else:  # It's a file
                self.file_listbox.insert(tk.END, f"{item}")

    def delete_file(self):
        selected = self.file_listbox.get(tk.ACTIVE)
        if selected:
            item_name = selected[2:]  # Remove the icon
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {item_name}?"):
                full_path = os.path.join(self.current_path, item_name).replace("\\", "/")
                response = self.send_and_receive(f"DELETE_{full_path}")
                self.update_response(response)
                self.list_files()  # Refresh file list

    def check_memory(self):
        response = self.send_and_receive("CHECK_MEMORY")
        self.update_response(response)

    def go_up_folder(self):
        if self.current_path != "/":
            self.current_path = os.path.dirname(self.current_path)
            if self.current_path == "":
                self.current_path = "/"
            self.path_var.set(self.current_path)
            self.list_files()

    def on_item_double_click(self, event):
        selected = self.file_listbox.get(tk.ACTIVE)
        if selected.startswith("📁"):  # It's a folder
            folder_name = selected[2:-1]  # Remove the folder icon and trailing '/'
            self.current_path = os.path.join(self.current_path, folder_name).replace("\\", "/")
            self.path_var.set(self.current_path)
            self.list_files()
        elif selected.startswith("📄"):  # It's a file
            self.play()  # Play the selected file

    def update_response(self, text):
        self.response_text.delete('1.0', tk.END)
        self.response_text.insert(tk.END, text)

if __name__ == '__main__':
    root = tk.Tk()
    app = ESPRecorderTester(root)
    root.mainloop()