//bisa ketik text dan kirim

function sendWhatsAppMessage(text) {
    // Ketik pesan
    const textbox = document.querySelector('div[contenteditable="true"][aria-placeholder="Ketik pesan"][role="textbox"]');
    
    if (textbox) {
        textbox.click();
        textbox.focus();
        
        let index = 0;
        const typeInterval = setInterval(() => {
            if (index < text.length) {
                document.execCommand('insertText', false, text[index]);
                index++;
            } else {
                clearInterval(typeInterval);
                // Setelah selesai mengetik, klik tombol kirim
                setTimeout(() => {
                    const sendButton = document.querySelector('button[aria-label="Kirim"]');
                    if (sendButton) {
                        sendButton.click();
                        console.log('Pesan terkirim');
                    } else {
                        console.log('Tombol kirim tidak ditemukan');
                    }
                }, 500); // Tunggu 500ms setelah selesai mengetik
            }
        }, 100);
    } else {
        console.log('Textbox tidak ditemukan');
    }
}

// Gunakan fungsi
sendWhatsAppMessage('Halo, ini adalah pesan test');