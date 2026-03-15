"""
IPTV Player - Main Application Entry Point
Windows IPTV Player with Xtreme Codes support and License Validation
Current Date and Time (UTC): 2025-11-16 16:18:44
Current User: covchump
"""

import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor
from ui.main_page import MainWindow
from player.vlc_player import get_vlc_player  # ensure we can stop VLC on quit
from license_validator import validate_app_license, get_license_validator

# Prevent Python from writing .pyc files and creating __pycache__ directories
sys.dont_write_bytecode = True

def create_splash_screen():
    """Create a professional splash screen"""
    # Create a simple splash screen pixmap
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
    
    # Draw app name
    title_font = QFont()
    title_font.setPointSize(24)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(0, 180, 400, 40, Qt.AlignmentFlag.AlignCenter, "Stream Hub")
    
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
    painter.drawText(0, 250, 400, 30, Qt.AlignmentFlag.AlignCenter, "Validating License...")
    
    painter.end()
    
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
    # Add other themes as needed (light, custom, etc.)

def initialize_application():
    """Initialize the main application with all necessary setup"""
    # Enable high DPI support for Windows
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Create application
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Set default application info
    app.setApplicationName("Stream Hub")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("StreamHub Technologies")
    app.setOrganizationDomain("streamhub.com")
    
    print("[Main] Application initialized")
    return app

def validate_license_with_splash(app):
    """Validate license with splash screen"""
    print("[Main] Starting license validation process...")
    
    # Create and show splash screen
    splash = create_splash_screen()
    splash.show()
    app.processEvents()
    
    # Small delay to show splash screen
    QTimer.singleShot(1000, lambda: None)
    app.processEvents()
    
    try:
        # Validate license
        print("[Main] Calling license validator...")
        license_valid = validate_app_license()
        
        if not license_valid:
            splash.close()
            print("[Main] ❌ License validation failed")
            
            # Show error message
            QMessageBox.critical(
                None, 
                "License Required", 
                "A valid license is required to use this application.\n\n"
                "Please contact support if you need assistance with licensing."
            )
            return False, None
        
        print("[Main] ✅ License validation successful")
        
        # Get customizations
        license_validator = get_license_validator()
        customizations = license_validator.get_app_customizations()
        
        # Update splash with custom app name if available
        custom_app_name = customizations.get('app_name', 'Stream Hub')
        app.setApplicationName(custom_app_name)
        
        # Close splash after validation
        splash.close()
        
        print(f"[Main] License validation complete - App Name: {custom_app_name}")
        return True, customizations
        
    except Exception as e:
        splash.close()
        print(f"[Main] 💥 Error during license validation: {e}")
        
        QMessageBox.critical(
            None,
            "Application Error",
            f"An error occurred during license validation:\n\n{str(e)}\n\n"
            "Please contact support for assistance."
        )
        return False, None

def setup_application_lifecycle(app):
    """Setup application lifecycle management"""
    def cleanup_on_exit():
        """Cleanup function called when application exits"""
        print("[Main] Application shutting down...")
        
        try:
            # Stop VLC if running
            vlc_player = get_vlc_player()
            if vlc_player:
                vlc_player.stop()
                print("[Main] VLC player stopped")
        except Exception as e:
            print(f"[Main] Error stopping VLC: {e}")
        
        try:
            # Sync any pending settings
            license_validator = get_license_validator()
            if license_validator.is_license_valid():
                # Could sync final settings here if needed
                print("[Main] License validator cleanup complete")
        except Exception as e:
            print(f"[Main] Error during license cleanup: {e}")
        
        print("[Main] Cleanup complete")
    
    # Connect cleanup function to application exit
    app.aboutToQuit.connect(cleanup_on_exit)

def create_main_window(customizations):
    """Create and configure the main application window"""
    print("[Main] Creating main window...")
    
    try:
        # Create main window
        window = MainWindow()
        
        # Apply customizations
        if customizations:
            print("[Main] Applying user customizations...")
            window.apply_customizations(customizations)
        
        # Show the main window
        window.show()
        
        print("[Main] ✅ Main window created and displayed")
        return window
        
    except Exception as e:
        print(f"[Main] ❌ Error creating main window: {e}")
        
        QMessageBox.critical(
            None,
            "Application Error", 
            f"Failed to create main window:\n\n{str(e)}\n\n"
            "The application will now exit."
        )
        return None

def main():
    """Main application entry point"""
    print("=" * 60)
    print("[Main] 🚀 Starting IPTV Player Application")
    print(f"[Main] Date: 2025-11-16 16:18:44 UTC")
    print(f"[Main] User: covchump")
    print("=" * 60)
    
    try:
        # Initialize application
        app = initialize_application()
        
        # Validate license with splash screen
        license_valid, customizations = validate_license_with_splash(app)
        if not license_valid:
            print("[Main] Exiting due to license validation failure")
            sys.exit(1)
        
        # Apply global theme based on customizations
        apply_global_theme(app, customizations or {})
        
        # Setup application lifecycle management
        setup_application_lifecycle(app)
        
        # Create main window
        window = create_main_window(customizations)
        if not window:
            print("[Main] Exiting due to window creation failure")
            sys.exit(1)
        
        # Check authentication status
        if not window.api or not window.api.is_authenticated():
            print("[Main] No authentication found - login dialog will be shown")
        else:
            print("[Main] User already authenticated")
        
        print("[Main] ✅ Application startup complete")
        print("[Main] Starting event loop...")
        
        # Start the application event loop
        exit_code = app.exec()
        
        print(f"[Main] Application exited with code: {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        print("[Main] Application interrupted by user (Ctrl+C)")
        return 0
        
    except Exception as e:
        print(f"[Main] 💥 Fatal application error: {e}")
        
        # Try to show error to user if possible
        try:
            if 'app' in locals():
                QMessageBox.critical(
                    None,
                    "Fatal Error",
                    f"A fatal error occurred:\n\n{str(e)}\n\n"
                    "The application will now exit."
                )
        except:
            pass  # If we can't show the message box, just continue
        
        return 1

if __name__ == "__main__":
    # Set the exit code and exit
    exit_code = main()
    print(f"[Main] Final exit with code: {exit_code}")
    sys.exit(exit_code)