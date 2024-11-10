import tkinter as tk
import requests

# Fungsi untuk mengirim permintaan PUT ke server
def switch_mode(mode):
    url = "http://192.168.0.3/LAPI/V1.0/Channels/0/Smart/WorkingStatus"
    headers = {
        "Content-Type": "application/json",
        "Authorization": 'Digest username="admin", realm="102fa3342661", nonce="e8e64f2885e85818b289496d1472a100", algorithm="MD5", uri="/LAPI/V1.0/Channels/0/Smart/WorkingStatus", response="60fa5d8c2abc92e590c2c559878d78b8", qop="auth", nc="00000302", cnonce="d41d8cd98f00b204e9800998ecf8427e", opaque="07c984bd79faee74498abe2331d5e8db"'
    }

    modes = [0, 100, 101, 102, 103, 400, 500]
    enable_ids = [mode]
    disable_ids = [m for m in modes if m != mode]

    data = {
        "EnableNum": 1,
        "EnableIDs": enable_ids,
        "DisableNum": len(disable_ids),
        "DisableIDs": disable_ids
    }

    response = requests.put(url, headers=headers, json=data)
    print(f"Mode {mode} response: {response.status_code}")

# Membuat jendela utama
window = tk.Tk()
window.title("Mode Switch")

# Membuat tombol untuk setiap mode
for mode in [0, 100, 101, 102, 103, 400, 500]:
    button = tk.Button(window, text=f"Mode {mode}", command=lambda m=mode: switch_mode(m))
    button.pack()

# Menjalankan loop utama GUI
window.mainloop()