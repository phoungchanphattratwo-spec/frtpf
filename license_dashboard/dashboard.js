// License Admin Dashboard JavaScript

let serverUrl = '';
let adminKey = '';
let licenses = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Check for saved credentials
    const saved = localStorage.getItem('licenseAdmin');
    if (saved) {
        const data = JSON.parse(saved);
        serverUrl = data.serverUrl;
        adminKey = data.adminKey;
        document.getElementById('serverUrl').value = serverUrl;
        document.getElementById('adminKey').value = adminKey;
    }
});

// Toast notifications
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${type === 'success' ? '✓' : '✗'}</span> ${message}`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// API calls
async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'X-Admin-Key': adminKey
        }
    };
    if (body) options.body = JSON.stringify(body);
    
    const response = await fetch(`${serverUrl}${endpoint}`, options);
    if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
    }
    return response.json();
}

// Login
async function login() {
    serverUrl = document.getElementById('serverUrl').value.trim().replace(/\/$/, '');
    adminKey = document.getElementById('adminKey').value.trim();
    
    if (!serverUrl || !adminKey) {
        showToast('Please fill in all fields', 'error');
        return;
    }
    
    try {
        await apiCall('/admin/stats');
        
        // Save credentials
        localStorage.setItem('licenseAdmin', JSON.stringify({ serverUrl, adminKey }));
        
        // Show dashboard
        document.getElementById('loginScreen').style.display = 'none';
        document.getElementById('dashboard').style.display = 'block';
        
        // Load data
        refreshStats();
        loadLicenses();
        
        showToast('Login successful');
    } catch (e) {
        showToast('Login failed: Invalid credentials', 'error');
    }
}

function logout() {
    localStorage.removeItem('licenseAdmin');
    location.reload();
}

// Navigation
function showPage(page) {
    // Update nav
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
    event.target.closest('.nav-item').classList.add('active');
    
    // Show page
    document.querySelectorAll('.page-section').forEach(section => section.classList.remove('active'));
    document.getElementById(`page-${page}`).classList.add('active');
    
    // Load data
    if (page === 'licenses') loadLicenses();
    if (page === 'activations') loadActivations();
    if (page === 'logs') loadLogs();
    if (page === 'overview') refreshStats();
}

// Stats
async function refreshStats() {
    try {
        const stats = await apiCall('/admin/stats');
        document.getElementById('statTotal').textContent = stats.total_licenses;
        document.getElementById('statActive').textContent = stats.active_licenses;
        document.getElementById('statExpired').textContent = stats.expired_licenses;
        document.getElementById('statActivations').textContent = stats.total_activations;
        document.getElementById('statActivity').textContent = stats.recent_activity_24h;
        
        // Load recent logs
        const logs = await apiCall('/admin/logs?limit=5');
        renderRecentLogs(logs.logs);
    } catch (e) {
        showToast('Failed to load stats', 'error');
    }
}

function renderRecentLogs(logs) {
    const container = document.getElementById('recentLogs');
    container.innerHTML = logs.map(log => {
        const iconClass = log.action.includes('success') ? 'success' : 
                         log.action.includes('failed') ? 'error' : 'info';
        const icon = log.action.includes('success') ? '✓' : 
                    log.action.includes('failed') ? '✗' : 'ℹ';
        
        return `
            <div class="log-item">
                <div class="log-icon ${iconClass}">${icon}</div>
                <div class="log-details">
                    <div class="log-action">${log.action}</div>
                    <div class="log-meta">${JSON.stringify(log.details || {})}</div>
                </div>
                <div class="log-time">${new Date(log.timestamp).toLocaleString()}</div>
            </div>
        `;
    }).join('');
}

// Licenses
async function loadLicenses() {
    try {
        const data = await apiCall('/admin/licenses');
        licenses = data.licenses;
        renderLicenses(licenses);
    } catch (e) {
        showToast('Failed to load licenses', 'error');
    }
}

function renderLicenses(items) {
    const tbody = document.getElementById('licensesTable');
    tbody.innerHTML = items.map(l => {
        const isExpired = l.expires_at && new Date(l.expires_at) < new Date();
        const statusClass = !l.active ? 'inactive' : isExpired ? 'expired' : 'active';
        const statusText = !l.active ? 'Disabled' : isExpired ? 'Expired' : 'Active';
        
        return `
            <tr>
                <td><span class="license-key">${l.key}</span></td>
                <td>${l.email || '-'}</td>
                <td>${l.license_type || 'standard'}</td>
                <td><span class="badge badge-${statusClass}">${statusText}</span></td>
                <td>${l.expires_at ? new Date(l.expires_at).toLocaleDateString() : 'Never'}</td>
                <td class="actions">
                    <button class="btn btn-secondary" onclick="copyLicense('${l.key}')">📋</button>
                    <button class="btn btn-secondary" onclick="toggleLicense('${l.key}')">${l.active ? '🔒' : '🔓'}</button>
                    <button class="btn btn-secondary" onclick="resetLicense('${l.key}')">🔄</button>
                    <button class="btn btn-danger" onclick="deleteLicense('${l.key}')">🗑</button>
                </td>
            </tr>
        `;
    }).join('');
}

function filterLicenses() {
    const search = document.getElementById('searchLicense').value.toLowerCase();
    const filtered = licenses.filter(l => 
        l.key.toLowerCase().includes(search) ||
        (l.email && l.email.toLowerCase().includes(search)) ||
        (l.name && l.name.toLowerCase().includes(search))
    );
    renderLicenses(filtered);
}

function copyLicense(key) {
    navigator.clipboard.writeText(key);
    showToast('License key copied!');
}

async function toggleLicense(key) {
    try {
        const result = await apiCall(`/admin/licenses/${key}/toggle`, 'POST');
        showToast(`License ${result.active ? 'enabled' : 'disabled'}`);
        loadLicenses();
    } catch (e) {
        showToast('Failed to toggle license', 'error');
    }
}

async function resetLicense(key) {
    if (!confirm('Reset all device activations for this license?')) return;
    try {
        await apiCall(`/admin/licenses/${key}/reset`, 'POST');
        showToast('License devices reset');
        loadLicenses();
    } catch (e) {
        showToast('Failed to reset license', 'error');
    }
}

async function deleteLicense(key) {
    if (!confirm('Delete this license permanently?')) return;
    try {
        await apiCall(`/admin/licenses/${key}`, 'DELETE');
        showToast('License deleted');
        loadLicenses();
    } catch (e) {
        showToast('Failed to delete license', 'error');
    }
}

// Create License
function showCreateModal() {
    document.getElementById('createModal').classList.add('active');
}

function showBulkModal() {
    document.getElementById('bulkModal').classList.add('active');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

async function createLicense() {
    const data = {
        email: document.getElementById('newEmail').value,
        name: document.getElementById('newName').value,
        license_type: document.getElementById('newType').value,
        max_machines: parseInt(document.getElementById('newMaxMachines').value),
        duration_days: parseInt(document.getElementById('newDuration').value) || null,
        notes: document.getElementById('newNotes').value
    };
    
    try {
        const result = await apiCall('/admin/licenses', 'POST', data);
        showToast(`License created: ${result.license_key}`);
        closeModal('createModal');
        loadLicenses();
        
        // Copy to clipboard
        navigator.clipboard.writeText(result.license_key);
    } catch (e) {
        showToast('Failed to create license', 'error');
    }
}

async function bulkGenerate() {
    const data = {
        count: parseInt(document.getElementById('bulkCount').value),
        batch_name: document.getElementById('bulkName').value,
        license_type: document.getElementById('bulkType').value,
        duration_days: parseInt(document.getElementById('bulkDuration').value) || null
    };
    
    try {
        const result = await apiCall('/admin/bulk/generate', 'POST', data);
        showToast(`Generated ${result.licenses.length} licenses`);
        closeModal('bulkModal');
        loadLicenses();
        
        // Copy all to clipboard
        navigator.clipboard.writeText(result.licenses.join('\n'));
    } catch (e) {
        showToast('Failed to generate licenses', 'error');
    }
}

// Activations
async function loadActivations() {
    try {
        const data = await apiCall('/admin/activations');
        const tbody = document.getElementById('activationsTable');
        tbody.innerHTML = data.activations.map(a => `
            <tr>
                <td><span class="license-key">${a.license_key}</span></td>
                <td>${a.machine_hash.substring(0, 12)}...</td>
                <td>${new Date(a.activated_at).toLocaleString()}</td>
                <td>${a.ip || '-'}</td>
                <td>${a.app_version || '-'}</td>
            </tr>
        `).join('');
    } catch (e) {
        showToast('Failed to load activations', 'error');
    }
}

// Logs
async function loadLogs() {
    try {
        const data = await apiCall('/admin/logs?limit=100');
        const container = document.getElementById('logsContainer');
        container.innerHTML = data.logs.map(log => {
            const iconClass = log.action.includes('success') ? 'success' : 
                             log.action.includes('failed') ? 'error' : 'info';
            const icon = log.action.includes('success') ? '✓' : 
                        log.action.includes('failed') ? '✗' : 'ℹ';
            
            return `
                <div class="log-item">
                    <div class="log-icon ${iconClass}">${icon}</div>
                    <div class="log-details">
                        <div class="log-action">${log.action}</div>
                        <div class="log-meta">${JSON.stringify(log.details || {})} ${log.ip ? `• IP: ${log.ip}` : ''}</div>
                    </div>
                    <div class="log-time">${new Date(log.timestamp).toLocaleString()}</div>
                </div>
            `;
        }).join('');
    } catch (e) {
        showToast('Failed to load logs', 'error');
    }
}

// Settings
async function disableExpired() {
    if (!confirm('Disable all expired licenses?')) return;
    try {
        const result = await apiCall('/admin/bulk/disable-expired', 'POST');
        showToast(`Disabled ${result.disabled_count} expired licenses`);
    } catch (e) {
        showToast('Failed to disable expired licenses', 'error');
    }
}
