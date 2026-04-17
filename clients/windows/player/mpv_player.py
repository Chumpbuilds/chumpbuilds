"""
Embedded MPV player module for inline and fullscreen playback.
Falls back to EmbeddedVLCPlayer when python-mpv/libmpv is unavailable.
"""

import os
import sys

if sys.platform == 'win32':
    _app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.environ['PATH'] = _app_dir + os.pathsep + os.environ['PATH']
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(_app_dir)

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFrame
from PyQt6.QtCore import QSettings, Qt, QTimer

from .vlc_player import EmbeddedVLCPlayer
try:
    from ui.player_controls import PlayerControlsOverlay
except Exception:
    try:
        from clients.windows.ui.player_controls import PlayerControlsOverlay
    except Exception:
        PlayerControlsOverlay = None

try:
    import mpv as _mpv
    _MPV_AVAILABLE = True
except Exception:
    _mpv = None
    _MPV_AVAILABLE = False
    print("[MPV] Warning: python-mpv/libmpv not available. EmbeddedMPVPlayer will fall back to EmbeddedVLCPlayer.")


class EmbeddedMPVPlayer:
    """Embedded MPV player with API compatibility with EmbeddedVLCPlayer."""

    def __init__(self, video_frame: QFrame):
        self._video_frame = video_frame
        self._mpv_available = _MPV_AVAILABLE
        self._player = None
        self._fallback_player = None
        self._is_muted = False
        self._volume = 80
        self._current_url = None
        self._current_title = None
        self._current_content_type = 'live'
        self._fullscreen_dialog = None
        self._active_frame = video_frame
        self._controls_overlay = None

        settings = QSettings('IPTVPlayer', 'VLCSettings')
        self._network_caching = settings.value('network_caching', 15000, type=int)
        self._live_caching = settings.value('live_caching', 15000, type=int)
        self._file_caching = settings.value('file_caching', 20000, type=int)

        if not self._mpv_available:
            self._activate_fallback("python-mpv import failed")
        else:
            self._attach_overlay(self._video_frame, is_fullscreen=False)

    def play(self, url: str, title: str = "Stream", content_type: str = 'live'):
        self._current_url = url
        self._current_title = title
        self._current_content_type = content_type
        self._update_overlay_title()

        if self._fallback_player:
            self._fallback_player.play(url, title, content_type)
            return

        try:
            self._create_and_attach_player(self._video_frame, url, title, content_type)
        except Exception as exc:
            print(f"[EmbeddedMPV] Error starting playback: {exc}")
            self._activate_fallback(f"MPV backend unavailable during playback ({exc})")
            self._fallback_player.play(url, title, content_type)

    def stop(self):
        if self._fallback_player:
            self._fallback_player.stop()
            return
        self._destroy_active_player()
        print("[EmbeddedMPV] Stopped.")

    def pause(self):
        if self._fallback_player:
            self._fallback_player.pause()
            return
        if self._player:
            try:
                self._player.pause = True
            except Exception as exc:
                print(f"[EmbeddedMPV] Error pausing: {exc}")

    def resume(self):
        if self._fallback_player:
            self._fallback_player.resume()
            return
        if self._player:
            try:
                self._player.pause = False
            except Exception as exc:
                print(f"[EmbeddedMPV] Error resuming: {exc}")

    def set_volume(self, vol: int):
        self._volume = max(0, min(100, vol))
        if self._fallback_player:
            self._fallback_player.set_volume(self._volume)
            return
        if self._player:
            try:
                self._player.volume = self._volume
            except Exception as exc:
                print(f"[EmbeddedMPV] Error setting volume: {exc}")

    def toggle_mute(self):
        self._is_muted = not self._is_muted
        if self._fallback_player:
            return self._fallback_player.toggle_mute()
        if self._player:
            try:
                self._player.mute = self._is_muted
            except Exception as exc:
                print(f"[EmbeddedMPV] Error toggling mute: {exc}")
        return self._is_muted

    def go_fullscreen(self):
        if self._fallback_player:
            self._fallback_player.go_fullscreen()
            return
        if self._fullscreen_dialog and self._fullscreen_dialog.isVisible():
            self._destroy_overlay()
            self._fullscreen_dialog.close()
            return
        if not self._current_url:
            return

        self._destroy_active_player()
        self._destroy_overlay()

        self._fullscreen_dialog = QDialog()
        self._fullscreen_dialog.setWindowTitle("MPV – Fullscreen")
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

        self._fullscreen_dialog.finished.connect(self._on_fullscreen_closed)
        self._fullscreen_dialog.showFullScreen()

        def _start_fs():
            try:
                self._attach_overlay(
                    fs_frame,
                    is_fullscreen=True,
                    fullscreen_dialog=self._fullscreen_dialog,
                )
                self._create_and_attach_player(fs_frame)
                self._update_overlay_title()
            except Exception as exc:
                print(f"[EmbeddedMPV] Error starting fullscreen playback: {exc}")
                self._activate_fallback(f"MPV fullscreen unavailable ({exc})")
                if self._fullscreen_dialog:
                    self._fullscreen_dialog.close()

        QTimer.singleShot(150, _start_fs)

    def _on_fullscreen_closed(self):
        if self._fallback_player:
            if self._current_url:
                self._fallback_player.play(
                    self._current_url,
                    self._current_title or "Stream",
                    self._current_content_type or "live",
                )
            return

        self._destroy_overlay()
        self._destroy_active_player()
        self._fullscreen_dialog = None

        if self._current_url:
            def _resume_embedded():
                try:
                    self._attach_overlay(self._video_frame, is_fullscreen=False)
                    self._create_and_attach_player(self._video_frame)
                    self._update_overlay_title()
                except Exception as exc:
                    print(f"[EmbeddedMPV] Error resuming embedded playback: {exc}")
                    self._activate_fallback(f"MPV resume unavailable ({exc})")
                    self._fallback_player.play(
                        self._current_url,
                        self._current_title or "Stream",
                        self._current_content_type or "live",
                    )

            QTimer.singleShot(100, _resume_embedded)

    @property
    def is_playing(self) -> bool:
        if self._fallback_player:
            return self._fallback_player.is_playing
        if not self._player:
            return False
        try:
            return not bool(getattr(self._player, "core_idle", True))
        except Exception:
            return False

    def _activate_fallback(self, reason: str):
        if self._fallback_player:
            return
        print(f"[EmbeddedMPV] Warning: {reason}. Falling back to EmbeddedVLCPlayer.")
        self._mpv_available = False
        self._destroy_overlay()
        self._destroy_active_player()
        self._fallback_player = EmbeddedVLCPlayer(self._video_frame)
        self._fallback_player.set_volume(self._volume)
        if self._is_muted:
            self._fallback_player.toggle_mute()

    def _destroy_active_player(self):
        if not self._player:
            return
        try:
            self._player.stop()
        except Exception:
            pass
        try:
            self._player.terminate()
        except Exception:
            pass
        self._player = None

    def _create_and_attach_player(self, frame: QFrame, url: str = None, title: str = None, content_type: str = None):
        if not self._mpv_available:
            raise RuntimeError("MPV backend not available")

        url = url or self._current_url
        title = title or self._current_title or "Stream"
        content_type = content_type or self._current_content_type or 'live'

        if not url:
            return

        self._destroy_active_player()

        frame.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        wid = int(frame.winId())

        cache_ms = self._live_caching if content_type == 'live' else self._file_caching
        readahead_secs = max(1.0, cache_ms / 1000.0)
        demuxer_max_mib = max(16, int(readahead_secs * 8))
        demuxer_max_bytes = f"{demuxer_max_mib}MiB"

        self._player = _mpv.MPV(
            wid=wid,
            cache='yes',
            cache_secs=readahead_secs,
            demuxer_readahead_secs=readahead_secs,
            demuxer_max_bytes=demuxer_max_bytes,
            demuxer_max_back_bytes=demuxer_max_bytes,
            osc='no',
            keep_open='yes',
        )
        self._player.volume = self._volume
        self._player.mute = self._is_muted
        self._player.play(url)
        self._active_frame = frame
        self._update_overlay_title()
        print(f"[EmbeddedMPV] Playing on frame {frame}: {title} ({url})")

    def _attach_overlay(self, frame: QFrame, is_fullscreen: bool, fullscreen_dialog: QDialog = None):
        if PlayerControlsOverlay is None:
            print("[EmbeddedMPV] Controls overlay unavailable: failed to import PlayerControlsOverlay.")
            return
        if not hasattr(frame, "rect"):
            print(f"[EmbeddedMPV] Controls overlay attach skipped: invalid frame {frame!r}.")
            return
        self._destroy_overlay()
        try:
            self._controls_overlay = PlayerControlsOverlay(
                frame,
                player_getter=lambda: self._player,
                fullscreen_toggle_callback=self.go_fullscreen,
            )
            self._controls_overlay.set_fullscreen(is_fullscreen)
            self._controls_overlay.set_fullscreen_dialog(fullscreen_dialog)
            self._update_overlay_title()
            print(
                f"[EmbeddedMPV] Controls overlay attached to {'fullscreen' if is_fullscreen else 'embedded'} frame."
            )
        except Exception as exc:
            print(f"[EmbeddedMPV] Warning: could not attach controls overlay: {exc}")
            self._controls_overlay = None

    def _destroy_overlay(self):
        if not self._controls_overlay:
            return
        try:
            self._controls_overlay.cleanup()
        except Exception:
            pass
        self._controls_overlay = None

    def _update_overlay_title(self):
        if not self._controls_overlay:
            return
        try:
            self._controls_overlay.set_stream_title(self._current_title or "Stream")
        except Exception:
            pass


def get_embedded_mpv_player(video_frame: QFrame) -> EmbeddedMPVPlayer:
    """Create and return a new EmbeddedMPVPlayer attached to *video_frame*."""
    return EmbeddedMPVPlayer(video_frame)
