// dashboard.js - Script untuk Dashboard Analitik Lalu Lintas Kabupaten Sorong

// Timezone settings
const TIMEZONE_OFFSET = 9; // GMT+9 untuk Waktu Indonesia Timur (WIT)
const TIMEZONE_NAME = 'WIT'; // Nama timezone untuk ditampilkan

// Function untuk konversi tanggal ke format lokal dengan timezone yang ditentukan
function convertToLocalTime(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    // Tambahkan offset timezone (dalam jam)
    return new Date(date.getTime() + (TIMEZONE_OFFSET * 60 * 60 * 1000));
}

// Function untuk format tanggal ke string YYYY-MM-DD HH:MM:SS dengan timezone yang ditentukan
function formatDateTimeForServer(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    
    // Format tanggal untuk server (tetap UTC/GMT untuk konsistensi dengan server)
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

// Constants - Smart API URL detection
const getBaseApiUrl = () => {
    const { protocol, hostname, port } = window.location;
    
    // Jika kita di localhost
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        // Jika port halaman web adalah 5000, maka API ada di 5001
        if (port === '5000') {
            return `${protocol}//${hostname}:5001/api`;
        }
        // Jika port halaman web adalah 5001, maka API juga ada di 5001
        else if (port === '5001') {
            return `${protocol}//${hostname}:5001/api`;
        }
        // Jika port halaman web lainnya
        else {
            // Gunakan konfigurasi default
            return `${protocol}//${hostname}:5001/api`;
        }
    }
    // Jika di lingkungan produksi (bukan localhost)
    else {
        // Untuk lingkungan produksi, seringkali API berada di hostname yang sama
        // dan diakses melalui path tertentu seperti /api
        // atau Anda bisa menggunakan subdomain terpisah
        
        // Gunakan path /api pada host yang sama
        return `${protocol}//${hostname}${port ? ':' + port : ''}/api`;
        
        // ATAU gunakan subdomain api
        // return `${protocol}//api.${hostname.replace(/^www\./, '')}/api`;
    }
};

// Inisialisasi konstanta
const BASE_API_URL = getBaseApiUrl();

console.log('Using API URL:', BASE_API_URL);
console.log(`Timezone setting: GMT+${TIMEZONE_OFFSET} (${TIMEZONE_NAME})`);

// Global variables
let currentPage = 1;
let itemsPerPage = 10;
let tableData = [];
let charts = {};

// Initialize the dashboard
document.addEventListener('DOMContentLoaded', function() {
    // Update current date
    updateCurrentDate();

    // Initialize filter handling
    initializeFilters();

    // Load initial data
    loadDashboardData();

    // Initialize event listeners
    document.getElementById('apply-filter').addEventListener('click', applyFilters);
    document.getElementById('export-data').addEventListener('click', exportToExcel);
    document.getElementById('prev-page').addEventListener('click', () => changePage(currentPage - 1));
    document.getElementById('next-page').addEventListener('click', () => changePage(currentPage + 1));
    document.getElementById('prev-page-mobile').addEventListener('click', () => changePage(currentPage - 1));
    document.getElementById('next-page-mobile').addEventListener('click', () => changePage(currentPage + 1));
});

// Utility functions
function updateCurrentDate() {
    const now = convertToLocalTime(new Date());
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' };
    document.getElementById('current-date').textContent = now.toLocaleDateString('id-ID', options) + ` (${TIMEZONE_NAME})`;
}

function formatNumber(num) {
    return new Intl.NumberFormat('id-ID').format(num);
}

function initializeFilters() {
    // Initialize camera list
    fetchCameraList();

    // Handle date range selection change
    document.getElementById('date-range').addEventListener('change', function() {
        const customDateContainer = document.getElementById('custom-date-container');
        if (this.value === 'custom') {
            customDateContainer.style.display = 'block';
        } else {
            customDateContainer.style.display = 'none';
        }
    });
    
    // Set default dates for custom filter
    const today = convertToLocalTime(new Date());
    const lastMonth = convertToLocalTime(new Date());
    lastMonth.setMonth(today.getMonth() - 1);
    
    // Format tanggal untuk input HTML dengan timezone yang ditentukan
    document.getElementById('start-date').value = formatDateForInput(lastMonth);
    document.getElementById('end-date').value = formatDateForInput(today);
}

// Helper function untuk memformat tanggal untuk input date HTML (YYYY-MM-DD)
function formatDateForInput(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

async function fetchCameraList() {
    try {
        const response = await axios.get(`${BASE_API_URL}/camera-list`);
        const cameras = response.data;
        
        const cameraSelect = document.getElementById('camera-select');
        // Clear existing options except for the first one
        while (cameraSelect.options.length > 1) {
            cameraSelect.remove(1);
        }
        
        // Add camera options
        cameras.forEach(camera => {
            const option = document.createElement('option');
            option.value = camera.name;
            option.textContent = camera.name;
            cameraSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Error fetching camera list:', error);
        showError('Gagal memuat daftar kamera');
    }
}

function getFilterValues() {
    const camera = document.getElementById('camera-select').value;
    const dateRange = document.getElementById('date-range').value;
    
    let startDate, endDate;
    if (dateRange === 'custom') {
        // Dapatkan nilai dari input tanggal
        const startInput = document.getElementById('start-date').value;
        const endInput = document.getElementById('end-date').value;
        
        // Tambahkan waktu dengan timezone yang sesuai
        startDate = new Date(`${startInput}T00:00:00`);
        endDate = new Date(`${endInput}T23:59:59`);
        
        // Konversi ke UTC untuk server
        startDate = new Date(startDate.getTime() - (TIMEZONE_OFFSET * 60 * 60 * 1000));
        endDate = new Date(endDate.getTime() - (TIMEZONE_OFFSET * 60 * 60 * 1000));
    } else {
        // Jika menggunakan rentang waktu otomatis
        const now = new Date();
        endDate = new Date(now);
        
        const start = new Date(now);
        start.setDate(now.getDate() - parseInt(dateRange));
        startDate = start;
    }
    
    // Format tanggal untuk server dengan format YYYY-MM-DD HH:MM:SS
    const formattedStartDate = formatDateTimeForServer(startDate);
    const formattedEndDate = formatDateTimeForServer(endDate);
    
    return {
        camera,
        startDate: formattedStartDate,
        endDate: formattedEndDate
    };
}

function showLoading() {
    // Add loading indicators for each section
    document.getElementById('data-table-body').innerHTML = '<tr><td colspan="11" class="px-6 py-4 text-center text-sm text-gray-500">Memuat data...</td></tr>';
}

function hideLoading() {
    // Could be implemented to remove specific loading indicators
}

function showError(message) {
    alert(message);
}

async function applyFilters() {
    // Reset to the first page when applying new filters
    currentPage = 1;
    loadDashboardData();
}

async function loadDashboardData() {
    // Show loading state
    showLoading();
    
    try {
        // Fetch all required data concurrently
        await Promise.all([
            fetchSummaryData(),
            fetchWeeklyTrend(),
            fetchVehicleComparison(),
            fetchPeakHours(),
            fetchDirectionFlow(),
            fetchDailyData()
        ]);
        
        // Hide loading state
        hideLoading();
    } catch (error) {
        console.error('Error loading dashboard data:', error);
        hideLoading();
        showError('Terjadi kesalahan saat memuat data dashboard');
    }
}

// Data fetching functions
async function fetchSummaryData() {
    try {
        const filters = getFilterValues();
        let url = `${BASE_API_URL}/summary`;
        
        if (filters.camera) {
            url += `?camera_name=${encodeURIComponent(filters.camera)}`;
        }
        
        const response = await axios.get(url);
        const data = response.data;
        
        // Update summary cards
        document.getElementById('total-vehicles').textContent = formatNumber(data.total_vehicles || 0);
        document.getElementById('total-cars').textContent = formatNumber(data.total_car || 0);
        document.getElementById('total-bus-truck').textContent = formatNumber((data.total_bus || 0) + (data.total_truck || 0));
        document.getElementById('total-person-motor').textContent = formatNumber(data.total_person_motor || 0);
    } catch (error) {
        console.error('Error fetching summary data:', error);
        throw error;
    }
}

async function fetchWeeklyTrend() {
    try {
        // Get filter values
        const filters = getFilterValues();
        
        // Build URL with filter parameters
        let url = `${BASE_API_URL}/weekly-trend`;
        if (filters.camera) {
            url += `?camera_name=${encodeURIComponent(filters.camera)}`;
        }
        
        const response = await axios.get(url);
        const data = response.data;
        
        // Konversi tanggal ke timezone lokal sebelum ditampilkan
        const localizedDays = data.days.map(day => {
            // Asumsikan format tanggal adalah 'YYYY-MM-DD'
            const utcDate = new Date(`${day}T00:00:00Z`);
            const localDate = convertToLocalTime(utcDate);
            return formatDateForDisplay(localDate);
        });
        
        // Initialize or update chart
        if (charts.weeklyTrend) {
            charts.weeklyTrend.data.labels = localizedDays;
            charts.weeklyTrend.data.datasets[0].data = data.counts;
            charts.weeklyTrend.update();
        } else {
            const ctx = document.getElementById('weekly-trend-chart').getContext('2d');
            charts.weeklyTrend = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: localizedDays,
                    datasets: [{
                        label: 'Total Kendaraan',
                        data: data.counts,
                        backgroundColor: 'rgba(59, 130, 246, 0.2)',
                        borderColor: 'rgba(59, 130, 246, 1)',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Jumlah Kendaraan'
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: `Tanggal (${TIMEZONE_NAME})`
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            callbacks: {
                                title: function(tooltipItems) {
                                    // Menampilkan tanggal dengan zona waktu
                                    return `${tooltipItems[0].label} (${TIMEZONE_NAME})`;
                                }
                            }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error fetching weekly trend data:', error);
        throw error;
    }
}

// Format tanggal untuk ditampilkan di UI dengan format DD/MM/YYYY
function formatDateForDisplay(date) {
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
}

async function fetchVehicleComparison() {
    try {
        // Get filter values
        const filters = getFilterValues();
        
        // Build URL with filter parameters
        let url = `${BASE_API_URL}/vehicle-comparison`;
        if (filters.camera) {
            url += `?camera_name=${encodeURIComponent(filters.camera)}`;
        }
        
        const response = await axios.get(url);
        const data = response.data;
        
        // Initialize or update chart
        if (charts.vehicleType) {
            charts.vehicleType.data.labels = data.labels;
            charts.vehicleType.data.datasets[0].data = data.data;
            charts.vehicleType.update();
        } else {
            const ctx = document.getElementById('vehicle-type-chart').getContext('2d');
            charts.vehicleType = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: data.labels,
                    datasets: [{
                        data: data.data,
                        backgroundColor: [
                            'rgba(59, 130, 246, 0.8)',
                            'rgba(16, 185, 129, 0.8)',
                            'rgba(139, 92, 246, 0.8)',
                            'rgba(249, 115, 22, 0.8)'
                        ],
                        borderColor: [
                            'rgba(59, 130, 246, 1)',
                            'rgba(16, 185, 129, 1)',
                            'rgba(139, 92, 246, 1)',
                            'rgba(249, 115, 22, 1)'
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.raw || 0;
                                    const total = context.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                                    const percentage = Math.round((value / total) * 100);
                                    return `${label}: ${formatNumber(value)} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error fetching vehicle comparison data:', error);
        throw error;
    }
}

async function fetchPeakHours() {
    try {
        // Get filter values
        const filters = getFilterValues();
        
        // Build URL with filter parameters
        let url = `${BASE_API_URL}/peak-hours`;
        if (filters.camera) {
            url += `?camera_name=${encodeURIComponent(filters.camera)}`;
        }
        
        const response = await axios.get(url);
        const data = response.data;
        
        console.log("Original peak hours data:", data);
        
        // Sesuaikan jam berdasarkan timezone
        // Array baru untuk jam dan data yang sudah disesuaikan
        const adjustedData = {
            hours: [],
            counts: []
        };
        
        // Proses penyesuaian jam berdasarkan timezone
        for (let i = 0; i < 24; i++) {
            // Hitung jam dalam timezone WIT (GMT+9)
            const localHour = (i + TIMEZONE_OFFSET) % 24;
            
            // Dapatkan indeks dari data asli yang sesuai dengan jam lokal ini
            const originalIndex = data.hours.indexOf(i);
            
            // Tambahkan ke array yang sudah disesuaikan
            adjustedData.hours.push(localHour);
            adjustedData.counts.push(originalIndex !== -1 ? data.counts[originalIndex] : 0);
        }
        
        // Urutkan data berdasarkan jam (0-23)
        const sortedIndices = adjustedData.hours
            .map((hour, index) => ({ hour, index }))
            .sort((a, b) => a.hour - b.hour)
            .map(item => item.index);
        
        const sortedHours = sortedIndices.map(i => adjustedData.hours[i]);
        const sortedCounts = sortedIndices.map(i => adjustedData.counts[i]);
        
        console.log("Adjusted peak hours data (WIT/GMT+9):", {
            hours: sortedHours,
            counts: sortedCounts
        });
        
        // Initialize or update chart
        if (charts.peakHours) {
            charts.peakHours.data.labels = sortedHours.map(h => `${h}:00`);
            charts.peakHours.data.datasets[0].data = sortedCounts;
            charts.peakHours.update();
        } else {
            const ctx = document.getElementById('peak-hours-chart').getContext('2d');
            charts.peakHours = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: sortedHours.map(h => `${h}:00`),
                    datasets: [{
                        label: 'Volume Kendaraan',
                        data: sortedCounts,
                        backgroundColor: 'rgba(139, 92, 246, 0.6)',
                        borderColor: 'rgba(139, 92, 246, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Jumlah Kendaraan'
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: `Jam (${TIMEZONE_NAME})`
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            callbacks: {
                                title: function(tooltipItems) {
                                    // Menampilkan jam dengan zona waktu
                                    return `${tooltipItems[0].label} (${TIMEZONE_NAME})`;
                                }
                            }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error fetching peak hours data:', error);
        throw error;
    }
}

async function fetchDirectionFlow() {
    try {
        // Get filter values
        const filters = getFilterValues();
        
        // Build URL with filter parameters
        let url = `${BASE_API_URL}/direction-flow`;
        if (filters.camera) {
            url += `?camera_name=${encodeURIComponent(filters.camera)}`;
        }
        
        const response = await axios.get(url);
        const data = response.data;
        
        // Initialize or update chart
        if (charts.directionFlow) {
            charts.directionFlow.data.labels = data.labels;
            charts.directionFlow.data.datasets[0].data = data.up_counts;
            charts.directionFlow.data.datasets[1].data = data.down_counts;
            charts.directionFlow.update();
        } else {
            const ctx = document.getElementById('direction-flow-chart').getContext('2d');
            charts.directionFlow = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [
                        {
                            label: 'Arus Naik',
                            data: data.up_counts,
                            backgroundColor: 'rgba(16, 185, 129, 0.6)',
                            borderColor: 'rgba(16, 185, 129, 1)',
                            borderWidth: 1
                        },
                        {
                            label: 'Arus Turun',
                            data: data.down_counts,
                            backgroundColor: 'rgba(249, 115, 22, 0.6)',
                            borderColor: 'rgba(249, 115, 22, 1)',
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Jumlah Kendaraan'
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: 'Jenis Kendaraan'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error fetching direction flow data:', error);
        throw error;
    }
}

async function fetchDailyData() {
    try {
        // Get filter values
        const filters = getFilterValues();
        
        // Build URL with filter parameters
        let url = `${BASE_API_URL}/data/filter?start_date=${encodeURIComponent(filters.startDate)}&end_date=${encodeURIComponent(filters.endDate)}&mode=Counting Kendaraan`;
        if (filters.camera) {
            url += `&camera_name=${encodeURIComponent(filters.camera)}`;
        }
        
        console.log("Fetching daily data with URL:", url);
        
        const response = await axios.get(url);
        const data = response.data;
        
        console.log("Retrieved daily data:", data.length, "records");
        
        // Process data for display in table
        processTableData(data);
        
        // Render first page of data
        renderTablePage(1);
        
        // Update pagination info
        updatePagination();
    } catch (error) {
        console.error('Error fetching daily data:', error);
        document.getElementById('data-table-body').innerHTML = '<tr><td colspan="11" class="px-6 py-4 text-center text-sm text-gray-500">Error: Gagal memuat data</td></tr>';
        throw error;
    }
}

function processTableData(data) {
    // Group data by date and camera for daily summary
    const groupedByDateCamera = {};
    
    data.forEach(item => {
        try {
            const result = JSON.parse(item.result);
            
            // Konversi timestamp UTC ke timezone lokal
            const utcTimestamp = new Date(item.timestamp.replace(' ', 'T') + 'Z');
            const localTimestamp = convertToLocalTime(utcTimestamp);
            
            // Format tanggal lokal (YYYY-MM-DD)
            const localDate = formatDateForInput(localTimestamp);
            
            const key = `${localDate}-${item.camera_name}`;
            
            if (!groupedByDateCamera[key]) {
                groupedByDateCamera[key] = {
                    date: localDate,
                    camera_name: item.camera_name,
                    car_up: 0,
                    car_down: 0,
                    bus_up: 0,
                    bus_down: 0,
                    truck_up: 0,
                    truck_down: 0,
                    person_motor_up: 0,
                    person_motor_down: 0,
                    count: 0
                };
            }
            
            // Add values
            groupedByDateCamera[key].car_up += result.car_up || 0;
            groupedByDateCamera[key].car_down += result.car_down || 0;
            groupedByDateCamera[key].bus_up += result.bus_up || 0;
            groupedByDateCamera[key].bus_down += result.bus_down || 0;
            groupedByDateCamera[key].truck_up += result.truck_up || 0;
            groupedByDateCamera[key].truck_down += result.truck_down || 0;
            groupedByDateCamera[key].person_motor_up += result.person_motor_up || 0;
            groupedByDateCamera[key].person_motor_down += result.person_motor_down || 0;
            groupedByDateCamera[key].count++;
        } catch (error) {
            console.error('Error processing table data item:', error, item);
        }
    });
    
    // Convert to array and sort by date (newest first)
    tableData = Object.values(groupedByDateCamera).sort((a, b) => {
        return new Date(b.date) - new Date(a.date);
    });
    
    // Calculate totals for each row
    tableData.forEach(row => {
        row.total = row.car_up + row.car_down + row.bus_up + row.bus_down + row.truck_up + row.truck_down + row.person_motor_up + row.person_motor_down;
    });
}

function renderTablePage(page) {
    const start = (page - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const pageData = tableData.slice(start, end);
    
    const tableBody = document.getElementById('data-table-body');
    
    if (pageData.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="11" class="px-6 py-4 text-center text-sm text-gray-500">Tidak ada data</td></tr>';
        return;
    }
    
    let html = '';
    
    pageData.forEach(row => {
        html += `
            <tr class="hover:bg-gray-50">
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${formatDate(row.date)} ${TIMEZONE_NAME}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${row.camera_name}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formatNumber(row.car_up)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formatNumber(row.car_down)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formatNumber(row.bus_up)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formatNumber(row.bus_down)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formatNumber(row.truck_up)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formatNumber(row.truck_down)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formatNumber(row.person_motor_up)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formatNumber(row.person_motor_down)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${formatNumber(row.total)}</td>
            </tr>
        `;
    });
    
    tableBody.innerHTML = html;
}

function formatDate(dateStr) {
    const [year, month, day] = dateStr.split('-');
    return `${day}/${month}/${year}`;
}

function updatePagination() {
    const totalPages = Math.ceil(tableData.length / itemsPerPage);
    
    // Update pagination info text
    const start = (currentPage - 1) * itemsPerPage + 1;
    const end = Math.min(start + itemsPerPage - 1, tableData.length);
    
    document.getElementById('pagination-info').innerHTML = tableData.length > 0 
        ? `Menampilkan <span class="font-medium">${start}-${end}</span> dari <span class="font-medium">${tableData.length}</span> data`
        : 'Tidak ada data';
    
    // Generate pagination buttons
    const paginationPages = document.getElementById('pagination-pages');
    paginationPages.innerHTML = '';
    
    const maxVisiblePages = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
    
    // Adjust startPage if we're near the end
    if (endPage - startPage + 1 < maxVisiblePages && startPage > 1) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
        const pageButton = document.createElement('button');
        pageButton.className = i === currentPage
            ? 'relative inline-flex items-center px-4 py-2 border border-blue-500 bg-blue-50 text-sm font-medium text-blue-600'
            : 'relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50';
        pageButton.textContent = i;
        pageButton.addEventListener('click', () => changePage(i));
        paginationPages.appendChild(pageButton);
    }
    
    // Update prev/next buttons state
    document.getElementById('prev-page').disabled = currentPage === 1;
    document.getElementById('next-page').disabled = currentPage === totalPages;
    document.getElementById('prev-page-mobile').disabled = currentPage === 1;
    document.getElementById('next-page-mobile').disabled = currentPage === totalPages;
    
    document.getElementById('prev-page').classList.toggle('opacity-50', currentPage === 1);
    document.getElementById('next-page').classList.toggle('opacity-50', currentPage === totalPages);
    document.getElementById('prev-page-mobile').classList.toggle('opacity-50', currentPage === 1);
    document.getElementById('next-page-mobile').classList.toggle('opacity-50', currentPage === totalPages);
}

function changePage(page) {
    if (page < 1 || page > Math.ceil(tableData.length / itemsPerPage)) {
        return;
    }
    
    currentPage = page;
    renderTablePage(currentPage);
    updatePagination();
}

function exportToExcel() {
    try {
        // Create a new workbook
        const XLSX = window.XLSX;
        const wb = XLSX.utils.book_new();
        
        // Prepare data for export
        const exportData = [
            // Header row
            ['Tanggal', 'Zona Waktu', 'Kamera', 'Mobil (Naik)', 'Mobil (Turun)', 'Bus (Naik)', 'Bus (Turun)', 
             'Truk (Naik)', 'Truk (Turun)', 'Motor/Orang (Naik)', 'Motor/Orang (Turun)', 'Total']
        ];
        
        // Add all data rows
        tableData.forEach(row => {
            exportData.push([
                formatDate(row.date),
                TIMEZONE_NAME,
                row.camera_name,
                row.car_up,
                row.car_down,
                row.bus_up,
                row.bus_down,
                row.truck_up,
                row.truck_down,
                row.person_motor_up,
                row.person_motor_down,
                row.total
            ]);
        });
        
        // Create worksheet and add to workbook
        const ws = XLSX.utils.aoa_to_sheet(exportData);
        XLSX.utils.book_append_sheet(wb, ws, 'Data Lalu Lintas');
        
        // Generate filename with current date
        const today = convertToLocalTime(new Date());
        const dateStr = formatDateForInput(today);
        const filename = `Rekap_Lalu_Lintas_${dateStr}_${TIMEZONE_NAME}.xlsx`;
        
        // Trigger download
        XLSX.writeFile(wb, filename);
    } catch (error) {
        console.error('Error exporting to Excel:', error);
        showError('Gagal mengekspor data ke Excel');
    }
}