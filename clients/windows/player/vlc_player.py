"""
VLC Player Module - Launches external VLC player and provides an embedded player.
Added pre-warming functionality to reduce initial startup delay.
Updated to include EmbeddedVLCPlayer using python-vlc bindings.
Fullscreen: stop + re-create the media player on the fullscreen frame's HWND.
"""

import subprocess
import os
import platform
import shutil
import time
import traceback
from PyQt6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QFrame
from PyQt6.QtCore import QSettings, Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut

# Attempt to import python-vlc; graceful fallback if not available
try:
    import vlc as _vlc
    _VLC_AVAILABLE = True
except Exception:
    _vlc = None
    _VLC_AVAILABLE = False
    print("[VLC] Warning: python-vlc not available. EmbeddedVLCPlayer will fall back to external VLC.")


class ExternalVLCPlayer:
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
            '--intf', 'dummy',
            '--vout', 'dummy',
            '--no-one-instance'
        ]

        try:
            prewarm_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
            prewarm_process.terminate()
            prewarm_process.wait(timeout=1)
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


class EmbeddedVLCPlayer:
    """Embedded VLC player that renders video inside a QFrame widget using python-vlc.
    Falls back to ExternalVLCPlayer.play_stream() if python-vlc is not available.

    Fullscreen strategy: stop the current player, create a brand-new VLC instance
    bound to the fullscreen QDialog's frame HWND, then start playback fresh.
    When fullscreen closes, create another new instance bound to the embedded frame.
    This is the only reliable approach on Windows since VLC cannot redirect video
    output from one HWND to another on a live MediaPlayer instance.
    """

    def __init__(self, video_frame: QFrame):
        self._video_frame = video_frame
        self._vlc_available = _VLC_AVAILABLE
        self._instance = None
        self._media_player = None
        self._is_muted = False
        self._volume = 80
        self._current_url = None
        self._current_title = None
        self._current_content_type = 'live'
        self._fullscreen_dialog = None

        # Read caching settings
        settings = QSettings('IPTVPlayer', 'VLCSettings')
        self._network_caching = settings.value('network_caching', 15000, type=int)
        self._live_caching = settings.value('live_caching', 15000, type=int)
        self._file_caching = settings.value('file_caching', 20000, type=int)

        if not self._vlc_available:
            self._external_player = ExternalVLCPlayer()
        else:
            self._external_player = None

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play(self, url: str, title: str = "Stream", content_type: str = 'live'):
        """Play a stream URL inside the embedded QFrame."""
        self._current_url = url
        self._current_title = title
        self._current_content_type = content_type

        if not self._vlc_available:
            print("[EmbeddedVLC] python-vlc not available, falling back to external VLC.")
            self._external_player.play_stream(url, title, False, content_type)
            return

        try:
            self._create_and_attach_player(self._video_frame, url, title, content_type)
        except Exception as exc:
            print(f"[EmbeddedVLC] Error starting playback: {exc}")

    def stop(self):
        """Stop playback."""
        if self._media_player:
            try:
                self._media_player.stop()
            except Exception as exc:
                print(f"[EmbeddedVLC] Error stopping: {exc}")
            finally:
                self._media_player = None
                self._instance = None
        print("[EmbeddedVLC] Stopped.")

    def pause(self):
        """Pause playback."""
        if self._media_player and self._vlc_available:
            self._media_player.pause()

    def resume(self):
        """Resume playback."""
        if self._media_player and self._vlc_available:
            self._media_player.play()

    # ------------------------------------------------------------------
    # Volume / Mute
    # ------------------------------------------------------------------

    def set_volume(self, vol: int):
        """Set volume (0–100)."""
        self._volume = max(0, min(100, vol))
        if self._media_player and self._vlc_available:
            self._media_player.audio_set_volume(self._volume)

    def toggle_mute(self):
        """Toggle mute state."""
        self._is_muted = not self._is_muted
        if self._media_player and self._vlc_available:
            self._media_player.audio_set_mute(self._is_muted)
        return self._is_muted

    # ------------------------------------------------------------------
    # Fullscreen
    # ------------------------------------------------------------------

    def go_fullscreen(self):
        """Open a fullscreen dialog and start a fresh player instance attached to it."""
        if not self._vlc_available or not self._current_url:
            return

        # Stop the embedded player first
        if self._media_player:
            try:
                self._media_player.stop()
            except Exception:
                pass
            self._media_player = None
            self._instance = None

        # Build the fullscreen dialog
        self._fullscreen_dialog = QDialog()
        self._fullscreen_dialog.setWindowTitle("VLC – Fullscreen")
        self._fullscreen_dialog.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        )
        self._fullscreen_dialog.setStyleSheet("background-color: #000000;")
        self._fullscreen_dialog.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)

        layout = QVBoxLayout(self._fullscreen_dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        fs_frame = QFrame(self._fullscreen_dialog)
        fs_frame.setStyleSheet("background-color: #000000;")
        fs_frame.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        layout.addWidget(fs_frame)

        # Escape key closes fullscreen
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self._fullscreen_dialog)
        esc_shortcut.activated.connect(self._fullscreen_dialog.close)

        self._fullscreen_dialog.finished.connect(self._on_fullscreen_closed)
        self._fullscreen_dialog.showFullScreen()

        # Defer player creation until dialog surface is ready
        def _start_fs():
            self._create_and_attach_player(fs_frame)

        QTimer.singleShot(150, _start_fs)

    def _on_fullscreen_closed(self):
        """Stop fullscreen player and restart playback in the original embedded frame."""
        # Stop the fullscreen player
        if self._media_player:
            try:
                self._media_player.stop()
            except Exception:
                pass
            self._media_player = None
            self._instance = None

        self._fullscreen_dialog = None

        # Restart in the embedded frame after a short delay
        if self._current_url:
            QTimer.singleShot(100, lambda: self._create_and_attach_player(self._video_frame))

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def is_playing(self) -> bool:
        """Return True if the player is currently playing."""
        if self._media_player and self._vlc_available:
            return bool(self._media_player.is_playing())
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_and_attach_player(self, frame: QFrame, url: str = None, title: str = None, content_type: str = None):
        """
        Create a fresh VLC instance + media player, attach it to *frame*, and start playback.
        Uses stored current URL/title/content_type if not provided.
        """
        url = url or self._current_url
        title = title or self._current_title or "Stream"
        content_type = content_type or self._current_content_type or 'live'

        if not url:
            return

        # Stop/release any previous player
        if self._media_player:
            try:
                self._media_player.stop()
            except Exception:
                pass
            self._media_player = None
            self._instance = None

        cache_ms = self._live_caching if content_type == 'live' else self._file_caching
        vlc_args = [
            f'--network-caching={cache_ms}',
            f'--live-caching={self._live_caching}',
            f'--file-caching={self._file_caching}',
            '--no-video-title-show',
            '--quiet',
        ]

        self._instance = _vlc.Instance(' '.join(vlc_args))
        self._media_player = self._instance.media_player_new()

        self._attach_to_frame(frame)

        media = self._instance.media_new(url)
        self._media_player.set_media(media)
        self._media_player.audio_set_volume(self._volume)
        if self._is_muted:
            self._media_player.audio_set_mute(True)
        self._media_player.play()
        print(f"[EmbeddedVLC] Playing on frame {frame}: {title} ({url})")

    def _attach_to_frame(self, frame: QFrame):
        """Attach the media player's output to a QFrame."""
        if not self._media_player:
            return
        frame.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        wid = int(frame.winId())
        system = platform.system()
        if system == "Windows":
            self._media_player.set_hwnd(wid)
        elif system == "Darwin":
            self._media_player.set_nsobject(wid)
        else:
            self._media_player.set_xwindow(wid)


def get_embedded_vlc_player(video_frame: QFrame) -> EmbeddedVLCPlayer:
    """Create and return a new EmbeddedVLCPlayer attached to *video_frame*."""
    return EmbeddedVLCPlayer(video_frame)


# Singleton instance
_player_instance = None

def get_vlc_player():
    """Get or create ExternalVLCPlayer singleton instance (used by Movies/Series/etc.)."""
    global _player_instance
    if _player_instance is None:
        _player_instance = ExternalVLCPlayer()
    return _player_instance