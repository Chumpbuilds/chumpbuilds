package com.x87player.x87_mobile

import android.content.Context
import android.content.res.Configuration
import android.os.Build
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.exoplayer.trackselection.DefaultTrackSelector

/**
 * Shared ExoPlayer builder used by both [NativePlayerActivity] (fullscreen)
 * and [ExoPlayerPlatformView] (embedded inline in Flutter widget tree).
 *
 * Device detection and all codec/track-selector configuration live here so
 * that the two playback paths always behave identically.
 */
object ExoPlayerFactory {

    internal const val USER_AGENT = "X87-IPTV-Player/1.0"
    private const val HTTP_CONNECT_TIMEOUT_MS = 15_000
    private const val HTTP_READ_TIMEOUT_MS = 15_000

    /**
     * Returns true when running on an Android TV, Amlogic-based box, or
     * Amazon Fire Stick — devices that advertise tunneling / audio-offload
     * support but implement it incorrectly in firmware.
     */
    fun isTvOrAmlogicDevice(context: Context): Boolean {
        val uiModeManager = context.getSystemService(android.app.UiModeManager::class.java)
        if (uiModeManager?.currentModeType == Configuration.UI_MODE_TYPE_TELEVISION) {
            return true
        }
        val hardware = Build.HARDWARE.lowercase()
        val board = Build.BOARD.lowercase()
        val manufacturer = Build.MANUFACTURER.lowercase()
        val model = Build.MODEL.lowercase()
        if (hardware.contains("amlogic") || board.contains("amlogic") ||
            hardware.contains("meson") || board.contains("meson")) {
            return true
        }
        if (manufacturer == "amazon" && model.contains("fire")) {
            return true
        }
        return false
    }

    /**
     * Builds a fully-configured [ExoPlayer] instance.
     *
     * @param context  Android [Context] — an Activity or Application context.
     * @param isTvDevice  Pass the result of [isTvOrAmlogicDevice] to avoid
     *                    calling it twice in the same setup sequence.
     */
    fun build(context: Context, isTvDevice: Boolean): ExoPlayer {
        val renderersFactory = DefaultRenderersFactory(context).apply {
            setExtensionRendererMode(DefaultRenderersFactory.EXTENSION_RENDERER_MODE_ON)
            setEnableDecoderFallback(true)
            if (isTvDevice) {
                setEnableAudioTrackPlaybackParams(false)
            } else {
                setEnableAudioTrackPlaybackParams(true)
            }
        }

        val trackSelector = DefaultTrackSelector(context).apply {
            parameters = buildUponParameters()
                .setTunnelingEnabled(!isTvDevice)
                .build()
        }

        val httpDataSourceFactory = DefaultHttpDataSource.Factory()
            .setUserAgent(USER_AGENT)
            .setConnectTimeoutMs(HTTP_CONNECT_TIMEOUT_MS)
            .setReadTimeoutMs(HTTP_READ_TIMEOUT_MS)
            .setAllowCrossProtocolRedirects(true)

        val mediaSourceFactory = DefaultMediaSourceFactory(httpDataSourceFactory)

        return ExoPlayer.Builder(context, renderersFactory)
            .setTrackSelector(trackSelector)
            .setMediaSourceFactory(mediaSourceFactory)
            .build()
    }
}
