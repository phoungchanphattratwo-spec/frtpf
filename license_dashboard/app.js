// Authentication Configuration
const AUTH_CONFIG = {
    sessionKey: 'license_dashboard_auth',
    sessionTimeout: 3600000 // 1 hour
};

// Check authentication before loading dashboard
function checkAuthentication() {
    const session = getSession();
    
    if (!session || !isSessionValid(session)) {
        // Not authenticated, redirect to login
        window.location.href = 'login.html';
        return false;
    }
    
    return true;
}

// Get session from storage
function getSession() {
    try {
        const sessionData = sessionStorage.getItem(AUTH_CONFIG.sessionKey);
        return sessionData ? JSON.parse(sessionData) : null;
    } catch (error) {
        return null;
    }
}

// Check if session is valid
function isSessionValid(session) {
    if (!session || !session.authenticated) {
        return false;
    }
    
    const currentTime = Date.now();
    const sessionAge = currentTime - session.loginTime;
    
    if (sessionAge > AUTH_CONFIG.sessionTimeout) {
        clearSession();
        return false;
    }
    
    return true;
}

// Clear session
function clearSession() {
    sessionStorage.removeItem(AUTH_CONFIG.sessionKey);
}

// Logout function
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        clearSession();
        window.location.href = 'login.html';
    }
}

// Get Supabase credentials from session
function getSupabaseCredentials() {
    const session = getSession();
    if (!session) {
        return null;
    }
    
    return {
        url: atob(session.supabaseUrl), // Decode from Base64
        key: atob(session.supabaseKey)  // Decode from Base64
    };
}

// Initialize Supabase client
let supabaseClient = null;

function initializeSupabase() {
    const credentials = getSupabaseCredentials();
    if (!credentials) {
        window.location.href = 'login.html';
        return false;
    }
    
    const { createClient } = supabase;
    supabaseClient = createClient(credentials.url, credentials.key);
    return true;
}

let allLicenses = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Check authentication first
    if (!checkAuthentication()) {
        return;
    }
    
    // Initialize Supabase with session credentials
    if (!initializeSupabase()) {
        return;
    }
    
    // Load dashboard
    loadLicenses();
    setDefaultExpiryDate();
});

// Load all licenses
async function loadLicenses() {
    try {
        showLoading();
        
        const { data, error } = await supabaseClient
            .from('licenses')
            .select('*')
            .order('created_at', { ascending: false });

        if (error) throw error;

        allLicenses = data || [];
        updateStats();
        renderLicenses(allLicenses);
        
    } catch (error) {
        console.error('Error loading licenses:', error);
        alert('Failed to load licenses: ' + error.message);
        showEmpty();
    }
}

// Update statistics
function updateStats() {
    const now = new Date();
    const thirtyDaysFromNow = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);

    const total = allLicenses.length;
    const active = allLicenses.filter(l => {
        const expiry = new Date(l.expiry_date);
        return l.is_active && expiry > now;
    }).length;
    const expired = allLicenses.filter(l => {
        const expiry = new Date(l.expiry_date);
        return expiry <= now;
    }).length;
    const expiring = allLicenses.filter(l => {
        const expiry = new Date(l.expiry_date);
        return l.is_active && expiry > now && expiry <= thirtyDaysFromNow;
    }).length;

    document.getElementById('totalLicenses').textContent = total;
    document.getElementById('activeLicenses').textContent = active;
    document.getElementById('expiredLicenses').textContent = expired;
    document.getElementById('expiringLicenses').textContent = expiring;
}

// Render licenses table
function renderLicenses(licenses) {
    const tbody = document.getElementById('licensesTableBody');
    const table = document.getElementById('licensesTable');
    const emptyState = document.getElementById('emptyState');
    const loadingState = document.getElementById('loadingState');

    loadingState.style.display = 'none';

    if (licenses.length === 0) {
        table.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }

    table.style.display = 'table';
    emptyState.style.display = 'none';

    tbody.innerHTML = licenses.map(license => {
        const status = getLicenseStatus(license);
        const expiryDate = new Date(license.expiry_date).toLocaleDateString();
        
        return `
            <tr>
                <td><strong>${license.license_key}</strong></td>
                <td>${license.tool_id}</td>
                <td>${license.license_type}</td>
                <td>${license.user_name || '<em>Not activated</em>'}</td>
                <td><span class="status-badge status-${status.class}">${status.text}</span></td>
                <td>${expiryDate}</td>
                <td>
                    <button class="action-btn edit" onclick="editLicense('${license.id}')">
                        <i class="fas fa-edit"></i> Edit
                    </button>
                    <button class="action-btn delete" onclick="deleteLicense('${license.id}', '${license.license_key}')">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// Get license status
function getLicenseStatus(license) {
    const now = new Date();
    const expiry = new Date(license.expiry_date);

    if (expiry <= now) {
        return { text: 'Expired', class: 'expired' };
    }
    if (license.is_activated && license.is_active) {
        return { text: 'Active', class: 'active' };
    }
    if (!license.is_active) {
        return { text: 'Deactivated', class: 'inactive' };
    }
    return { text: 'Not Activated', class: 'inactive' };
}

// Filter licenses
function filterLicenses() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const filtered = allLicenses.filter(license => {
        return license.license_key.toLowerCase().includes(searchTerm) ||
               license.tool_id.toLowerCase().includes(searchTerm) ||
               (license.user_name && license.user_name.toLowerCase().includes(searchTerm)) ||
               license.license_type.toLowerCase().includes(searchTerm);
    });
    renderLicenses(filtered);
}

// Open create modal
function openCreateModal() {
    document.getElementById('modalTitle').textContent = 'Create New License';
    document.getElementById('licenseForm').reset();
    document.getElementById('licenseId').value = '';
    setDefaultExpiryDate();
    generateLicenseKey();
    generateToolId();
    document.getElementById('licenseModal').classList.add('active');
}

// Edit license
async function editLicense(id) {
    const license = allLicenses.find(l => l.id === id);
    if (!license) return;

    document.getElementById('modalTitle').textContent = 'Edit License';
    document.getElementById('licenseId').value = license.id;
    document.getElementById('licenseKey').value = license.license_key;
    document.getElementById('toolId').value = license.tool_id;
    document.getElementById('licenseType').value = license.license_type;
    document.getElementById('expiryDate').value = license.expiry_date.split('T')[0];
    document.getElementById('notes').value = license.notes || '';
    
    document.getElementById('licenseModal').classList.add('active');
}

// Save license
async function saveLicense(event) {
    event.preventDefault();

    const id = document.getElementById('licenseId').value;
    const licenseData = {
        license_key: document.getElementById('licenseKey').value.toUpperCase(),
        tool_id: document.getElementById('toolId').value,
        license_type: document.getElementById('licenseType').value,
        expiry_date: new Date(document.getElementById('expiryDate').value).toISOString(),
        notes: document.getElementById('notes').value || null
    };

    try {
        if (id) {
            // Update existing license
            const { error } = await supabaseClient
                .from('licenses')
                .update(licenseData)
                .eq('id', id);

            if (error) throw error;
            alert('License updated successfully!');
        } else {
            // Create new license
            const { error } = await supabaseClient
                .from('licenses')
                .insert([licenseData]);

            if (error) throw error;
            alert('License created successfully!');
        }

        closeModal();
        loadLicenses();
    } catch (error) {
        console.error('Error saving license:', error);
        alert('Failed to save license: ' + error.message);
    }
}

// Delete license
async function deleteLicense(id, licenseKey) {
    if (!confirm(`Are you sure you want to delete license ${licenseKey}?`)) {
        return;
    }

    try {
        const { error } = await supabaseClient
            .from('licenses')
            .delete()
            .eq('id', id);

        if (error) throw error;

        alert('License deleted successfully!');
        loadLicenses();
    } catch (error) {
        console.error('Error deleting license:', error);
        alert('Failed to delete license: ' + error.message);
    }
}

// Close modal
function closeModal() {
    document.getElementById('licenseModal').classList.remove('active');
}

// Refresh data
function refreshData() {
    loadLicenses();
}

// Generate random license key
function generateLicenseKey() {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    let key = '';
    for (let i = 0; i < 4; i++) {
        if (i > 0) key += '-';
        for (let j = 0; j < 4; j++) {
            key += chars.charAt(Math.floor(Math.random() * chars.length));
        }
    }
    document.getElementById('licenseKey').value = key;
}

// Generate Tool ID
function generateToolId() {
    const count = allLicenses.length + 1;
    const toolId = `FRT-2024-${String(count).padStart(4, '0')}`;
    document.getElementById('toolId').value = toolId;
}

// Set default expiry date (1 year from now)
function setDefaultExpiryDate() {
    const date = new Date();
    date.setFullYear(date.getFullYear() + 1);
    document.getElementById('expiryDate').value = date.toISOString().split('T')[0];
}

// Show loading state
function showLoading() {
    document.getElementById('loadingState').style.display = 'block';
    document.getElementById('licensesTable').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';
}

// Show empty state
function showEmpty() {
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('licensesTable').style.display = 'none';
    document.getElementById('emptyState').style.display = 'block';
}

// Close modal on outside click
document.getElementById('licenseModal').addEventListener('click', (e) => {
    if (e.target.id === 'licenseModal') {
        closeModal();
    }
});
