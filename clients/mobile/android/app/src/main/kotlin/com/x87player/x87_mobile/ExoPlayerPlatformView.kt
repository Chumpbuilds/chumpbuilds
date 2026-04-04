package com.x87player.x87_mobile

import android.content.Context
import android.view.View
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.common.StandardMessageCodec
import io.flutter.plugin.platform.PlatformView

/**
 * Embedded ExoPlayer surface rendered inline inside the Flutter widget tree
 * via the PlatformView mechanism.
 *
 * One instance is created per Flutter [AndroidView] (i.e. per
 * [EmbeddedExoPlayerWidget]). Playback control messages arrive on a dedicated
 * per-view [MethodChannel] named
 * `com.x87player/exo_player_view/<viewId>`.
 *
 * Playback state changes are pushed back to Flutter on the same channel as
 * method calls named `onPlaybackStateChanged` with a map payload:
 * ```
 * {
 *   "isPlaying":    bool,
 *   "isBuffering":  bool,
 *   "hasError":     bool,
 *   "errorMessage": String?
 * }
 * ```
 */
class ExoPlayerPlatformView(
    private val context: Context,
    viewId: Int,
    messenger: BinaryMessenger,
    creationParams: Map<*, *>?,
) : PlatformView, MethodChannel.MethodCallHandler {

    private val playerView: PlayerView = PlayerView(context).apply {
        useController = false
    }

    private val player = run {
        val isTv = ExoPlayerFactory.isTvOrAmlogicDevice(context)
        android.util.Log.i(
            "ExoPlayerPlatformView",
            "viewId=$viewId isTv=$isTv manufacturer=${android.os.Build.MANUFACTURER} " +
            "model=${android.os.Build.MODEL}"
        )
        ExoPlayerFactory.build(context, isTv)
    }

    private val channel = MethodChannel(
        messenger,
        "com.x87player/exo_player_view/$viewId"
    )

    init {
        channel.setMethodCallHandler(this)

        playerView.player = player

        playerView.setOnClickListener {
            channel.invokeMethod("onTapped", null)
        }

        player.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) {
                sendStateUpdate()
            }
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                sendStateUpdate()
            }
            override fun onPlayerError(error: PlaybackException) {
                sendStateUpdate(hasError = true, errorMessage = error.message)
            }
        })

        // Auto-start if url + autoPlay were passed as creation params
        val url = creationParams?.get("url") as? String
        val autoPlay = creationParams?.get("autoPlay") as? Boolean ?: false
        if (!url.isNullOrEmpty()) {
            player.setMediaItem(MediaItem.fromUri(url))
            player.prepare()
            if (autoPlay) player.playWhenReady = true
        }
    }

    // ── PlatformView ──────────────────────────────────────────────────────────

    override fun getView(): View = playerView

    override fun dispose() {
        channel.setMethodCallHandler(null)
        player.release()
    }

    // ── MethodChannel.MethodCallHandler ───────────────────────────────────────

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "play" -> {
                val url = call.argument<String>("url") ?: run {
                    result.error("INVALID_ARGS", "url is required", null)
                    return
                }
                player.setMediaItem(MediaItem.fromUri(url))
                player.prepare()
                player.playWhenReady = true
                result.success(null)
            }
            "pause" -> {
                player.pause()
                result.success(null)
            }
            "resume" -> {
                player.play()
                result.success(null)
            }
            "stop" -> {
                player.stop()
                result.success(null)
            }
            "setVolume" -> {
                val volume = call.argument<Double>("volume")?.toFloat()
                    ?: call.argument<Int>("volume")?.toFloat()?.div(100f)
                    ?: 1f
                player.volume = volume.coerceIn(0f, 1f)
                result.success(null)
            }
            "toggleMute" -> {
                player.volume = if (player.volume > 0f) 0f else 1f
                result.success(null)
            }
            "setResizeMode" -> {
                val mode = call.argument<Int>("mode") ?: AspectRatioFrameLayout.RESIZE_MODE_FIT
                playerView.resizeMode = mode
                result.success(null)
            }
            "dispose" -> {
                dispose()
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private fun sendStateUpdate(
        hasError: Boolean = false,
        errorMessage: String? = null,
    ) {
        val isBuffering = player.playbackState == Player.STATE_BUFFERING
        channel.invokeMethod(
            "onPlaybackStateChanged",
            mapOf(
                "isPlaying"    to player.isPlaying,
                "isBuffering"  to isBuffering,
                "hasError"     to hasError,
                "errorMessage" to errorMessage,
            )
        )
    }
}
