function checkKPJ() {
    const input = prompt("Masukkan nomor KPJ (pisahkan dengan spasi atau enter):").trim();
    if (!input) return;
    
    // Parse input - split by spasi atau newline
    const kpjList = input
        .split(/[\s,\n]+/) // Split by spasi, koma, atau newline
        .map(kpj => kpj.trim())
        .filter(kpj => kpj.length > 0); // Remove empty entries
    
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

    // Close button
    const closeButton = document.createElement('button');
    closeButton.textContent = '×';
    closeButton.style.cssText = `
        position: absolute;
        top: 10px;
        right: 10px;
        background: none;
        border: none;
        font-size: 20px;
        cursor: pointer;
        color: #666;
    `;
    closeButton.onclick = () => container.remove();

    const progressArea = document.createElement('div');
    progressArea.style.cssText = `
        margin-bottom: 15px;
        padding: 10px;
        background: #f5f5f5;
        border-radius: 4px;
        margin-top: 20px;
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

    container.appendChild(closeButton);
    container.appendChild(progressArea);
    container.appendChild(finalResultArea);
    container.appendChild(copyButton);
    document.body.appendChild(container);

    const url = "https://sipp.bpjsketenagakerjaan.go.id/tenaga-kerja/baru/get-tk-kpj";
    const allResults = [];
    
    progressArea.innerHTML = `Total KPJ: ${kpjList.length}<br>Memproses...`;
    
    (async () => {
        for(let i = 0; i < kpjList.length; i++) {
            const kpj = kpjList[i];
            try {
                progressArea.innerHTML = `Progress: ${i + 1}/${kpjList.length}<br>Checking KPJ: ${kpj}...`;
                
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
                    result = `${kpj}&${tk.tgl_lahir.split('-')[1]}-${tk.tgl_lahir.split('-')[2]}&${tk.nomor_identitas}&${tk.nama_tk}&${tk.tempat_lahir}&${tk.alamat}&${tk.tgl_lahir}&0&${tk.jenis_identitas}&${tk.jenis_kelamin}&${tk.email}&${tk.handphone}`;
                } else {
                    result = `KPJ ${kpj} sudah tidak dapat digunakan.`;
                }
                
                allResults.push(result);
                progressArea.innerHTML += `<br>${result}`;
                
                await new Promise(r => setTimeout(r, 1000));
            } catch(e) {
                const errorMsg = `Error checking KPJ ${kpj}: ${e.message}`;
                allResults.push(errorMsg);
                progressArea.innerHTML += `<br>${errorMsg}`;
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
    })();
}

checkKPJ();