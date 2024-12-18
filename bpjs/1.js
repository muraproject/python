async function checkKPJ() {
    const input = prompt("Masukkan nomor KPJ (pisahkan dengan koma):").trim();
    if (!input) return;
    
    const kpjList = input.split(',').map(kpj => kpj.trim());
    const url = "https://sipp.bpjsketenagakerjaan.go.id/tenaga-kerja/baru/get-tk-kpj";
    
    console.log("Memproses...");
    
    for(const kpj of kpjList) {
        if (!kpj) continue;
        try {
            const response = await fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: `kpj=${kpj}`
            });
            const data = await response.json();
            
            if(data.ret === "0" && data.data && data.data[0]) {
                const tk = data.data[0];
                const result = `${tk.tgl_lahir.split('-')[1]}-${tk.tgl_lahir.split('-')[2]}&${tk.nomor_identitas}&${tk.nama_tk}&${tk.tempat_lahir}&${tk.alamat}&${tk.tgl_lahir}&0&${tk.jenis_identitas}&${tk.jenis_kelamin}&${tk.email}&${tk.handphone}`;
                console.log(result);
            } else {
                console.log(`KPJ ${kpj} sudah tidak dapat digunakan.`);
            }
            
            await new Promise(r => setTimeout(r, 1000));
        } catch(e) {
            console.error(`Error checking KPJ ${kpj}:`, e);
        }
    }
    
    console.log("Selesai!");
}

// Jalankan
checkKPJ();