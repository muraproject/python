// Fungsi untuk mencari dan menampilkan semua list chat
function getWhatsAppChats() {
    // Cari semua list item chat
    const chatList = document.querySelectorAll('div[role="listitem"]');
    
    // Array untuk menyimpan hasil
    const chats = [];
    
    chatList.forEach((chat, index) => {
        // Cari judul chat (nama kontak/grup)
        const titleElement = chat.querySelector('span[dir="auto"][title]');
        const chatTitle = titleElement ? titleElement.title : 'Unknown Chat';
        
        // Masukkan ke array
        chats.push(chatTitle);
    });
    
    // Tampilkan hasil
    console.log('=== Daftar Chat WhatsApp ===');
    chats.forEach((chat, index) => {
        console.log(`${index + 1}. ${chat}`);
    });
    console.log(`Total chat ditemukan: ${chats.length}`);
    
    // Kembalikan array hasil jika diperlukan untuk penggunaan lain
    return chats;
 }
 
 // Jalankan fungsi
 getWhatsAppChats();