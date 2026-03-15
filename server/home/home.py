"""
Setup script for X87 Player Home Page
Creates directory structure and installs dependencies
Current Date and Time (UTC): 2025-11-21 17:43:33
Current User: covchump
"""

import os
import subprocess
import sys

def setup_home_directory():
    """Create the home directory structure"""
    base_dir = '/opt/iptv-panel/home'
    
    # Create directory if it doesn't exist
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        print(f"✅ Created directory: {base_dir}")
    
    # Create subdirectories
    subdirs = ['logs', 'static', 'templates']
    for subdir in subdirs:
        path = os.path.join(base_dir, subdir)
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"✅ Created subdirectory: {path}")
    
    print("\n📁 Directory structure created successfully!")
    return base_dir

def install_requirements():
    """Install Python requirements"""
    requirements = [
        'flask',
        'flask-cors',
        'requests',
        'gunicorn'
    ]
    
    print("\n📦 Installing Python packages...")
    for package in requirements:
        subprocess.run(['pip3', 'install', package], capture_output=True)
        print(f"✅ Installed: {package}")

def create_systemd_service():
    """Create systemd service for home page"""
    service_content = """[Unit]
Description=X87 Player Home Page
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/iptv-panel/home
ExecStart=/usr/bin/python3 /opt/iptv-panel/home/home_main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_file = '/etc/systemd/system/x87-home.service'
    
    with open(service_file, 'w') as f:
        f.write(service_content)
    
    print(f"\n✅ Created systemd service: {service_file}")
    
    # Reload systemd and enable service
    subprocess.run(['systemctl', 'daemon-reload'])
    subprocess.run(['systemctl', 'enable', 'x87-home.service'])
    print("✅ Service enabled")

def update_nginx_config():
    """Update nginx configuration for home page"""
    nginx_config = """
# X87 Player Home Page Configuration
server {
    listen 80;
    server_name x87player.xyz www.x87player.xyz;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name x87player.xyz www.x87player.xyz;
    
    # SSL certificates
    ssl_certificate /etc/letsencrypt/live/x87player.xyz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/x87player.xyz/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Proxy to Flask home page app
    location / {
        proxy_pass http://127.0.0.1:5002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
"""
    
    print("\n📝 Nginx configuration:")
    print(nginx_config)
    print("\n⚠️  Add this to your nginx configuration and reload nginx")

def main():
    if os.geteuid() != 0:
        print("❌ This script must be run as root!")
        sys.exit(1)
    
    print("="*70)
    print("🏠 Setting up X87 Player Home Page")
    print("="*70)
    
    # Setup directory
    base_dir = setup_home_directory()
    
    # Install requirements
    install_requirements()
    
    # Create service
    create_systemd_service()
    
    # Show nginx config
    update_nginx_config()
    
    print("\n" + "="*70)
    print("✅ Setup complete!")
    print("="*70)
    print("\n📋 Next steps:")
    print("1. Copy the Python files to /opt/iptv-panel/home/")
    print("2. Update nginx configuration")
    print("3. Start the service: systemctl start x87-home")
    print("4. Check status: systemctl status x87-home")
    print("\n🌐 The home page will be available at:")
    print("   https://x87player.xyz")

if __name__ == "__main__":
    main()