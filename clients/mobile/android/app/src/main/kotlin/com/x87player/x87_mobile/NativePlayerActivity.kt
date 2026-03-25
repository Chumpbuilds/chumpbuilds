package com.x87player.x87_mobile

import android.app.Activity
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView

/**
 * Native Android fullscreen video player Activity.
 *
 * Uses ExoPlayer (Media3) with a SurfaceView for zero-copy hardware compositor
 * rendering — the same path used by XCIPTV and other high-performance IPTV
 * players. This avoids the Flutter texture bridge which copies every video
 * frame through the rendering pipeline and causes lag on Fire Stick and
 * Amlogic-based Android TV boxes.
 *
 * Extras:
 *   EXTRA_URL         – stream URL (required)
 *   EXTRA_TITLE       – human-readable title for the overlay
 *   EXTRA_CONTENT_TYPE – 'live', 'movie', or 'series'
 *
 * Returns [Activity.RESULT_OK] when playback finishes normally,
 * or [Activity.RESULT_CANCELED] if the activity is dismissed early.
 */
class NativePlayerActivity : Activity() {

    companion object {
        const val EXTRA_URL = "url"
        const val EXTRA_TITLE = "title"
        const val EXTRA_CONTENT_TYPE = "contentType"

        private const val CONTROLS_HIDE_DELAY_MS = 5_000L
    }

    private lateinit var player: ExoPlayer
    private lateinit var playerView: PlayerView
    private lateinit var controlsOverlay: View
    private lateinit var titleTextView: TextView
    private lateinit var playPauseButton: ImageButton
    private lateinit var backButton: ImageButton

    private val mainHandler = Handler(Looper.getMainLooper())
    private var controlsVisible = true

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

        val url = intent.getStringExtra(EXTRA_URL) ?: run {
            Toast.makeText(this, "No stream URL provided", Toast.LENGTH_SHORT).show()
            setResult(RESULT_CANCELED)
            finish()
            return
        }
        val title = intent.getStringExtra(EXTRA_TITLE) ?: ""

        titleTextView.text = title

        // Build ExoPlayer with audio tunneling disabled.
        // Amlogic / Fire Stick devices advertise tunneled audio but their
        // firmware doesn't implement it correctly, causing silent playback.
        // Disabling it forces the standard software audio renderer path.
        val renderersFactory = DefaultRenderersFactory(this).apply {
            setEnableAudioTrackPlaybackParams(false)
            // Allow fallback to alternative decoders when the primary one fails.
            // Amlogic / Droidlogic devices often advertise hardware codec support
            // but their firmware doesn't implement it correctly, causing silent
            // decode failures or black-screen playback.
            setEnableDecoderFallback(true)
            // Prefer software extension renderers (e.g. libgav1, libvpx) over
            // broken hardware decoders on problematic chipsets.
            setExtensionRendererMode(DefaultRenderersFactory.EXTENSION_RENDERER_MODE_PREFER)
        }

        try {
            player = ExoPlayer.Builder(this, renderersFactory).build().also { exo ->
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
            KeyEvent.KEYCODE_DPAD_CENTER,
            KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE,
            KeyEvent.KEYCODE_MEDIA_PLAY,
            KeyEvent.KEYCODE_MEDIA_PAUSE -> {
                togglePlayPause()
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
        if (player.isPlaying) {
            player.pause()
        } else {
            player.play()
        }
        showControls()
    }

    private fun updatePlayPauseIcon(isPlaying: Boolean) {
        playPauseButton.setImageResource(
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

        // Overlay container — tap to toggle
        controlsOverlay = buildControlsOverlay()
        frame.addView(controlsOverlay)

        // Tap anywhere on the frame to toggle controls visibility.
        // We use onTouchListener on the frame so it works regardless of
        // whether the overlay is VISIBLE or GONE — SurfaceView click
        // listeners are unreliable.
        frame.setOnTouchListener { _, event ->
            if (event.action == android.view.MotionEvent.ACTION_UP) {
                if (controlsVisible) hideControls() else showControls()
            }
            // Return false so child views (buttons) still receive their events.
            false
        }

        return frame
    }

    private fun buildControlsOverlay(): View {
        val overlay = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            layoutParams = android.widget.FrameLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                android.view.ViewGroup.LayoutParams.MATCH_PARENT
            )
        }

        // Top bar: back button + title
        val topBar = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.HORIZONTAL
            setBackgroundColor(0xCC000000.toInt())
            val pad = dpToPx(8)
            setPadding(pad, pad, pad, pad)
        }

        backButton = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_media_previous)
            setBackgroundColor(android.graphics.Color.TRANSPARENT)
            setColorFilter(android.graphics.Color.WHITE)
            setOnClickListener {
                setResult(RESULT_CANCELED)
                finish()
            }
        }
        topBar.addView(backButton)

        titleTextView = TextView(this).apply {
            setTextColor(android.graphics.Color.WHITE)
            textSize = 16f
            setPadding(dpToPx(8), 0, 0, 0)
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
            layoutParams = android.widget.LinearLayout.LayoutParams(
                0,
                android.view.ViewGroup.LayoutParams.WRAP_CONTENT,
                1f
            )
        }
        topBar.addView(titleTextView)

        overlay.addView(topBar)

        // Spacer
        overlay.addView(android.view.View(this).apply {
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        })

        // Center play/pause
        val centerArea = android.widget.FrameLayout(this).apply {
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                android.view.ViewGroup.LayoutParams.WRAP_CONTENT
            )
        }

        playPauseButton = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_media_pause)
            setBackgroundColor(0x88000000.toInt())
            setColorFilter(android.graphics.Color.WHITE)
            val size = dpToPx(64)
            layoutParams = android.widget.FrameLayout.LayoutParams(size, size).apply {
                gravity = android.view.Gravity.CENTER
            }
            setOnClickListener { togglePlayPause() }
            isFocusable = true
            isFocusableInTouchMode = true
        }
        centerArea.addView(playPauseButton)
        overlay.addView(centerArea)

        // Spacer
        overlay.addView(android.view.View(this).apply {
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        })

        return overlay
    }

    private fun dpToPx(dp: Int): Int {
        val density = resources.displayMetrics.density
        return (dp * density + 0.5f).toInt()
    }
}
