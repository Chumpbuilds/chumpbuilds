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
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.ImageButton
import android.widget.SeekBar
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

        private const val CONTROLS_HIDE_DELAY_MS = 5_000L
        private const val SEEK_BAR_UPDATE_INTERVAL_MS = 500L
        private const val SKIP_REWIND_MS = 30_000L
        private const val SKIP_FORWARD_MS = 30_000L
        private const val PREFS_NAME = "player_prefs"
        private const val PREF_RESIZE_MODE = "resize_mode"
        private const val SEEK_BAR_FOCUS_BACKGROUND_COLOR: Int = 0x333498DB
        private const val SEEK_BAR_SCRUB_INCREMENT = 10   // 1% per D-pad press (out of max=1000)
        private const val SEEK_COMMIT_DELAY_MS = 1_000L   // commit seek 1 second after last scrub
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
    private lateinit var playPauseButton: ImageButton
    private lateinit var seekBar: SeekBar
    private lateinit var currentTimeText: TextView
    private lateinit var durationText: TextView
    private lateinit var liveIndicator: TextView
    private lateinit var seekBarRow: android.widget.LinearLayout

    private val mainHandler = Handler(Looper.getMainLooper())
    private var controlsVisible = true
    private var currentResizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT
    private var isUserSeekingBar = false

    private val hideControlsRunnable = Runnable { hideControls() }
    private val seekCommitRunnable = Runnable { commitSeek() }

    private val seekBarUpdateRunnable = object : Runnable {
        override fun run() {
            updateSeekBar()
            mainHandler.postDelayed(this, SEEK_BAR_UPDATE_INTERVAL_MS)
        }
    }

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

                    override fun onTracksChanged(tracks: Tracks) {
                        var hasAudio = false
                        var hasUnsupportedAudio = false
                        val unsupportedCodecs = mutableListOf<String>()

                        for (group in tracks.groups) {
                            if (group.type == C.TRACK_TYPE_AUDIO) {
                                for (i in 0 until group.length) {
                                    val format = group.getTrackFormat(i)
                                    val selected = group.isTrackSelected(i)
                                    val supported = group.isTrackSupported(i)
                                    val codec = format.codecs ?: format.sampleMimeType ?: "unknown"
                                    android.util.Log.i("NativePlayerActivity",
                                        "Audio track [$i]: codec=$codec " +
                                        "channels=${format.channelCount} " +
                                        "sampleRate=${format.sampleRate} " +
                                        "lang=${format.language ?: "?"} " +
                                        "selected=$selected supported=$supported")
                                    if (selected) {
                                        hasAudio = true
                                        if (!supported) {
                                            hasUnsupportedAudio = true
                                            unsupportedCodecs.add(codec)
                                        }
                                    }
                                }
                            }
                        }

                        // Auto-launch VLC when ExoPlayer cannot decode the selected
                        // audio track (e.g. EAC3 on Amlogic boxes with no Dolby decoder).
                        if (hasAudio && hasUnsupportedAudio) {
                            android.util.Log.w("NativePlayerActivity",
                                "Unsupported audio codec(s): ${unsupportedCodecs.joinToString()} — launching VLC")
                            launchVlcFallback()
                        }
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
        mainHandler.post(seekBarUpdateRunnable)
    }

    override fun onDestroy() {
        mainHandler.removeCallbacks(hideControlsRunnable)
        mainHandler.removeCallbacks(seekBarUpdateRunnable)
        mainHandler.removeCallbacks(seekCommitRunnable)
        if (::player.isInitialized) {
            player.release()
        }
        super.onDestroy()
    }

    // ── VLC fallback ──────────────────────────────────────────────────────────

    /**
     * Stops ExoPlayer and launches VLC (or any installed video player) with the
     * same stream URL. Called automatically when [onTracksChanged] detects that
     * the selected audio track cannot be decoded on this device.
     */
    private fun launchVlcFallback() {
        val url = intent.getStringExtra(EXTRA_URL) ?: return
        if (::player.isInitialized) player.stop()

        // Try VLC directly first, then fall back to any video app.
        val vlcIntent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
            setDataAndType(Uri.parse(url), "video/*")
            setPackage("org.videolan.vlc")
        }
        try {
            startActivity(vlcIntent)
        } catch (_: Exception) {
            val genericIntent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                setDataAndType(Uri.parse(url), "video/*")
            }
            try {
                startActivity(genericIntent)
            } catch (e2: Exception) {
                android.util.Log.e("NativePlayerActivity", "VLC fallback failed: ${e2.message}")
            }
        }
        setResult(RESULT_CANCELED)
        finish()
    }

    // ── Key / D-pad handling (Fire Stick remote) ──────────────────────────────

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        return when (keyCode) {
            KeyEvent.KEYCODE_DPAD_CENTER -> {
                if (!controlsVisible) {
                    showControls()
                    true
                } else {
                    // Let the focused button handle the click
                    super.onKeyDown(keyCode, event)
                }
            }
            KeyEvent.KEYCODE_DPAD_LEFT -> {
                if (!controlsVisible) {
                    showControls()
                    skipRewind()
                    true
                } else if (seekBar.hasFocus()) {
                    scrubSeekBar(-SEEK_BAR_SCRUB_INCREMENT)
                    true
                } else {
                    // Let Android's focus navigation move between buttons
                    super.onKeyDown(keyCode, event)
                }
            }
            KeyEvent.KEYCODE_DPAD_RIGHT -> {
                if (!controlsVisible) {
                    showControls()
                    skipForward()
                    true
                } else if (seekBar.hasFocus()) {
                    scrubSeekBar(SEEK_BAR_SCRUB_INCREMENT)
                    true
                } else {
                    // Let Android's focus navigation move between buttons
                    super.onKeyDown(keyCode, event)
                }
            }
            KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE,
            KeyEvent.KEYCODE_MEDIA_PLAY,
            KeyEvent.KEYCODE_MEDIA_PAUSE -> {
                togglePlayPause()
                showControls()
                true
            }
            KeyEvent.KEYCODE_MEDIA_REWIND,
            KeyEvent.KEYCODE_MEDIA_SKIP_BACKWARD,
            KeyEvent.KEYCODE_MEDIA_STEP_BACKWARD -> {
                skipRewind()
                showControls()
                true
            }
            KeyEvent.KEYCODE_MEDIA_FAST_FORWARD,
            KeyEvent.KEYCODE_MEDIA_SKIP_FORWARD,
            KeyEvent.KEYCODE_MEDIA_STEP_FORWARD -> {
                skipForward()
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
            KeyEvent.KEYCODE_DPAD_UP, KeyEvent.KEYCODE_DPAD_DOWN -> {
                if (!controlsVisible) {
                    showControls()
                    true
                } else {
                    // Pass through to Android's focus system without stealing focus
                    scheduleHideControls()
                    super.onKeyDown(keyCode, event)
                }
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
        val wasHidden = !controlsVisible
        controlsOverlay.visibility = View.VISIBLE
        controlsVisible = true
        // Only grab focus on play/pause when controls first appear,
        // not when they're already visible (which would steal focus from seek bar, settings, etc.)
        if (wasHidden && ::playPauseButton.isInitialized) {
            playPauseButton.requestFocus()
        }
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
        if (::playPauseButton.isInitialized) {
            playPauseButton.setImageResource(
                if (isPlaying) android.R.drawable.ic_media_pause
                else android.R.drawable.ic_media_play
            )
        }
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
        // Root: FrameLayout that covers the whole screen so we can place the
        // center transport controls and the bottom bar independently.
        val root = android.widget.FrameLayout(this).apply {
            layoutParams = android.widget.FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }

        // ── Center transport controls ─────────────────────────────────────────
        // Rewind 10s | Play/Pause (large) | Forward 30s
        val transportRow = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.CENTER
            layoutParams = android.widget.FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                gravity = android.view.Gravity.CENTER
            }
        }

        val largeBtnSize = dpToPx(56)
        val transportBtnMargin = dpToPx(24)

        // Rewind 30 s
        val rewindButton = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_media_previous)
            setColorFilter(android.graphics.Color.WHITE)
            background = makeFocusDrawable()
            layoutParams = android.widget.LinearLayout.LayoutParams(largeBtnSize, largeBtnSize).apply {
                marginEnd = transportBtnMargin
                gravity = android.view.Gravity.CENTER_VERTICAL
            }
            contentDescription = "Rewind 30 seconds"
            setOnClickListener {
                skipRewind()
                scheduleHideControls()
            }
            isClickable = true
            isFocusable = true
        }
        transportRow.addView(rewindButton)

        // Play / Pause (large, centered, default focus)
        val playBtnSize = dpToPx(72)
        playPauseButton = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_media_pause)
            setColorFilter(android.graphics.Color.WHITE)
            background = makeFocusDrawable()
            layoutParams = android.widget.LinearLayout.LayoutParams(playBtnSize, playBtnSize).apply {
                gravity = android.view.Gravity.CENTER_VERTICAL
            }
            contentDescription = "Play/Pause"
            setOnClickListener {
                togglePlayPause()
            }
            isClickable = true
            isFocusable = true
        }
        transportRow.addView(playPauseButton)

        // Forward 30 s
        val forwardButton = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_media_next)
            setColorFilter(android.graphics.Color.WHITE)
            background = makeFocusDrawable()
            layoutParams = android.widget.LinearLayout.LayoutParams(largeBtnSize, largeBtnSize).apply {
                marginStart = transportBtnMargin
                gravity = android.view.Gravity.CENTER_VERTICAL
            }
            contentDescription = "Forward 30 seconds"
            setOnClickListener {
                skipForward()
                scheduleHideControls()
            }
            isClickable = true
            isFocusable = true
        }
        transportRow.addView(forwardButton)

        // Assign stable IDs and wire up explicit D-pad focus navigation order
        rewindButton.id = View.generateViewId()
        playPauseButton.id = View.generateViewId()
        forwardButton.id = View.generateViewId()

        rewindButton.nextFocusRightId = playPauseButton.id
        playPauseButton.nextFocusLeftId = rewindButton.id
        playPauseButton.nextFocusRightId = forwardButton.id
        forwardButton.nextFocusLeftId = playPauseButton.id

        // Vertical: transport row → seek bar (set after seekBar.id is assigned below)
        // (wired after all views are built — see end of buildControlsOverlay)

        root.addView(transportRow)

        // ── Bottom bar ────────────────────────────────────────────────────────
        val bottomBar = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setBackgroundColor(0xCC000000.toInt())
            val hPad = dpToPx(12)
            val vPad = dpToPx(8)
            setPadding(hPad, vPad, hPad, vPad)
            layoutParams = android.widget.FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                gravity = android.view.Gravity.BOTTOM
            }
        }

        // Seek bar row: currentTime | SeekBar | duration
        seekBarRow = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.CENTER_VERTICAL
            layoutParams = android.widget.LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                bottomMargin = dpToPx(4)
            }
        }

        currentTimeText = TextView(this).apply {
            setTextColor(android.graphics.Color.WHITE)
            textSize = 12f
            text = "00:00:00"
            layoutParams = android.widget.LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                marginEnd = dpToPx(8)
            }
        }
        seekBarRow.addView(currentTimeText)

        seekBar = SeekBar(this).apply {
            layoutParams = android.widget.LinearLayout.LayoutParams(
                0,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                1f
            )
            max = 1000
            id = View.generateViewId()
            keyProgressIncrement = 10  // 1% per D-pad press
            // Blue accent thumb and progress
            progressDrawable = buildSeekBarDrawable()
            thumb = buildSeekBarThumb()
            isClickable = true
            isFocusable = true
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(bar: SeekBar?, progress: Int, fromUser: Boolean) {
                    if (fromUser && ::player.isInitialized) {
                        val duration = player.duration
                        if (duration > 0 && duration != C.TIME_UNSET) {
                            val seekPos = duration * progress / 1000L
                            currentTimeText.text = formatMs(seekPos)
                        }
                    }
                }
                override fun onStartTrackingTouch(bar: SeekBar?) {
                    isUserSeekingBar = true
                    mainHandler.removeCallbacks(hideControlsRunnable)
                }
                override fun onStopTrackingTouch(bar: SeekBar?) {
                    isUserSeekingBar = false
                    if (::player.isInitialized) {
                        val duration = player.duration
                        if (duration > 0 && duration != C.TIME_UNSET) {
                            val seekPos = duration * (bar?.progress ?: 0) / 1000L
                            player.seekTo(seekPos)
                        }
                    }
                    scheduleHideControls()
                }
            })
            setOnFocusChangeListener { _, hasFocus ->
                if (hasFocus) {
                    seekBarRow.setBackgroundColor(SEEK_BAR_FOCUS_BACKGROUND_COLOR)
                    thumb = buildSeekBarThumbFocused()
                } else {
                    seekBarRow.setBackgroundColor(android.graphics.Color.TRANSPARENT)
                    thumb = buildSeekBarThumb()
                }
                scheduleHideControls()
            }
        }
        seekBarRow.addView(seekBar)

        durationText = TextView(this).apply {
            setTextColor(android.graphics.Color.WHITE)
            textSize = 12f
            text = "00:00:00"
            layoutParams = android.widget.LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                marginStart = dpToPx(8)
            }
        }
        seekBarRow.addView(durationText)

        // LIVE indicator (hidden by default; shown instead of seek bar for live streams)
        liveIndicator = TextView(this).apply {
            setTextColor(android.graphics.Color.WHITE)
            textSize = 12f
            text = "● LIVE"
            setBackgroundColor(0xFFCC0000.toInt())
            val lp = android.widget.LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                marginStart = dpToPx(8)
            }
            layoutParams = lp
            visibility = View.GONE
            val livePad = dpToPx(4)
            setPadding(livePad, dpToPx(2), livePad, dpToPx(2))
        }
        seekBarRow.addView(liveIndicator)

        bottomBar.addView(seekBarRow)

        // Info row: title + resize/settings/CC buttons
        val infoRow = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.CENTER_VERTICAL
            layoutParams = android.widget.LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
        }

        // Title (fills remaining space)
        titleTextView = TextView(this).apply {
            setTextColor(android.graphics.Color.WHITE)
            textSize = 14f
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
            layoutParams = android.widget.LinearLayout.LayoutParams(
                0,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                1f
            )
        }
        infoRow.addView(titleTextView)

        val btnSize = dpToPx(36)

        // Resize mode button
        val resizeModeButton = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_menu_crop)
            setColorFilter(android.graphics.Color.WHITE)
            background = makeFocusDrawable()
            layoutParams = android.widget.LinearLayout.LayoutParams(btnSize, btnSize).apply {
                gravity = android.view.Gravity.CENTER_VERTICAL
            }
            contentDescription = "Resize mode"
            setOnClickListener {
                cycleResizeMode()
                scheduleHideControls()
            }
            isClickable = true
            isFocusable = true
        }
        infoRow.addView(resizeModeButton)

        // Settings (audio/video tracks) button
        val settingsButton = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_menu_manage)
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
        }
        infoRow.addView(settingsButton)

        // Subtitles (CC) button
        val ccButton = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_btn_speak_now)
            setColorFilter(android.graphics.Color.WHITE)
            background = makeFocusDrawable()
            layoutParams = android.widget.LinearLayout.LayoutParams(btnSize, btnSize).apply {
                gravity = android.view.Gravity.CENTER_VERTICAL
            }
            contentDescription = "Subtitles"
            setOnClickListener {
                showSubtitlesDialog()
                scheduleHideControls()
            }
            isClickable = true
            isFocusable = true
        }
        infoRow.addView(ccButton)

        // Assign stable IDs to bottom bar buttons
        resizeModeButton.id = View.generateViewId()
        settingsButton.id = View.generateViewId()
        ccButton.id = View.generateViewId()

        // Wire up the complete vertical D-pad focus chain:
        //   [Rewind] ←→ [Play/Pause] ←→ [Forward]
        //                    ↕
        //                [Seek Bar]
        //                    ↕
        //       [Resize] ←→ [Settings] ←→ [CC]
        rewindButton.nextFocusDownId = seekBar.id
        playPauseButton.nextFocusDownId = seekBar.id
        forwardButton.nextFocusDownId = seekBar.id

        seekBar.nextFocusUpId = playPauseButton.id
        seekBar.nextFocusDownId = resizeModeButton.id

        resizeModeButton.nextFocusUpId = seekBar.id
        resizeModeButton.nextFocusRightId = settingsButton.id

        settingsButton.nextFocusUpId = seekBar.id
        settingsButton.nextFocusLeftId = resizeModeButton.id
        settingsButton.nextFocusRightId = ccButton.id

        ccButton.nextFocusUpId = seekBar.id
        ccButton.nextFocusLeftId = settingsButton.id

        bottomBar.addView(infoRow)
        root.addView(bottomBar)

        return root
    }

    // ── Skip helpers ──────────────────────────────────────────────────────────

    private fun skipRewind() {
        if (::player.isInitialized) {
            val newPos = (player.currentPosition - SKIP_REWIND_MS).coerceAtLeast(0L)
            player.seekTo(newPos)
        }
    }

    private fun skipForward() {
        if (::player.isInitialized) {
            val duration = player.duration
            val newPos = if (duration != C.TIME_UNSET)
                (player.currentPosition + SKIP_FORWARD_MS).coerceAtMost(duration)
            else
                player.currentPosition + SKIP_FORWARD_MS
            player.seekTo(newPos)
        }
    }

    private fun scrubSeekBar(delta: Int) {
        if (!::player.isInitialized) return
        val duration = player.duration
        if (duration <= 0 || duration == C.TIME_UNSET) return

        // Mark as user-seeking so updateSeekBar() doesn't override our position
        isUserSeekingBar = true

        // Adjust progress
        val newProgress = (seekBar.progress + delta).coerceIn(0, seekBar.max)
        seekBar.progress = newProgress

        // Update time display in real-time
        val seekPos = duration * newProgress / 1000L
        currentTimeText.text = formatMs(seekPos)

        // Cancel any previous commit, schedule a new one after 1 second
        mainHandler.removeCallbacks(seekCommitRunnable)
        mainHandler.postDelayed(seekCommitRunnable, SEEK_COMMIT_DELAY_MS)

        // Keep controls visible while scrubbing
        mainHandler.removeCallbacks(hideControlsRunnable)
        scheduleHideControls()
    }

    private fun commitSeek() {
        if (!::player.isInitialized) return
        val duration = player.duration
        if (duration <= 0 || duration == C.TIME_UNSET) return

        val seekPos = duration * seekBar.progress / 1000L
        player.seekTo(seekPos)
        isUserSeekingBar = false
    }

    // ── Seek bar update ───────────────────────────────────────────────────────

    private fun updateSeekBar() {
        if (!::player.isInitialized || isUserSeekingBar) return
        val position = player.currentPosition
        val duration = player.duration
        val isLive = duration == C.TIME_UNSET || duration <= 0
        if (isLive) {
            seekBar.visibility = View.GONE
            currentTimeText.visibility = View.GONE
            durationText.visibility = View.GONE
            liveIndicator.visibility = View.VISIBLE
        } else {
            seekBar.visibility = View.VISIBLE
            currentTimeText.visibility = View.VISIBLE
            durationText.visibility = View.VISIBLE
            liveIndicator.visibility = View.GONE
            seekBar.progress = ((position * 1000L) / duration).toInt().coerceIn(0, 1000)
            currentTimeText.text = formatMs(position)
            durationText.text = formatMs(duration)
        }
    }

    private fun formatMs(ms: Long): String {
        val totalSecs = ms / 1000L
        val h = totalSecs / 3600
        val m = (totalSecs % 3600) / 60
        val s = totalSecs % 60
        return "%02d:%02d:%02d".format(h, m, s)
    }

    private fun buildSeekBarDrawable(): android.graphics.drawable.Drawable {
        val played = android.graphics.drawable.GradientDrawable().apply {
            setColor(0xFF3498DB.toInt())
        }
        val bg = android.graphics.drawable.GradientDrawable().apply {
            setColor(0x66FFFFFF.toInt())
        }
        val layerList = android.graphics.drawable.LayerDrawable(
            arrayOf(bg, android.graphics.drawable.ClipDrawable(played,
                android.view.Gravity.START, android.graphics.drawable.ClipDrawable.HORIZONTAL))
        )
        layerList.setId(0, android.R.id.background)
        layerList.setId(1, android.R.id.progress)
        return layerList
    }

    private fun buildSeekBarThumb(): android.graphics.drawable.Drawable {
        return android.graphics.drawable.GradientDrawable().apply {
            shape = android.graphics.drawable.GradientDrawable.OVAL
            setColor(0xFF3498DB.toInt())
            val size = dpToPx(14)
            setSize(size, size)
        }
    }

    private fun buildSeekBarThumbFocused(): android.graphics.drawable.Drawable {
        return android.graphics.drawable.GradientDrawable().apply {
            shape = android.graphics.drawable.GradientDrawable.OVAL
            setColor(android.graphics.Color.WHITE)
            val size = dpToPx(20)
            setSize(size, size)
        }
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

    private fun cycleResizeMode() {
        val currentIndex = RESIZE_MODES.indexOfFirst { it.first == currentResizeMode }
        val next = RESIZE_MODES[(currentIndex + 1) % RESIZE_MODES.size]
        currentResizeMode = next.first
        playerView.resizeMode = currentResizeMode
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .edit()
            .putInt(PREF_RESIZE_MODE, currentResizeMode)
            .apply()
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
