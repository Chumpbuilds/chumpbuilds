"""
X87 Player - Customer Portal Customization Module
Allows customers to customize and download their app
Current Date and Time (UTC): 2025-11-22 12:32:35
Current User: covchump
"""

from flask import Blueprint, render_template_string, request, redirect, url_for, session, flash, send_file, jsonify
from portal_auth import login_required
from portal_database import get_db_connection
import json
import os
import zipfile
import shutil
import tempfile
from datetime import datetime

customization_bp = Blueprint('customization', __name__)

CUSTOMIZATION_PORTAL_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🎨 Customize Your App - X87 Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .header { 
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            color: white; 
            padding: 1rem 2rem; 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .header h1 { 
            font-size: 1.5rem; 
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .nav-buttons {
            display: flex;
            gap: 1rem;
        }
        
        .nav-btn {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            text-decoration: none;
            transition: all 0.3s;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }
        
        .nav-btn:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }
        
        .container { 
            max-width: 1200px; 
            margin: 2rem auto; 
            padding: 0 2rem; 
        }
        
        .welcome-card {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        
        .welcome-card h2 {
            color: #1f2937;
            margin-bottom: 1rem;
        }
        
        .license-info {
            background: #f3f4f6;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        }
        
        .license-info-item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.5rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #e5e7eb;
        }
        
        .license-info-item:last-child {
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }
        
        .customization-card {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        
        .section-title {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            color: #1f2937;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
        }
        
        @media (max-width: 768px) {
            .form-grid {
                grid-template-columns: 1fr;
            }
        }
        
        .form-group {
            margin-bottom: 1.5rem;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            color: #374151;
            font-weight: 500;
            font-size: 0.875rem;
        }
        
        .form-group input,
        .form-group select {
            width: 100%;
            padding: 0.75rem;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            font-size: 1rem;
            transition: all 0.3s;
        }
        
        .form-group input:focus,
        .form-group select:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .color-input-group {
            display: flex;
            gap: 1rem;
            align-items: center;
        }
        
        .color-preview {
            width: 50px;
            height: 50px;
            border-radius: 8px;
            border: 2px solid #e5e7eb;
        }
        
        .features-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }
        
        .feature-card {
            background: #f9fafb;
            padding: 1rem;
            border-radius: 8px;
            border: 2px solid #e5e7eb;
            transition: all 0.3s;
            cursor: pointer;
        }
        
        .feature-card.enabled {
            background: #dcfce7;
            border-color: #86efac;
        }
        
        .feature-card.disabled {
            background: #fee2e2;
            border-color: #fecaca;
            opacity: 0.6;
        }
        
        .feature-card-header {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }
        
        .feature-icon {
            font-size: 1.5rem;
        }
        
        .feature-name {
            font-weight: 600;
            color: #1f2937;
        }
        
        .feature-description {
            font-size: 0.875rem;
            color: #6b7280;
        }
        
        .preview-section {
            background: #f3f4f6;
            border-radius: 12px;
            padding: 2rem;
            margin-top: 2rem;
        }
        
        .phone-mockup {
            width: 300px;
            height: 600px;
            background: white;
            border-radius: 30px;
            border: 8px solid #1f2937;
            margin: 0 auto;
            overflow: hidden;
            position: relative;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
        }
        
        .phone-screen {
            width: 100%;
            height: 100%;
            overflow: hidden;
        }
        
        .app-header {
            padding: 1rem;
            color: white;
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .app-logo {
            width: 40px;
            height: 40px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
        }
        
        .app-content {
            padding: 1rem;
        }
        
        .download-section {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            text-align: center;
        }
        
        .download-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-top: 2rem;
        }
        
        .download-card {
            background: #f9fafb;
            padding: 1.5rem;
            border-radius: 12px;
            border: 2px solid #e5e7eb;
            transition: all 0.3s;
        }
        
        .download-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
        }
        
        .platform-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        
        .platform-name {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #1f2937;
        }
        
        .platform-version {
            color: #6b7280;
            margin-bottom: 1rem;
        }
        
        .btn {
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            font-size: 1rem;
            font-weight: 500;
            transition: all 0.3s;
            text-decoration: none;
            display: inline-block;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
        }
        
        .btn-success:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(16, 185, 129, 0.3);
        }
        
        .btn-secondary {
            background: #6b7280;
            color: white;
        }
        
        .btn-secondary:hover {
            background: #4b5563;
        }
        
        .action-buttons {
            display: flex;
            gap: 1rem;
            justify-content: center;
            margin-top: 2rem;
        }
        
        .alert {
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        }
        
        .alert-success {
            background: #dcfce7;
            color: #166534;
            border: 1px solid #86efac;
        }
        
        .alert-error {
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fecaca;
        }
        
        .status-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 500;
        }
        
        .status-badge.active {
            background: #dcfce7;
            color: #166534;
        }
        
        .coming-soon {
            opacity: 0.5;
            pointer-events: none;
        }
        
        .coming-soon .btn {
            background: #9ca3af;
        }
        
        .tooltip {
            position: relative;
        }
        
        .tooltip:hover::after {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: #1f2937;
            color: white;
            padding: 0.5rem;
            border-radius: 6px;
            font-size: 0.875rem;
            white-space: nowrap;
            z-index: 10;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎬 X87 Player Portal</h1>
        <div class="nav-buttons">
            <a href="{{ url_for('dashboard.customer_dashboard') }}" class="nav-btn">📊 Dashboard</a>
            <a href="{{ url_for('customization.customize') }}" class="nav-btn">🎨 Customize</a>
            <a href="{{ url_for('customization.download') }}" class="nav-btn">📥 Download</a>
            <a href="{{ url_for('auth.logout') }}" class="nav-btn">🚪 Logout</a>
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
        
        <!-- Welcome Section -->
        <div class="welcome-card">
            <h2>Welcome, {{ license.customer_name }}! 👋</h2>
            <p>Customize your X87 Player app with your preferred settings and branding.</p>
            
            <div class="license-info">
                <div class="license-info-item">
                    <span><strong>License Key:</strong></span>
                    <span><code>{{ license.license_key }}</code></span>
                </div>
                <div class="license-info-item">
                    <span><strong>Status:</strong></span>
                    <span class="status-badge {{ license.status }}">{{ license.status|upper }}</span>
                </div>
                <div class="license-info-item">
                    <span><strong>Expires:</strong></span>
                    <span>{{ license.expires_at[:10] if license.expires_at else 'Never' }}</span>
                </div>
            </div>
        </div>
        
        <!-- Customization Form -->
        <form method="POST" action="{{ url_for('customization.save_settings') }}">
            <!-- Branding Section -->
            <div class="customization-card">
                <h3 class="section-title">🎨 App Branding</h3>
                <div class="form-grid">
                    <div class="form-group">
                        <label for="app_name">App Name</label>
                        <input type="text" id="app_name" name="app_name" 
                               value="{{ customization.app_name or 'X87 Player' }}" 
                               placeholder="Your App Name">
                    </div>
                    
                    <div class="form-group">
                        <label for="theme">Theme</label>
                        <select id="theme" name="theme">
                            <option value="dark" {% if customization.theme == 'dark' %}selected{% endif %}>🌙 Dark Mode</option>
                            <option value="light" {% if customization.theme == 'light' %}selected{% endif %}>☀️ Light Mode</option>
                            <option value="auto" {% if customization.theme == 'auto' %}selected{% endif %}>🔄 Auto</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="primary_color">Primary Color</label>
                        <div class="color-input-group">
                            <input type="color" id="primary_color" name="primary_color" 
                                   value="{{ customization.primary_color or '#667eea' }}">
                            <div class="color-preview" style="background: {{ customization.primary_color or '#667eea' }}"></div>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label for="secondary_color">Accent Color</label>
                        <div class="color-input-group">
                            <input type="color" id="secondary_color" name="secondary_color" 
                                   value="{{ customization.secondary_color or '#764ba2' }}">
                            <div class="color-preview" style="background: {{ customization.secondary_color or '#764ba2' }}"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Features Section -->
            <div class="customization-card">
                <h3 class="section-title">✨ Available Features</h3>
                <div class="features-grid">
                    {% set features = features_dict %}
                    
                    <div class="feature-card {% if features.live_tv %}enabled{% else %}disabled{% endif %}">
                        <div class="feature-card-header">
                            <span class="feature-icon">📺</span>
                            <span class="feature-name">Live TV</span>
                        </div>
                        <div class="feature-description">
                            Watch live television channels
                        </div>
                    </div>
                    
                    <div class="feature-card {% if features.movies %}enabled{% else %}disabled{% endif %}">
                        <div class="feature-card-header">
                            <span class="feature-icon">🎬</span>
                            <span class="feature-name">Movies</span>
                        </div>
                        <div class="feature-description">
                            Access movie library
                        </div>
                    </div>
                    
                    <div class="feature-card {% if features.series %}enabled{% else %}disabled{% endif %}">
                        <div class="feature-card-header">
                            <span class="feature-icon">📺</span>
                            <span class="feature-name">TV Series</span>
                        </div>
                        <div class="feature-description">
                            Browse TV series collection
                        </div>
                    </div>
                    
                    <div class="feature-card {% if features.search %}enabled{% else %}disabled{% endif %}">
                        <div class="feature-card-header">
                            <span class="feature-icon">🔍</span>
                            <span class="feature-name">Search</span>
                        </div>
                        <div class="feature-description">
                            Search across all content
                        </div>
                    </div>
                    
                    <div class="feature-card {% if features.favorites %}enabled{% else %}disabled{% endif %}">
                        <div class="feature-card-header">
                            <span class="feature-icon">⭐</span>
                            <span class="feature-name">Favorites</span>
                        </div>
                        <div class="feature-description">
                            Save your favorite content
                        </div>
                    </div>
                    
                    <div class="feature-card {% if features.epg %}enabled{% else %}disabled{% endif %}">
                        <div class="feature-card-header">
                            <span class="feature-icon">📅</span>
                            <span class="feature-name">EPG Guide</span>
                        </div>
                        <div class="feature-description">
                            Electronic program guide
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Live Preview -->
            <div class="customization-card">
                <h3 class="section-title">👁️ Live Preview</h3>
                <div class="preview-section">
                    <div class="phone-mockup">
                        <div class="phone-screen">
                            <div class="app-header" id="previewHeader" 
                                 style="background: linear-gradient(135deg, {{ customization.primary_color or '#667eea' }} 0%, {{ customization.secondary_color or '#764ba2' }} 100%)">
                                <div class="app-logo">🎬</div>
                                <div>
                                    <div id="previewAppName" style="font-weight: 600; font-size: 1.125rem;">
                                        {{ customization.app_name or 'X87 Player' }}
                                    </div>
                                    <div style="font-size: 0.75rem; opacity: 0.9;">
                                        Premium Version
                                    </div>
                                </div>
                            </div>
                            <div class="app-content">
                                <div style="margin-bottom: 1.5rem;">
                                    <strong>Your Features:</strong>
                                </div>
                                <div id="featuresPreview">
                                    {% if features.live_tv %}<div style="margin-bottom: 0.5rem;">✅ Live TV</div>{% endif %}
                                    {% if features.movies %}<div style="margin-bottom: 0.5rem;">✅ Movies</div>{% endif %}
                                    {% if features.series %}<div style="margin-bottom: 0.5rem;">✅ TV Series</div>{% endif %}
                                    {% if features.search %}<div style="margin-bottom: 0.5rem;">✅ Search</div>{% endif %}
                                    {% if features.favorites %}<div style="margin-bottom: 0.5rem;">✅ Favorites</div>{% endif %}
                                    {% if features.epg %}<div style="margin-bottom: 0.5rem;">✅ EPG Guide</div>{% endif %}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="action-buttons">
                <button type="submit" class="btn btn-primary">💾 Save Settings</button>
            </div>
        </form>
    </div>
    
    <script>
        // Live preview updates
        document.getElementById('app_name').addEventListener('input', function() {
            document.getElementById('previewAppName').textContent = this.value || 'X87 Player';
        });
        
        document.getElementById('primary_color').addEventListener('input', function() {
            const primary = this.value;
            const secondary = document.getElementById('secondary_color').value;
            document.getElementById('previewHeader').style.background = 
                `linear-gradient(135deg, ${primary} 0%, ${secondary} 100%)`;
            document.querySelectorAll('.color-preview')[0].style.background = primary;
        });
        
        document.getElementById('secondary_color').addEventListener('input', function() {
            const primary = document.getElementById('primary_color').value;
            const secondary = this.value;
            document.getElementById('previewHeader').style.background = 
                `linear-gradient(135deg, ${primary} 0%, ${secondary} 100%)`;
            document.querySelectorAll('.color-preview')[1].style.background = secondary;
        });
    </script>
</body>
</html>
'''

DOWNLOAD_PORTAL_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>📥 Download Your App - X87 Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* Use same styles as above */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .header { 
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            color: white; 
            padding: 1rem 2rem; 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .container { 
            max-width: 1200px; 
            margin: 2rem auto; 
            padding: 0 2rem; 
        }
        
        .download-section {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        
        .download-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-top: 2rem;
        }
        
        .download-card {
            background: #f9fafb;
            padding: 2rem;
            border-radius: 12px;
            border: 2px solid #e5e7eb;
            transition: all 0.3s;
            text-align: center;
        }
        
        .download-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
            border-color: #667eea;
        }
        
        .platform-icon {
            font-size: 4rem;
            margin-bottom: 1rem;
        }
        
        .platform-name {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #1f2937;
        }
        
        .platform-info {
            color: #6b7280;
            margin-bottom: 1rem;
            font-size: 0.875rem;
        }
        
        .btn {
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            font-size: 1rem;
            font-weight: 500;
            transition: all 0.3s;
            text-decoration: none;
            display: inline-block;
            width: 100%;
        }
        
        .btn-download {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
        }
        
        .btn-download:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(16, 185, 129, 0.3);
        }
        
        .btn-coming-soon {
            background: #9ca3af;
            color: white;
            cursor: not-allowed;
        }
        
        .instructions-card {
            background: #f3f4f6;
            padding: 1.5rem;
            border-radius: 12px;
            margin-top: 2rem;
        }
        
        .instructions-title {
            font-size: 1.125rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #1f2937;
        }
        
        .instructions-list {
            list-style: none;
            padding: 0;
        }
        
        .instructions-list li {
            padding: 0.75rem 0;
            border-bottom: 1px solid #e5e7eb;
            display: flex;
            gap: 1rem;
        }
        
        .instructions-list li:last-child {
            border-bottom: none;
        }
        
        .step-number {
            background: #667eea;
            color: white;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            flex-shrink: 0;
        }
        
        .nav-buttons {
            display: flex;
            gap: 1rem;
        }
        
        .nav-btn {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            text-decoration: none;
            transition: all 0.3s;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }
        
        .nav-btn:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎬 X87 Player Portal</h1>
        <div class="nav-buttons">
            <a href="{{ url_for('dashboard.customer_dashboard') }}" class="nav-btn">📊 Dashboard</a>
            <a href="{{ url_for('customization.customize') }}" class="nav-btn">🎨 Customize</a>
            <a href="{{ url_for('customization.download') }}" class="nav-btn">📥 Download</a>
            <a href="{{ url_for('auth.logout') }}" class="nav-btn">🚪 Logout</a>
        </div>
    </div>
    
    <div class="container">
        <div class="download-section">
            <h2 style="text-align: center; margin-bottom: 1rem;">📥 Download Your Customized App</h2>
            <p style="text-align: center; color: #6b7280;">Choose your platform and download your personalized X87 Player</p>
            
            <div class="download-grid">
                <!-- Windows Download -->
                <div class="download-card">
                    <div class="platform-icon">🪟</div>
                    <div class="platform-name">Windows</div>
                    <div class="platform-info">
                        Windows 10/11<br>
                        Version {{ app_version }}<br>
                        Size: ~45 MB
                    </div>
                    <form method="POST" action="{{ url_for('customization.download_app', platform='windows') }}">
                        <button type="submit" class="btn btn-download">
                            Download for Windows
                        </button>
                    </form>
                </div>
                
                <!-- Android Download -->
                <div class="download-card">
                    <div class="platform-icon">🤖</div>
                    <div class="platform-name">Android</div>
                    <div class="platform-info">
                        Android 5.0+<br>
                        Version {{ app_version }}<br>
                        Size: ~25 MB
                    </div>
                    <form method="POST" action="{{ url_for('customization.download_app', platform='android') }}">
                        <button type="submit" class="btn btn-download">
                            Download APK
                        </button>
                    </form>
                </div>
                
                <!-- iOS Download -->
                <div class="download-card">
                    <div class="platform-icon">🍎</div>
                    <div class="platform-name">iOS</div>
                    <div class="platform-info">
                        iOS 12.0+<br>
                        Coming Soon<br>
                        &nbsp;
                    </div>
                    <button class="btn btn-coming-soon" disabled>
                        Coming Soon
                    </button>
                </div>
                
                <!-- Mac Download -->
                <div class="download-card">
                    <div class="platform-icon">💻</div>
                    <div class="platform-name">macOS</div>
                    <div class="platform-info">
                        macOS 10.14+<br>
                        Coming Soon<br>
                        &nbsp;
                    </div>
                    <button class="btn btn-coming-soon" disabled>
                        Coming Soon
                    </button>
                </div>
            </div>
            
            <div class="instructions-card">
                <div class="instructions-title">📋 Installation Instructions</div>
                <ol class="instructions-list">
                    <li>
                        <span class="step-number">1</span>
                        <span>Download the app for your platform using the buttons above</span>
                    </li>
                    <li>
                        <span class="step-number">2</span>
                        <span>Extract the downloaded file to your preferred location</span>
                    </li>
                    <li>
                        <span class="step-number">3</span>
                        <span>Run the application installer (Windows) or install the APK (Android)</span>
                    </li>
                    <li>
                        <span class="step-number">4</span>
                        <span>Launch the app and it will automatically activate with your license</span>
                    </li>
                    <li>
                        <span class="step-number">5</span>
                        <span>Your customized settings will be applied automatically</span>
                    </li>
                </ol>
            </div>
            
            <div class="instructions-card" style="background: #fee2e2; border: 1px solid #fecaca;">
                <div class="instructions-title">⚠️ Important Information</div>
                <ul style="list-style: none; padding: 0;">
                    <li style="margin-bottom: 0.5rem;">• Your license key: <strong>{{ license_key }}</strong></li>
                    <li style="margin-bottom: 0.5rem;">• The app is pre-configured with your license</li>
                    <li style="margin-bottom: 0.5rem;">• Device binding will occur on first launch</li>
                    <li>• Contact support if you need to change devices</li>
                </ul>
            </div>
        </div>
    </div>
</body>
</html>
'''

@customization_bp.route('/customize')
@login_required
def customize():
    """Show customization page for customer"""
    license_key = session.get('license_key')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get license info
    cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
    license = cursor.fetchone()
    
    if not license:
        flash('License not found!', 'error')
        return redirect(url_for('dashboard.customer_dashboard'))
    
    # Get customization or create default
    cursor.execute('SELECT * FROM customizations WHERE license_key = ?', (license_key,))
    customization = cursor.fetchone()
    
    if not customization:
        # Create default customization
        cursor.execute('''
            INSERT INTO customizations (license_key, app_name, primary_color, secondary_color, theme, features)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (license_key, 'X87 Player', '#667eea', '#764ba2', 'dark', license['features']))
        conn.commit()
        
        cursor.execute('SELECT * FROM customizations WHERE license_key = ?', (license_key,))
        customization = cursor.fetchone()
    
    # Parse features
    features_dict = json.loads(license['features']) if license['features'] else {}
    
    conn.close()
    
    return render_template_string(CUSTOMIZATION_PORTAL_TEMPLATE,
                                 license=license,
                                 customization=customization,
                                 features_dict=features_dict,
                                 url_for=url_for)

@customization_bp.route('/save_settings', methods=['POST'])
@login_required
def save_settings():
    """Save customer's customization settings"""
    license_key = session.get('license_key')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update customization
        cursor.execute('''
            UPDATE customizations 
            SET app_name = ?, primary_color = ?, secondary_color = ?, theme = ?, updated_at = CURRENT_TIMESTAMP
            WHERE license_key = ?
        ''', (
            request.form.get('app_name', 'X87 Player'),
            request.form.get('primary_color', '#667eea'),
            request.form.get('secondary_color', '#764ba2'),
            request.form.get('theme', 'dark'),
            license_key
        ))
        
        # Log the action
        cursor.execute('''
            INSERT INTO license_logs (license_key, action, ip_address, user_agent, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            license_key,
            'customization_updated',
            request.remote_addr,
            request.headers.get('User-Agent', ''),
            json.dumps({
                'app_name': request.form.get('app_name'),
                'theme': request.form.get('theme'),
                'timestamp': datetime.now().isoformat()
            })
        ))
        
        conn.commit()
        conn.close()
        
        flash('✅ Your settings have been saved successfully!', 'success')
        
    except Exception as e:
        flash(f'❌ Error saving settings: {str(e)}', 'error')
    
    return redirect(url_for('customization.customize'))

@customization_bp.route('/download')
@login_required
def download():
    """Show download page"""
    license_key = session.get('license_key')
    app_version = '1.0.0'  # You can make this dynamic
    
    return render_template_string(DOWNLOAD_PORTAL_TEMPLATE,
                                 license_key=license_key,
                                 app_version=app_version,
                                 url_for=url_for)

@customization_bp.route('/download/<platform>', methods=['POST'])
@login_required  
def download_app(platform):
    """Generate and download customized app for specific platform"""
    license_key = session.get('license_key')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get license and customization
        cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
        license = cursor.fetchone()
        
        cursor.execute('SELECT * FROM customizations WHERE license_key = ?', (license_key,))
        customization = cursor.fetchone()
        
        if not license or not customization:
            flash('Configuration not found!', 'error')
            return redirect(url_for('customization.download'))
        
        # Create app configuration
        app_config = {
            'license_key': license_key,
            'customer_name': license['customer_name'],
            'app_name': customization['app_name'],
            'primary_color': customization['primary_color'],
            'secondary_color': customization['secondary_color'],
            'theme': customization['theme'],
            'features': json.loads(customization['features']),
            'server_url': request.host_url,
            'api_endpoint': '/api/license/validate',
            'platform': platform,
            'generated_at': datetime.now().isoformat()
        }
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Create config file
        config_file = os.path.join(temp_dir, 'config.json')
        with open(config_file, 'w') as f:
            json.dump(app_config, f, indent=2)
        
        # Create readme file
        readme_content = f"""
X87 Player - {platform.title()} Edition
=====================================

Licensed to: {license['customer_name']}
License Key: {license_key}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This app has been customized with your settings:
- App Name: {customization['app_name']}
- Theme: {customization['theme']}

Installation:
1. Extract all files
2. Run the installer/app
3. The app will automatically activate with your license

Note: This app is bound to your license and will only work with your account.

Support: support@x87player.xyz
"""
        
        readme_file = os.path.join(temp_dir, 'README.txt')
        with open(readme_file, 'w') as f:
            f.write(readme_content)
        
        # Create zip file
        zip_filename = f"X87Player_{platform}_{license_key}_{datetime.now().strftime('%Y%m%d')}.zip"
        zip_path = os.path.join(tempfile.gettempdir(), zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            zipf.write(config_file, 'config.json')
            zipf.write(readme_file, 'README.txt')
            # Here you would add the actual app files based on platform
        
        # Clean up
        shutil.rmtree(temp_dir)
        
        # Log the download
        cursor.execute('''
            INSERT INTO license_logs (license_key, action, ip_address, user_agent, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            license_key,
            'app_downloaded',
            request.remote_addr,
            request.headers.get('User-Agent', ''),
            json.dumps({
                'platform': platform,
                'app_name': customization['app_name'],
                'timestamp': datetime.now().isoformat()
            })
        ))
        
        conn.commit()
        conn.close()
        
        return send_file(zip_path, as_attachment=True, download_name=zip_filename)
        
    except Exception as e:
        flash(f'❌ Error generating download: {str(e)}', 'error')
        return redirect(url_for('customization.download'))