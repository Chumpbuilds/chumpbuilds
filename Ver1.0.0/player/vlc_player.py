"""
VLC Player Module - External Launch with Popup
- Uses subprocess to launch external VLC (Stability)
- Adds "Initializing Player" popup dialog (User Feedback)
- Fixes popup centering and size
Current Date: 2025-12-01
"""

import subprocess
import os
import platform
import shutil
import time
import traceback
from PyQt6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QProgressBar, QFrame, QApplication
from PyQt6.QtCore import QSettings, Qt, QTimer

# --- LOADING DIALOG ---
class PlayerLoadingDialog(QDialog):
    def __init__(self, parent=None, text="Initializing Player..."):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Increased size to prevent text cutoff
        self.setFixedSize(350, 140)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.frame = QFrame()
        self.frame.setStyleSheet("""
            QFrame { 
                background-color: #1a1a1a; 
                border: 2px solid #333; 
                border-radius: 12px; 
            }
        """)
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.setSpacing(15)
        
        # Dynamic Label
        self.label = QLabel(text)
        self.label.setStyleSheet("color: white; font-size: 14px; font-weight: bold; border: none;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        frame_layout.addWidget(self.label)
        
        # Spinner/Bar
        bar = QProgressBar()
        bar.setFixedHeight(6)
        bar.setTextVisible(False)
        bar.setRange(0, 0) # Indeterminate animation
        bar.setStyleSheet("""
            QProgressBar { border: none; background-color: #333; border-radius: 3px; }
            QProgressBar::chunk { background-color: #0d7377; border-radius: 3px; }
        """)
        bar.setFixedWidth(280)
        frame_layout.addWidget(bar, 0, Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.frame)
        
        # Initial centering attempt
        self.center_on_screen()

    def center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            self.move(
                geom.center().x() - self.width() // 2,
                geom.center().y() - self.height() // 2
            )

    def update_text(self, text):
        if text:
            self.label.setText(f"Opening: {text}...")
        else:
            self.label.setText("Initializing Player...")

# --- MAIN PLAYER CLASS (External Process) ---
class VLCPlayer:
    def __init__(self):
        self.vlc_path = self.find_vlc()
        self.process = None
        self.settings = QSettings('IPTVPlayer', 'VLCSettings')
        self.loading_dialog = None
        
        self.network_caching = self.settings.value('network_caching', 15000, type=int)
        self.live_caching = self.settings.value('live_caching', 15000, type=int)
        self.file_caching = self.settings.value('file_caching', 20000, type=int)
        
        print(f"[VLC] Found VLC at: {self.vlc_path}")
        
    def find_vlc(self):
        """Find VLC executable on the system"""
        if platform.system() == "Windows":
            possible_paths = [
                r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    return path
            return shutil.which("vlc")
        elif platform.system() == "Darwin":
            return "/Applications/VLC.app/Contents/MacOS/VLC"
        else:
            return shutil.which("vlc") or "/usr/bin/vlc"
    
    def prewarm_vlc(self):
        """
        Launch and quickly close a dummy VLC instance to pre-load it into memory.
        """
        if not self.vlc_path or not os.path.exists(self.vlc_path):
            print("[VLC Pre-warm] VLC not found, skipping.")
            return

        print("[VLC Pre-warm] Starting VLC pre-warming process in background...")
        
        cmd = [
            self.vlc_path,
            '--intf', 'dummy',
            '--vout', 'dummy',
            '--no-one-instance'
        ]

        try:
            if platform.system() == "Windows":
                CREATE_NO_WINDOW = 0x08000000
                prewarm_process = subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW, 
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                prewarm_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            time.sleep(1.5)
            
            try:
                prewarm_process.terminate()
                prewarm_process.wait(timeout=1)
            except:
                prewarm_process.kill()
                
            print("[VLC Pre-warm] VLC pre-warming complete.")
            
        except Exception as e:
            print(f"[VLC Pre-warm] Error during VLC pre-warming: {e}")

    def update_buffer_settings(self, network_caching=None, live_caching=None, file_caching=None):
        if network_caching is not None:
            self.network_caching = network_caching
            self.settings.setValue('network_caching', network_caching)
        
        if live_caching is not None:
            self.live_caching = live_caching
            self.settings.setValue('live_caching', live_caching)
        
        if file_caching is not None:
            self.file_caching = file_caching
            self.settings.setValue('file_caching', file_caching)
        
        print(f"[VLC] Buffer settings updated")
    
    # Updated signature to match UI expectations
    def play_stream(self, url, title="Stream", fullscreen=False, content_type="live"):
        """
        Launch VLC to play a stream with popup.
        """
        if not self.vlc_path or not os.path.exists(self.vlc_path):
            print("[VLC] ERROR: VLC executable not found!")
            QMessageBox.critical(None, "VLC Not Found", "VLC Media Player could not be found.")
            return False
        
        # --- SHOW LOADING POPUP ---
        self.show_loading_dialog(title)
        
        # Use QTimer to allow the popup to render before blocking slightly with subprocess
        QTimer.singleShot(100, lambda: self._play_stream_internal(url, title, fullscreen, content_type))
        return True

    def _play_stream_internal(self, url, title, fullscreen, content_type):
        try:
            # Kill previous process
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=1)
                except:
                    self.process.kill()
            self.process = None

            print(f"[VLC] Launching VLC for '{title}'")
            
            cmd = [self.vlc_path, url]
            
            vlc_args = [
                "--no-video-title-show",
                "--no-osd",
                "--no-interact",
                "--quiet",
                "--play-and-exit",
                "--no-repeat",
                "--no-loop",
                "--no-one-instance",
                "--qt-notification=0",
                "--no-snapshot-preview",
            ]

            # Only add start minimized if we assume it takes focus later
            # vlc_args.append("--qt-start-minimized") 

            if fullscreen:
                vlc_args.append("--fullscreen")

            vlc_args.extend(["--meta-title", title, "--video-title", title])
            
            if content_type == "live":
                buffer_size = self.live_caching
            else:
                buffer_size = self.file_caching
            
            vlc_args.append(f"--network-caching={buffer_size}")

            cmd.extend(vlc_args)
            
            # Launch Process
            if platform.system() == "Windows":
                CREATE_NO_WINDOW = 0x08000000
                self.process = subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW,
                                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            print(f"[VLC] Process started with PID: {self.process.pid}")
            
            # Close dialog after a delay (time for VLC to open window)
            QTimer.singleShot(3500, self.close_loading_dialog)
            
        except Exception as e:
            print(f"[VLC] ERROR launching: {e}")
            self.close_loading_dialog()
            traceback.print_exc()

    def show_loading_dialog(self, title):
        try:
            # Close existing if any
            self.close_loading_dialog()
            
            # Create new dialog
            # We pass None as parent to ensure it floats freely and can be centered on screen
            self.loading_dialog = PlayerLoadingDialog(None, text=f"Opening {title}...")
            self.loading_dialog.show()
            self.loading_dialog.center_on_screen()
            QApplication.processEvents()
        except Exception as e:
            print(f"[VLC] Popup error: {e}")

    def close_loading_dialog(self):
        if self.loading_dialog:
            try:
                self.loading_dialog.close()
                self.loading_dialog = None
            except:
                pass

    def stop(self):
        """Stop VLC if running"""
        if self.process:
            print("[VLC] Stopping playback...")
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
            finally:
                self.process = None

# Singleton instance
_player_instance = None

def get_vlc_player(parent=None):
    """Get or create VLC player instance"""
    global _player_instance
    if _player_instance is None:
        _player_instance = VLCPlayer()
    return _player_instance