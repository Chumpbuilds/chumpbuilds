"""
X87 Player - Customer Management Template
HTML template for the customer management page
Current Date and Time (UTC): 2025-11-22 11:59:59
Current User: covchump
FIXED: Added Settings Link to Navigation
"""

CUSTOMER_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🎯 Customer Management - X87 Player Admin</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; }
        
        .header { 
            background: linear-gradient(135deg, #1e40af 0%, #7c3aed 100%); 
            color: white; 
            padding: 1rem 2rem; 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header h1 { font-size: 1.5rem; }
        .header .user-info { display: flex; align-items: center; gap: 1rem; }
        .nav-buttons {
            display: flex;
            gap: 0.5rem;
            margin-right: 2rem;
        }
        .nav-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            border: 1px solid rgba(255,255,255,0.3);
            padding: 0.5rem 1rem;
            border-radius: 6px;
            text-decoration: none;
            transition: all 0.2s;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .nav-btn:hover { background: rgba(255,255,255,0.3); }
        .nav-btn.active { background: rgba(255,255,255,0.4); font-weight: 600; }
        .logout-btn { 
            background: rgba(255,255,255,0.2); 
            color: white; 
            border: 1px solid rgba(255,255,255,0.3);
            padding: 0.5rem 1rem; 
            border-radius: 6px; 
            text-decoration: none;
            transition: background-color 0.2s;
        }
        .logout-btn:hover { background: rgba(255,255,255,0.3); }
        
        .container { max-width: 1400px; margin: 2rem auto; padding: 0 2rem; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .stat-card {
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            border: 1px solid #e5e7eb;
        }
        .stat-number { font-size: 2rem; font-weight: bold; }
        .stat-label { color: #6b7280; font-size: 0.875rem; margin-top: 0.5rem; }
        
        .alert { 
            padding: 1rem 1.5rem; 
            border-radius: 8px; 
            margin-bottom: 1rem;
            border: 1px solid;
        }
        .alert-success {
            background: #dcfce7;
            color: #166534;
            border-color: #86efac;
        }
        .alert-error {
            background: #fee2e2;
            color: #991b1b;
            border-color: #fecaca;
        }
        .alert-warning {
            background: #fef3c7;
            color: #92400e;
            border-color: #fde68a;
        }
        
        .table-container { 
            background: white; 
            border-radius: 12px; 
            overflow: hidden; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            margin-bottom: 2rem;
        }
        .table-header {
            padding: 1.5rem 2rem;
            background: #f9fafb;
            border-bottom: 1px solid #e5e7eb;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .table-header h2 { color: #1f2937; }
        
        table { width: 100%; border-collapse: collapse; }
        th { 
            background: #f9fafb; 
            padding: 1rem; 
            text-align: left; 
            font-weight: 600; 
            color: #374151; 
            border-bottom: 1px solid #e5e7eb;
            font-size: 0.875rem;
        }
        td { 
            padding: 1rem; 
            border-bottom: 1px solid #f3f4f6; 
            color: #1f2937;
        }
        tr:hover { background: #f9fafb; }
        
        .license-key {
            font-family: 'Courier New', monospace;
            background: #f3f4f6;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.875rem;
        }
        
        .status { 
            padding: 0.25rem 0.75rem; 
            border-radius: 20px; 
            font-size: 0.75rem; 
            font-weight: 500;
            display: inline-block;
        }
        .status.active { background: #dcfce7; color: #166534; }
        .status.expired { background: #fee2e2; color: #991b1b; }
        .status.suspended { background: #fef3c7; color: #92400e; }
        
        .device-bound {
            color: #059669;
            font-size: 0.75rem;
        }
        .device-unbound {
            color: #6b7280;
            font-size: 0.75rem;
        }
        
        .action-buttons {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        .btn {
            padding: 0.375rem 0.75rem;
            border-radius: 6px;
            font-size: 0.75rem;
            border: none;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            transition: all 0.2s;
        }
        .btn-sm {
            padding: 0.25rem 0.5rem;
            font-size: 0.7rem;
        }
        .btn-add {
            background: #10b981;
            color: white;
            padding: 0.5rem 1rem;
            font-size: 0.875rem;
        }
        .btn-add:hover { background: #059669; }
        .btn-edit {
            background: #3b82f6;
            color: white;
        }
        .btn-edit:hover { background: #2563eb; }
        .btn-delete {
            background: #ef4444;
            color: white;
        }
        .btn-delete:hover { background: #dc2626; }
        .btn-unbind {
            background: #f59e0b;
            color: white;
        }
        .btn-unbind:hover { background: #d97706; }
        .btn-hardware {
            background: #8b5cf6;
            color: white;
        }
        .btn-hardware:hover { background: #7c3aed; }
        .btn-warning {
            background: #fbbf24;
            color: #78350f;
            padding: 0.5rem 1rem;
            font-size: 0.875rem;
        }
        .btn-warning:hover { background: #f59e0b; }
        .btn-clear-conflict {
            background: #fb923c;
            color: white;
            padding: 0.25rem 0.5rem;
            font-size: 0.7rem;
        }
        .btn-clear-conflict:hover { background: #f97316; }
        
        /* Modal styles */
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        .modal.show {
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .modal-content {
            background: white;
            padding: 2rem;
            border-radius: 12px;
            width: 90%;
            max-width: 700px;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 20px 40px rgba(0,0,0,0.2);
        }
        .modal-header {
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #e5e7eb;
        }
        .modal-title {
            font-size: 1.5rem;
            color: #1f2937;
        }
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }
        .form-group {
            margin-bottom: 1.5rem;
        }
        .form-group.full-width {
            grid-column: 1 / -1;
        }
        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            color: #374151;
            font-weight: 500;
            font-size: 0.875rem;
        }
        .form-group input,
        .form-group select,
        .form-group textarea {
            width: 100%;
            padding: 0.75rem;
            border: 2px solid #e5e7eb;
            border-radius: 6px;
            font-size: 0.875rem;
        }
        .form-group textarea {
            min-height: 80px;
            resize: vertical;
        }
        .form-group input:focus,
        .form-group select:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        
        .features-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 0.75rem;
        }
        .checkbox-label {
            display: flex;
            align-items: center;
            cursor: pointer;
            padding: 0.5rem;
            border-radius: 6px;
            transition: background 0.2s;
        }
        .checkbox-label:hover {
            background: #f3f4f6;
        }
        .checkbox-label input[type="checkbox"] {
            width: auto;
            margin-right: 0.5rem;
        }
        
        .modal-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #e5e7eb;
        }
        .btn-cancel {
            background: #e5e7eb;
            color: #374151;
            padding: 0.75rem 1.5rem;
        }
        .btn-cancel:hover { background: #d1d5db; }
        .btn-save {
            background: #3b82f6;
            color: white;
            padding: 0.75rem 1.5rem;
        }
        .btn-save:hover { background: #2563eb; }
        .btn-generate {
            background: #10b981;
            color: white;
            padding: 0.5rem 1rem;
        }
        .btn-generate:hover { background: #059669; }
        
        .conflict-warning {
            background: #fef3c7;
            border: 1px solid #fde68a;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        }
        .conflict-warning h3 {
            color: #92400e;
            margin-bottom: 0.5rem;
        }
        .conflict-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        .conflict-item {
            background: white;
            padding: 0.75rem;
            border-radius: 6px;
            margin-bottom: 0.5rem;
            border: 1px solid #fde68a;
            display: flex;
            justify-content: space-between;
            align-items: start;
        }
        .conflict-details {
            flex: 1;
        }
        
        .info-hint {
            font-size: 0.75rem;
            color: #6b7280;
            margin-top: 0.25rem;
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>🎬 X87 Player Business Panel</h1>
            <small style="opacity: 0.8;">Customer & License Management</small>
        </div>
        <div style="display: flex; align-items: center; gap: 2rem;">
            <div class="nav-buttons">
                <a href="{{ url_for('dashboard.admin_dashboard') }}" class="nav-btn">📊 Dashboard</a>
                <a href="{{ url_for('customers.manage_customers') }}" class="nav-btn active">🎯 Customers</a>
                <a href="{{ url_for('users.manage_users') }}" class="nav-btn">👥 Users</a>
                <a href="{{ url_for('settings.manage_settings') }}" class="nav-btn">⚙️ Settings</a>
                <a href="{{ url_for('profile.my_profile') }}" class="nav-btn">👤 Profile</a>
            </div>
            <div class="user-info">
                <span>👤 {{ session.username }}</span>
                <a href="{{ url_for('auth.logout') }}" class="logout-btn">🚪 Logout</a>
            </div>
        </div>
    </div>
    
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <!-- Statistics -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{{ stats.total_licenses }}</div>
                <div class="stat-label">📋 Total Licenses</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.active_licenses }}</div>
                <div class="stat-label">✅ Active</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.expired_licenses }}</div>
                <div class="stat-label">⏰ Expired</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.suspended_licenses }}</div>
                <div class="stat-label">⏸️ Suspended</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.bound_licenses }}</div>
                <div class="stat-label">🔗 Device Bound</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.expiring_soon }}</div>
                <div class="stat-label">⚠️ Expiring Soon</div>
            </div>
        </div>
        
        <!-- Binding Conflicts Warning -->
        {% if conflicts %}
        <div class="conflict-warning">
            <div class="conflict-header">
                <h3>⚠️ Recent Binding Conflicts (Last 7 Days)</h3>
                <form method="POST" action="{{ form_urls.clear_all_conflicts }}" style="display: inline;">
                    <button type="submit" class="btn btn-warning" onclick="return confirm('This will clear ALL binding conflict logs. Are you sure?')">
                        🧹 Clear All Conflicts
                    </button>
                </form>
            </div>
            <p style="margin-bottom: 1rem; color: #6b7280;">These licenses had attempted activations from different devices:</p>
            
            {% for conflict in conflicts %}
            <div class="conflict-item">
                <div class="conflict-details">
                    <strong>{{ conflict.license_key }}</strong> - {{ conflict.customer_name }}
                    <br>
                    <small style="color: #6b7280;">Attempted: {{ conflict.attempted_device }} | Currently bound to: {{ conflict.bound_device }}</small>
                    <br>
                    <small style="color: #9ca3af;">{{ conflict.timestamp }}</small>
                </div>
                <form method="POST" action="{{ url_for('customers.clear_conflicts', license_key=conflict.license_key) }}" style="margin-left: 1rem;">
                    <button type="submit" class="btn btn-clear-conflict" title="Clear this conflict">
                        Clear
                    </button>
                </form>
            </div>
            {% endfor %}
        </div>
        {% endif %}
        
        <!-- Licenses Table -->
        <div class="table-container">
            <div class="table-header">
                <h2>🔑 License Management</h2>
                <button class="btn btn-add" onclick="showAddLicenseModal()">➕ Add New License</button>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>License Key</th>
                        <th>Customer</th>
                        <th>Status</th>
                        <th>Device</th>
                        <th>Expires</th>
                        <th>Features</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for license in licenses %}
                    <tr>
                        <td>
                            <span class="license-key">{{ license['license_key'] }}</span>
                            {% if license.recent_binding_conflicts > 0 %}
                            <br>
                            <small style="color: #ef4444;">⚠️ {{ license.recent_binding_conflicts }} conflicts</small>
                            <form method="POST" action="{{ url_for('customers.clear_conflicts', license_key=license['license_key']) }}" style="display: inline; margin-left: 0.5rem;">
                                <button type="submit" class="btn btn-clear-conflict" style="font-size: 0.65rem; padding: 0.15rem 0.3rem;">
                                    Clear
                                </button>
                            </form>
                            {% endif %}
                        </td>
                        <td>
                            <strong>{{ license['customer_name'] or 'Not assigned' }}</strong>
                            {% if license['customer_email'] %}
                            <br><small>{{ license['customer_email'] }}</small>
                            {% endif %}
                        </td>
                        <td>
                            <span class="status {{ license['status'] }}">
                                {{ license['status'].upper() }}
                            </span>
                        </td>
                        <td>
                            {% if license['device_id'] %}
                                <span class="device-bound">🔗 Bound</span>
                                <br><small>{{ license['device_id'][:12] }}...</small>
                            {% else %}
                                <span class="device-unbound">⭕ Not bound</span>
                            {% endif %}
                        </td>
                        <td>
                            {% if license['expires_at'] %}
                                {{ license['expires_at'][:10] }}
                            {% else %}
                                Never
                            {% endif %}
                        </td>
                        <td>
                            {% if license.features_dict %}
                                {% if license.features_dict.live_tv %}📺{% endif %}
                                {% if license.features_dict.movies %}🎬{% endif %}
                                {% if license.features_dict.series %}📺{% endif %}
                                {% if license.features_dict.search %}🔍{% endif %}
                                {% if license.features_dict.favorites %}⭐{% endif %}
                                {% if license.features_dict.epg %}📅{% endif %}
                            {% else %}
                                All
                            {% endif %}
                        </td>
                        <td>
                            <div class="action-buttons">
                                <button class="btn btn-edit" onclick='editLicense({{ license|tojson }})'>✏️ Edit</button>
                                
                                {% if license['device_id'] %}
                                <form method="POST" action="{{ url_for('customers.unbind_device', license_id=license['id']) }}" style="display: inline;">
                                    <button type="submit" class="btn btn-unbind" title="Unbind device and clear conflicts">🔓 Unbind</button>
                                </form>
                                {% endif %}
                                
                                <form method="POST" action="{{ url_for('customers.delete_customer', license_id=license['id']) }}" 
                                      style="display: inline;" 
                                      onsubmit="return confirmDelete('{{ license['license_key'] }}', '{{ license['customer_name'] }}')">
                                    <button type="submit" class="btn btn-delete">🗑️</button>
                                </form>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <!-- Add/Edit License Modal -->
    <div id="licenseModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title" id="modalTitle">Add New License</h2>
            </div>
            <form id="licenseForm" method="POST" action="{{ form_urls.add_license }}">
                <!-- Hidden field for license ID when editing -->
                <input type="hidden" id="license_id" name="license_id" value="">
                
                <div class="form-row">
                    <div class="form-group">
                        <label for="license_key">License Key *</label>
                        <div style="display: flex; gap: 0.5rem;">
                            <input type="text" id="license_key" name="license_key" placeholder="X87-XXXX-XXXX-XXXX">
                            <button type="button" class="btn btn-generate" onclick="generateLicenseKey()">🔑 Generate</button>
                        </div>
                        <span class="info-hint">Leave empty to auto-generate</span>
                    </div>
                    
                    <div class="form-group">
                        <label for="customer_name">Customer Name *</label>
                        <input type="text" id="customer_name" name="customer_name" required placeholder="John Doe">
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label for="customer_email">Customer Email</label>
                        <input type="email" id="customer_email" name="customer_email" placeholder="customer@example.com">
                    </div>
                    
                    <div class="form-group">
                        <label for="status">Status</label>
                        <select id="status" name="status">
                            <option value="active">Active</option>
                            <option value="suspended">Suspended</option>
                            <option value="expired">Expired</option>
                        </select>
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label for="expires_at">Expiry Date</label>
                        <input type="datetime-local" id="expires_at" name="expires_at">
                        <span class="info-hint">Leave empty for lifetime license</span>
                    </div>
                    
                    <div class="form-group">
                        <label for="max_devices">Max Devices</label>
                        <input type="number" id="max_devices" name="max_devices" value="1" min="1" max="10">
                    </div>
                </div>
                
                <div class="form-group full-width">
                    <label>Features</label>
                    <div class="features-grid">
                        <label class="checkbox-label">
                            <input type="checkbox" id="feature_live_tv" name="feature_live_tv" checked>
                            <span>📺 Live TV</span>
                        </label>
                        <label class="checkbox-label">
                            <input type="checkbox" id="feature_movies" name="feature_movies" checked>
                            <span>🎬 Movies</span>
                        </label>
                        <label class="checkbox-label">
                            <input type="checkbox" id="feature_series" name="feature_series" checked>
                            <span>📺 Series</span>
                        </label>
                        <label class="checkbox-label">
                            <input type="checkbox" id="feature_search" name="feature_search" checked>
                            <span>🔍 Search</span>
                        </label>
                        <label class="checkbox-label">
                            <input type="checkbox" id="feature_favorites" name="feature_favorites" checked>
                            <span>⭐ Favorites</span>
                        </label>
                        <label class="checkbox-label">
                            <input type="checkbox" id="feature_epg" name="feature_epg" checked>
                            <span>📅 EPG</span>
                        </label>
                    </div>
                </div>
                
                <div class="form-group full-width">
                    <label for="notes">Notes</label>
                    <textarea id="notes" name="notes" placeholder="Add any notes about this license..."></textarea>
                </div>
                
                <div class="form-group" id="resetDeviceGroup" style="display: none;">
                    <label class="checkbox-label">
                        <input type="checkbox" id="reset_device" name="reset_device">
                        <span>🔓 Reset device binding (customer will need to reactivate)</span>
                    </label>
                </div>
                
                <div class="modal-footer">
                    <button type="button" class="btn btn-cancel" onclick="closeLicenseModal()">Cancel</button>
                    <button type="submit" class="btn btn-save">💾 Save License</button>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        // Store current editing license
        let currentEditLicense = null;
        
        // Store the URLs from Flask (passed from Python)
        const urls = {
            addLicense: "{{ form_urls.add_license }}",
            editLicense: "{{ form_urls.edit_license }}"
        };
        
        function showAddLicenseModal() {
            document.getElementById('modalTitle').textContent = 'Add New License';
            document.getElementById('licenseForm').action = urls.addLicense;
            document.getElementById('licenseForm').reset();
            document.getElementById('license_id').value = '';
            document.getElementById('resetDeviceGroup').style.display = 'none';
            
            // Set all checkboxes to checked for new license
            document.querySelectorAll('#licenseForm input[type="checkbox"]').forEach(cb => {
                if (cb.id !== 'reset_device') {
                    cb.checked = true;
                }
            });
            
            currentEditLicense = null;
            document.getElementById('licenseModal').classList.add('show');
        }
        
        function editLicense(license) {
            document.getElementById('modalTitle').textContent = 'Edit License';
            document.getElementById('licenseForm').action = urls.editLicense;
            currentEditLicense = license;
            
            // Set the license ID in hidden field
            document.getElementById('license_id').value = license.id;
            
            // Fill form with license data
            document.getElementById('license_key').value = license.license_key;
            document.getElementById('customer_name').value = license.customer_name || '';
            document.getElementById('customer_email').value = license.customer_email || '';
            document.getElementById('status').value = license.status || 'active';
            document.getElementById('max_devices').value = license.max_devices || 1;
            document.getElementById('notes').value = license.notes || '';
            
            // Set expiry date if exists
            if (license.expires_at) {
                // Convert to datetime-local format (YYYY-MM-DDTHH:MM)
                const expiryDate = license.expires_at.replace(' ', 'T').substring(0, 16);
                document.getElementById('expires_at').value = expiryDate;
            } else {
                document.getElementById('expires_at').value = '';
            }
            
            // Set features checkboxes
            const features = license.features_dict || {};
            document.getElementById('feature_live_tv').checked = features.live_tv !== false;
            document.getElementById('feature_movies').checked = features.movies !== false;
            document.getElementById('feature_series').checked = features.series !== false;
            document.getElementById('feature_search').checked = features.search !== false;
            document.getElementById('feature_favorites').checked = features.favorites !== false;
            document.getElementById('feature_epg').checked = features.epg !== false;
            
            // Show reset device option if device is bound
            if (license.device_id) {
                document.getElementById('resetDeviceGroup').style.display = 'block';
                document.getElementById('reset_device').checked = false;
            } else {
                document.getElementById('resetDeviceGroup').style.display = 'none';
            }
            
            // Disable license key field when editing
            document.getElementById('license_key').disabled = true;
            
            document.getElementById('licenseModal').classList.add('show');
        }
        
        function closeLicenseModal() {
            document.getElementById('licenseModal').classList.remove('show');
            // Re-enable license key field
            document.getElementById('license_key').disabled = false;
            currentEditLicense = null;
        }
        
        function generateLicenseKey() {
            // Generate random license key
            const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
            let key = 'X87-';
            for (let i = 0; i < 3; i++) {
                for (let j = 0; j < 4; j++) {
                    key += chars.charAt(Math.floor(Math.random() * chars.length));
                }
                if (i < 2) key += '-';
            }
            document.getElementById('license_key').value = key;
        }
        
        function confirmDelete(licenseKey, customerName) {
            const message = `⚠️ DELETE LICENSE CONFIRMATION\\n\\n` +
                          `License Key: ${licenseKey}\\n` +
                          `Customer: ${customerName}\\n\\n` +
                          `This will permanently delete:\\n` +
                          `• The license\\n` +
                          `• All customizations\\n` +
                          `• All logs\\n\\n` +
                          `Are you absolutely sure?`;
            
            if (confirm(message)) {
                // Double confirmation for safety
                return confirm(`🔴 FINAL CONFIRMATION\\n\\nDelete license ${licenseKey}?\\n\\nThis action cannot be undone!`);
            }
            return false;
        }
        
        // Close modal when clicking outside
        window.onclick = function(event) {
            var modal = document.getElementById('licenseModal');
            
            if (event.target == modal) {
                closeLicenseModal();
            }
        }
        
        // Form validation
        document.getElementById('licenseForm').addEventListener('submit', function(e) {
            const customerName = document.getElementById('customer_name').value.trim();
            
            if (!customerName) {
                e.preventDefault();
                alert('Customer name is required!');
                return false;
            }
            
            // If editing and reset device is checked, confirm
            if (currentEditLicense && document.getElementById('reset_device').checked) {
                if (!confirm('Are you sure you want to reset the device binding? The customer will need to reactivate on their device.')) {
                    e.preventDefault();
                    return false;
                }
            }
            
            // Re-enable license key field before submit (if it was disabled for editing)
            document.getElementById('license_key').disabled = false;
            
            return true;
        });
        
        // Auto-generate license key if field is empty when adding new license
        document.getElementById('licenseForm').addEventListener('submit', function(e) {
            const licenseKeyField = document.getElementById('license_key');
            const isNewLicense = !currentEditLicense;
            
            if (isNewLicense && !licenseKeyField.value.trim()) {
                // Generate a key automatically
                generateLicenseKey();
            }
        });
    </script>
</body>
</html>
'''