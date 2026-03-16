"""
Tests for VLC prewarm startup-latency optimisation.

Covers:
  1. Prewarm initialisation (env-flag config, default values)
  2. Prewarm background-thread lifecycle
  3. play_stream using a warmed instance (fast path)
  4. play_stream cold-launch fallback (prewarm not done)
  5. Prewarm crash/error recovery

Run with:
    python -m pytest clients/windows/tests/test_vlc_prewarm.py
or
    python clients/windows/tests/test_vlc_prewarm.py
"""

import os
import subprocess
import sys
import threading
import types
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Inject minimal PyQt6 / python-vlc stubs so the module can be imported
# without a display server or the real Qt / VLC libraries.
# ---------------------------------------------------------------------------

class _FakeQSettings:
    """Thread-safe in-memory QSettings replacement."""
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

    def setValue(self, key, val):
        _FakeQSettings._store[key] = val

    @classmethod
    def reset(cls):
        cls._store.clear()


def _install_qt_stubs():
    """Inject minimal stubs for PyQt6 and python-vlc."""
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
    # Ensure python-vlc is absent so EmbeddedVLCPlayer falls back gracefully
    sys.modules['vlc'] = None  # type: ignore[assignment]


_install_qt_stubs()

# Put the player directory on sys.path before importing
_player_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', 'player'))
if _player_dir not in sys.path:
    sys.path.insert(0, _player_dir)

# Force a clean import (tests may be collected multiple times in a suite)
sys.modules.pop('vlc_player', None)
import vlc_player  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(vlc_path='/usr/bin/vlc'):
    """Return a fresh ExternalVLCPlayer with QSettings reset."""
    _FakeQSettings.reset()
    with patch.object(vlc_player.ExternalVLCPlayer, 'find_vlc', return_value=vlc_path):
        return vlc_player.ExternalVLCPlayer()


def _make_mock_proc(pid=1234):
    proc = MagicMock()
    proc.pid = pid
    return proc


# ---------------------------------------------------------------------------
# 1. Prewarm initialisation
# ---------------------------------------------------------------------------

class TestPrewarmInitialization(unittest.TestCase):
    """ExternalVLCPlayer initialises prewarm flags correctly."""

    def setUp(self):
        os.environ.pop('VLC_PREWARM_ENABLED', None)
        os.environ.pop('VLC_NETWORK_CACHING_MS', None)

    def tearDown(self):
        os.environ.pop('VLC_PREWARM_ENABLED', None)
        os.environ.pop('VLC_NETWORK_CACHING_MS', None)

    def test_prewarm_enabled_by_default(self):
        player = _make_player()
        self.assertTrue(player.prewarm_enabled)

    def test_prewarm_disabled_via_env(self):
        os.environ['VLC_PREWARM_ENABLED'] = '0'
        player = _make_player()
        self.assertFalse(player.prewarm_enabled)

    def test_prewarm_done_initially_false(self):
        player = _make_player()
        self.assertFalse(player._prewarm_done)

    def test_prewarm_thread_initially_none(self):
        player = _make_player()
        self.assertIsNone(player._prewarm_thread)

    def test_play_start_time_initially_none(self):
        player = _make_player()
        self.assertIsNone(player._play_start_time)

    def test_network_caching_override_via_env(self):
        os.environ['VLC_NETWORK_CACHING_MS'] = '500'
        player = _make_player()
        self.assertEqual(player.live_caching, 500)
        self.assertEqual(player.network_caching, 500)

    def test_invalid_caching_env_does_not_crash(self):
        os.environ['VLC_NETWORK_CACHING_MS'] = 'notanumber'
        # Should not raise; default values must be ints
        player = _make_player()
        self.assertIsInstance(player.live_caching, int)
        self.assertIsInstance(player.network_caching, int)

    def test_prewarm_enabled_saved_to_settings(self):
        _FakeQSettings.reset()
        _FakeQSettings._store['prewarm_enabled'] = False
        # Create player directly (without _make_player) to preserve store values
        with patch.object(vlc_player.ExternalVLCPlayer, 'find_vlc', return_value='/usr/bin/vlc'):
            player = vlc_player.ExternalVLCPlayer()
        self.assertFalse(player.prewarm_enabled)


# ---------------------------------------------------------------------------
# 2. Prewarm background-thread lifecycle
# ---------------------------------------------------------------------------

class TestPrewarmThread(unittest.TestCase):
    """prewarm_vlc() runs in a background daemon thread and sets _prewarm_done."""

    def setUp(self):
        os.environ.pop('VLC_PREWARM_ENABLED', None)

    def tearDown(self):
        os.environ.pop('VLC_PREWARM_ENABLED', None)

    @patch('os.path.exists', return_value=True)
    @patch('subprocess.Popen')
    @patch('time.sleep')
    def test_prewarm_spawns_daemon_thread(self, _sleep, mock_popen, _exists):
        mock_popen.return_value = _make_mock_proc()
        player = _make_player()
        player.prewarm_vlc()

        self.assertIsNotNone(player._prewarm_thread)
        self.assertIsInstance(player._prewarm_thread, threading.Thread)
        self.assertTrue(player._prewarm_thread.daemon)

    @patch('os.path.exists', return_value=True)
    @patch('subprocess.Popen')
    @patch('time.sleep')
    def test_prewarm_sets_done_flag(self, _sleep, mock_popen, _exists):
        mock_popen.return_value = _make_mock_proc()
        player = _make_player()
        player.prewarm_vlc()

        # Wait for the background thread to finish (up to 3 s)
        if player._prewarm_thread:
            player._prewarm_thread.join(timeout=3)

        self.assertTrue(player._prewarm_done)

    @patch('os.path.exists', return_value=True)
    @patch('subprocess.Popen')
    @patch('time.sleep')
    def test_prewarm_not_duplicated_while_running(self, _sleep, mock_popen, _exists):
        mock_popen.return_value = _make_mock_proc()
        player = _make_player()
        player.prewarm_vlc()
        first_thread = player._prewarm_thread

        player.prewarm_vlc()  # second call must be a no-op
        self.assertIs(player._prewarm_thread, first_thread)

    @patch('os.path.exists', return_value=True)
    @patch('subprocess.Popen')
    @patch('time.sleep')
    def test_prewarm_not_duplicated_after_completion(self, _sleep, mock_popen, _exists):
        mock_popen.return_value = _make_mock_proc()
        player = _make_player()
        player.prewarm_vlc()
        if player._prewarm_thread:
            player._prewarm_thread.join(timeout=3)

        first_thread = player._prewarm_thread
        player.prewarm_vlc()  # already done – must be a no-op
        self.assertIs(player._prewarm_thread, first_thread)

    def test_prewarm_skipped_when_disabled_via_env(self):
        os.environ['VLC_PREWARM_ENABLED'] = '0'
        player = _make_player()
        player.prewarm_vlc()
        self.assertIsNone(player._prewarm_thread)

    def test_prewarm_skipped_when_vlc_not_found(self):
        player = _make_player(vlc_path=None)
        # Override exists so _do_prewarm path can be exercised
        with patch('os.path.exists', return_value=False):
            player.prewarm_vlc()

        if player._prewarm_thread:
            player._prewarm_thread.join(timeout=3)

        self.assertFalse(player._prewarm_done)

    @patch('os.path.exists', return_value=True)
    @patch('subprocess.Popen', side_effect=OSError('exec failed'))
    def test_prewarm_survives_popen_error(self, _popen, _exists):
        """Popen failure must not crash the app; _prewarm_done stays False."""
        player = _make_player()
        player.prewarm_vlc()
        if player._prewarm_thread:
            player._prewarm_thread.join(timeout=3)

        self.assertFalse(player._prewarm_done)


# ---------------------------------------------------------------------------
# 3. play_stream – warmed (fast) path
# ---------------------------------------------------------------------------

class TestPlayStreamWarmedPath(unittest.TestCase):
    """play_stream succeeds and logs timing when prewarm is complete."""

    @patch('os.path.exists', return_value=True)
    @patch('subprocess.Popen')
    def test_play_stream_succeeds_when_prewarmed(self, mock_popen, _exists):
        mock_popen.return_value = _make_mock_proc(pid=9999)
        player = _make_player()
        player._prewarm_done = True  # simulate completed prewarm

        result = player.play_stream('http://example.com/live', 'Test Channel', content_type='live')

        self.assertTrue(result)
        mock_popen.assert_called_once()

    @patch('os.path.exists', return_value=True)
    @patch('subprocess.Popen')
    def test_play_stream_records_start_time(self, mock_popen, _exists):
        mock_popen.return_value = _make_mock_proc()
        player = _make_player()
        player._prewarm_done = True

        player.play_stream('http://example.com/live', 'Timing Test')

        self.assertIsNotNone(player._play_start_time)
        self.assertIsInstance(player._play_start_time, float)

    @patch('os.path.exists', return_value=True)
    @patch('subprocess.Popen')
    def test_play_stream_live_uses_live_caching(self, mock_popen, _exists):
        mock_popen.return_value = _make_mock_proc()
        player = _make_player()
        player.live_caching = 5000
        player.file_caching = 20000

        player.play_stream('http://example.com/live', 'Live', content_type='live')

        cmd_args = ' '.join(mock_popen.call_args[0][0])
        self.assertIn('--network-caching=5000', cmd_args)

    @patch('os.path.exists', return_value=True)
    @patch('subprocess.Popen')
    def test_play_stream_vod_uses_file_caching(self, mock_popen, _exists):
        mock_popen.return_value = _make_mock_proc()
        player = _make_player()
        player.live_caching = 5000
        player.file_caching = 20000

        player.play_stream('http://example.com/movie.mp4', 'Movie', content_type='movie')

        cmd_args = ' '.join(mock_popen.call_args[0][0])
        self.assertIn('--network-caching=20000', cmd_args)


# ---------------------------------------------------------------------------
# 4. play_stream – cold-launch fallback
# ---------------------------------------------------------------------------

class TestPlayStreamColdLaunchFallback(unittest.TestCase):
    """play_stream works transparently when prewarm has not yet completed."""

    @patch('os.path.exists', return_value=True)
    @patch('subprocess.Popen')
    def test_cold_launch_succeeds(self, mock_popen, _exists):
        mock_popen.return_value = _make_mock_proc(pid=1234)
        player = _make_player()
        self.assertFalse(player._prewarm_done)

        result = player.play_stream('http://example.com/stream', 'Cold Launch')

        self.assertTrue(result)
        mock_popen.assert_called_once()

    @patch('os.path.exists', return_value=True)
    @patch('subprocess.Popen', side_effect=OSError('exec failed'))
    def test_launch_error_returns_false(self, _popen, _exists):
        player = _make_player()
        result = player.play_stream('http://example.com/stream', 'Error Case')
        self.assertFalse(result)

    def test_play_stream_returns_false_when_vlc_missing(self):
        player = _make_player(vlc_path=None)
        with patch('os.path.exists', return_value=False):
            result = player.play_stream('http://example.com/stream')
        self.assertFalse(result)

    @patch('os.path.exists', return_value=True)
    @patch('subprocess.Popen')
    def test_play_terminates_previous_process(self, mock_popen, _exists):
        """A running process must be stopped before launching a new stream."""
        old_proc = MagicMock()
        new_proc = _make_mock_proc(pid=5678)
        mock_popen.return_value = new_proc

        player = _make_player()
        player.process = old_proc

        player.play_stream('http://example.com/new', 'New Stream')

        old_proc.terminate.assert_called_once()
        self.assertEqual(player.process, new_proc)


# ---------------------------------------------------------------------------
# 5. update_buffer_settings – prewarm_enabled parameter
# ---------------------------------------------------------------------------

class TestUpdateBufferSettings(unittest.TestCase):
    """update_buffer_settings persists prewarm_enabled correctly."""

    def test_prewarm_enabled_can_be_disabled(self):
        player = _make_player()
        player.update_buffer_settings(prewarm_enabled=False)
        self.assertFalse(player.prewarm_enabled)

    def test_prewarm_enabled_can_be_re_enabled(self):
        player = _make_player()
        player.update_buffer_settings(prewarm_enabled=False)
        player.update_buffer_settings(prewarm_enabled=True)
        self.assertTrue(player.prewarm_enabled)

    def test_buffer_settings_unchanged_when_omitted(self):
        player = _make_player()
        player.live_caching = 7000
        player.update_buffer_settings(prewarm_enabled=False)
        # live_caching should not have been touched
        self.assertEqual(player.live_caching, 7000)


if __name__ == '__main__':
    unittest.main()
