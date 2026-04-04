/**
 * Primary fullscreen video player Activity.
 *
 * Uses ExoPlayer (Media3) with a SurfaceView for zero-copy hardware compositor
 * rendering — the same path used by XCIPTV and other high-performance IPTV
 * players. Device type is detected at runtime so that phones receive the full
 * feature set (tunneling, audio offload) while TV boxes / Amlogic / Fire Stick
 * devices get a conservative configuration that avoids broken firmware paths.
 */
package com.x87player.x87_mobile

import android.app.Activity
import android.app.AlertDialog
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.TrackSelectionOverride
import androidx.media3.common.Tracks
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView

class NativePlayerActivity : Activity() {

    companion object {
        const val EXTRA_URL = "url"
        const val EXTRA_TITLE = "title"
        const val EXTRA_CONTENT_TYPE = "contentType"

        private const val CONTROLS_HIDE_DELAY_MS = 2_000L
        private const val PREFS_NAME = "player_prefs"
        private const val PREF_RESIZE_MODE = "resize_mode"
        private val RESIZE_MODES = listOf(
            AspectRatioFrameLayout.RESIZE_MODE_FIT to "Fit",
            AspectRatioFrameLayout.RESIZE_MODE_FIXED_WIDTH to "Width",
            AspectRatioFrameLayout.RESIZE_MODE_FIXED_HEIGHT to "Height",
            AspectRatioFrameLayout.RESIZE_MODE_FILL to "Fill",
            AspectRatioFrameLayout.RESIZE_MODE_ZOOM to "Zoom",
        )
    }

    private lateinit var player: ExoPlayer
    private lateinit var playerView: PlayerView
    private lateinit var controlsOverlay: View
    private lateinit var titleTextView: TextView
    private lateinit var playPauseIcon: android.widget.ImageView
    private lateinit var resizeModeLabel: TextView

    private val mainHandler = Handler(Looper.getMainLooper())
    private var controlsVisible = true
    private var currentResizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT

    private val hideControlsRunnable = Runnable { hideControls() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Fullscreen, landscape, keep screen on, hardware-accelerated
        window.addFlags(
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        )

        setContentView(buildContentView())

        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        currentResizeMode = prefs.getInt(PREF_RESIZE_MODE, AspectRatioFrameLayout.RESIZE_MODE_FIT)
        playerView.resizeMode = currentResizeMode
        resizeModeLabel.text = RESIZE_MODES.firstOrNull { it.first == currentResizeMode }?.second ?: "Fit"

        val url = intent.getStringExtra(EXTRA_URL) ?: run {
            Toast.makeText(this, "No stream URL provided", Toast.LENGTH_SHORT).show()
            setResult(RESULT_CANCELED)
            finish()
            return
        }
        val title = intent.getStringExtra(EXTRA_TITLE) ?: ""

        titleTextView.text = title

        val isTvDevice = ExoPlayerFactory.isTvOrAmlogicDevice(this)
        android.util.Log.i("NativePlayerActivity",
            "Device config: isTv=$isTvDevice manufacturer=${android.os.Build.MANUFACTURER} " +
            "model=${android.os.Build.MODEL} hardware=${android.os.Build.HARDWARE}")

        try {
            player = ExoPlayerFactory.build(this, isTvDevice).also { exo ->
                playerView.player = exo
                exo.setMediaItem(MediaItem.fromUri(url))
                exo.prepare()
                exo.playWhenReady = true
                exo.addListener(object : Player.Listener {
                    override fun onPlaybackStateChanged(state: Int) {
                        if (state == Player.STATE_ENDED) {
                            setResult(RESULT_OK)
                            finish()
                        }
                    }

                    override fun onIsPlayingChanged(isPlaying: Boolean) {
                        updatePlayPauseIcon(isPlaying)
                    }

                    override fun onPlayerError(error: PlaybackException) {
                        Toast.makeText(
                            this@NativePlayerActivity,
                            "Playback error: ${error.message}",
                            Toast.LENGTH_LONG
                        ).show()
                        setResult(RESULT_CANCELED)
                        finish()
                    }
                })
            }
        } catch (e: Exception) {
            Toast.makeText(this, "Failed to initialize player: ${e.message}", Toast.LENGTH_LONG).show()
            setResult(RESULT_CANCELED)
            finish()
            return
        }

        scheduleHideControls()
    }

    override fun onDestroy() {
        mainHandler.removeCallbacks(hideControlsRunnable)
        if (::player.isInitialized) {
            player.release()
        }
        super.onDestroy()
    }

    // ── Key / D-pad handling (Fire Stick remote) ──────────────────────────────

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        return when (keyCode) {
            KeyEvent.KEYCODE_DPAD_CENTER -> {
                // On D-pad: first tap shows controls, second tap toggles play/pause
                if (!controlsVisible) {
                    showControls()
                } else {
                    togglePlayPause()
                }
                true
            }
            KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE,
            KeyEvent.KEYCODE_MEDIA_PLAY,
            KeyEvent.KEYCODE_MEDIA_PAUSE -> {
                togglePlayPause()
                showControls()
                true
            }
            KeyEvent.KEYCODE_BACK,
            KeyEvent.KEYCODE_ESCAPE -> {
                setResult(RESULT_CANCELED)
                finish()
                true
            }
            KeyEvent.KEYCODE_MEDIA_STOP -> {
                setResult(RESULT_OK)
                finish()
                true
            }
            else -> {
                // Any other key shows controls
                showControls()
                super.onKeyDown(keyCode, event)
            }
        }
    }

    // ── Controls visibility ───────────────────────────────────────────────────

    private fun showControls() {
        controlsOverlay.visibility = View.VISIBLE
        controlsVisible = true
        scheduleHideControls()
    }

    private fun hideControls() {
        controlsOverlay.visibility = View.GONE
        controlsVisible = false
    }

    private fun scheduleHideControls() {
        mainHandler.removeCallbacks(hideControlsRunnable)
        mainHandler.postDelayed(hideControlsRunnable, CONTROLS_HIDE_DELAY_MS)
    }

    private fun togglePlayPause() {
        if (::player.isInitialized) {
            if (player.isPlaying) {
                player.pause()
            } else {
                player.play()
            }
        }
        // Only reschedule the auto-hide timer — don't force-show controls if
        // they're already hidden (e.g. user tapped the video area).
        if (controlsVisible) {
            scheduleHideControls()
        }
    }

    private fun updatePlayPauseIcon(isPlaying: Boolean) {
        playPauseIcon.setImageResource(
            if (isPlaying) android.R.drawable.ic_media_pause
            else android.R.drawable.ic_media_play
        )
    }

    // ── View construction (programmatic to avoid layout XML dependency) ───────

    @Suppress("DEPRECATION")
    private fun buildContentView(): View {
        val frame = android.widget.FrameLayout(this)
        frame.setBackgroundColor(android.graphics.Color.BLACK)

        // PlayerView (Media3) — uses SurfaceView internally for zero-copy rendering
        playerView = PlayerView(this).apply {
            useController = false   // We draw our own overlay controls
            layoutParams = android.widget.FrameLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                android.view.ViewGroup.LayoutParams.MATCH_PARENT
            )
        }
        frame.addView(playerView)

        // Invisible touch-catcher layer — sits between the PlayerView and the
        // controls overlay. When controls are hidden this is the topmost
        // clickable surface, so tapping it shows controls. When controls are
        // visible, the overlay's own buttons sit above this layer and receive
        // their clicks normally.
        val touchCatcher = View(this).apply {
            layoutParams = android.widget.FrameLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                android.view.ViewGroup.LayoutParams.MATCH_PARENT
            )
            isClickable = true
            isFocusable = false
            setOnClickListener {
                // The touchCatcher is below the overlay in z-order; it only
                // receives taps when the overlay is GONE (controls hidden).
                showControls()
            }
        }
        frame.addView(touchCatcher)

        // Overlay container
        controlsOverlay = buildControlsOverlay()
        frame.addView(controlsOverlay)

        return frame
    }

    private fun buildControlsOverlay(): View {
        // Bottom bar: play/pause icon + title + resize/settings/CC buttons
        val bottomBar = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.HORIZONTAL
            setBackgroundColor(0xCC000000.toInt())
            val hPad = dpToPx(12)
            val vPad = dpToPx(10)
            setPadding(hPad, vPad, hPad, vPad)
            gravity = android.view.Gravity.CENTER_VERTICAL
            layoutParams = android.widget.FrameLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                android.view.ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                gravity = android.view.Gravity.BOTTOM
            }
        }

        // Play/pause indicator icon (small, left side)
        playPauseIcon = android.widget.ImageView(this).apply {
            setImageResource(android.R.drawable.ic_media_pause)
            setColorFilter(android.graphics.Color.WHITE)
            val size = dpToPx(16)
            layoutParams = android.widget.LinearLayout.LayoutParams(size, size).apply {
                marginEnd = dpToPx(8)
                gravity = android.view.Gravity.CENTER_VERTICAL
            }
        }
        bottomBar.addView(playPauseIcon)

        // Title (fills remaining space)
        titleTextView = TextView(this).apply {
            setTextColor(android.graphics.Color.WHITE)
            textSize = 14f
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
            layoutParams = android.widget.LinearLayout.LayoutParams(
                0,
                android.view.ViewGroup.LayoutParams.WRAP_CONTENT,
                1f
            )
        }
        bottomBar.addView(titleTextView)

        val btnSize = dpToPx(36)

        // Resize mode button
        resizeModeLabel = TextView(this).apply {
            text = "Fit"
            setTextColor(android.graphics.Color.WHITE)
            textSize = 12f
            setPadding(dpToPx(4), dpToPx(4), dpToPx(4), dpToPx(4))
            background = makeFocusDrawable()
            layoutParams = android.widget.LinearLayout.LayoutParams(btnSize, btnSize).apply {
                gravity = android.view.Gravity.CENTER_VERTICAL
            }
            gravity = android.view.Gravity.CENTER
            setOnClickListener {
                cycleResizeMode(this)
                scheduleHideControls()
            }
            isClickable = true
            isFocusable = true
            isFocusableInTouchMode = true
        }
        bottomBar.addView(resizeModeLabel)

        // Settings (audio/video tracks) button
        val settingsButton = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_menu_preferences)
            background = makeFocusDrawable()
            setColorFilter(android.graphics.Color.WHITE)
            layoutParams = android.widget.LinearLayout.LayoutParams(btnSize, btnSize).apply {
                gravity = android.view.Gravity.CENTER_VERTICAL
            }
            contentDescription = "Settings"
            setOnClickListener {
                showSettingsDialog()
                scheduleHideControls()
            }
            isFocusable = true
            isFocusableInTouchMode = true
        }
        bottomBar.addView(settingsButton)

        // Subtitles (CC) button
        val ccButton = TextView(this).apply {
            text = "CC"
            setTextColor(android.graphics.Color.WHITE)
            textSize = 14f
            setPadding(dpToPx(4), dpToPx(4), dpToPx(4), dpToPx(4))
            background = makeFocusDrawable()
            layoutParams = android.widget.LinearLayout.LayoutParams(btnSize, btnSize).apply {
                gravity = android.view.Gravity.CENTER_VERTICAL
            }
            gravity = android.view.Gravity.CENTER
            contentDescription = "Subtitles"
            setOnClickListener {
                showSubtitlesDialog()
                scheduleHideControls()
            }
            isClickable = true
            isFocusable = true
            isFocusableInTouchMode = true
        }
        bottomBar.addView(ccButton)

        return bottomBar
    }

    // ── Track / resize helpers ────────────────────────────────────────────────

    private fun getTracksOfType(type: Int): List<Pair<Tracks.Group, Int>> {
        val result = mutableListOf<Pair<Tracks.Group, Int>>()
        for (group in player.currentTracks.groups) {
            if (group.type == type) {
                for (i in 0 until group.length) {
                    if (group.isTrackSupported(i)) {
                        result.add(group to i)
                    }
                }
            }
        }
        return result
    }

    private fun cycleResizeMode(label: TextView) {
        val currentIndex = RESIZE_MODES.indexOfFirst { it.first == currentResizeMode }
        val next = RESIZE_MODES[(currentIndex + 1) % RESIZE_MODES.size]
        currentResizeMode = next.first
        playerView.resizeMode = currentResizeMode
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .edit()
            .putInt(PREF_RESIZE_MODE, currentResizeMode)
            .apply()
        label.text = next.second
        Toast.makeText(this, next.second, Toast.LENGTH_SHORT).show()
    }

    private fun showSubtitlesDialog() {
        val tracks = getTracksOfType(C.TRACK_TYPE_TEXT)
        if (tracks.isEmpty()) {
            Toast.makeText(this, "No subtitles available", Toast.LENGTH_SHORT).show()
            return
        }

        val labels = mutableListOf("Off")
        for ((group, index) in tracks) {
            val format = group.getTrackFormat(index)
            val label = format.label
                ?: format.language
                ?: "Track ${labels.size}"
            labels.add(label)
        }

        AlertDialog.Builder(this)
            .setTitle("Subtitles")
            .setItems(labels.toTypedArray()) { _, which ->
                if (which == 0) {
                    player.trackSelectionParameters = player.trackSelectionParameters
                        .buildUpon()
                        .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, true)
                        .build()
                } else {
                    val (group, index) = tracks[which - 1]
                    player.trackSelectionParameters = player.trackSelectionParameters
                        .buildUpon()
                        .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, false)
                        .setOverrideForType(TrackSelectionOverride(group.mediaTrackGroup, listOf(index)))
                        .build()
                }
            }
            .show()
    }

    private fun showSettingsDialog() {
        val videoTracks = getTracksOfType(C.TRACK_TYPE_VIDEO)
        val audioTracks = getTracksOfType(C.TRACK_TYPE_AUDIO)

        val items = mutableListOf<String>()
        val actions = mutableListOf<() -> Unit>()

        items.add("── Video ──")
        actions.add({})
        if (videoTracks.isEmpty()) {
            items.add("  (none)")
            actions.add({})
        } else {
            for ((group, index) in videoTracks) {
                val format = group.getTrackFormat(index)
                val res = "${format.width}x${format.height}"
                val bitrate = if (format.bitrate > 0) " @ ${format.bitrate / 1000}kbps" else ""
                items.add("  $res$bitrate")
                actions.add {
                    player.trackSelectionParameters = player.trackSelectionParameters
                        .buildUpon()
                        .setOverrideForType(TrackSelectionOverride(group.mediaTrackGroup, listOf(index)))
                        .build()
                }
            }
        }

        items.add("── Audio ──")
        actions.add({})
        if (audioTracks.isEmpty()) {
            items.add("  (none)")
            actions.add({})
        } else {
            for ((group, index) in audioTracks) {
                val format = group.getTrackFormat(index)
                val lang = format.label ?: format.language ?: "Unknown"
                val codec = format.codecs ?: "Unknown"
                val channels = when (format.channelCount) {
                    1 -> "Mono"
                    2 -> "Stereo"
                    6 -> "5.1"
                    8 -> "7.1"
                    else -> if (format.channelCount > 0) "${format.channelCount}ch" else "Unknown"
                }
                items.add("  $lang - $codec - $channels")
                actions.add {
                    player.trackSelectionParameters = player.trackSelectionParameters
                        .buildUpon()
                        .setOverrideForType(TrackSelectionOverride(group.mediaTrackGroup, listOf(index)))
                        .build()
                }
            }
        }

        AlertDialog.Builder(this)
            .setTitle("Settings")
            .setItems(items.toTypedArray()) { _, which ->
                // Header items (Video/Audio section labels) have no-op actions;
                // only track items perform a selection.
                actions[which].invoke()
            }
            .show()
    }

    // ── Device detection ──────────────────────────────────────────────────────

    private fun makeFocusDrawable(): android.graphics.drawable.StateListDrawable {
        val pressed = android.graphics.drawable.GradientDrawable().apply {
            setColor(0x993498DB.toInt())
            cornerRadius = dpToPx(4).toFloat()
        }
        val focused = android.graphics.drawable.GradientDrawable().apply {
            setColor(0x663498DB.toInt())
            cornerRadius = dpToPx(4).toFloat()
        }
        val normal = android.graphics.drawable.ColorDrawable(android.graphics.Color.TRANSPARENT)
        return android.graphics.drawable.StateListDrawable().apply {
            addState(intArrayOf(android.R.attr.state_pressed), pressed)
            addState(intArrayOf(android.R.attr.state_focused), focused)
            addState(intArrayOf(), normal)
        }
    }

    private fun dpToPx(dp: Int): Int {
        val density = resources.displayMetrics.density
        return (dp * density + 0.5f).toInt()
    }
}
