import tkinter as tk
import subprocess
import json

def send_curl_request(url, data):
    headers = [
        "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
        "Accept: application/json, text/javascript, */*; q=0.01",
        "Accept-Language: en-US,en;q=0.5",
        "Accept-Encoding: gzip, deflate",
        "Referer: http://192.168.0.3/page/common/frame.59923ff2.htm",
        "Content-Type: application/json; charset=UTF-8",
        "Authorization: Digest username=\"admin\", realm=\"102fa3342661\", nonce=\"e8e64f2885e85818b289496d1472a100\", algorithm=\"MD5\", uri=\"/LAPI/V1.0/Channels/0/Smart/WorkingStatus\", response=\"92d2d6cb40b9abed77c56650267c5294\", qop=\"auth\", nc=\"00000050\", cnonce=\"d41d8cd98f00b204e9800998ecf8427e\", opaque=\"07c984bd79faee74498abe2331d5e8db\"",
        "X-Requested-With: XMLHttpRequest",
        "Origin: http://192.168.0.3",
        "Connection: keep-alive", 
        "Cookie: WebLoginHandle=1731240138974; langInfo_=1",
        "Priority: u=0",
        "Pragma: no-cache",
        "Cache-Control: no-cache"
    ]

    cmd = [
        'curl', url, 
        '-X', 'PUT',
        *['-H' + header for header in headers],
        '--data-raw', json.dumps(data)
    ]

    response = subprocess.run(cmd, capture_output=True, text=True)
    return response.stdout

def disable_items():
    url = "http://192.168.0.3/LAPI/V1.0/Channels/0/Smart/WorkingStatus"
    data = {
        "EnableNum": 0,
        "EnableIDs": [],
        "DisableNum": 25,
        "DisableIDs": [101, 102, 103, 207, 200, 208, 201, 202, 203, 204, 205, 1, 3, 206, 4, 0, 2, 106, 5, 6, 300, 301, 400, 500, 100]
    }
    response = send_curl_request(url, data)
    log_text.insert(tk.END, "Disable Response:\n" + response + "\n")

def enable_items():
    url = "http://192.168.0.3/LAPI/V1.0/Channels/0/Smart/WorkingStatus"  
    data = {
        "EnableNum": 1,
        "EnableIDs": [100],
        "DisableNum": 24,
        "DisableIDs": [101, 102, 103, 207, 200, 208, 201, 202, 203, 204, 205, 1, 3, 206, 4, 0, 2, 106, 5, 6, 300, 301, 400, 500]
    }
    response = send_curl_request(url, data)
    log_text.insert(tk.END, "Enable Response:\n" + response + "\n")

# Create main window
window = tk.Tk()
window.title("CURL Control")

# Create buttons
disable_button = tk.Button(window, text="Disable", command=disable_items)
disable_button.pack()

enable_button = tk.Button(window, text="Enable", command=enable_items)
enable_button.pack()

# Create log text area
log_text = tk.Text(window)
log_text.pack()

# Start GUI
window.mainloop()