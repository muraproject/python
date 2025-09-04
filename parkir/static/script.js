// Global variables
let currentPage = 'masuk';
let currentBarcodeData = null;
let parkingUpdateInterval;
let cameraStreamIntervals = {};

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    showPage('masuk');
    loadSettings();
    startParkingListUpdates();
    updateCameraStatus();
    initializeCameraStreams();
});

// Page Navigation
function showPage(pageName) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.add('hidden');
    });
    
    // Show selected page
    document.getElementById(`page-${pageName}`).classList.remove('hidden');
    
    // Update navigation buttons
    document.querySelectorAll('nav button').forEach(btn => {
        btn.classList.remove('bg-primary');
        btn.classList.add('hover:bg-gray-700');
    });
    
    document.getElementById(`nav-${pageName}`).classList.add('bg-primary');
    document.getElementById(`nav-${pageName}`).classList.remove('hover:bg-gray-700');
    
    currentPage = pageName;
    
    // Page-specific initialization
    if (pageName === 'keluar') {
        updateParkingList();
        updateCameraPreview('keluar');
    } else if (pageName === 'masuk') {
        updateCameraPreview('masuk');
    } else if (pageName === 'admin') {
        loadSettings();
        updateCameraStatus();
    }
}

// Camera Stream Management
function initializeCameraStreams() {
    startCameraStream('masuk');
    startCameraStream('keluar');
}

function startCameraStream(cameraType) {
    // Stop existing stream if any
    if (cameraStreamIntervals[cameraType]) {
        clearInterval(cameraStreamIntervals[cameraType]);
    }
    
    const streamImg = document.getElementById(`camera-${cameraType}-stream`);
    const placeholder = document.getElementById(`camera-${cameraType}-placeholder`);
    
    if (!streamImg || !placeholder) return;
    
    // Try MJPEG stream first (faster)
    streamImg.src = `/api/camera-stream/${cameraType}`;
    streamImg.onerror = function() {
        // Fallback to static frame updates if stream fails
        streamImg.classList.add('hidden');
        placeholder.classList.remove('hidden');
        startStaticFrameUpdates(cameraType);
    };
    
    streamImg.onload = function() {
        streamImg.classList.remove('hidden');
        placeholder.classList.add('hidden');
    };
}

function startStaticFrameUpdates(cameraType) {
    // Update with static frames every 2 seconds as fallback
    cameraStreamIntervals[cameraType] = setInterval(() => {
        updateStaticCameraFrame(cameraType);
    }, 2000);
}

function updateStaticCameraFrame(cameraType) {
    fetch(`/api/camera-frame/${cameraType}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.image) {
                const streamImg = document.getElementById(`camera-${cameraType}-stream`);
                const placeholder = document.getElementById(`camera-${cameraType}-placeholder`);
                
                if (streamImg && placeholder) {
                    streamImg.src = `data:image/jpeg;base64,${data.image}`;
                    streamImg.classList.remove('hidden');
                    placeholder.classList.add('hidden');
                }
            }
        })
        .catch(error => {
            console.error('Error updating camera frame:', error);
        });
}

// Camera Preview Updates
function updateCameraPreview(cameraType) {
    fetch(`/api/simulate-camera/${cameraType}`)
        .then(response => response.json())
        .then(data => {
            const urlElement = document.getElementById(`camera-${cameraType}-url`);
            if (urlElement) {
                urlElement.textContent = data.camera_url || 'No URL configured';
            }
            
            if (data.success && data.status === 'connected') {
                // Camera is connected, stream should be working
                startCameraStream(cameraType);
            } else {
                // Camera not connected, show placeholder
                const streamImg = document.getElementById(`camera-${cameraType}-stream`);
                const placeholder = document.getElementById(`camera-${cameraType}-placeholder`);
                
                if (streamImg) streamImg.classList.add('hidden');
                if (placeholder) {
                    placeholder.classList.remove('hidden');
                    placeholder.innerHTML = `
                        <div class="text-center">
                            <div class="text-4xl mb-2 text-red-500">📷</div>
                            <p class="text-gray-600">Camera ${data.status}</p>
                            <p class="text-xs text-gray-500 mt-1">${data.camera_url || 'Not configured'}</p>
                        </div>
                    `;
                }
            }
        })
        .catch(error => {
            console.error('Error updating camera preview:', error);
        });
}

// Pintu Masuk - Simulate Capture
function simulateCapture() {
    showLoading(true);
    showToast('📸 Capturing photo from camera...', 'info');
    
    // Capture current frame before sending to API
    capturePhotoFromCamera('masuk', (capturedImage) => {
        fetch('/api/masuk', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            showLoading(false);
            if (data.success) {
                displayMasukResult(data.data);
                
                // Show captured photo
                if (capturedImage) {
                    displayCapturedPhoto('masuk', capturedImage);
                }
                
                showToast('✅ Kendaraan berhasil masuk!', 'success');
                
                // Simulate gate opening
                setTimeout(() => {
                    showToast('🚪 Palang terbuka! Silakan masuk.', 'info');
                }, 1000);
            } else {
                showToast('❌ ' + data.message, 'error');
            }
        })
        .catch(error => {
            showLoading(false);
            showToast('❌ Error: ' + error.message, 'error');
        });
    });
}

function capturePhotoFromCamera(cameraType, callback) {
    fetch(`/api/camera-frame/${cameraType}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.image) {
                callback(`data:image/jpeg;base64,${data.image}`);
            } else {
                callback(null);
            }
        })
        .catch(error => {
            console.error('Error capturing photo:', error);
            callback(null);
        });
}

function displayCapturedPhoto(cameraType, imageData) {
    const photoDiv = document.getElementById(`captured-photo-${cameraType}`);
    const photoImg = document.getElementById(`captured-img-${cameraType}`);
    
    if (photoDiv && photoImg && imageData) {
        photoImg.src = imageData;
        photoDiv.classList.remove('hidden');
    }
}

function displayMasukResult(data) {
    const statusDiv = document.getElementById('status-masuk');
    statusDiv.innerHTML = `
        <div class="space-y-4">
            <div class="text-center p-6 bg-green-50 rounded-lg border border-green-200">
                <div class="text-4xl mb-2">✅</div>
                <h4 class="text-xl font-semibold text-green-800 mb-2">Berhasil Masuk!</h4>
                <p class="text-green-700">Kendaraan telah terdaftar dalam sistem</p>
            </div>
            
            <div class="bg-gray-50 p-4 rounded-lg space-y-2">
                <div class="flex justify-between">
                    <span class="font-semibold">Barcode:</span>
                    <span class="font-mono bg-white px-2 py-1 rounded text-lg">${data.barcode}</span>
                </div>
                <div class="flex justify-between">
                    <span class="font-semibold">Tanggal:</span>
                    <span>${data.tanggal_masuk}</span>
                </div>
                <div class="flex justify-between">
                    <span class="font-semibold">Waktu:</span>
                    <span>${data.waktu_masuk}</span>
                </div>
                <div class="flex justify-between">
                    <span class="font-semibold">Foto:</span>
                    <span class="text-sm text-gray-600">${data.foto_masuk}</span>
                </div>
            </div>
            
            <button onclick="resetMasukForm()" class="w-full bg-blue-500 hover:bg-blue-600 text-white py-3 rounded-lg font-semibold transition">
                🔄 Proses Kendaraan Baru
            </button>
        </div>
    `;
}

function resetMasukForm() {
    const statusDiv = document.getElementById('status-masuk');
    const photoDiv = document.getElementById('captured-photo-masuk');
    
    statusDiv.innerHTML = `
        <div class="text-center py-8">
            <div class="text-4xl mb-2">⚡</div>
            <p class="text-gray-600">Tekan tombol untuk memproses kendaraan masuk</p>
        </div>
    `;
    
    if (photoDiv) {
        photoDiv.classList.add('hidden');
    }
}

// Pintu Keluar Functions
function cekBarcode() {
    const barcode = document.getElementById('barcode-input').value.trim();
    if (!barcode) {
        showToast('❌ Barcode tidak boleh kosong!', 'error');
        return;
    }
    
    showLoading(true);
    
    fetch('/api/cek-barcode', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ barcode: barcode })
    })
    .then(response => response.json())
    .then(data => {
        showLoading(false);
        if (data.success) {
            currentBarcodeData = data.data;
            displayKendaraanDetail(data.data);
            showToast('✅ Kendaraan ditemukan!', 'success');
        } else {
            document.getElementById('detail-kendaraan').classList.add('hidden');
            showToast('❌ ' + data.message, 'error');
        }
    })
    .catch(error => {
        showLoading(false);
        showToast('❌ Error: ' + error.message, 'error');
    });
}

function displayKendaraanDetail(data) {
    const detailDiv = document.getElementById('detail-kendaraan');
    const contentDiv = document.getElementById('detail-content');
    
    // Calculate current duration
    const masukTime = new Date(`${data.tanggal_masuk} ${data.waktu_masuk}`);
    const now = new Date();
    const durationMs = now - masukTime;
    const duration = formatDuration(durationMs);
    
    contentDiv.innerHTML = `
        <div class="flex justify-between py-1">
            <span class="text-gray-600">Barcode:</span>
            <span class="font-mono font-semibold">${data.barcode}</span>
        </div>
        <div class="flex justify-between py-1">
            <span class="text-gray-600">Tanggal Masuk:</span>
            <span>${data.tanggal_masuk}</span>
        </div>
        <div class="flex justify-between py-1">
            <span class="text-gray-600">Waktu Masuk:</span>
            <span>${data.waktu_masuk}</span>
        </div>
        <div class="flex justify-between py-1">
            <span class="text-gray-600">Durasi:</span>
            <span class="font-semibold text-blue-600">${duration}</span>
        </div>
        <div class="flex justify-between py-1">
            <span class="text-gray-600">Foto Masuk:</span>
            <span class="text-xs text-gray-500">${data.foto_masuk}</span>
        </div>
    `;
    
    detailDiv.classList.remove('hidden');
}

function prosesKeluar() {
    if (!currentBarcodeData) {
        showToast('❌ Tidak ada data kendaraan untuk diproses!', 'error');
        return;
    }
    
    showLoading(true);
    showToast('📸 Capturing exit photo...', 'info');
    
    // Capture photo from exit camera first
    capturePhotoFromCamera('keluar', (capturedImage) => {
        fetch('/api/keluar', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ barcode: currentBarcodeData.barcode })
        })
        .then(response => response.json())
        .then(data => {
            showLoading(false);
            if (data.success) {
                showToast('✅ ' + data.message, 'success');
                
                // Show captured exit photo
                if (capturedImage) {
                    displayCapturedPhoto('keluar', capturedImage);
                }
                
                // Show exit details
                displayExitSuccess(data.data);
                
                // Reset form after success
                setTimeout(() => {
                    document.getElementById('barcode-input').value = '';
                    document.getElementById('detail-kendaraan').classList.add('hidden');
                    document.getElementById('captured-photo-keluar').classList.add('hidden');
                    currentBarcodeData = null;
                    updateParkingList();
                }, 4000);
                
            } else {
                showToast('❌ ' + data.message, 'error');
            }
        })
        .catch(error => {
            showLoading(false);
            showToast('❌ Error: ' + error.message, 'error');
        });
    });
}

function displayExitSuccess(data) {
    const detailDiv = document.getElementById('detail-kendaraan');
    detailDiv.innerHTML = `
        <div class="text-center p-4 bg-green-50 rounded-lg border border-green-200">
            <div class="text-3xl mb-2">🚪✅</div>
            <h4 class="text-lg font-semibold text-green-800 mb-2">Kendaraan Keluar!</h4>
            <div class="text-sm text-green-700 space-y-1">
                <p><strong>Barcode:</strong> ${data.barcode}</p>
                <p><strong>Durasi Parkir:</strong> ${data.durasi}</p>
                <p><strong>Waktu Keluar:</strong> ${data.waktu_keluar}</p>
            </div>
        </div>
    `;
}

// Parking List Management
function updateParkingList() {
    fetch('/api/parking-list')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayParkingList(data.data);
                document.getElementById('total-parkir').textContent = `${data.data.length} kendaraan`;
            }
        })
        .catch(error => {
            console.error('Error updating parking list:', error);
        });
}

function displayParkingList(vehicles) {
    const tbody = document.getElementById('parking-list');
    
    if (vehicles.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="px-4 py-8 text-center text-gray-500">
                    <div class="text-4xl mb-2">🚗</div>
                    <p>Tidak ada kendaraan yang sedang parkir</p>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = vehicles.map(vehicle => {
        const masukTime = new Date(`${vehicle.tanggal_masuk} ${vehicle.waktu_masuk}`);
        const now = new Date();
        const durationMs = now - masukTime;
        const duration = formatDuration(durationMs);
        
        return `
            <tr class="hover:bg-gray-50 transition">
                <td class="px-4 py-3 font-mono text-sm">${vehicle.barcode}</td>
                <td class="px-4 py-3 text-sm">${vehicle.tanggal_masuk}</td>
                <td class="px-4 py-3 text-sm">${vehicle.waktu_masuk}</td>
                <td class="px-4 py-3 text-sm font-semibold text-blue-600">${duration}</td>
                <td class="px-4 py-3">
                    <button onclick="quickExit('${vehicle.barcode}')" class="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded text-sm font-semibold transition">
                        Keluar
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function quickExit(barcode) {
    if (confirm(`Apakah yakin ingin mengeluarkan kendaraan dengan barcode ${barcode}?`)) {
        document.getElementById('barcode-input').value = barcode;
        cekBarcode();
    }
}

function startParkingListUpdates() {
    // Update parking list every 5 seconds
    parkingUpdateInterval = setInterval(() => {
        if (currentPage === 'keluar') {
            updateParkingList();
        }
    }, 5000);
}

function loadSettings() {
    fetch('/api/settings')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('camera-masuk-setting').value = data.data.camera_masuk || '';
                document.getElementById('camera-keluar-setting').value = data.data.camera_keluar || '';
            }
        })
        .catch(error => {
            console.error('Error loading settings:', error);
        });
}

function testCameras() {
    showLoading(true);
    showToast('🔧 Testing camera connections...', 'info');
    
    Promise.all([
        fetch('/api/test-camera/masuk'),
        fetch('/api/test-camera/keluar')
    ])
    .then(responses => Promise.all(responses.map(r => r.json())))
    .then(results => {
        showLoading(false);
        
        const [masukResult, keluarResult] = results;
        
        let successCount = 0;
        let messages = [];
        
        if (masukResult.success) {
            successCount++;
            messages.push('✅ Kamera Masuk: Connected');
        } else {
            messages.push('❌ Kamera Masuk: ' + masukResult.message);
        }
        
        if (keluarResult.success) {
            successCount++;
            messages.push('✅ Kamera Keluar: Connected');
        } else {
            messages.push('❌ Kamera Keluar: ' + keluarResult.message);
        }
        
        if (successCount === 2) {
            showToast('✅ Semua kamera terhubung dengan baik!', 'success');
            // Restart camera streams
            initializeCameraStreams();
        } else if (successCount === 1) {
            showToast('⚠️ Hanya 1 kamera yang terhubung', 'warning');
        } else {
            showToast('❌ Tidak ada kamera yang terhubung', 'error');
        }
        
        // Show detailed messages in console
        console.log('Camera test results:', messages);
        
        updateCameraStatus();
    })
    .catch(error => {
        showLoading(false);
        showToast('❌ Error testing cameras: ' + error.message, 'error');
    });
}

function updateCameraStatus() {
    const statusMasuk = document.getElementById('status-camera-masuk');
    const statusKeluar = document.getElementById('status-camera-keluar');
    
    // Check camera status via API
    fetch('/api/simulate-camera/masuk')
        .then(response => response.json())
        .then(data => {
            if (statusMasuk) {
                if (data.success && data.status === 'connected') {
                    statusMasuk.className = 'px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs';
                    statusMasuk.textContent = 'Online';
                } else {
                    statusMasuk.className = 'px-2 py-1 bg-red-100 text-red-800 rounded-full text-xs';
                    statusMasuk.textContent = data.status || 'Offline';
                }
            }
        })
        .catch(() => {
            if (statusMasuk) {
                statusMasuk.className = 'px-2 py-1 bg-red-100 text-red-800 rounded-full text-xs';
                statusMasuk.textContent = 'Error';
            }
        });
    
    fetch('/api/simulate-camera/keluar')
        .then(response => response.json())
        .then(data => {
            if (statusKeluar) {
                if (data.success && data.status === 'connected') {
                    statusKeluar.className = 'px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs';
                    statusKeluar.textContent = 'Online';
                } else {
                    statusKeluar.className = 'px-2 py-1 bg-red-100 text-red-800 rounded-full text-xs';
                    statusKeluar.textContent = data.status || 'Offline';
                }
            }
        })
        .catch(() => {
            if (statusKeluar) {
                statusKeluar.className = 'px-2 py-1 bg-red-100 text-red-800 rounded-full text-xs';
                statusKeluar.textContent = 'Error';
            }
        });
}

// Utility Functions
function formatDuration(ms) {
    const hours = Math.floor(ms / (1000 * 60 * 60));
    const minutes = Math.floor((ms % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((ms % (1000 * 60)) / 1000);
    
    if (hours > 0) {
        return `${hours}j ${minutes}m`;
    } else if (minutes > 0) {
        return `${minutes}m ${seconds}s`;
    } else {
        return `${seconds}s`;
    }
}

function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container');
    const toast = document.createElement('div');
    
    const colors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        warning: 'bg-yellow-500',
        info: 'bg-blue-500'
    };
    
    toast.className = `${colors[type]} text-white px-6 py-3 rounded-lg shadow-lg transform transition-all duration-300 translate-x-full`;
    toast.textContent = message;
    
    toastContainer.appendChild(toast);
    
    // Animate in
    setTimeout(() => {
        toast.classList.remove('translate-x-full');
    }, 100);
    
    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.add('translate-x-full');
        setTimeout(() => {
            toastContainer.removeChild(toast);
        }, 300);
    }, 3000);
}

function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (show) {
        overlay.classList.remove('hidden');
    } else {
        overlay.classList.add('hidden');
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // Enter key in barcode input
    if (event.target.id === 'barcode-input' && event.key === 'Enter') {
        cekBarcode();
    }
    
    // F1-F3 for page navigation
    if (event.key === 'F1') {
        event.preventDefault();
        showPage('masuk');
    } else if (event.key === 'F2') {
        event.preventDefault();
        showPage('keluar');
    } else if (event.key === 'F3') {
        event.preventDefault();
        showPage('admin');
    }
});

// Cleanup when page is closed
window.addEventListener('beforeunload', function() {
    // Stop all camera stream intervals
    for (let interval of Object.values(cameraStreamIntervals)) {
        if (interval) clearInterval(interval);
    }
    
    // Stop parking list updates
    if (parkingUpdateInterval) {
        clearInterval(parkingUpdateInterval);
    }
});

// Auto-refresh camera previews and status
setInterval(() => {
    updateCameraStatus();
}, 30000); // Every 30 seconds

// Restart camera streams when settings are saved
function saveSettings(event) {
    event.preventDefault();
    
    const cameraMasuk = document.getElementById('camera-masuk-setting').value;
    const cameraKeluar = document.getElementById('camera-keluar-setting').value;
    
    showLoading(true);
    
    fetch('/api/settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            camera_masuk: cameraMasuk,
            camera_keluar: cameraKeluar
        })
    })
    .then(response => response.json())
    .then(data => {
        showLoading(false);
        if (data.success) {
            showToast('✅ ' + data.message, 'success');
            updateCameraStatus();
            
            // Restart camera streams with new settings
            setTimeout(() => {
                initializeCameraStreams();
            }, 1000);
        } else {
            showToast('❌ ' + data.message, 'error');
        }
    })
    .catch(error => {
        showLoading(false);
        showToast('❌ Error: ' + error.message, 'error');
    });
}