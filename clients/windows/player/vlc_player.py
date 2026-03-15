"""
VLC Player Module - Launches external VLC player
Added pre-warming functionality to reduce initial startup delay.
Current Date and Time (UTC): 2025-11-16 08:13:26
Current User: covchump
"""

import subprocess
import os
import platform
import shutil
import time
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QSettings

class VLCPlayer:
    def __init__(self):
        self.vlc_path = self.find_vlc()
        self.process = None
        self.settings = QSettings('IPTVPlayer', 'VLCSettings')
        
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
        Launch and quickly close a dummy VLC instance to pre-load it into memory,
        making the first real playback faster. This runs in the background.
        """
        if not self.vlc_path or not os.path.exists(self.vlc_path):
            print("[VLC Pre-warm] VLC not found, skipping.")
            return

        print("[VLC Pre-warm] Starting VLC pre-warming process in background...")
        
        cmd = [
            self.vlc_path,
            '--intf', 'dummy',    # Run without a GUI interface
            '--vout', 'dummy',    # Run without a video output window
            '--no-one-instance'   # Ensure it doesn't interfere with other instances
        ]

        try:
            # Launch the dummy process
            prewarm_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Let it run for a very short time (e.g., 1.5 seconds) to initialize
            time.sleep(1.5)
            
            # Terminate the process
            prewarm_process.terminate()
            prewarm_process.wait(timeout=1) # Give it a moment to close
            print("[VLC Pre-warm] VLC pre-warming complete.")
            
        except Exception as e:
            print(f"[VLC Pre-warm] Error during VLC pre-warming: {e}")

    def update_buffer_settings(self, network_caching=None, live_caching=None, file_caching=None):
        """Update buffer settings"""
        if network_caching is not None:
            self.network_caching = network_caching
            self.settings.setValue('network_caching', network_caching)
        
        if live_caching is not None:
            self.live_caching = live_caching
            self.settings.setValue('live_caching', live_caching)
        
        if file_caching is not None:
            self.file_caching = file_caching
            self.settings.setValue('file_caching', file_caching)
        
        print(f"[VLC] Buffer settings updated - Network: {self.network_caching}ms, Live: {self.live_caching}ms, File: {self.file_caching}ms")
    
    def play_stream(self, url, title="Stream", fullscreen=False, content_type="live"):
        """
        Launch VLC to play a stream with robust settings and no notifications.
        """
        if not self.vlc_path or not os.path.exists(self.vlc_path):
            print("[VLC] ERROR: VLC executable not found!")
            QMessageBox.critical(None, "VLC Not Found", "VLC Media Player could not be found. Please ensure it is installed.")
            return False
        
        try:
            if self.process:
                self.process.terminate()
                self.process.wait(timeout=1)
        except Exception:
            if self.process:
                self.process.kill()
        finally:
            self.process = None

        print(f"[VLC] Launching VLC for '{title}'")
        
        cmd = [self.vlc_path, url]
        
        vlc_args = [
            "--qt-start-minimized",
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

        if fullscreen:
            vlc_args.append("--fullscreen")

        vlc_args.extend(["--meta-title", title, "--video-title", title])
        
        if content_type == "live":
            buffer_size = self.live_caching
        else:
            buffer_size = self.file_caching
        
        vlc_args.append(f"--network-caching={buffer_size}")
        print(f"[VLC] Applying buffer: {buffer_size}ms")

        cmd.extend(vlc_args)
        
        print(f"[VLC] Command: {' '.join(cmd)}")
        
        try:
            if platform.system() == "Windows":
                CREATE_NO_WINDOW = 0x08000000
                self.process = subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW,
                                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            print(f"[VLC] Process started with PID: {self.process.pid}")
            return True
            
        except Exception as e:
            print(f"[VLC] ERROR launching: {e}")
            traceback.print_exc()
            return False

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

def get_vlc_player():
    """Get or create VLC player instance"""
    global _player_instance
    if _player_instance is None:
        _player_instance = VLCPlayer()
    return _player_instance