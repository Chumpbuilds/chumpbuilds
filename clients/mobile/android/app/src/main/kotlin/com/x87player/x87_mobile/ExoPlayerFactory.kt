package com.x87player.x87_mobile

import android.content.Context
import android.content.res.Configuration
import android.os.Build
import androidx.media3.common.MimeTypes
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
            // Use EXTENSION_RENDERER_MODE_ON for all devices. PREFER was only useful
            // when the FFmpeg extension (media3-decoder-ffmpeg) was present to provide
            // software AC3/EAC3 decoders; without it PREFER has no benefit and may
            // unnecessarily delay hardware decoder selection. The AudioAttributes fix
            // below is now responsible for forcing PCM output on TV/Amlogic devices.
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
                .apply {
                    if (isTvDevice) {
                        // Prefer stereo over surround — many cheap boxes/TVs can't
                        // decode or downmix 5.1 AC3/EAC3 properly via HDMI.
                        setMaxAudioChannelCount(2)

                        // Prefer AAC over AC3/EAC3 — AAC is universally decoded in
                        // software, while AC3 passthrough depends on HDMI sink caps.
                        setPreferredAudioMimeType(MimeTypes.AUDIO_AAC)

                        // Allow non-seamless adaptation so ExoPlayer can switch to a
                        // working audio track mid-stream if the initial one fails.
                        setAllowAudioMixedMimeTypeAdaptiveness(true)
                    }
                }
                .build()
        }

        android.util.Log.i("ExoPlayerFactory",
            "TrackSelector config: tunneling=${!isTvDevice}, " +
            "maxAudioChannels=${if (isTvDevice) 2 else "unlimited"}, " +
            "preferredAudioMime=${if (isTvDevice) MimeTypes.AUDIO_AAC else "default"}, " +
            "extensionRendererMode=ON, " +
            "audioPassthrough=${if (isTvDevice) "disabled(PCM)" else "default"}")

        val httpDataSourceFactory = DefaultHttpDataSource.Factory()
            .setUserAgent(USER_AGENT)
            .setConnectTimeoutMs(HTTP_CONNECT_TIMEOUT_MS)
            .setReadTimeoutMs(HTTP_READ_TIMEOUT_MS)
            .setAllowCrossProtocolRedirects(true)

        val mediaSourceFactory = DefaultMediaSourceFactory(httpDataSourceFactory)

        val player = ExoPlayer.Builder(context, renderersFactory)
            .setTrackSelector(trackSelector)
            .setMediaSourceFactory(mediaSourceFactory)
            .build()
            .apply {
                if (isTvDevice) {
                    // Force CONTENT_TYPE_MUSIC with USAGE_MEDIA — this tells the Android
                    // audio system to use a standard PCM audio path rather than attempting
                    // HDMI passthrough for AC3/EAC3 bitstreams. On Amlogic boxes, the
                    // passthrough path silently fails when the connected TV doesn't
                    // support the codec, producing no audio.
                    setAudioAttributes(
                        androidx.media3.common.AudioAttributes.Builder()
                            .setContentType(androidx.media3.common.C.AUDIO_CONTENT_TYPE_MUSIC)
                            .setUsage(androidx.media3.common.C.USAGE_MEDIA)
                            .build(),
                        /* handleAudioFocus= */ true
                    )
                }
            }
        return player
    }
}
