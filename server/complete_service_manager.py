#!/usr/bin/env python3
"""
X87 Player - Complete Service Manager (FIXED)
Manages all X87 services with proper home page detection
Current Date and Time (UTC): 2025-11-22 18:32:48
Current User: covchump
Server: 217.154.17.128
FIXED: Proper detection and management of home page service
"""

import os
import sys
import time
import subprocess
import signal
import psutil
from datetime import datetime

# Configuration
ADMIN_DIR = "/opt/iptv-panel/admin"
PORTAL_DIR = "/opt/iptv-panel/portal"
HOME_DIR = "/opt/iptv-panel/home"  # Added home directory
ADMIN_PORT = 5000
PORTAL_PORT = 5001
HOME_PORT = 5002  # Added home port
LOG_DIR = "/var/log"

class ServiceManager:
    def __init__(self):
        self.services = {
            'home': {
                'name': 'Home Page',
                'dir': HOME_DIR,
                'file': 'main.py',
                'port': HOME_PORT,
                'log': f'{LOG_DIR}/x87-home.log'
            },
            'admin': {
                'name': 'Admin Panel',
                'dir': ADMIN_DIR,
                'file': 'admin_main.py',
                'port': ADMIN_PORT,
                'log': f'{LOG_DIR}/x87-admin.log'
            },
            'portal': {
                'name': 'Customer Portal',
                'dir': PORTAL_DIR,
                'file': 'portal_main.py',
                'port': PORTAL_PORT,
                'log': f'{LOG_DIR}/x87-portal.log'
            }
        }
    
    def print_header(self):
        """Print a nice header"""
        print("\n" + "="*70)
        print("🎬 X87 Player - Complete Service Manager")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"🖥️  Server: 217.154.17.128")
        print("="*70 + "\n")
    
    def kill_all_processes(self):
        """Kill all X87 Player related processes"""
        print("🛑 STOPPING ALL SERVICES...")
        print("-" * 50)
        
        killed_count = 0
        
        # Kill by port first (most reliable)
        for service_name, service_info in self.services.items():
            port = service_info['port']
            try:
                # Kill process on port
                result = subprocess.run(
                    ['fuser', '-k', f'{port}/tcp'],
                    capture_output=True,
                    text=True,
                    stderr=subprocess.DEVNULL
                )
                if result.returncode == 0:
                    print(f"  ✅ Killed process on port {port} ({service_info['name']})")
                    killed_count += 1
                    time.sleep(1)
            except Exception as e:
                pass
        
        # Kill by process name patterns
        patterns = [
            'python3.*admin_main',
            'python3.*portal_main',
            'python3.*main.py',  # Home page main.py
            'python.*admin_main',
            'python.*portal_main',
            'python.*main.py',
            'gunicorn',
            'flask'
        ]
        
        for pattern in patterns:
            try:
                subprocess.run(
                    ['pkill', '-f', pattern],
                    capture_output=True,
                    text=True,
                    stderr=subprocess.DEVNULL
                )
            except:
                pass
        
        # Kill any remaining Python processes in our directories
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    if '/opt/iptv-panel' in cmdline and 'python' in proc.info['name']:
                        try:
                            proc.kill()
                            print(f"  ✅ Killed PID {proc.info['pid']}: {proc.info['name']}")
                            killed_count += 1
                        except:
                            pass
        except:
            pass
        
        time.sleep(2)
        print(f"\n✅ All processes stopped (killed {killed_count} processes)\n")
    
    def clean_temp_files(self):
        """Clean temporary files"""
        print("🧹 CLEANING TEMPORARY FILES...")
        print("-" * 50)
        
        # Clean Python cache files
        dirs_to_clean = [
            '/opt/iptv-panel',
            '/opt/iptv-panel/admin',
            '/opt/iptv-panel/portal',
            '/opt/iptv-panel/home'
        ]
        
        for dir_path in dirs_to_clean:
            if os.path.exists(dir_path):
                try:
                    # Remove __pycache__ directories
                    subprocess.run(['find', dir_path, '-type', 'd', '-name', '__pycache__', '-exec', 'rm', '-rf', '{}', '+'], 
                                 capture_output=True, stderr=subprocess.DEVNULL)
                    # Remove .pyc files
                    subprocess.run(['find', dir_path, '-name', '*.pyc', '-delete'], 
                                 capture_output=True, stderr=subprocess.DEVNULL)
                    print(f"  ✅ Cleaned: {dir_path}")
                except:
                    pass
        
        print("\n✅ Cleanup completed\n")
    
    def start_service(self, service_name):
        """Start a specific service"""
        service = self.services[service_name]
        
        print(f"🚀 Starting {service['name']}...")
        
        # Check if directory exists
        if not os.path.exists(service['dir']):
            print(f"  ❌ Directory not found: {service['dir']}")
            return False
        
        # Check if main file exists
        main_file = os.path.join(service['dir'], service['file'])
        if not os.path.exists(main_file):
            print(f"  ❌ Main file not found: {main_file}")
            return False
        
        # Start the service
        try:
            # Create log file if it doesn't exist
            os.makedirs(os.path.dirname(service['log']), exist_ok=True)
            
            # Start the process
            with open(service['log'], 'a') as log_file:
                process = subprocess.Popen(
                    [sys.executable, service['file']],
                    cwd=service['dir'],
                    stdout=log_file,
                    stderr=log_file,
                    start_new_session=True
                )
            
            time.sleep(3)  # Give it more time to start
            
            # Check if process is running by checking the port
            port_check = subprocess.run(
                ['netstat', '-tlnp'],
                capture_output=True,
                text=True
            )
            
            if f":{service['port']}" in port_check.stdout:
                print(f"  ✅ {service['name']} started on port {service['port']}")
                print(f"     Log: {service['log']}")
                return True
            else:
                print(f"  ⚠️  {service['name']} process started but port {service['port']} not listening")
                print(f"     Check log: {service['log']}")
                return False
                
        except Exception as e:
            print(f"  ❌ Error starting {service['name']}: {e}")
            return False
    
    def start_all_services(self):
        """Start all services in order"""
        print("🚀 STARTING ALL SERVICES...")
        print("-" * 50 + "\n")
        
        success_count = 0
        
        # Start services in specific order: home first, then admin, then portal
        service_order = ['home', 'admin', 'portal']
        
        for service_name in service_order:
            if self.start_service(service_name):
                success_count += 1
            time.sleep(2)  # Wait between starting services
        
        print(f"\n✅ Started {success_count}/{len(self.services)} services\n")
    
    def check_status(self):
        """Check status of all services"""
        print("📊 SERVICE STATUS...")
        print("-" * 50)
        
        all_running = True
        
        for service_name, service_info in self.services.items():
            # Check if port is in use
            try:
                # Check using netstat
                result = subprocess.run(
                    ['netstat', '-tlnp'],
                    capture_output=True,
                    text=True
                )
                
                port_active = f":{service_info['port']}" in result.stdout
                
                if port_active:
                    # Try to get PID
                    pid_result = subprocess.run(
                        ['lsof', '-ti', f':{service_info["port"]}'],
                        capture_output=True,
                        text=True
                    )
                    pids = pid_result.stdout.strip()
                    
                    if pids:
                        print(f"  ✅ {service_info['name']:<20} RUNNING (PID: {pids}) Port: {service_info['port']}")
                    else:
                        print(f"  ✅ {service_info['name']:<20} RUNNING on port {service_info['port']}")
                else:
                    print(f"  ❌ {service_info['name']:<20} NOT RUNNING")
                    all_running = False
                    
            except Exception as e:
                print(f"  ⚠️  {service_info['name']:<20} Unable to check status")
                all_running = False
        
        print()
        return all_running
    
    def show_logs(self, lines=10):
        """Show recent logs"""
        print(f"📝 RECENT LOGS (last {lines} lines)...")
        print("-" * 50)
        
        for service_name, service_info in self.services.items():
            if os.path.exists(service_info['log']):
                print(f"\n{service_info['name']}:")
                try:
                    result = subprocess.run(
                        ['tail', '-n', str(lines), service_info['log']],
                        capture_output=True,
                        text=True
                    )
                    if result.stdout:
                        for line in result.stdout.split('\n'):
                            if line:
                                print(f"  {line}")
                    else:
                        print("  (empty log)")
                except:
                    print("  (unable to read log)")
            else:
                print(f"\n{service_info['name']}: (log file not found)")
    
    def restart_all(self):
        """Complete restart of all services"""
        self.print_header()
        print("🔄 RESTARTING ALL X87 SERVICES...")
        print("="*70 + "\n")
        
        self.kill_all_processes()
        self.clean_temp_files()
        self.start_all_services()
        
        print("="*70)
        print("📡 X87 Player Service Status")
        print("="*70)
        
        all_running = self.check_status()
        
        print("="*70 + "\n")
        
        if all_running:
            print("✅ ALL SERVICES RUNNING SUCCESSFULLY!")
        else:
            print("⚠️  Some services are not running. Check the logs for details.")
        
        print("\n📌 QUICK ACCESS URLs:")
        print("-" * 50)
        print(f"  🏠 Home Page:        http://217.154.17.128:{HOME_PORT}")
        print(f"  🔧 Admin Panel:      http://217.154.17.128:{ADMIN_PORT}")
        print(f"  🌐 Customer Portal:  http://217.154.17.128:{PORTAL_PORT}")
        print()
        print("📝 TO VIEW LOGS:")
        print(f"  Home:   tail -f {self.services['home']['log']}")
        print(f"  Admin:  tail -f {self.services['admin']['log']}")
        print(f"  Portal: tail -f {self.services['portal']['log']}")
        print()
        print("✅ SERVICE MANAGER COMPLETED!")
        print("="*70 + "\n")

def main():
    """Main function"""
    manager = ServiceManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'stop':
            manager.print_header()
            manager.kill_all_processes()
        elif command == 'start':
            manager.print_header()
            manager.start_all_services()
            manager.check_status()
        elif command == 'restart':
            manager.restart_all()
        elif command == 'status':
            manager.print_header()
            manager.check_status()
        elif command == 'logs':
            manager.print_header()
            lines = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            manager.show_logs(lines)
        else:
            print("Usage: python3 complete_service_manager.py [stop|start|restart|status|logs]")
            print("  stop    - Stop all services")
            print("  start   - Start all services")
            print("  restart - Stop and restart all services")
            print("  status  - Check status of all services")
            print("  logs    - Show recent logs")
    else:
        # Default action is restart
        manager.restart_all()

if __name__ == "__main__":
    # Make sure we have root privileges for some operations
    if os.geteuid() != 0:
        print("⚠️  Warning: Running without root privileges. Some operations may fail.")
        print("   Run with: sudo python3 complete_service_manager.py")
        print()
    
    # Install psutil if not available
    try:
        import psutil
    except ImportError:
        print("Installing required package: psutil...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'psutil'])
        import psutil
    
    main()