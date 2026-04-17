"""
MPV player controls overlay for embedded/fullscreen playback surfaces.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QEvent, QPoint, QRect, QSettings, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)

try:
    from services import subtitle_service
except Exception:
    from clients.windows.services import subtitle_service


def _fmt_time(seconds) -> str:
    try:
        total = max(0, int(float(seconds)))
    except Exception:
        total = 0
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _track_value(track: dict, *keys):
    for key in keys:
        if key in track and track.get(key) is not None:
            return track.get(key)
    return None


def _normalize_subtitle_languages(raw_value) -> List[str]:
    if isinstance(raw_value, list):
        values = raw_value
    elif isinstance(raw_value, str):
        values = [v.strip() for v in raw_value.replace(";", ",").split(",")]
    else:
        values = []
    normalized = [str(v).strip().lower() for v in values if str(v).strip()]
    return normalized or ["en"]


class SubtitleSearchWorker(QThread):
    finished = pyqtSignal(object, str)

    def __init__(self, metadata: Dict[str, Any], language: str):
        super().__init__()
        self._metadata = dict(metadata or {})
        self._language = (language or "en").strip().lower() or "en"

    def run(self):
        title = (self._metadata.get("title") or "").strip()
        if not title:
            self.finished.emit([], "Missing content title for subtitle search.")
            return
        try:
            results = subtitle_service.search_subtitles(
                title=title,
                lang=self._language,
                year=self._metadata.get("year"),
                tmdb_id=self._metadata.get("tmdb_id"),
                imdb_id=self._metadata.get("imdb_id"),
                season=self._metadata.get("season"),
                episode=self._metadata.get("episode"),
            )
            self.finished.emit(results or [], "")
        except Exception as exc:
            self.finished.emit([], str(exc))


class SubtitleDownloadWorker(QThread):
    finished = pyqtSignal(str, str)

    def __init__(self, file_id):
        super().__init__()
        self._file_id = file_id

    def run(self):
        if not self._file_id:
            self.finished.emit("", "Invalid subtitle file id.")
            return
        try:
            srt_text = subtitle_service.download_subtitle(self._file_id)
            path = subtitle_service.save_srt_to_temp(srt_text, self._file_id)
            self.finished.emit(path, "")
        except Exception as exc:
            self.finished.emit("", str(exc))


class SubtitleSearchDialog(QDialog):
    PROVIDER_COLORS = {
        "opensubtitles": "#4FC3F7",
        "subs.ro": "#FFD700",
    }
    LANGUAGE_OPTIONS = ["en", "ro", "es", "fr", "de", "it", "pt", "tr", "ar"]

    def __init__(self, parent: QWidget, player_getter: Callable[[], object], metadata: Dict[str, Any]):
        super().__init__(parent)
        self._player_getter = player_getter
        self._metadata = dict(metadata or {})
        self._search_worker: Optional[SubtitleSearchWorker] = None
        self._download_worker: Optional[SubtitleDownloadWorker] = None

        self.setWindowTitle("Search Online Subtitles")
        self.resize(760, 420)
        self._build_ui()
        self._start_search()

    def _build_ui(self):
        root = QVBoxLayout(self)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Language:"))
        self.language_combo = QComboBox(self)
        self.language_combo.setEditable(True)
        for lang in self.LANGUAGE_OPTIONS:
            self.language_combo.addItem(lang)
        preferred = self._preferred_languages()
        self.language_combo.setCurrentText(preferred[0])
        self.language_combo.currentTextChanged.connect(self._on_language_changed)
        top_row.addWidget(self.language_combo, 1)

        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self._start_search)
        top_row.addWidget(self.search_btn)
        root.addLayout(top_row)

        title = self._metadata.get("title") or "Unknown"
        self.title_label = QLabel(f"Title: {title}")
        root.addWidget(self.title_label)

        self.status_label = QLabel("Searching...")
        root.addWidget(self.status_label)

        self.results_list = QListWidget(self)
        self.results_list.itemClicked.connect(self._on_result_clicked)
        root.addWidget(self.results_list, 1)

    def _preferred_languages(self) -> List[str]:
        settings = QSettings("IPTVPlayer", "SubtitleSettings")
        return _normalize_subtitle_languages(settings.value("subtitle_languages", ["en"]))

    def _on_language_changed(self, value: str):
        lang = (value or "").strip().lower()
        if not lang:
            return
        settings = QSettings("IPTVPlayer", "SubtitleSettings")
        settings.setValue("subtitle_languages", [lang])

    def _start_search(self):
        if self._search_worker and self._search_worker.isRunning():
            return
        language = (self.language_combo.currentText() or "en").strip().lower() or "en"
        self.results_list.clear()
        self.status_label.setText("Searching...")
        self.search_btn.setEnabled(False)
        self._search_worker = SubtitleSearchWorker(self._metadata, language)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.start()

    def _on_search_finished(self, results, error: str):
        self.search_btn.setEnabled(True)
        if error:
            self.status_label.setText(f"Search failed: {error}")
            QMessageBox.warning(self, "Subtitle Search", f"Failed to search subtitles:\n{error}")
            return
        if not results:
            self.status_label.setText("No subtitle results found.")
            return
        self.status_label.setText(f"Found {len(results)} subtitle result(s). Click one to download.")
        for result in results:
            lang = str(result.get("language") or "").upper() or "??"
            release = str(result.get("release") or result.get("filename") or "Unknown release")
            downloads = result.get("download_count", 0)
            provider = str(result.get("provider") or "OpenSubtitles")
            text = f"[{lang}] {release} (↓{downloads})  {provider}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, result)
            color_key = provider.strip().lower()
            item.setForeground(QColor(self.PROVIDER_COLORS.get(color_key, self.PROVIDER_COLORS["opensubtitles"])))
            self.results_list.addItem(item)

    def _on_result_clicked(self, item: QListWidgetItem):
        result = item.data(Qt.ItemDataRole.UserRole) or {}
        file_id = result.get("file_id")
        if not file_id:
            QMessageBox.warning(self, "Subtitle Download", "Selected result does not contain a file_id.")
            return
        if self._download_worker and self._download_worker.isRunning():
            return
        self.status_label.setText("Downloading...")
        self._download_worker = SubtitleDownloadWorker(file_id)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.start()

    def _on_download_finished(self, subtitle_path: str, error: str):
        if error:
            self.status_label.setText(f"Download failed: {error}")
            QMessageBox.warning(self, "Subtitle Download", f"Failed to download subtitle:\n{error}")
            return
        player = self._player_getter() if self._player_getter else None
        if not player:
            QMessageBox.warning(self, "Subtitle Download", "Player is not available.")
            return
        try:
            player.sub_add(subtitle_path)
            self.status_label.setText("Subtitle loaded.")
            QMessageBox.information(self, "Subtitles", "Subtitle downloaded and loaded successfully.")
            self.accept()
        except Exception as exc:
            self.status_label.setText(f"Could not add subtitle: {exc}")
            QMessageBox.warning(self, "Subtitles", f"Subtitle downloaded but could not be loaded:\n{exc}")


class PlayerControlsOverlay(QWidget):
    HIDE_DELAY_MS = 5000
    POLL_INTERVAL_MS = 500
    MOUSE_POLL_INTERVAL_MS = 100
    ACCENT_COLOR = "#64b5f6"
    ASPECT_MODES = ("Fit", "Zoom", "Stretch", "16:9", "4:3")

    def __init__(
        self,
        host_widget: QWidget,
        player_getter: Callable[[], object],
        fullscreen_toggle_callback: Optional[Callable[[], None]] = None,
    ):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self._host_widget = host_widget
        self._player_getter = player_getter
        self._fullscreen_toggle_callback = fullscreen_toggle_callback
        self._fullscreen_dialog: Optional[QWidget] = None
        self._is_fullscreen = False
        self._is_dragging_seek = False
        self._aspect_index = 0
        self._known_duration = None
        self._title = "Stream"
        self._content_metadata: Dict[str, Any] = {"title": "Stream"}
        self._controls_visible = False
        self._event_sources = []
        self._app = QApplication.instance()
        self._app_filter_installed = False

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.add_event_source(self._host_widget)
        if self._app:
            self._app.installEventFilter(self)
            self._app_filter_installed = True

        self._build_ui()
        self._sync_geometry()

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_controls)

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_player_state)
        self._poll_timer.start(self.POLL_INTERVAL_MS)

        self._mouse_timer = QTimer(self)
        self._mouse_timer.timeout.connect(self._check_mouse_position)
        self._mouse_timer.start(self.MOUSE_POLL_INTERVAL_MS)
        self._last_cursor_pos = QCursor.pos()

        self.show_controls()

    def set_stream_title(self, title: str):
        self._title = title or "Stream"
        self._content_metadata["title"] = self._title
        self.title_label.setText(self._title)

    def set_content_metadata(
        self,
        title: Optional[str] = None,
        year=None,
        tmdb_id=None,
        imdb_id=None,
        season=None,
        episode=None,
        languages=None,
    ):
        metadata = dict(self._content_metadata or {})
        if title:
            metadata["title"] = title
            self.set_stream_title(title)
        metadata["year"] = year
        metadata["tmdb_id"] = tmdb_id
        metadata["imdb_id"] = imdb_id
        metadata["season"] = season
        metadata["episode"] = episode
        metadata["languages"] = _normalize_subtitle_languages(languages or metadata.get("languages") or ["en"])
        self._content_metadata = metadata

    def set_fullscreen(self, is_fullscreen: bool):
        self._is_fullscreen = bool(is_fullscreen)
        self.fullscreen_btn.setText("🡼" if self._is_fullscreen else "🔲")
        self._sync_geometry()

    def set_fullscreen_dialog(self, dialog: Optional[QWidget]):
        if self._fullscreen_dialog and self._fullscreen_dialog in self._event_sources:
            try:
                self._fullscreen_dialog.removeEventFilter(self)
            except RuntimeError:
                pass
            try:
                self._event_sources.remove(self._fullscreen_dialog)
            except ValueError:
                pass
        self._fullscreen_dialog = dialog
        if dialog:
            self.add_event_source(dialog)
        self._sync_geometry()

    def cleanup(self):
        for source in self._event_sources[:]:
            try:
                source.removeEventFilter(self)
            except Exception:
                pass
        self._event_sources.clear()
        self._hide_timer.stop()
        self._poll_timer.stop()
        self._mouse_timer.stop()
        if self._app and self._app_filter_installed:
            try:
                self._app.removeEventFilter(self)
            except RuntimeError:
                pass
        self.hide_controls(show_cursor=False)
        self.deleteLater()

    def add_event_source(self, widget: Optional[QWidget]):
        if widget is None or widget in self._event_sources:
            return
        try:
            widget.setMouseTracking(True)
            widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            widget.installEventFilter(self)
            self._event_sources.append(widget)
        except Exception:
            pass

    def eventFilter(self, watched, event):  # noqa: N802
        et = event.type()
        if watched in self._event_sources:
            if et in (
                QEvent.Type.Resize,
                QEvent.Type.Show,
                QEvent.Type.Move,
            ):
                self._sync_geometry()
        if et == QEvent.Type.KeyPress and self._should_handle_key_event(watched):
            if self._handle_key_event(event):
                return True
        return super().eventFilter(watched, event)

    def mouseMoveEvent(self, event):  # noqa: N802
        self.show_controls()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if self._controls_visible:
                self.hide_controls()
            else:
                self.show_controls()
        super().mousePressEvent(event)

    def show_controls(self):
        target = self._target_widget()
        if target is None or not target.isVisible():
            return
        self._sync_geometry()
        self._controls_visible = True
        self.show()
        self.raise_()
        self._host_widget.setCursor(Qt.CursorShape.ArrowCursor)
        self._hide_timer.start(self.HIDE_DELAY_MS)

    def hide_controls(self, show_cursor: bool = False):
        self._controls_visible = False
        self.hide()
        if show_cursor:
            self._host_widget.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self._host_widget.setCursor(QCursor(Qt.CursorShape.BlankCursor))

    def _sync_geometry(self):
        target = self._target_widget()
        if target is None or not target.isVisible():
            self.hide()
            return
        top_left = target.mapToGlobal(QPoint(0, 0))
        self.setGeometry(QRect(top_left, target.size()))
        if self.isVisible():
            self.raise_()

    def _build_ui(self):
        self.setStyleSheet(
            f"""
            QLabel, QPushButton {{
                color: #ffffff;
                font-size: 13px;
            }}
            QPushButton {{
                border: 1px solid rgba(255,255,255,0.22);
                border-radius: 4px;
                background: rgba(0,0,0,0.45);
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                border-color: {self.ACCENT_COLOR};
                background: rgba(100,181,246,0.25);
            }}
            QSlider::groove:horizontal {{
                background: rgba(255,255,255,0.3);
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {self.ACCENT_COLOR};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff;
                width: 10px;
                margin: -3px 0;
                border-radius: 5px;
            }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.top_bar = QWidget(self)
        self.top_bar.setStyleSheet("background: rgba(0,0,0,0.7); border-radius: 8px;")
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(12, 8, 12, 8)
        self.title_label = QLabel(self._title)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.subtitles_btn = QPushButton("CC")
        self.resolution_btn = QPushButton("📺")
        self.subtitles_btn.clicked.connect(self._open_subtitle_menu)
        self.resolution_btn.clicked.connect(self._open_resolution_menu)
        top_layout.addWidget(self.title_label)
        top_layout.addWidget(self.subtitles_btn)
        top_layout.addWidget(self.resolution_btn)
        root.addWidget(self.top_bar)

        root.addStretch()

        center_wrap = QWidget(self)
        center_layout = QHBoxLayout(center_wrap)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(18)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rewind_btn = QPushButton("⏪")
        self.play_pause_btn = QPushButton("▶")
        self.play_pause_btn.setStyleSheet(
            f"""
            QPushButton {{
                color: #ffffff;
                font-size: 30px;
                font-weight: bold;
                border: 2px solid rgba(255,255,255,0.5);
                border-radius: 28px;
                min-width: 56px;
                min-height: 56px;
                background: rgba(0,0,0,0.65);
            }}
            QPushButton:hover {{
                border-color: {self.ACCENT_COLOR};
                background: rgba(100,181,246,0.3);
            }}
            """
        )
        self.forward_btn = QPushButton("⏩")
        self.rewind_btn.clicked.connect(lambda: self._seek_by(-10))
        self.play_pause_btn.clicked.connect(self._toggle_pause)
        self.forward_btn.clicked.connect(lambda: self._seek_by(30))
        center_layout.addWidget(self.rewind_btn)
        center_layout.addWidget(self.play_pause_btn)
        center_layout.addWidget(self.forward_btn)
        root.addWidget(center_wrap)

        root.addStretch()

        self.bottom_bar = QWidget(self)
        self.bottom_bar.setStyleSheet("background: rgba(0,0,0,0.7); border-radius: 8px;")
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(12, 8, 12, 8)
        bottom_layout.setSpacing(10)

        self.live_label = QLabel("🔴 LIVE")
        self.current_time_label = QLabel("00:00:00")
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        self.seek_slider.sliderMoved.connect(self._on_seek_preview)
        self.duration_label = QLabel("00:00:00")
        self.volume_btn = QPushButton("🔊")
        self.volume_btn.clicked.connect(self._toggle_mute)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setFixedWidth(90)
        self.volume_slider.valueChanged.connect(self._set_volume)
        self.aspect_btn = QPushButton("⚙️ Fit")
        self.aspect_btn.clicked.connect(self._cycle_aspect_ratio)
        self.fullscreen_btn = QPushButton("🔲")
        self.fullscreen_btn.clicked.connect(self._toggle_fullscreen)

        bottom_layout.addWidget(self.live_label)
        bottom_layout.addWidget(self.current_time_label)
        bottom_layout.addWidget(self.seek_slider, 1)
        bottom_layout.addWidget(self.duration_label)
        bottom_layout.addWidget(self.volume_btn)
        bottom_layout.addWidget(self.volume_slider)
        bottom_layout.addWidget(self.aspect_btn)
        bottom_layout.addWidget(self.fullscreen_btn)
        root.addWidget(self.bottom_bar)

    def _player(self):
        try:
            return self._player_getter()
        except Exception:
            return None

    def _seek_by(self, seconds: int):
        player = self._player()
        if not player:
            return
        try:
            player.seek(seconds)
            self.show_controls()
        except Exception:
            pass

    def _toggle_pause(self):
        player = self._player()
        if not player:
            return
        try:
            player.pause = not bool(getattr(player, "pause", False))
            self.show_controls()
        except Exception:
            pass

    def _set_volume(self, value: int):
        player = self._player()
        if not player:
            return
        try:
            player.volume = int(max(0, min(100, value)))
            self.show_controls()
        except Exception:
            pass

    def _bump_volume(self, delta: int):
        player = self._player()
        if not player:
            return
        try:
            cur = int(float(getattr(player, "volume", 80)))
            nxt = int(max(0, min(100, cur + delta)))
            player.volume = nxt
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(nxt)
            self.volume_slider.blockSignals(False)
            self.show_controls()
        except Exception:
            pass

    def _toggle_mute(self):
        player = self._player()
        if not player:
            return
        try:
            player.mute = not bool(getattr(player, "mute", False))
            self.show_controls()
        except Exception:
            pass

    def _toggle_fullscreen(self):
        if self._fullscreen_toggle_callback:
            self._fullscreen_toggle_callback()
            self.show_controls()

    def _escape_fullscreen(self):
        if self._is_fullscreen and self._fullscreen_toggle_callback:
            self._fullscreen_toggle_callback()
            self.show_controls()

    def _on_seek_pressed(self):
        self._is_dragging_seek = True
        self.show_controls()

    def _on_seek_preview(self, value: int):
        if self._known_duration:
            pos = (float(value) / 1000.0) * float(self._known_duration)
            self.current_time_label.setText(_fmt_time(pos))

    def _on_seek_released(self):
        self._is_dragging_seek = False
        player = self._player()
        if not player or not self._known_duration:
            return
        try:
            target = (float(self.seek_slider.value()) / 1000.0) * float(self._known_duration)
            player.seek(target, reference="absolute")
            self.show_controls()
        except Exception:
            pass

    def _subtitle_tracks(self):
        player = self._player()
        if not player:
            return []
        tracks = getattr(player, "track_list", None) or []
        return [t for t in tracks if isinstance(t, dict) and t.get("type") == "sub"]

    def _video_tracks(self):
        player = self._player()
        if not player:
            return []
        tracks = getattr(player, "track_list", None) or []
        return [t for t in tracks if isinstance(t, dict) and t.get("type") == "video"]

    def _open_subtitle_menu(self):
        player = self._player()
        if not player:
            return
        menu = QMenu(self)
        off_action = menu.addAction("Off")
        off_action.triggered.connect(lambda: setattr(player, "sub", "no"))
        menu.addSeparator()
        for track in self._subtitle_tracks():
            tid = track.get("id")
            title = _track_value(track, "title", "lang") or f"Subtitle {tid}"
            act = menu.addAction(str(title))
            act.setCheckable(True)
            act.setChecked(bool(track.get("selected")))
            act.triggered.connect(lambda checked=False, track_id=tid: setattr(player, "sub", track_id))
        menu.addSeparator()
        search_online = menu.addAction("🔍 Search Online Subtitles...")
        search_online.triggered.connect(self._open_online_subtitle_search_dialog)
        load_external = menu.addAction("Load external subtitle (.srt)…")
        load_external.triggered.connect(self._load_external_subtitle)
        menu.exec(self.subtitles_btn.mapToGlobal(QPoint(0, self.subtitles_btn.height())))

    def _open_online_subtitle_search_dialog(self):
        player = self._player()
        if not player:
            return
        metadata = dict(self._content_metadata or {})
        if not metadata.get("title"):
            metadata["title"] = self._title or "Stream"
        metadata["languages"] = _normalize_subtitle_languages(
            metadata.get("languages") or QSettings("IPTVPlayer", "SubtitleSettings").value("subtitle_languages", ["en"])
        )
        dialog = SubtitleSearchDialog(self, player_getter=self._player, metadata=metadata)
        dialog.exec()

    def _open_resolution_menu(self):
        player = self._player()
        if not player:
            return
        menu = QMenu(self)
        tracks = self._video_tracks()
        url = str(getattr(player, "path", "") or "")
        is_hls = ".m3u8" in url.lower()
        if is_hls and tracks:
            for track in tracks:
                tid = track.get("id")
                w = _track_value(track, "demux_w", "demux-w", "w", "width")
                h = _track_value(track, "demux_h", "demux-h", "h", "height")
                title = _track_value(track, "title") or (f"{w}x{h}" if w and h else f"Track {tid}")
                act = menu.addAction(str(title))
                act.setCheckable(True)
                act.setChecked(bool(track.get("selected")))
                act.triggered.connect(lambda checked=False, track_id=tid: setattr(player, "vid", track_id))
        else:
            info = self._current_resolution_info(tracks)
            action = menu.addAction(info)
            action.setEnabled(False)
        menu.exec(self.resolution_btn.mapToGlobal(QPoint(0, self.resolution_btn.height())))

    def _load_external_subtitle(self):
        player = self._player()
        if not player:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select subtitle file",
            "",
            "Subtitle files (*.srt *.ass *.ssa);;All files (*)",
        )
        if not path:
            return
        try:
            player.sub_add(path)
        except Exception:
            pass

    def _current_resolution_info(self, tracks) -> str:
        selected = next((t for t in tracks if t.get("selected")), None)
        if not selected:
            return "Resolution: Unknown"
        w = _track_value(selected, "demux_w", "demux-w", "w", "width")
        h = _track_value(selected, "demux_h", "demux-h", "h", "height")
        if w and h:
            return f"Resolution: {w}x{h}"
        return f"Resolution: {selected.get('title') or 'Unknown'}"

    def _cycle_aspect_ratio(self):
        player = self._player()
        if not player:
            return
        self._aspect_index = (self._aspect_index + 1) % len(self.ASPECT_MODES)
        mode = self.ASPECT_MODES[self._aspect_index]
        try:
            if mode == "Fit":
                player.keepaspect = True
                player.video_zoom = 0.0
                player.video_aspect_override = ""
            elif mode == "Zoom":
                player.keepaspect = True
                player.video_aspect_override = ""
                player.video_zoom = 0.2
            elif mode == "Stretch":
                player.video_zoom = 0.0
                player.video_aspect_override = ""
                player.keepaspect = False
            elif mode in ("16:9", "4:3"):
                player.keepaspect = True
                player.video_zoom = 0.0
                player.video_aspect_override = mode
        except Exception:
            pass
        self.aspect_btn.setText(f"⚙️ {mode}")
        self.show_controls()

    def _poll_player_state(self):
        player = self._player()
        if not player:
            return

        paused = bool(getattr(player, "pause", False))
        self.play_pause_btn.setText("⏸" if not paused else "▶")

        muted = bool(getattr(player, "mute", False))
        self.volume_btn.setText("🔇" if muted else "🔊")

        try:
            volume = int(float(getattr(player, "volume", 80)))
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(max(0, min(100, volume)))
            self.volume_slider.blockSignals(False)
        except Exception:
            pass

        time_pos = getattr(player, "time_pos", None)
        duration = getattr(player, "duration", None)
        try:
            self.current_time_label.setText(_fmt_time(time_pos or 0))
            duration_val = float(duration) if duration is not None else 0.0
        except Exception:
            duration_val = 0.0

        live = duration_val <= 0.0
        self.live_label.setVisible(live)
        self.seek_slider.setVisible(not live)
        self.duration_label.setVisible(not live)
        if not live:
            self._known_duration = duration_val
            self.duration_label.setText(_fmt_time(duration_val))
            if not self._is_dragging_seek and duration_val > 0:
                slider_value = int((float(time_pos or 0.0) / duration_val) * 1000.0)
                self.seek_slider.setValue(max(0, min(1000, slider_value)))

        tracks = self._video_tracks()
        self.resolution_btn.setText("📺")
        if tracks:
            self.resolution_btn.setText("HD")

    def _target_widget(self) -> Optional[QWidget]:
        if self._is_fullscreen and self._fullscreen_dialog and self._fullscreen_dialog.isVisible():
            return self._fullscreen_dialog
        return self._host_widget

    def _target_global_rect(self) -> QRect:
        target = self._target_widget()
        if target is None:
            return QRect()
        return QRect(target.mapToGlobal(QPoint(0, 0)), target.size())

    def _check_mouse_position(self):
        pos = QCursor.pos()
        if pos == self._last_cursor_pos:
            return
        self._last_cursor_pos = pos
        target = self._target_widget()
        if target is None or not target.isVisible():
            return
        if self._target_global_rect().contains(pos):
            self.show_controls()

    def _should_handle_key_event(self, watched) -> bool:
        if watched is self or watched is self._host_widget or (
            self._fullscreen_dialog and watched is self._fullscreen_dialog
        ):
            return True
        if isinstance(watched, QWidget):
            if self.isAncestorOf(watched):
                return True
            if self._host_widget and self._host_widget.isAncestorOf(watched):
                return True
            if self._fullscreen_dialog and self._fullscreen_dialog.isAncestorOf(watched):
                return True
        return False

    def _handle_key_event(self, event) -> bool:
        key = event.key()
        if key == Qt.Key.Key_Space:
            self._toggle_pause()
            return True
        if key == Qt.Key.Key_Left:
            self._seek_by(-10)
            return True
        if key == Qt.Key.Key_Right:
            self._seek_by(30)
            return True
        if key == Qt.Key.Key_Up:
            self._bump_volume(5)
            return True
        if key == Qt.Key.Key_Down:
            self._bump_volume(-5)
            return True
        if key == Qt.Key.Key_M:
            self._toggle_mute()
            return True
        if key in (Qt.Key.Key_F, Qt.Key.Key_F11):
            self._toggle_fullscreen()
            return True
        if key == Qt.Key.Key_Escape and self._is_fullscreen:
            self._escape_fullscreen()
            return True
        return False
