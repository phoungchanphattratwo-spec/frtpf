"""
Script to create the license dashboard HTML file.
Run this script to generate the web dashboard.
"""

import os

HTML_CONTENT = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>License Management Dashboard</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        /* Header */
        .header {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 24px 32px;
            margin-bottom: 24px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .header-left h1 {
            font-size: 28px;
            color: #1a1a1a;
            margin-bottom: 4px;
        }

        .header-left p {
            color: #666;
            font-size: 14px;
        }

        .header-right {
            display: flex;
            gap: 12px;
        }

        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
        }

        .btn-secondary {
            background: #f5f5f5;
            color: #333;
        }

        .btn-secondary:hover {
            background: #e0e0e0;
        }

        /* Stats Cards */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }

        .stat-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }

        .stat-card:hover {
            transform: translateY(-4px);
        }

        .stat-icon {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            margin-bottom: 16px;
        }

        .stat-icon.blue { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .stat-icon.green { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; }
        .stat-icon.orange { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; }
        .stat-icon.purple { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; }

        .stat-value {
            font-size: 32px;
            font-weight: 700;
            color: #1a1a1a;
            margin-bottom: 4px;
        }

        .stat-label {
            color: #666;
            font-size: 14px;
            font-weight: 500;
        }

        /* Main Content */
        .main-content {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 32px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }

        .content-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }

        .content-header h2 {
            font-size: 22px;
            color: #1a1a1a;
        }

        .search-box {
            position: relative;
            width: 300px;
        }

        .search-box input {
            width: 100%;
            padding: 12px 16px 12px 44px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 14px;
            transition: all 0.3s ease;
        }

        .search-box input:focus {
            outline: none;
            border-color: #667eea;
        }

        .search-box i {
            position: absolute;
            left: 16px;
            top: 50%;
            transform: translateY(-50%);
            color: #999;
        }

        /* Table */
        .table-container {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        thead {
            background: #f8f9fa;
        }

        th {
            padding: 16px;
            text-align: left;
            font-size: 13px;
            font-weight: 600;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        td {
            padding: 16px;
            border-bottom: 1px solid #f0f0f0;
            font-size: 14px;
            color: #333;
        }

        tr:hover {
            background: #f8f9fa;
        }

        .status-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }

        .status-active {
            background: #d4edda;
            color: #155724;
        }

        .status-inactive {
            background: #f8d7da;
            color: #721c24;
        }

        .status-expired {
            background: #fff3cd;
            color: #856404;
        }

        .action-btn {
            padding: 6px 12px;
            border: none;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            margin-right: 6px;
            transition: all 0.2s ease;
        }

        .action-btn.edit {
            background: #e3f2fd;
            color: #1976d2;
        }

        .action-btn.edit:hover {
            background: #1976d2;
            color: white;
        }

        .action-btn.delete {
            background: #ffebee;
            color: #c62828;
        }

        .action-btn.delete:hover {
            background: #c62828;
            color: white;
        }

        /* Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(4px);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }

        .modal.active {
            display: flex;
        }

        .modal-content {
            background: white;
            border-radius: 16px;
            padding: 32px;
            max-width: 600px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }

        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }

        .modal-header h3 {
            font-size: 24px;
            color: #1a1a1a;
        }

        .close-modal {
            background: none;
            border: none;
            font-size: 24px;
            color: #999;
            cursor: pointer;
            padding: 0;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
            transition: all 0.2s ease;
        }

        .close-modal:hover {
            background: #f5f5f5;
            color: #333;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-size: 14px;
            font-weight: 600;
            color: #333;
        }

        .form-group input,
        .form-group select,
        .form-group textarea {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 14px;
            font-family: inherit;
            transition: all 0.3s ease;
        }

        .form-group input:focus,
        .form-group select:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
        }

        .form-group textarea {
            resize: vertical;
            min-height: 80px;
        }

        .form-actions {
            display: flex;
            gap: 12px;
            justify-content: flex-end;
            margin-top: 24px;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }

        .loading i {
            font-size: 32px;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #999;
        }

        .empty-state i {
            font-size: 64px;
            margin-bottom: 16px;
            opacity: 0.3;
        }

        .empty-state h3 {
            font-size: 20px;
            margin-bottom: 8px;
            color: #666;
        }

        .empty-state p {
            font-size: 14px;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .header {
                flex-direction: column;
                gap: 16px;
            }

            .header-right {
                width: 100%;
                justify-content: stretch;
            }

            .header-right .btn {
                flex: 1;
            }

            .content-header {
                flex-direction: column;
                gap: 16px;
            }

            .search-box {
                width: 100%;
            }

            .stats-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="header-left">
                <h1><i class="fas fa-key"></i> License Management</h1>
                <p>Manage and monitor your software licenses</p>
            </div>
            <div class="header-right">
                <button class="btn btn-secondary" onclick="refreshData()">
                    <i class="fas fa-sync-alt"></i> Refresh
                </button>
                <button class="btn btn-primary" onclick="openCreateModal()">
                    <i class="fas fa-plus"></i> Create License
                </button>
            </div>
        </div>

        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon blue">
                    <i class="fas fa-ticket-alt"></i>
                </div>
                <div class="stat-value" id="totalLicenses">0</div>
                <div class="stat-label">Total Licenses</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon green">
                    <i class="fas fa-check-circle"></i>
                </div>
                <div class="stat-value" id="activeLicenses">0</div>
                <div class="stat-label">Active Licenses</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon orange">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <div class="stat-value" id="expiredLicenses">0</div>
                <div class="stat-label">Expired Licenses</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon purple">
                    <i class="fas fa-clock"></i>
                </div>
                <div class="stat-value" id="expiringLicenses">0</div>
                <div class="stat-label">Expiring Soon (30 days)</div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="content-header">
                <h2>All Licenses</h2>
                <div class="search-box">
                    <i class="fas fa-search"></i>
                    <input type="text" id="searchInput" placeholder="Search licenses..." onkeyup="filterLicenses()">
                </div>
            </div>

            <div class="table-container">
                <div id="loadingState" class="loading">
                    <i class="fas fa-spinner"></i>
                    <p>Loading licenses...</p>
                </div>
                <div id="emptyState" class="empty-state" style="display: none;">
                    <i class="fas fa-inbox"></i>
                    <h3>No licenses found</h3>
                    <p>Create your first license to get started</p>
                </div>
                <table id="licensesTable" style="display: none;">
                    <thead>
                        <tr>
                            <th>License Key</th>
                            <th>Tool ID</th>
                            <th>Type</th>
                            <th>User</th>
                            <th>Status</th>
                            <th>Expiry Date</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="licensesTableBody">
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Create/Edit Modal -->
    <div id="licenseModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="modalTitle">Create New License</h3>
                <button class="close-modal" onclick="closeModal()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <form id="licenseForm" onsubmit="saveLicense(event)">
                <input type="hidden" id="licenseId">
                
                <div class="form-group">
                    <label for="licenseKey">License Key</label>
                    <input type="text" id="licenseKey" required placeholder="XXXX-XXXX-XXXX-XXXX">
                </div>

                <div class="form-group">
                    <label for="toolId">Tool ID</label>
                    <input type="text" id="toolId" required placeholder="FRT-2024-0001">
                </div>

                <div class="form-group">
                    <label for="licenseType">License Type</label>
                    <select id="licenseType" required>
                        <option value="Professional">Professional</option>
                        <option value="Enterprise">Enterprise</option>
                        <option value="Trial">Trial</option>
                        <option value="Educational">Educational</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="expiryDate">Expiry Date</label>
                    <input type="date" id="expiryDate" required>
                </div>

                <div class="form-group">
                    <label for="notes">Notes (Optional)</label>
                    <textarea id="notes" placeholder="Add any notes about this license..."></textarea>
                </div>

                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary">
                        <i class="fas fa-save"></i> Save License
                    </button>
                </div>
            </form>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
    <script>
        // Supabase Configuration
        const SUPABASE_URL = 'https://ntudetvfgwnnhqluwaqe.supabase.co';
        const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im50dWRldHZmZ3dubmhxbHV3YW9lIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc1NTgzMzIsImV4cCI6MjA5MzEzNDMzMn0.tbpGJX9IM5r0zbHTQT4bDGQKhGhJ_lw7z2ive_e8Nhs';

        const { createClient } = supabase;
        const supabaseClient = createClient(SUPABASE_URL, SUPABASE_KEY);

        let allLicenses = [];

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
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
    </script>
</body>
</html>'''

def main():
    """Create the license dashboard HTML file."""
    import os
    os.makedirs('license_dashboard', exist_ok=True)
    output_file = 'license_dashboard/index.html'
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(HTML_CONTENT)
        print(f"✓ Successfully created {output_file}")
        print(f"\nTo use the dashboard:")
        print(f"1. Open {output_file} in your web browser")
        print(f"2. The dashboard will connect to your Supabase database")
        print(f"3. You can create, edit, and manage licenses")
        print(f"\nNote: Make sure you've run the SQL schema in Supabase first!")
    except Exception as e:
        print(f"✗ Error creating dashboard: {e}")
        print(f"\nTry running this script as administrator or check file permissions.")

if __name__ == '__main__':
    main()
