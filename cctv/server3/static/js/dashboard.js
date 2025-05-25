// dashboard.js - Script untuk Dashboard Analitik Lalu Lintas Kabupaten Sorong

// Constants
const BASE_API_URL = 'http://localhost:5001/api';

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
    const now = new Date();
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    document.getElementById('current-date').textContent = now.toLocaleDateString('id-ID', options);
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
    const today = new Date();
    const lastMonth = new Date(today);
    lastMonth.setMonth(today.getMonth() - 1);
    
    document.getElementById('start-date').valueAsDate = lastMonth;
    document.getElementById('end-date').valueAsDate = today;
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
        startDate = document.getElementById('start-date').value;
        endDate = document.getElementById('end-date').value;
    } else {
        const today = new Date();
        endDate = today.toISOString().split('T')[0];
        
        const start = new Date(today);
        start.setDate(today.getDate() - parseInt(dateRange));
        startDate = start.toISOString().split('T')[0];
    }
    
    return {
        camera,
        startDate,
        endDate
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
        
        // Initialize or update chart
        if (charts.weeklyTrend) {
            charts.weeklyTrend.data.labels = data.days;
            charts.weeklyTrend.data.datasets[0].data = data.counts;
            charts.weeklyTrend.update();
        } else {
            const ctx = document.getElementById('weekly-trend-chart').getContext('2d');
            charts.weeklyTrend = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.days,
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
                                text: 'Tanggal'
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
        
        // Initialize or update chart
        if (charts.peakHours) {
            charts.peakHours.data.labels = data.hours.map(h => `${h}:00`);
            charts.peakHours.data.datasets[0].data = data.counts;
            charts.peakHours.update();
        } else {
            const ctx = document.getElementById('peak-hours-chart').getContext('2d');
            charts.peakHours = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.hours.map(h => `${h}:00`),
                    datasets: [{
                        label: 'Volume Kendaraan',
                        data: data.counts,
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
                                text: 'Jam'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
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
        
        const response = await axios.get(url);
        const data = response.data;
        
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
            const date = item.timestamp.split(' ')[0]; // Get date part only
            const key = `${date}-${item.camera_name}`;
            
            if (!groupedByDateCamera[key]) {
                groupedByDateCamera[key] = {
                    date: date,
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
            console.error('Error processing table data item:', error);
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
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${formatDate(row.date)}</td>
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
            ['Tanggal', 'Kamera', 'Mobil (Naik)', 'Mobil (Turun)', 'Bus (Naik)', 'Bus (Turun)', 
             'Truk (Naik)', 'Truk (Turun)', 'Motor/Orang (Naik)', 'Motor/Orang (Turun)', 'Total']
        ];
        
        // Add all data rows
        tableData.forEach(row => {
            exportData.push([
                row.date,
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
        const today = new Date();
        const dateStr = today.toISOString().split('T')[0];
        const filename = `Rekap_Lalu_Lintas_${dateStr}.xlsx`;
        
        // Trigger download
        XLSX.writeFile(wb, filename);
    } catch (error) {
        console.error('Error exporting to Excel:', error);
        showError('Gagal mengekspor data ke Excel');
    }
}