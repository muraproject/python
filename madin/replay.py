from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import json
import time
from datetime import datetime

class BrowserRecorder:
    def __init__(self):
        self.driver = webdriver.Chrome()
        self.actions = []
        self.is_recording = False
        
    def start_recording(self):
        """Memulai perekaman aktivitas browser"""
        self.is_recording = True
        self.actions = []
        print("Perekaman dimulai. Ketik 'selesai' di terminal untuk mengakhiri.")
        
    def stop_recording(self):
        """Menghentikan perekaman dan menyimpan hasil"""
        self.is_recording = False
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.actions, f)
        
        print(f"Perekaman disimpan ke {filename}")
        
    def record_action(self, action_type, data):
        """Merekam setiap aksi yang dilakukan"""
        if self.is_recording:
            self.actions.append({
                'type': action_type,
                'data': data,
                'timestamp': time.time()
            })
            
    def replay(self, filename):
        """Memutar ulang rekaman dari file"""
        with open(filename, 'r') as f:
            actions = json.load(f)
        
        print("Memulai replay...")
        for action in actions:
            if action['type'] == 'navigate':
                self.driver.get(action['data'])
            elif action['type'] == 'click':
                element = self.driver.find_element(By.XPATH, action['data'])
                element.click()
            elif action['type'] == 'type':
                element = self.driver.find_element(By.XPATH, action['data']['xpath'])
                element.send_keys(action['data']['text'])
            time.sleep(1)  # Delay antar aksi
        
        print("Replay selesai")

    def listen_events(self):
        """Mendengarkan event dari browser"""
        self.driver.execute_script("""
            document.addEventListener('click', function(e) {
                window.last_click = {
                    xpath: getXPath(e.target),
                    text: e.target.textContent
                };
            });
            
            document.addEventListener('input', function(e) {
                window.last_input = {
                    xpath: getXPath(e.target),
                    value: e.target.value
                };
            });
            
            function getXPath(element) {
                if (element.id !== '')
                    return `//*[@id="${element.id}"]`;
                if (element === document.body)
                    return '/html/body';
                
                var ix = 0;
                var siblings = element.parentNode.childNodes;
                
                for (var i = 0; i < siblings.length; i++) {
                    var sibling = siblings[i];
                    if (sibling === element)
                        return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                    if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                        ix++;
                }
            };
        """)

def main():
    recorder = BrowserRecorder()
    print("Ketik 'mulai' untuk memulai perekaman, 'selesai' untuk mengakhiri")
    print("Untuk replay, ketik 'replay nama_file.json'")
    
    while True:
        command = input("> ").strip().lower()
        
        if command == "mulai":
            recorder.start_recording()
            recorder.listen_events()
        
        elif command == "selesai":
            recorder.stop_recording()
        
        elif command.startswith("replay "):
            filename = command.split()[1]
            recorder.replay(filename)
        
        elif command == "keluar":
            recorder.driver.quit()
            break

if __name__ == "__main__":
    main()