"""
IPTV Player - Main Application Entry Point
Windows IPTV Player with Xtreme Codes support and License Validation
Current Date and Time (UTC): 2025-11-16 16:18:44
Current User: covchump
FIXED: Splash screen updates App Name dynamically from server response
"""

import sys
import os
import time
from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PyQt6.QtCore import Qt, QTimer, QSettings
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor
from ui.main_page import MainWindow
from player.vlc_player import get_vlc_player
from license_validator import validate_app_license, get_license_validator

# Prevent Python from writing .pyc files and creating __pycache__ directories
sys.dont_write_bytecode = True

def generate_splash_pixmap(app_name="X87 Player"):
    """Generate the pixmap for the splash screen (reusable)"""
    pixmap = QPixmap(400, 300)
    pixmap.fill(QColor(30, 30, 30))  # Dark background
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Draw app icon/logo area
    painter.setPen(QColor(100, 181, 246))  # Blue color
    painter.setBrush(QColor(100, 181, 246, 50))
    painter.drawRoundedRect(150, 50, 100, 100, 15, 15)
    
    # Draw icon
    icon_font = QFont()
    icon_font.setPointSize(48)
    painter.setFont(icon_font)
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(150, 50, 100, 100, Qt.AlignmentFlag.AlignCenter, "🎬")
    
    # Draw app name (Dynamic)
    title_font = QFont()
    title_font.setPointSize(24)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor(255, 255, 255))
    # Align center rectangle for text
    painter.drawText(0, 180, 400, 40, Qt.AlignmentFlag.AlignCenter, app_name)
    
    # Draw subtitle
    subtitle_font = QFont()
    subtitle_font.setPointSize(12)
    painter.setFont(subtitle_font)
    painter.setPen(QColor(176, 176, 176))
    painter.drawText(0, 210, 400, 30, Qt.AlignmentFlag.AlignCenter, "Premium IPTV Player")
    
    # Draw loading text
    loading_font = QFont()
    loading_font.setPointSize(10)
    painter.setFont(loading_font)
    painter.setPen(QColor(100, 181, 246))
    painter.drawText(0, 250, 400, 30, Qt.AlignmentFlag.AlignCenter, "Loading...")
    
    painter.end()
    return pixmap

def create_splash_screen(app_name="X87 Player"):
    """Create the splash screen widget"""
    pixmap = generate_splash_pixmap(app_name)
    return QSplashScreen(pixmap)

def apply_global_theme(app, customizations):
    """Apply global application theme based on license customizations"""
    theme = customizations.get('theme', 'dark')
    primary_color = customizations.get('primary_color', '#0d7377')
    accent_color = customizations.get('accent_color', '#64b5f6')
    
    if theme == 'dark':
        app.setStyleSheet(f"""
            QApplication {{
                background-color: #1e1e1e;
                color: #ffffff;
            }}
            QMainWindow {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f0f1e,
                    stop:0.5 #1a1a2e,
                    stop:1 #16213e);
                color: #ffffff;
            }}
            QDialog {{
                background-color: #1e1e1e;
                color: #ffffff;
            }}
            QPushButton {{
                background-color: {primary_color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {accent_color};
            }}
            QLabel {{
                color: #ffffff;
            }}
            QLineEdit {{
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px;
                color: #ffffff;
            }}
            QLineEdit:focus {{
                border: 2px solid {accent_color};
            }}
        """)

def initialize_application():
    """Initialize the main application"""
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Set initial defaults
    app.setApplicationName("X87 Player")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("X87 Technologies")
    app.setOrganizationDomain("x87player.xyz")
    
    print("[Main] Application initialized")
    return app

def validate_license_with_splash(app):
    """Validate license with splash screen"""
    print("[Main] Starting license validation process...")
    
    # 1. Load cached branding (so it looks correct immediately if possible)
    branding_settings = QSettings('IPTVPlayer', 'Branding')
    cached_app_name = branding_settings.value('app_name', 'X87 Player')
    
    # 2. Create splash
    splash = create_splash_screen(cached_app_name)
    splash.show()
    app.processEvents()
    
    start_time = time.time()
    
    try:
        # 3. Validate license (Fetches new data from server)
        print("[Main] Calling license validator...")
        license_valid = validate_app_license()
        
        if not license_valid:
            splash.close()
            print("[Main] ❌ License validation failed")
            QMessageBox.critical(None, "License Required", "A valid license is required.")
            return False, None
        
        print("[Main] ✅ License validation successful")
        
        # 4. Get new customizations from server
        license_validator = get_license_validator()
        customizations = license_validator.get_app_customizations()
        
        # 5. Update branding if it changed on the server
        new_app_name = customizations.get('app_name', 'X87 Player')
        
        if new_app_name != cached_app_name:
            print(f"[Main] Branding updated from server: {new_app_name}")
            # Save to cache
            branding_settings.setValue('app_name', new_app_name)
            app.setApplicationName(new_app_name)
            
            # *** UPDATE SPLASH SCREEN IMAGE INSTANTLY ***
            updated_pixmap = generate_splash_pixmap(new_app_name)
            splash.setPixmap(updated_pixmap)
            app.processEvents() # Force UI redraw
        
        # 6. Wait out the remaining 5 seconds
        elapsed = time.time() - start_time
        if elapsed < 5.0:
            while time.time() - start_time < 5.0:
                app.processEvents()
                time.sleep(0.05)
        
        splash.close()
        print(f"[Main] License validation complete - App Name: {new_app_name}")
        return True, customizations
        
    except Exception as e:
        splash.close()
        print(f"[Main] 💥 Error: {e}")
        QMessageBox.critical(None, "Application Error", f"Error: {str(e)}")
        return False, None

def setup_application_lifecycle(app):
    """Setup cleanup on exit"""
    def cleanup_on_exit():
        print("[Main] Shutting down...")
        try:
            vlc_player = get_vlc_player()
            if vlc_player: vlc_player.stop()
        except: pass
    app.aboutToQuit.connect(cleanup_on_exit)

def create_main_window(customizations):
    """Create main window"""
    try:
        window = MainWindow()
        if customizations:
            window.apply_customizations(customizations)
        window.show()
        return window
    except Exception as e:
        QMessageBox.critical(None, "Error", f"Failed to create window: {str(e)}")
        return None

def main():
    print("=" * 60)
    print("[Main] 🚀 Starting IPTV Player")
    print("=" * 60)
    
    try:
        app = initialize_application()
        
        license_valid, customizations = validate_license_with_splash(app)
        if not license_valid:
            sys.exit(1)
        
        apply_global_theme(app, customizations or {})
        setup_application_lifecycle(app)
        
        window = create_main_window(customizations)
        if not window:
            sys.exit(1)
        
        exit_code = app.exec()
        return exit_code
        
    except Exception as e:
        print(f"[Main] 💥 Fatal error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())