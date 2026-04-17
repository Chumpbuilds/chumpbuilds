"""
Tests for EmbeddedMPVPlayer fallback behavior.
"""

import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, PropertyMock


class _FakeQSettings:
    _store: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    def value(self, key, default=None, type=None):  # noqa: A002
        val = _FakeQSettings._store.get(key, default)
        if type is not None and val is not None:
            try:
                return type(val)
            except (TypeError, ValueError):
                return default
        return val


def _install_qt_stubs():
    fake_qtwidgets = types.ModuleType('PyQt6.QtWidgets')
    fake_qtwidgets.QMessageBox = MagicMock()
    fake_qtwidgets.QDialog = object
    fake_qtwidgets.QVBoxLayout = MagicMock()
    fake_qtwidgets.QFrame = object

    fake_qtcore = types.ModuleType('PyQt6.QtCore')
    fake_qtcore.QSettings = _FakeQSettings
    fake_qtcore.Qt = MagicMock()
    fake_qtcore.QTimer = MagicMock()

    fake_qtgui = types.ModuleType('PyQt6.QtGui')
    fake_qtgui.QKeySequence = MagicMock()
    fake_qtgui.QShortcut = MagicMock()

    fake_pyqt6 = types.ModuleType('PyQt6')
    fake_pyqt6.QtWidgets = fake_qtwidgets
    fake_pyqt6.QtCore = fake_qtcore
    fake_pyqt6.QtGui = fake_qtgui

    sys.modules.setdefault('PyQt6', fake_pyqt6)
    sys.modules['PyQt6.QtWidgets'] = fake_qtwidgets
    sys.modules['PyQt6.QtCore'] = fake_qtcore
    sys.modules['PyQt6.QtGui'] = fake_qtgui


_install_qt_stubs()

_windows_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
if _windows_dir not in sys.path:
    sys.path.insert(0, _windows_dir)

sys.modules.pop('player.mpv_player', None)
import player.mpv_player as mpv_player  # noqa: E402


class TestEmbeddedMPVFallback(unittest.TestCase):
    def test_falls_back_to_embedded_vlc_when_mpv_unavailable(self):
        with patch.object(mpv_player, '_MPV_AVAILABLE', False), \
             patch.object(mpv_player, 'EmbeddedVLCPlayer') as mock_vlc:
            player = mpv_player.EmbeddedMPVPlayer(video_frame=object())
            player.play('http://example.com/live', 'Live', 'live')

            mock_vlc.assert_called_once()
            mock_vlc.return_value.play.assert_called_once_with(
                'http://example.com/live', 'Live', 'live'
            )

    def test_runtime_mpv_failure_switches_to_fallback(self):
        with patch.object(mpv_player, '_MPV_AVAILABLE', True), \
             patch.object(mpv_player, 'EmbeddedVLCPlayer') as mock_vlc:
            player = mpv_player.EmbeddedMPVPlayer(video_frame=object())
            with patch.object(player, '_create_and_attach_player', side_effect=RuntimeError("libmpv missing")):
                player.play('http://example.com/movie', 'Movie', 'movie')

            mock_vlc.assert_called_once()
            mock_vlc.return_value.play.assert_called_once_with(
                'http://example.com/movie', 'Movie', 'movie'
            )

    def test_is_playing_proxies_to_fallback(self):
        with patch.object(mpv_player, '_MPV_AVAILABLE', False), \
             patch.object(mpv_player, 'EmbeddedVLCPlayer') as mock_vlc:
            type(mock_vlc.return_value).is_playing = PropertyMock(return_value=True)
            player = mpv_player.EmbeddedMPVPlayer(video_frame=object())
            self.assertTrue(player.is_playing)

    def test_fullscreen_close_with_fallback_resumes_playback(self):
        with patch.object(mpv_player, '_MPV_AVAILABLE', False), \
             patch.object(mpv_player, 'EmbeddedVLCPlayer') as mock_vlc:
            player = mpv_player.EmbeddedMPVPlayer(video_frame=object())
            player._current_url = 'http://example.com/live'
            player._current_title = 'Live'
            player._current_content_type = 'live'

            player._on_fullscreen_closed()

            mock_vlc.return_value.play.assert_called_with(
                'http://example.com/live', 'Live', 'live'
            )

    def test_play_updates_overlay_title_when_overlay_exists(self):
        with patch.object(mpv_player, '_MPV_AVAILABLE', True), \
             patch.object(mpv_player, 'PlayerControlsOverlay', None):
            player = mpv_player.EmbeddedMPVPlayer(video_frame=object())
            player._controls_overlay = MagicMock()
            with patch.object(player, '_create_and_attach_player'):
                player.play('http://example.com/live', 'Overlay Title', 'live')

            player._controls_overlay.set_stream_title.assert_called_with('Overlay Title')

    def test_go_fullscreen_toggles_off_when_dialog_visible(self):
        with patch.object(mpv_player, '_MPV_AVAILABLE', True), \
             patch.object(mpv_player, 'PlayerControlsOverlay', None):
            player = mpv_player.EmbeddedMPVPlayer(video_frame=object())
            dialog = MagicMock()
            dialog.isVisible.return_value = True
            player._fullscreen_dialog = dialog

            player.go_fullscreen()

            dialog.close.assert_called_once()

    def test_attach_overlay_logs_when_overlay_import_unavailable(self):
        frame = MagicMock()
        frame.rect = MagicMock(return_value=object())
        with patch.object(mpv_player, '_MPV_AVAILABLE', True), \
             patch.object(mpv_player, 'PlayerControlsOverlay', None), \
             patch('builtins.print') as mock_print:
            player = mpv_player.EmbeddedMPVPlayer(video_frame=frame)
            player._attach_overlay(frame, is_fullscreen=False)

            mock_print.assert_any_call(
                "[EmbeddedMPV] Controls overlay unavailable: failed to import PlayerControlsOverlay."
            )

    def test_attach_overlay_adds_fullscreen_dialog_as_event_source(self):
        frame = MagicMock()
        frame.rect = MagicMock(return_value=object())
        overlay_instance = MagicMock()

        with patch.object(mpv_player, '_MPV_AVAILABLE', True), \
             patch.object(mpv_player, 'PlayerControlsOverlay', return_value=overlay_instance):
            player = mpv_player.EmbeddedMPVPlayer(video_frame=frame)
            player._fullscreen_dialog = MagicMock()
            player._attach_overlay(frame, is_fullscreen=True)

            overlay_instance.set_fullscreen.assert_called_with(True)
            overlay_instance.add_event_source.assert_called_once_with(player._fullscreen_dialog)
            overlay_instance.set_stream_title.assert_called_with("Stream")


if __name__ == '__main__':
    unittest.main()
