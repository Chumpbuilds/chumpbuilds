"""
X87 Player - User Management Module
Handles admin user operations
Current Date and Time (UTC): 2025-11-22 08:41:09
Current User: covchump
UPDATED: Added full edit functionality for users with modal dialog
"""

from flask import Blueprint, render_template_string, request, redirect, url_for, session, flash
from admin_auth import login_required
from admin_database import get_db_connection
import hashlib
import sqlite3
import json
from datetime import datetime

users_bp = Blueprint('users', __name__)

# Full User Management Template with Edit Functionality
USER_MANAGEMENT_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <title>👥 User Management - X87 Player Admin</title>
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
        
        .page-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
        }
        
        .page-title {
            font-size: 2rem;
            color: #1e293b;
        }
        
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
        
        .table-container { 
            background: white; 
            border-radius: 12px; 
            overflow: hidden; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            border: 1px solid #e2e8f0;
            margin-bottom: 2rem;
        }
        
        table { width: 100%; border-collapse: collapse; }
        th { 
            background: #f8fafc; 
            padding: 1rem 1.5rem; 
            text-align: left; 
            font-weight: 600; 
            color: #374151; 
            border-bottom: 1px solid #e2e8f0;
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        td { 
            padding: 1rem 1.5rem; 
            border-bottom: 1px solid #f1f5f9; 
            color: #475569;
        }
        tr:hover { background: #f8fafc; }
        
        .role-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 500;
        }
        .role-badge.superadmin { background: #fef3c7; color: #92400e; }
        .role-badge.admin { background: #ddd6fe; color: #6b21a8; }
        .role-badge.viewer { background: #e0e7ff; color: #3730a3; }
        
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 0.5rem;
        }
        .status-indicator.active { background: #22c55e; }
        .status-indicator.inactive { background: #ef4444; }
        
        .action-buttons {
            display: flex;
            gap: 0.5rem;
        }
        .btn {
            padding: 0.25rem 0.75rem;
            border-radius: 6px;
            font-size: 0.875rem;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.2s;
            border: none;
            display: inline-block;
        }
        .btn-edit {
            background: #3b82f6;
            color: white;
        }
        .btn-edit:hover {
            background: #2563eb;
        }
        .btn-delete {
            background: #ef4444;
            color: white;
        }
        .btn-delete:hover {
            background: #dc2626;
        }
        .btn-toggle {
            background: #f59e0b;
            color: white;
        }
        .btn-toggle:hover {
            background: #d97706;
        }
        .btn-add {
            background: #22c55e;
            color: white;
            padding: 0.75rem 1.5rem;
            font-size: 1rem;
        }
        .btn-add:hover {
            background: #16a34a;
        }
        
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
            max-width: 600px;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 20px 40px rgba(0,0,0,0.2);
        }
        .modal-header {
            margin-bottom: 1.5rem;
            border-bottom: 1px solid #e5e7eb;
            padding-bottom: 1rem;
        }
        .modal-title {
            font-size: 1.5rem;
            color: #1e293b;
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
            border-radius: 8px;
            font-size: 1rem;
            transition: border-color 0.2s;
        }
        .form-group textarea {
            min-height: 100px;
            resize: vertical;
        }
        .form-group input:focus,
        .form-group select:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        .checkbox-label {
            display: flex;
            align-items: center;
            cursor: pointer;
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
        .btn-cancel:hover {
            background: #d1d5db;
        }
        .btn-save {
            background: #3b82f6;
            color: white;
            padding: 0.75rem 1.5rem;
        }
        .btn-save:hover {
            background: #2563eb;
        }
        
        .password-hint {
            font-size: 0.875rem;
            color: #6b7280;
            margin-top: 0.25rem;
        }
        
        .empty-state {
            text-align: center;
            padding: 3rem;
            color: #6b7280;
        }
        
        .empty-state h3 {
            font-size: 1.25rem;
            margin-bottom: 0.5rem;
        }
        
        .info-section {
            background: #f8fafc;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .info-section h4 {
            font-size: 0.875rem;
            color: #6b7280;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
        }
        .info-row {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid #e5e7eb;
        }
        .info-row:last-child {
            border-bottom: none;
        }
        .info-label {
            font-weight: 500;
            color: #374151;
        }
        .info-value {
            color: #6b7280;
        }
        
        .danger-zone {
            background: #fee2e2;
            border: 1px solid #fecaca;
            border-radius: 8px;
            padding: 1rem;
            margin-top: 1rem;
        }
        .danger-zone h4 {
            color: #991b1b;
            margin-bottom: 0.5rem;
        }
        .danger-zone p {
            color: #dc2626;
            font-size: 0.875rem;
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>🎬 X87 Player Business Panel</h1>
            <small style="opacity: 0.8;">User Management</small>
        </div>
        <div style="display: flex; align-items: center; gap: 2rem;">
            <div class="nav-buttons">
                <a href="{{ url_for('dashboard.admin_dashboard') }}" class="nav-btn">📊 Dashboard</a>
                <a href="{{ url_for('customers.manage_customers') }}" class="nav-btn">🎯 Customers</a>
                <a href="{{ url_for('users.manage_users') }}" class="nav-btn active">👥 Users</a>
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
        
        <div class="page-header">
            <h1 class="page-title">👥 Admin Users</h1>
            <button class="btn btn-add" onclick="showAddUserModal()">➕ Add New User</button>
        </div>
        
        <div class="table-container">
            {% if users %}
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Username</th>
                        <th>Email</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Last Login</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for user in users %}
                    <tr>
                        <td>#{{ user['id'] }}</td>
                        <td><strong>{{ user['username'] }}</strong></td>
                        <td>{{ user['email'] or 'Not set' }}</td>
                        <td><span class="role-badge {{ user['role'] if user['role'] else 'admin' }}">{{ (user['role'] if user['role'] else 'admin').title() }}</span></td>
                        <td>
                            {% if 'is_active' in user.keys() %}
                                {% if user['is_active'] %}
                                    <span class="status-indicator active"></span>Active
                                {% else %}
                                    <span class="status-indicator inactive"></span>Inactive
                                {% endif %}
                            {% else %}
                                <span class="status-indicator active"></span>Active
                            {% endif %}
                        </td>
                        <td>{{ user['created_at'][:10] if user['created_at'] else 'N/A' }}</td>
                        <td>
                            {% if 'last_login' in user.keys() and user['last_login'] %}
                                {{ user['last_login'][:16] }}
                            {% else %}
                                Never
                            {% endif %}
                        </td>
                        <td>
                            <div class="action-buttons">
                                <button class="btn btn-edit" onclick='editUser({{ user|tojson }})'>✏️ Edit</button>
                                {% if user['id'] != session.user_id %}
                                    {% if 'is_active' in user.keys() %}
                                        <form method="POST" action="{{ url_for('users.toggle_user', user_id=user['id']) }}" style="display: inline;">
                                            <button type="submit" class="btn btn-toggle">
                                                {% if user['is_active'] %}⏸️ Disable{% else %}▶️ Enable{% endif %}
                                            </button>
                                        </form>
                                    {% else %}
                                        <form method="POST" action="{{ url_for('users.toggle_user', user_id=user['id']) }}" style="display: inline;">
                                            <button type="submit" class="btn btn-toggle">⏸️ Disable</button>
                                        </form>
                                    {% endif %}
                                    <form method="POST" action="{{ url_for('users.delete_user', user_id=user['id']) }}" style="display: inline;" onsubmit="return confirm('Are you sure you want to delete this user?\\n\\nThis action cannot be undone!');">
                                        <button type="submit" class="btn btn-delete">🗑️ Delete</button>
                                    </form>
                                {% else %}
                                    <span style="color: #6b7280; font-size: 0.875rem;">Current User</span>
                                {% endif %}
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="empty-state">
                <h3>No users found</h3>
                <p>Add your first admin user to get started</p>
            </div>
            {% endif %}
        </div>
    </div>
    
    <!-- Add/Edit User Modal -->
    <div id="userModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title" id="modalTitle">Add New User</h2>
            </div>
            <form id="userForm" method="POST" action="{{ url_for('users.add_user') }}">
                <input type="hidden" id="userId" name="user_id">
                <input type="hidden" id="formAction" name="action" value="add">
                
                <!-- User Information Section -->
                <div class="info-section" id="userInfoSection" style="display: none;">
                    <h4>User Information</h4>
                    <div class="info-row">
                        <span class="info-label">User ID:</span>
                        <span class="info-value" id="displayUserId">-</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Created:</span>
                        <span class="info-value" id="displayCreated">-</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Last Login:</span>
                        <span class="info-value" id="displayLastLogin">Never</span>
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label for="username">Username *</label>
                        <input type="text" id="username" name="username" required placeholder="Enter username">
                    </div>
                    
                    <div class="form-group">
                        <label for="email">Email Address</label>
                        <input type="email" id="email" name="email" placeholder="user@example.com">
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label for="password">Password <span id="passwordRequired">*</span></label>
                        <input type="password" id="password" name="password" placeholder="Enter password">
                        <div class="password-hint" id="passwordHint" style="display: none;">
                            Leave blank to keep current password
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label for="confirm_password">Confirm Password <span id="confirmRequired" style="display: none;">*</span></label>
                        <input type="password" id="confirm_password" name="confirm_password" placeholder="Confirm password">
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label for="role">Role *</label>
                        <select id="role" name="role" required>
                            <option value="viewer">Viewer (Read Only)</option>
                            <option value="admin" selected>Admin (Full Access)</option>
                            {% if session.role == 'superadmin' %}
                            <option value="superadmin">Super Admin (System Admin)</option>
                            {% endif %}
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="phone">Phone Number</label>
                        <input type="tel" id="phone" name="phone" placeholder="+1234567890">
                    </div>
                </div>
                
                <div class="form-group full-width">
                    <label for="notes">Notes</label>
                    <textarea id="notes" name="notes" placeholder="Add any notes about this user..."></textarea>
                </div>
                
                <div class="form-group">
                    <label class="checkbox-label">
                        <input type="checkbox" id="is_active" name="is_active" value="1" checked>
                        <span>Account is active (user can log in)</span>
                    </label>
                </div>
                
                <div class="form-group">
                    <label class="checkbox-label">
                        <input type="checkbox" id="send_welcome" name="send_welcome" value="1">
                        <span>Send welcome email with login details</span>
                    </label>
                </div>
                
                <div class="danger-zone" id="dangerZone" style="display: none;">
                    <h4>⚠️ Danger Zone</h4>
                    <p>Be careful with these settings. Changes here can affect user access.</p>
                    <label class="checkbox-label">
                        <input type="checkbox" id="force_logout" name="force_logout" value="1">
                        <span>Force logout from all sessions</span>
                    </label>
                    <label class="checkbox-label" style="margin-top: 0.5rem;">
                        <input type="checkbox" id="reset_password" name="reset_password" value="1">
                        <span>Require password reset on next login</span>
                    </label>
                </div>
                
                <div class="modal-footer">
                    <div>
                        <span id="lastModified" style="color: #6b7280; font-size: 0.875rem;"></span>
                    </div>
                    <div style="display: flex; gap: 1rem;">
                        <button type="button" class="btn btn-cancel" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-save">💾 Save User</button>
                    </div>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        // Store user data for editing
        let currentEditUser = null;
        
        function showAddUserModal() {
            currentEditUser = null;
            document.getElementById('modalTitle').textContent = 'Add New User';
            document.getElementById('userForm').action = "{{ url_for('users.add_user') }}";
            document.getElementById('formAction').value = 'add';
            document.getElementById('userId').value = '';
            
            // Reset form fields
            document.getElementById('username').value = '';
            document.getElementById('email').value = '';
            document.getElementById('password').value = '';
            document.getElementById('confirm_password').value = '';
            document.getElementById('phone').value = '';
            document.getElementById('notes').value = '';
            document.getElementById('role').value = 'admin';
            document.getElementById('is_active').checked = true;
            document.getElementById('send_welcome').checked = false;
            
            // Show/hide relevant sections
            document.getElementById('userInfoSection').style.display = 'none';
            document.getElementById('dangerZone').style.display = 'none';
            document.getElementById('passwordRequired').style.display = 'inline';
            document.getElementById('confirmRequired').style.display = 'inline';
            document.getElementById('password').required = true;
            document.getElementById('passwordHint').style.display = 'none';
            document.getElementById('lastModified').textContent = '';
            
            document.getElementById('userModal').classList.add('show');
        }
        
        function editUser(user) {
            currentEditUser = user;
            document.getElementById('modalTitle').textContent = 'Edit User: ' + user.username;
            document.getElementById('userForm').action = "{{ url_for('users.edit_user') }}";
            document.getElementById('formAction').value = 'edit';
            document.getElementById('userId').value = user.id;
            
            // Fill form with user data
            document.getElementById('username').value = user.username;
            document.getElementById('email').value = user.email || '';
            document.getElementById('password').value = '';
            document.getElementById('confirm_password').value = '';
            document.getElementById('phone').value = user.phone || '';
            document.getElementById('notes').value = user.notes || '';
            document.getElementById('role').value = user.role || 'admin';
            
            // Handle is_active safely
            var isActive = true;
            if (user.hasOwnProperty('is_active')) {
                isActive = user.is_active == 1 || user.is_active === true;
            }
            document.getElementById('is_active').checked = isActive;
            
            // Reset checkboxes
            document.getElementById('send_welcome').checked = false;
            document.getElementById('force_logout').checked = false;
            document.getElementById('reset_password').checked = false;
            
            // Show user info section
            document.getElementById('userInfoSection').style.display = 'block';
            document.getElementById('displayUserId').textContent = '#' + user.id;
            document.getElementById('displayCreated').textContent = user.created_at ? user.created_at.substring(0, 16) : 'Unknown';
            document.getElementById('displayLastLogin').textContent = user.last_login ? user.last_login.substring(0, 16) : 'Never';
            
            // Show danger zone for editing
            document.getElementById('dangerZone').style.display = 'block';
            
            // Password is optional when editing
            document.getElementById('passwordRequired').style.display = 'none';
            document.getElementById('confirmRequired').style.display = 'none';
            document.getElementById('password').required = false;
            document.getElementById('passwordHint').style.display = 'block';
            
            // Show last modified info if available
            if (user.updated_at) {
                document.getElementById('lastModified').textContent = 'Last modified: ' + user.updated_at.substring(0, 16);
            }
            
            // Disable editing own role
            if (user.id == {{ session.user_id }}) {
                document.getElementById('role').disabled = true;
                document.getElementById('is_active').disabled = true;
            } else {
                document.getElementById('role').disabled = false;
                document.getElementById('is_active').disabled = false;
            }
            
            document.getElementById('userModal').classList.add('show');
        }
        
        function closeModal() {
            document.getElementById('userModal').classList.remove('show');
            currentEditUser = null;
            
            // Re-enable any disabled fields
            document.getElementById('role').disabled = false;
            document.getElementById('is_active').disabled = false;
        }
        
        // Validate password confirmation
        document.getElementById('userForm').addEventListener('submit', function(e) {
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirm_password').value;
            
            if (password && password !== confirmPassword) {
                e.preventDefault();
                alert('Passwords do not match! Please check and try again.');
                return false;
            }
            
            // Warn if disabling own account
            if (currentEditUser && currentEditUser.id == {{ session.user_id }}) {
                if (!document.getElementById('is_active').checked) {
                    if (!confirm('Warning: You are about to disable your own account!\\n\\nYou will be logged out immediately.\\n\\nAre you sure?')) {
                        e.preventDefault();
                        return false;
                    }
                }
            }
            
            return true;
        });
        
        // Close modal when clicking outside
        window.onclick = function(event) {
            var modal = document.getElementById('userModal');
            if (event.target == modal) {
                closeModal();
            }
        }
        
        // Enable confirm password field only when password is entered
        document.getElementById('password').addEventListener('input', function() {
            const confirmField = document.getElementById('confirm_password');
            if (this.value) {
                confirmField.disabled = false;
                document.getElementById('confirmRequired').style.display = 'inline';
            } else {
                confirmField.disabled = true;
                confirmField.value = '';
                document.getElementById('confirmRequired').style.display = 'none';
            }
        });
    </script>
</body>
</html>
'''

@users_bp.route('/users')
@login_required
def manage_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
    rows = cursor.fetchall()
    
    # Convert Row objects to dictionaries for easier template handling
    users = []
    for row in rows:
        user = dict(row)
        users.append(user)
    
    conn.close()
    
    # Use the embedded template directly
    return render_template_string(USER_MANAGEMENT_PAGE, users=users, session=session)

@users_bp.route('/add_user', methods=['POST'])
@login_required
def add_user():
    username = request.form['username']
    email = request.form.get('email', '')
    password = request.form['password']
    role = request.form.get('role', 'admin')
    phone = request.form.get('phone', '')
    notes = request.form.get('notes', '')
    is_active = 1 if 'is_active' in request.form else 0
    
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if we need to add phone and notes columns
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'phone' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN phone TEXT')
        if 'notes' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN notes TEXT')
        if 'updated_at' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN updated_at TIMESTAMP')
        
        cursor.execute('''
            INSERT INTO users (username, password, email, role, is_active, phone, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (username, hashed_password, email, role, is_active, phone, notes))
        conn.commit()
        
        # Log the action
        cursor.execute('''
            INSERT INTO license_logs (license_key, action, ip_address, user_agent, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            'SYSTEM',
            'user_created',
            request.remote_addr,
            f'Admin: {session.get("username")}',
            json.dumps({
                'created_user': username,
                'role': role,
                'admin': session.get('username'),
                'timestamp': datetime.now().isoformat()
            })
        ))
        conn.commit()
        
        flash(f'✅ User "{username}" added successfully!', 'success')
    except sqlite3.IntegrityError:
        flash('❌ Username already exists!', 'error')
    except Exception as e:
        flash(f'❌ Error adding user: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('users.manage_users'))

@users_bp.route('/edit_user', methods=['POST'])
@login_required
def edit_user():
    user_id = request.form['user_id']
    username = request.form['username']
    email = request.form.get('email', '')
    role = request.form.get('role', 'admin')
    phone = request.form.get('phone', '')
    notes = request.form.get('notes', '')
    is_active = 1 if 'is_active' in request.form else 0
    force_logout = 'force_logout' in request.form
    reset_password_required = 'reset_password' in request.form
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if columns exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'phone' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN phone TEXT')
        if 'notes' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN notes TEXT')
        if 'updated_at' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN updated_at TIMESTAMP')
        
        # Get current user info for logging
        cursor.execute('SELECT username, role FROM users WHERE id = ?', (user_id,))
        old_user = cursor.fetchone()
        old_username = old_user['username'] if old_user else 'Unknown'
        old_role = old_user['role'] if old_user else 'Unknown'
        
        # Update basic user info
        cursor.execute('''
            UPDATE users 
            SET username = ?, email = ?, role = ?, is_active = ?, 
                phone = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (username, email, role, is_active, phone, notes, user_id))
        
        # Handle password change if provided
        password = request.form.get('password')
        if password:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            cursor.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_password, user_id))
            flash('🔐 Password updated', 'success')
        
        # Log the changes
        changes = []
        if old_username != username:
            changes.append(f'username: {old_username} → {username}')
        if old_role != role:
            changes.append(f'role: {old_role} → {role}')
        if password:
            changes.append('password changed')
        
        cursor.execute('''
            INSERT INTO license_logs (license_key, action, ip_address, user_agent, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            'SYSTEM',
            'user_edited',
            request.remote_addr,
            f'Admin: {session.get("username")}',
            json.dumps({
                'edited_user': username,
                'user_id': user_id,
                'changes': changes,
                'admin': session.get('username'),
                'timestamp': datetime.now().isoformat()
            })
        ))
        
        conn.commit()
        flash(f'✅ User "{username}" updated successfully!', 'success')
        
        # If user disabled their own account, log them out
        if int(user_id) == session.get('user_id') and not is_active:
            session.clear()
            return redirect(url_for('auth.login'))
            
    except Exception as e:
        flash(f'❌ Error updating user: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('users.manage_users'))

@users_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    # Prevent deleting own account
    if user_id == session.get('user_id'):
        flash('❌ You cannot delete your own account!', 'error')
        return redirect(url_for('users.manage_users'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if this is the last superadmin
        cursor.execute('SELECT COUNT(*) FROM users WHERE role = "superadmin" AND id != ?', (user_id,))
        superadmin_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT role, username FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        
        if user and user['role'] == 'superadmin' and superadmin_count == 0:
            flash('❌ Cannot delete the last superadmin!', 'error')
        else:
            username = user['username'] if user else 'Unknown'
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            
            # Log the deletion
            cursor.execute('''
                INSERT INTO license_logs (license_key, action, ip_address, user_agent, details)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                'SYSTEM',
                'user_deleted',
                request.remote_addr,
                f'Admin: {session.get("username")}',
                json.dumps({
                    'deleted_user': username,
                    'user_id': user_id,
                    'admin': session.get('username'),
                    'timestamp': datetime.now().isoformat()
                })
            ))
            
            conn.commit()
            flash(f'✅ User "{username}" deleted successfully!', 'success')
    except Exception as e:
        flash(f'❌ Error deleting user: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('users.manage_users'))

@users_bp.route('/toggle_user/<int:user_id>', methods=['POST'])
@login_required
def toggle_user(user_id):
    # Prevent disabling own account
    if user_id == session.get('user_id'):
        flash('❌ You cannot disable your own account!', 'error')
        return redirect(url_for('users.manage_users'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # First check if is_active column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_active' in columns:
            cursor.execute('SELECT is_active, username FROM users WHERE id = ?', (user_id,))
            result = cursor.fetchone()
            
            if result:
                current_status = result['is_active'] if result['is_active'] is not None else 1
                new_status = 0 if current_status else 1
                username = result['username']
                
                cursor.execute('UPDATE users SET is_active = ? WHERE id = ?', (new_status, user_id))
                
                # Log the action
                cursor.execute('''
                    INSERT INTO license_logs (license_key, action, ip_address, user_agent, details)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    'SYSTEM',
                    'user_toggled',
                    request.remote_addr,
                    f'Admin: {session.get("username")}',
                    json.dumps({
                        'toggled_user': username,
                        'user_id': user_id,
                        'new_status': 'active' if new_status else 'inactive',
                        'admin': session.get('username'),
                        'timestamp': datetime.now().isoformat()
                    })
                ))
                
                conn.commit()
                
                status_text = 'activated' if new_status else 'deactivated'
                flash(f'✅ User "{username}" {status_text} successfully!', 'success')
        else:
            flash('⚠️ User status feature not available. Please update database schema.', 'warning')
    except Exception as e:
        flash(f'❌ Error toggling user status: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('users.manage_users'))