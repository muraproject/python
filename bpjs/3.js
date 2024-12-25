async function checkKPJ() {
    // Rate limiting variables
    const MAX_REQUESTS = 10; // Maksimum request per sesi
    const COOLDOWN_MINUTES = 5; // Waktu cooldown dalam menit
    
    // Check last request time from localStorage
    const lastRequestTime = localStorage.getItem('lastKPJRequestTime');
    const currentTime = Date.now();
    const requestCount = parseInt(localStorage.getItem('kpjRequestCount') || '0');
    
    // Check cooldown
    if (lastRequestTime && (currentTime - parseInt(lastRequestTime)) < (COOLDOWN_MINUTES * 60 * 1000)) {
        const remainingTime = Math.ceil((COOLDOWN_MINUTES * 60 * 1000 - (currentTime - parseInt(lastRequestTime))) / 1000 / 60);
        alert(`Mohon tunggu ${remainingTime} menit lagi sebelum melakukan request baru.`);
        return;
    }
    
    // Check request limit
    if (requestCount >= MAX_REQUESTS) {
        if (!lastRequestTime || (currentTime - parseInt(lastRequestTime)) >= (COOLDOWN_MINUTES * 60 * 1000)) {
            // Reset counter after cooldown
            localStorage.setItem('kpjRequestCount', '0');
        } else {
            alert(`Batas maksimum ${MAX_REQUESTS} request tercapai. Mohon tunggu ${COOLDOWN_MINUTES} menit.`);
            return;
        }
    }

    const input = prompt("Masukkan nomor KPJ (maksimum 10, pisahkan dengan koma):").trim();
    if (!input) return;
    
    const kpjList = input.split(',').map(kpj => kpj.trim()).filter(kpj => kpj);
    
    // Limit jumlah KPJ yang bisa diproses
    if (kpjList.length > MAX_REQUESTS) {
        alert(`Maksimum ${MAX_REQUESTS} KPJ per request. Anda memasukkan ${kpjList.length} KPJ.`);
        return;
    }

    // Create results container
    const container = document.createElement('div');
    container.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        width: 400px;
        max-height: 80vh;
        background: white;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        z-index: 10000;
        font-family: Arial, sans-serif;
        overflow-y: auto;
    `;

    // Update request counter and timestamp
    localStorage.setItem('kpjRequestCount', (requestCount + kpjList.length).toString());
    localStorage.setItem('lastKPJRequestTime', currentTime.toString());

    // Create progress counter
    const progressCounter = document.createElement('div');
    progressCounter.style.cssText = `
        position: sticky;
        top: 0;
        background: white;
        padding: 5px;
        border-bottom: 1px solid #ddd;
        margin-bottom: 10px;
    `;
    progressCounter.innerHTML = `Sisa request: ${MAX_REQUESTS - requestCount - kpjList.length}`;

    const progressArea = document.createElement('div');
    progressArea.style.cssText = `
        margin-bottom: 15px;
        padding: 10px;
        background: #f5f5f5;
        border-radius: 4px;
    `;

    const finalResultArea = document.createElement('div');
    finalResultArea.style.cssText = `
        border-top: 1px solid #ddd;
        padding-top: 15px;
        margin-top: 15px;
    `;

    const copyButton = document.createElement('button');
    copyButton.textContent = 'Copy Hasil';
    copyButton.style.cssText = `
        background: #28a745;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        cursor: pointer;
        margin-top: 10px;
    `;

    container.appendChild(progressCounter);
    container.appendChild(progressArea);
    container.appendChild(finalResultArea);
    container.appendChild(copyButton);
    document.body.appendChild(container);

    const url = "https://sipp.bpjsketenagakerjaan.go.id/tenaga-kerja/baru/get-tk-kpj";
    const allResults = [];
    
    progressArea.innerHTML = "Memproses...";
    
    for(const kpj of kpjList) {
        try {
            progressArea.innerHTML = `Checking KPJ: ${kpj}...`;
            
            const response = await fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: `kpj=${kpj}`
            });
            const data = await response.json();
            
            let result;
            if(data.ret === "0" && data.data && data.data[0]) {
                const tk = data.data[0];
                result = `${tk.tgl_lahir.split('-')[1]}-${tk.tgl_lahir.split('-')[2]}&${tk.nomor_identitas}&${tk.nama_tk}&${tk.tempat_lahir}&${tk.alamat}&${tk.tgl_lahir}&0&${tk.jenis_identitas}&${tk.jenis_kelamin}&${tk.email}&${tk.handphone}`;
            } else {
                result = `KPJ ${kpj} sudah tidak dapat digunakan.`;
            }
            
            allResults.push(result);
            progressArea.innerHTML += `<br>${result}`;
            console.log(result);
            
            await new Promise(r => setTimeout(r, 1000));
        } catch(e) {
            const errorMsg = `Error checking KPJ ${kpj}: ${e.message}`;
            allResults.push(errorMsg);
            progressArea.innerHTML += `<br>${errorMsg}`;
            console.error(errorMsg);
        }
    }
    
    progressArea.innerHTML = "Proses selesai!";
    finalResultArea.innerHTML = "<strong>Hasil Final:</strong><br>" + allResults.join('<br>');
    
    copyButton.addEventListener('click', () => {
        navigator.clipboard.writeText(allResults.join('\n')).then(() => {
            copyButton.textContent = 'Copied!';
            setTimeout(() => {
                copyButton.textContent = 'Copy Hasil';
            }, 2000);
        });
    });
}

// Jalankan
checkKPJ();