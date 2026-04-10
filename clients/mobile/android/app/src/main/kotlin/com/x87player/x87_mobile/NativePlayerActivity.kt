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
import android.app.ProgressDialog
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
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.TrackSelectionOverride
import androidx.media3.common.Tracks
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

class NativePlayerActivity : Activity() {

    companion object {
        const val EXTRA_URL = "url"
        const val EXTRA_TITLE = "title"
        const val EXTRA_CONTENT_TYPE = "contentType"
        const val EXTRA_YEAR = "year"
        const val EXTRA_TMDB_ID = "tmdbId"

        private const val CONTROLS_HIDE_DELAY_MS = 5_000L
        private const val SEEK_BAR_UPDATE_INTERVAL_MS = 500L
        private const val SKIP_REWIND_MS = 30_000L
        private const val SKIP_FORWARD_MS = 30_000L
        private const val PREFS_NAME = "player_prefs"
        private const val PREF_RESIZE_MODE = "resize_mode"
        private const val SEEK_BAR_FOCUS_BACKGROUND_COLOR: Int = 0x333498DB
        private const val SEEK_BAR_SCRUB_INCREMENT = 10   // 1% per D-pad press (out of max=1000)
        private const val SEEK_COMMIT_DELAY_MS = 1_000L   // commit seek 1 second after last scrub
        private const val SEEK_GUARD_TIMEOUT_MS = 2_000L  // max time to wait for seek completion
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

    // Metadata used for online subtitle search
    private var contentTitle: String = ""
    private var contentYear: String? = null
    private var contentTmdbId: String? = null
    // The original stream URI (needed to rebuild MediaItem with subtitle)
    private var streamUri: android.net.Uri? = null

    private val mainHandler = Handler(Looper.getMainLooper())
    private var controlsVisible = true
    private var currentResizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT
    private var isUserSeekingBar = false
    private var isDpadScrubbing = false
    private var pendingSeekComplete = false

    private val hideControlsRunnable = Runnable { hideControls() }
    private val seekCommitRunnable = Runnable { commitDpadSeek() }
    private val seekGuardTimeoutRunnable = Runnable {
        android.util.Log.w("NativePlayerActivity", "Seek guard timed out — clearing isUserSeekingBar")
        pendingSeekComplete = false
        isUserSeekingBar = false
    }

    private val seekBarUpdateRunnable = object : Runnable {
        override fun run() {
            updateSeekBar()
            mainHandler.postDelayed(this, SEEK_BAR_UPDATE_INTERVAL_MS)
        }
    }

    // Delayed runnable that force-selects the injected SRT track after prepare().
    private var subtitleSelectionRunnable: Runnable? = null

    // URI string of the currently injected SRT sidecar, or null if none is active.
    // Used to re-apply the track override after ExoPlayer re-resolves tracks.
    private var injectedSrtId: String? = null
    // Language code of the currently injected SRT sidecar (e.g. "fr", "de").
    // Used as a MIME-type-aware fallback when the ID match fails after track re-resolution.
    private var injectedSrtLang: String? = null

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
        contentTitle = title
        contentYear = intent.getStringExtra(EXTRA_YEAR)
        contentTmdbId = intent.getStringExtra(EXTRA_TMDB_ID)
        streamUri = Uri.parse(url)

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
                        // Clear the seek guard once ExoPlayer has finished seeking
                        if (state == Player.STATE_READY && pendingSeekComplete) {
                            pendingSeekComplete = false
                            isUserSeekingBar = false
                            mainHandler.removeCallbacks(seekGuardTimeoutRunnable)
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
                        var hasAnyAudioTrack = false
                        var hasPlayableAudio = false
                        val unsupportedCodecs = mutableListOf<String>()

                        for (group in tracks.groups) {
                            if (group.type == C.TRACK_TYPE_AUDIO) {
                                // At least one audio group exists — the stream has audio
                                hasAnyAudioTrack = true
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

                                    if (selected && supported) {
                                        // A selected+supported track means audio will actually play
                                        hasPlayableAudio = true
                                    } else if (!supported) {
                                        // Unsupported track (whether selected or not) — record it
                                        unsupportedCodecs.add(codec)
                                    }
                                }
                            }
                        }

                        // Trigger VLC fallback if the stream has audio but none of it is playable
                        if (hasAnyAudioTrack && !hasPlayableAudio) {
                            android.util.Log.w("NativePlayerActivity",
                                "No playable audio track found. Unsupported codec(s): ${unsupportedCodecs.joinToString()} — launching VLC")
                            launchVlcFallback()
                        }

                        // Re-apply the injected SRT override if ExoPlayer re-resolved tracks
                        // (e.g. after an HLS manifest refresh) while we still have an active
                        // sidecar subtitle.  Without this the DefaultTrackSelector can silently
                        // switch back to the supplier's embedded text track.
                        val srtId = injectedSrtId
                        if (srtId != null) {
                            val match = findTextTrackById(srtId, tracks)
                            if (match != null) {
                                val (group, i) = match
                                if (!group.isTrackSelected(i)) {
                                    android.util.Log.i(
                                        "NativePlayerActivity",
                                        "onTracksChanged: re-applying SRT override (id=$srtId)"
                                    )
                                    player.trackSelectionParameters =
                                        player.trackSelectionParameters
                                            .buildUpon()
                                            .clearOverridesOfType(C.TRACK_TYPE_TEXT)
                                            .setOverrideForType(
                                                TrackSelectionOverride(
                                                    group.mediaTrackGroup, listOf(i)
                                                )
                                            )
                                            .build()
                                }
                            } else {
                                // ID match failed (e.g. after HLS manifest refresh) — fall back to
                                // MIME-type-aware matching so we don't silently select an embedded
                                // stream subtitle with the same language code instead of the SRT.
                                val injectedLang = injectedSrtLang
                                if (injectedLang != null) {
                                    val textGroups = tracks.groups.filter { it.type == C.TRACK_TYPE_TEXT }
                                    val candidateGroup = textGroups.lastOrNull { group ->
                                        (0 until group.length).any { i ->
                                            isSrtTrackForLang(group.getTrackFormat(i), injectedLang)
                                        }
                                    }
                                    if (candidateGroup != null) {
                                        val candidateIndex = (0 until candidateGroup.length)
                                            .lastOrNull { i ->
                                                isSrtTrackForLang(candidateGroup.getTrackFormat(i), injectedLang)
                                            } ?: 0
                                        if (!candidateGroup.isTrackSelected(candidateIndex)) {
                                            android.util.Log.i(
                                                "NativePlayerActivity",
                                                "onTracksChanged: re-applying SRT via MIME fallback " +
                                                    "(lang=$injectedLang, mime=${MimeTypes.APPLICATION_SUBRIP})"
                                            )
                                            player.trackSelectionParameters =
                                                player.trackSelectionParameters
                                                    .buildUpon()
                                                    .clearOverridesOfType(C.TRACK_TYPE_TEXT)
                                                    .setOverrideForType(
                                                        TrackSelectionOverride(
                                                            candidateGroup.mediaTrackGroup,
                                                            listOf(candidateIndex)
                                                        )
                                                    )
                                                    .build()
                                        }
                                    }
                                }
                            }
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
        mainHandler.removeCallbacks(seekGuardTimeoutRunnable)
        subtitleSelectionRunnable?.let { mainHandler.removeCallbacks(it) }
        subtitleSelectionRunnable = null
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

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.action != KeyEvent.ACTION_DOWN) return super.dispatchKeyEvent(event)

        val keyCode = event.keyCode
        return when (keyCode) {
            KeyEvent.KEYCODE_DPAD_CENTER -> {
                if (!controlsVisible) {
                    showControls()
                    true
                } else if (::seekBar.isInitialized && seekBar.hasFocus() && isDpadScrubbing) {
                    // Commit the scrub immediately on center press
                    mainHandler.removeCallbacks(seekCommitRunnable)
                    commitDpadSeek()
                    true
                } else {
                    // Let the focused button handle the click naturally
                    scheduleHideControls()
                    super.dispatchKeyEvent(event)
                }
            }
            KeyEvent.KEYCODE_DPAD_LEFT -> {
                if (!controlsVisible) {
                    showControls()
                    true
                } else if (::seekBar.isInitialized && seekBar.hasFocus()) {
                    // Seek bar has focus — scrub left freely; consume so SeekBar won't also handle it
                    dpadScrubSeekBar(-SEEK_BAR_SCRUB_INCREMENT)
                    true
                } else {
                    // Other button focused — let Android handle focus navigation
                    scheduleHideControls()
                    super.dispatchKeyEvent(event)
                }
            }
            KeyEvent.KEYCODE_DPAD_RIGHT -> {
                if (!controlsVisible) {
                    showControls()
                    true
                } else if (::seekBar.isInitialized && seekBar.hasFocus()) {
                    // Seek bar has focus — scrub right freely; consume so SeekBar won't also handle it
                    dpadScrubSeekBar(SEEK_BAR_SCRUB_INCREMENT)
                    true
                } else {
                    // Other button focused — let Android handle focus navigation
                    scheduleHideControls()
                    super.dispatchKeyEvent(event)
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
            KeyEvent.KEYCODE_DPAD_UP,
            KeyEvent.KEYCODE_DPAD_DOWN -> {
                if (!controlsVisible) {
                    showControls()
                    true
                } else {
                    // If we were scrubbing the seek bar, commit before moving focus away
                    if (isDpadScrubbing) {
                        mainHandler.removeCallbacks(seekCommitRunnable)
                        commitDpadSeek()
                    }
                    scheduleHideControls()
                    super.dispatchKeyEvent(event)
                }
            }
            else -> {
                // Any other key shows controls
                showControls()
                super.dispatchKeyEvent(event)
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
        // If user was scrubbing, commit before hiding
        if (isDpadScrubbing) {
            mainHandler.removeCallbacks(seekCommitRunnable)
            commitDpadSeek()
        }
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
            keyProgressIncrement = 0   // Disable built-in D-pad handling — we handle it via dispatchKeyEvent
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
                    if (::player.isInitialized) {
                        val duration = player.duration
                        if (duration > 0 && duration != C.TIME_UNSET) {
                            val seekPos = duration * (bar?.progress ?: 0) / 1000L
                            pendingSeekComplete = true
                            player.seekTo(seekPos)
                            mainHandler.removeCallbacks(seekGuardTimeoutRunnable)
                            mainHandler.postDelayed(seekGuardTimeoutRunnable, SEEK_GUARD_TIMEOUT_MS)
                            // DO NOT clear isUserSeekingBar — wait for seek complete
                        } else {
                            isUserSeekingBar = false
                        }
                    } else {
                        isUserSeekingBar = false
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
                    // If scrubbing and lost focus, commit immediately
                    if (isDpadScrubbing) {
                        mainHandler.removeCallbacks(seekCommitRunnable)
                        commitDpadSeek()
                    }
                }
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

    private fun dpadScrubSeekBar(delta: Int) {
        if (!::player.isInitialized || !::seekBar.isInitialized) return
        val duration = player.duration
        if (duration <= 0 || duration == C.TIME_UNSET) return

        // Enter scrub mode — blocks updateSeekBar() from overwriting our position
        isDpadScrubbing = true
        isUserSeekingBar = true

        // Move the thumb
        val newProgress = (seekBar.progress + delta).coerceIn(0, seekBar.max)
        seekBar.progress = newProgress

        // Update the time text live
        val seekPos = duration * newProgress / 1000L
        currentTimeText.text = formatMs(seekPos)

        // Cancel previous commit, schedule new one 1s from now
        mainHandler.removeCallbacks(seekCommitRunnable)
        mainHandler.postDelayed(seekCommitRunnable, SEEK_COMMIT_DELAY_MS)

        // Keep controls visible — cancel hide, do NOT reschedule
        mainHandler.removeCallbacks(hideControlsRunnable)
    }

    private fun commitDpadSeek() {
        if (!::player.isInitialized || !::seekBar.isInitialized) return
        val duration = player.duration
        if (duration > 0 && duration != C.TIME_UNSET) {
            val seekPos = duration * seekBar.progress / 1000L
            pendingSeekComplete = true
            player.seekTo(seekPos)
            mainHandler.removeCallbacks(seekGuardTimeoutRunnable)
            mainHandler.postDelayed(seekGuardTimeoutRunnable, SEEK_GUARD_TIMEOUT_MS)
            // DO NOT clear isUserSeekingBar here — wait for seek to complete
        }
        isDpadScrubbing = false
        // isUserSeekingBar stays true until onPlaybackStateChanged fires STATE_READY
        scheduleHideControls()
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

    /** Returns ALL tracks of [type], including those ExoPlayer considers unsupported.
     *  The Boolean in each Triple is true when the track is supported, false otherwise. */
    private fun getAllTracksOfType(type: Int): List<Triple<Tracks.Group, Int, Boolean>> {
        val result = mutableListOf<Triple<Tracks.Group, Int, Boolean>>()
        for (group in player.currentTracks.groups) {
            if (group.type == type) {
                for (i in 0 until group.length) {
                    result.add(Triple(group, i, group.isTrackSupported(i)))
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
        // Pause playback immediately while the user chooses a subtitle
        val wasPlaying = player.isPlaying
        player.pause()

        // Read preferred languages from SharedPreferences (Flutter writes to the
        // default app shared preferences via the shared_preferences plugin).
        val flutterPrefs = getSharedPreferences("FlutterSharedPreferences", MODE_PRIVATE)
        val langsJson = flutterPrefs.getString("flutter.subtitle_languages", null)
        val langs: List<String> = if (langsJson != null) {
            try {
                val arr = org.json.JSONArray(langsJson)
                (0 until arr.length()).map { arr.getString(it) }
            } catch (_: Exception) {
                listOf("en")
            }
        } else {
            listOf("en")
        }

        val progressDialog = ProgressDialog(this).apply {
            setMessage("Searching for subtitles...")
            setCancelable(false)
            show()
        }

        Thread {
            // Collect results for all preferred languages from the search endpoint
            data class SubtitleResult(
                val fileId: Int,
                val language: String,
                val release: String,
                val downloadCount: Int,
                val provider: String,
            )

            val allResults = mutableListOf<SubtitleResult>()

            for (lang in langs) {
                try {
                    val sb = StringBuilder("https://x87player.xyz/subtitles/search?")
                    sb.append("title=").append(URLEncoder.encode(contentTitle, "UTF-8"))
                    if (!contentYear.isNullOrBlank()) {
                        sb.append("&year=").append(URLEncoder.encode(contentYear!!, "UTF-8"))
                    }
                    if (!contentTmdbId.isNullOrBlank()) {
                        sb.append("&tmdb_id=").append(URLEncoder.encode(contentTmdbId!!, "UTF-8"))
                    }
                    sb.append("&lang=").append(URLEncoder.encode(lang, "UTF-8"))

                    val connection = URL(sb.toString()).openConnection() as HttpURLConnection
                    connection.connectTimeout = 15_000
                    connection.readTimeout = 30_000
                    connection.requestMethod = "GET"

                    val code = connection.responseCode
                    if (code == 200) {
                        val body = connection.inputStream.bufferedReader().readText()
                        val arr = org.json.JSONArray(body)
                        for (i in 0 until arr.length()) {
                            val obj = arr.getJSONObject(i)
                            allResults.add(
                                SubtitleResult(
                                    fileId = obj.getInt("file_id"),
                                    language = obj.optString("language", lang),
                                    release = obj.optString("release", ""),
                                    downloadCount = obj.optInt("download_count", 0),
                                    provider = obj.optString("provider", "OpenSubtitles"),
                                )
                            )
                        }
                    }
                    connection.disconnect()
                } catch (_: Exception) {
                    // Try next language
                }
            }

            runOnUiThread {
                progressDialog.dismiss()

                if (allResults.isEmpty()) {
                    Toast.makeText(this, "No subtitles found", Toast.LENGTH_SHORT).show()
                    if (wasPlaying) player.play()
                    return@runOnUiThread
                }

                // Build dialog labels: "Off" first, then each subtitle result
                val labels = mutableListOf("Off")
                for (r in allResults) {
                    val downloads = if (r.downloadCount > 0) " (↓${r.downloadCount})" else ""
                    labels.add("[${r.language.uppercase()}] ${r.release}$downloads")
                }

                AlertDialog.Builder(this)
                    .setTitle("Subtitles")
                    .setItems(labels.toTypedArray()) { _, which ->
                        if (which == 0) {
                            // Off — clear the injected SRT state so the onTracksChanged
                            // listener stops re-applying the override, then disable subtitles.
                            injectedSrtId = null
                            injectedSrtLang = null
                            subtitleSelectionRunnable?.let { mainHandler.removeCallbacks(it) }
                            subtitleSelectionRunnable = null
                            player.trackSelectionParameters = player.trackSelectionParameters
                                .buildUpon()
                                .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, true)
                                .build()
                            if (wasPlaying) player.play()
                        } else {
                            val selected = allResults[which - 1]
                            downloadAndInjectSubtitle(selected.fileId, selected.language, wasPlaying)
                        }
                    }
                    .setOnCancelListener {
                        // Dialog dismissed — resume playback
                        if (wasPlaying) player.play()
                    }
                    .show()
            }
        }.start()
    }

    @Suppress("DEPRECATION")
    private fun downloadAndInjectSubtitle(fileId: Int, lang: String, resumePlayback: Boolean) {
        val uri = streamUri ?: run {
            Toast.makeText(this, "No stream URL available", Toast.LENGTH_SHORT).show()
            if (resumePlayback) player.play()
            return
        }

        val progressDialog = ProgressDialog(this).apply {
            setMessage("Downloading subtitle...")
            setCancelable(false)
            show()
        }

        Thread {
            var srtText: String? = null
            try {
                val url = "https://x87player.xyz/subtitles/download?file_id=$fileId"
                val connection = URL(url).openConnection() as HttpURLConnection
                connection.connectTimeout = 15_000
                connection.readTimeout = 60_000
                connection.requestMethod = "GET"
                val code = connection.responseCode
                if (code == 200) {
                    srtText = connection.inputStream.bufferedReader().readText()
                }
                connection.disconnect()
            } catch (_: Exception) {
                // handled below
            }

            runOnUiThread {
                progressDialog.dismiss()
                if (!srtText.isNullOrBlank()) {
                    injectSrtSubtitle(uri, srtText!!, lang)
                    if (resumePlayback) player.play()
                } else {
                    Toast.makeText(this, "Failed to download subtitle", Toast.LENGTH_SHORT).show()
                    if (resumePlayback) player.play()
                }
            }
        }.start()
    }

    private fun injectSrtSubtitle(videoUri: android.net.Uri, srtContent: String, langCode: String) {
        try {
            // Write SRT to a temp file in cacheDir
            val srtFile = File(cacheDir, "subtitle_${langCode}_${System.currentTimeMillis()}.srt")
            srtFile.writeText(srtContent)

            val savedPosition = player.currentPosition
            val wasPlaying = player.isPlaying

            val srtUri = Uri.fromFile(srtFile)
            val subtitleConfig = MediaItem.SubtitleConfiguration.Builder(srtUri)
                .setMimeType(MimeTypes.APPLICATION_SUBRIP)
                .setLanguage(langCode)
                .setSelectionFlags(C.SELECTION_FLAG_DEFAULT)
                .setId(srtUri.toString())
                .build()

            val newMediaItem = MediaItem.Builder()
                .setUri(videoUri)
                .setSubtitleConfigurations(listOf(subtitleConfig))
                .build()

            // Cancel any pending subtitle selection from a previous injection.
            subtitleSelectionRunnable?.let { mainHandler.removeCallbacks(it) }
            subtitleSelectionRunnable = null

            // Remember the injected SRT's unique ID so scheduleSubtitleSelection() and
            // the onTracksChanged listener can identify it unambiguously even when the
            // supplier stream contains embedded text tracks with the same language code.
            injectedSrtId = srtUri.toString()
            injectedSrtLang = langCode

            // Clear any stale text track overrides and hint the preferred language before
            // prepare() so ExoPlayer's automatic selection already favours the injected track.
            player.trackSelectionParameters = player.trackSelectionParameters
                .buildUpon()
                .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, false)
                .clearOverridesOfType(C.TRACK_TYPE_TEXT)
                .setPreferredTextLanguage(langCode)
                .build()

            player.setMediaItem(newMediaItem)
            player.prepare()
            player.seekTo(savedPosition)
            if (wasPlaying) player.play()

            // Schedule a delayed forced track selection.  By 2 seconds after prepare(),
            // ExoPlayer has finished merging all sources and the sidecar SRT is present.
            // MergingMediaSource appends the sidecar AFTER the main stream's text groups,
            // so the LAST text group matching langCode is always the injected SRT.
            // Max 2 retries (attempts 1, 2, 3) = up to 6 seconds total.
            scheduleSubtitleSelection(langCode, attemptsLeft = 3)

            val langName = when (langCode) {
                "en" -> "English"; "fr" -> "French"; "de" -> "German"
                "es" -> "Spanish"; "it" -> "Italian"; "pt" -> "Portuguese"
                "nl" -> "Dutch"; "pl" -> "Polish"; "ru" -> "Russian"
                "ar" -> "Arabic"; "tr" -> "Turkish"; "ro" -> "Romanian"
                "el" -> "Greek"; "hu" -> "Hungarian"; "cs" -> "Czech"
                "sv" -> "Swedish"; "da" -> "Danish"; "no" -> "Norwegian"
                "fi" -> "Finnish"; "hr" -> "Croatian"; "bg" -> "Bulgarian"
                "he" -> "Hebrew"; "zh" -> "Chinese"; "ja" -> "Japanese"
                "ko" -> "Korean"; "th" -> "Thai"; "vi" -> "Vietnamese"
                "id" -> "Indonesian"; "ms" -> "Malay"
                else -> langCode.uppercase()
            }
            Toast.makeText(this, "Subtitles loaded ($langName)", Toast.LENGTH_SHORT).show()
        } catch (e: Exception) {
            Toast.makeText(this, "Failed to load subtitles: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    /**
     * Returns true if [trackLang] (from ExoPlayer's Format.language, a BCP 47 tag) matches
     * [langCode] (a 2-letter IETF code sent by the app).  Accepts exact equality, prefix
     * matches (e.g. "ro" matches "ro-RO"), and 2-letter truncation (e.g. "ron" → "ro").
     */
    private fun langMatches(trackLang: String?, langCode: String): Boolean =
        trackLang == langCode ||
            trackLang?.startsWith("$langCode-") == true ||
            langCode == trackLang?.take(2)

    /**
     * Returns true when [fmt] is an SRT track whose language matches [langCode].
     * Used to discriminate the injected sidecar (always application/x-subrip) from
     * embedded stream subtitles (typically WebVTT or TTML).
     */
    private fun isSrtTrackForLang(fmt: androidx.media3.common.Format, langCode: String): Boolean =
        langMatches(fmt.language, langCode) && fmt.sampleMimeType == MimeTypes.APPLICATION_SUBRIP

    /**
     * Finds the text track whose format ID matches [srtId] in [tracks].
     * Returns the (group, trackIndex) pair, or null if not found.
     */
    private fun findTextTrackById(srtId: String, tracks: Tracks): Pair<Tracks.Group, Int>? {
        for (group in tracks.groups.filter { it.type == C.TRACK_TYPE_TEXT }) {
            for (i in 0 until group.length) {
                if (group.getTrackFormat(i).id == srtId) return Pair(group, i)
            }
        }
        return null
    }

    private fun scheduleSubtitleSelection(langCode: String, attemptsLeft: Int) {
        val runnable = Runnable {
            subtitleSelectionRunnable = null

            val textGroups = player.currentTracks.groups.filter { it.type == C.TRACK_TYPE_TEXT }
            if (textGroups.isEmpty()) {
                // Tracks not resolved yet — retry if attempts remain.
                if (attemptsLeft > 1) {
                    android.util.Log.d(
                        "NativePlayerActivity",
                        "Subtitle selection: no text groups yet, retrying (attemptsLeft=${attemptsLeft - 1})"
                    )
                    scheduleSubtitleSelection(langCode, attemptsLeft - 1)
                } else {
                    android.util.Log.w(
                        "NativePlayerActivity",
                        "Subtitle selection: no text groups after all attempts — relying on preferred language hint"
                    )
                }
                return@Runnable
            }

            // Prefer identifying the injected SRT by its unique track ID (the srtUri string
            // set via SubtitleConfiguration.Builder.setId()).  This is unambiguous even when
            // the supplier stream contains embedded text tracks with the same language code.
            val srtId = injectedSrtId
            var targetGroup: Tracks.Group?
            var trackIndex: Int

            val idMatch = if (srtId != null) findTextTrackById(srtId, player.currentTracks) else null
            if (idMatch != null) {
                targetGroup = idMatch.first
                trackIndex = idMatch.second
            } else {
                // ID match failed — fall back to matching by BOTH language AND SRT MIME type.
                // The injected sidecar is always application/x-subrip, while embedded stream
                // subtitles are typically WebVTT or TTML. This avoids selecting the wrong track.
                val langAndMimeMatches = textGroups.filter { group ->
                    (0 until group.length).any { i -> isSrtTrackForLang(group.getTrackFormat(i), langCode) }
                }

                targetGroup = if (langAndMimeMatches.isNotEmpty()) {
                    langAndMimeMatches.last()
                } else {
                    // No MIME+lang match — try language only (legacy fallback)
                    val langOnlyMatches = textGroups.filter { group ->
                        (0 until group.length).any { i ->
                            langMatches(group.getTrackFormat(i).language, langCode)
                        }
                    }
                    if (langOnlyMatches.isNotEmpty()) {
                        langOnlyMatches.last()
                    } else {
                        // No language match — pick the last text group as a last resort.
                        android.util.Log.w(
                            "NativePlayerActivity",
                            "Subtitle selection: no lang=$langCode match, picking last text group"
                        )
                        textGroups.last()
                    }
                }

                trackIndex = (0 until targetGroup.length)
                    .lastOrNull { i -> isSrtTrackForLang(targetGroup.getTrackFormat(i), langCode) }
                    ?: (0 until targetGroup.length)
                        .lastOrNull { i -> langMatches(targetGroup.getTrackFormat(i).language, langCode) }
                    ?: 0
            }

            android.util.Log.i(
                "NativePlayerActivity",
                "Forcing text track: group=${targetGroup.length} tracks," +
                    " trackIndex=$trackIndex," +
                    " id=${targetGroup.getTrackFormat(trackIndex).id}," +
                    " lang=${targetGroup.getTrackFormat(trackIndex).language}"
            )

            player.trackSelectionParameters = player.trackSelectionParameters
                .buildUpon()
                .clearOverridesOfType(C.TRACK_TYPE_TEXT)
                .setOverrideForType(
                    TrackSelectionOverride(targetGroup.mediaTrackGroup, listOf(trackIndex))
                )
                .build()
        }
        subtitleSelectionRunnable = runnable
        mainHandler.postDelayed(runnable, 2_000L)
    }

    private fun showSettingsDialog() {
        val videoTracks = getTracksOfType(C.TRACK_TYPE_VIDEO)
        val allAudioTracks = getAllTracksOfType(C.TRACK_TYPE_AUDIO)

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
        // "Auto" resets any manual override and re-applies the saved language
        // preference (default: English), exactly like XCIPTV's Auto button.
        val savedAudioLang = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .getString("preferred_audio_language", "en") ?: "en"
        val autoLabel = when (savedAudioLang) {
            "en" -> "English"; "fr" -> "French"; "de" -> "German"
            "es" -> "Spanish"; "it" -> "Italian"; "pt" -> "Portuguese"
            "nl" -> "Dutch"; "pl" -> "Polish"; "ru" -> "Russian"
            "ar" -> "Arabic"; "tr" -> "Turkish"; "ro" -> "Romanian"
            else -> savedAudioLang.uppercase()
        }
        items.add("  Auto ($autoLabel)")
        actions.add {
            player.trackSelectionParameters = player.trackSelectionParameters
                .buildUpon()
                .clearOverridesOfType(C.TRACK_TYPE_AUDIO)
                .setPreferredAudioLanguage(savedAudioLang)
                .build()
        }
        if (allAudioTracks.isEmpty()) {
            items.add("  (none)")
            actions.add({})
        } else {
            for ((group, index, supported) in allAudioTracks) {
                val format = group.getTrackFormat(index)
                val lang = format.label ?: format.language ?: "Unknown"
                val codec = format.codecs ?: format.sampleMimeType ?: "Unknown"
                val channels = when (format.channelCount) {
                    1 -> "Mono"
                    2 -> "Stereo"
                    6 -> "5.1"
                    8 -> "7.1"
                    else -> if (format.channelCount > 0) "${format.channelCount}ch" else "Unknown"
                }
                val isSelected = group.isTrackSelected(index)
                val prefix = if (isSelected) "▶ " else "  "
                val suffix = if (!supported) " ⚠️" else ""
                items.add("$prefix$lang - $codec - $channels$suffix")
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
