package com.x87player.x87_mobile

import android.app.AlertDialog
import android.app.ProgressDialog
import android.content.Context
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.view.View
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.TrackSelectionOverride
import androidx.media3.common.Tracks
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.platform.PlatformView
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

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
 *
 * Subtitle picker is exposed via the `showSubtitlePicker` method call. Flutter
 * callers invoke it with no arguments; the native side searches the subtitle
 * API, shows a selection dialog, downloads and injects the chosen subtitle as
 * a sidecar SRT — the same flow used by [NativePlayerActivity].
 */
class ExoPlayerPlatformView(
    private val context: Context,
    viewId: Int,
    messenger: BinaryMessenger,
    creationParams: Map<*, *>?,
) : PlatformView, MethodChannel.MethodCallHandler {

    private val playerView: PlayerView = PlayerView(context).apply {
        useController = false
        // Ensure the subtitle rendering surface is always visible even when the
        // built-in controller is disabled.
        subtitleView?.visibility = View.VISIBLE
        subtitleView?.setApplyEmbeddedStyles(true)
        subtitleView?.setApplyEmbeddedFontSizes(true)
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

    // ── Subtitle state ────────────────────────────────────────────────────────

    private val mainHandler = Handler(Looper.getMainLooper())

    // The stream URI set at last play() call — needed to rebuild the MediaItem
    // with a subtitle sidecar during subtitle injection.
    private var streamUri: Uri? = null

    // Metadata forwarded from Flutter for online subtitle search.
    private var contentTitle: String = ""
    private var contentYear: String? = null
    private var contentTmdbId: String? = null

    // URI string of the currently injected SRT sidecar, or null if none active.
    private var injectedSrtId: String? = null

    // Deferred runnable used to force-select the SRT track after prepare().
    private var subtitleSelectionRunnable: Runnable? = null

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

                            android.util.Log.i("ExoPlayerPlatformView",
                                "Audio track [$i]: codec=$codec " +
                                "channels=${format.channelCount} " +
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

                // If audio exists but none of it is playable, notify Flutter
                // so it can auto-launch VLC as a fallback player.
                if (hasAnyAudioTrack && !hasPlayableAudio) {
                    android.util.Log.w("ExoPlayerPlatformView",
                        "No playable audio track found. Unsupported codec(s): ${unsupportedCodecs.joinToString()}")
                    channel.invokeMethod("onUnsupportedAudioCodec", mapOf(
                        "codecs" to unsupportedCodecs
                    ))
                }

                // Re-apply the injected SRT override if ExoPlayer re-resolved tracks
                // (e.g. after a manifest refresh) while we still have an active sidecar.
                val srtId = injectedSrtId
                if (srtId != null) {
                    val textGroups = tracks.groups.filter { it.type == C.TRACK_TYPE_TEXT }
                    var targetGroup: Tracks.Group? = null
                    var targetIndex = 0

                    // Strategy 1: find by Format.id (the srtUri string set via setId())
                    outer@ for (group in textGroups) {
                        for (i in 0 until group.length) {
                            if (group.getTrackFormat(i).id == srtId) {
                                targetGroup = group
                                targetIndex = i
                                break@outer
                            }
                        }
                    }

                    // Strategy 2: find by MIME type — injected SRT is always
                    // application/x-subrip; embedded IPTV tracks are WebVTT or TTML.
                    if (targetGroup == null) {
                        outer@ for (group in textGroups) {
                            for (i in 0 until group.length) {
                                if (group.getTrackFormat(i).sampleMimeType == MimeTypes.APPLICATION_SUBRIP) {
                                    targetGroup = group
                                    targetIndex = i
                                    break@outer
                                }
                            }
                        }
                    }

                    if (targetGroup != null && !targetGroup.isTrackSelected(targetIndex)) {
                        android.util.Log.i(
                            "ExoPlayerPlatformView",
                            "onTracksChanged: force-selecting SRT sidecar (id=$srtId, index=$targetIndex)"
                        )
                        player.trackSelectionParameters =
                            player.trackSelectionParameters
                                .buildUpon()
                                .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, false)
                                .clearOverridesOfType(C.TRACK_TYPE_TEXT)
                                .setOverrideForType(
                                    TrackSelectionOverride(
                                        targetGroup.mediaTrackGroup, listOf(targetIndex)
                                    )
                                )
                                .build()
                        playerView.subtitleView?.visibility = View.VISIBLE
                    }
                }
            }
        })

        // Read content metadata from creation params for subtitle search.
        contentTitle = creationParams?.get("title") as? String ?: ""
        contentYear = creationParams?.get("year") as? String
        contentTmdbId = creationParams?.get("tmdbId") as? String

        // Auto-start if url + autoPlay were passed as creation params
        val url = creationParams?.get("url") as? String
        val autoPlay = creationParams?.get("autoPlay") as? Boolean ?: false
        if (!url.isNullOrEmpty()) {
            streamUri = Uri.parse(url)
            player.setMediaItem(MediaItem.fromUri(url))
            player.prepare()
            if (autoPlay) player.playWhenReady = true
        }
    }

    // ── PlatformView ──────────────────────────────────────────────────────────

    override fun getView(): View = playerView

    override fun dispose() {
        subtitleSelectionRunnable?.let { mainHandler.removeCallbacks(it) }
        subtitleSelectionRunnable = null
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
                streamUri = Uri.parse(url)
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
            "showSubtitlePicker" -> {
                showSubtitlePickerDialog()
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

    // ── Subtitle picker (mirrors NativePlayerActivity flow) ───────────────────

    @Suppress("DEPRECATION")
    private fun showSubtitlePickerDialog() {
        if (contentTitle.isBlank()) {
            android.widget.Toast.makeText(context, "No content title for subtitle search", android.widget.Toast.LENGTH_SHORT).show()
            return
        }

        val wasPlaying = player.isPlaying
        player.pause()

        // Read preferred languages from shared preferences (Flutter writes them via
        // the shared_preferences plugin under "FlutterSharedPreferences").
        val flutterPrefs = context.getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
        val langsJson = flutterPrefs.getString("flutter.subtitle_languages", null)
        val langs: List<String> = if (langsJson != null) {
            try {
                val arr = org.json.JSONArray(langsJson)
                (0 until arr.length()).map { arr.getString(it) }
            } catch (e: Exception) {
                android.util.Log.w("ExoPlayerPlatformView", "Failed to parse subtitle language prefs: ${e.message}")
                listOf("en")
            }
        } else { listOf("en") }

        val progressDialog = ProgressDialog(context).apply {
            setMessage("Searching for subtitles...")
            setCancelable(false)
            show()
        }

        Thread {
            data class SubtitleResult(
                val fileId: Int,
                val language: String,
                val release: String,
                val downloadCount: Int,
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

                    if (connection.responseCode == 200) {
                        val body = connection.inputStream.bufferedReader().readText()
                        val arr = org.json.JSONArray(body)
                        for (i in 0 until arr.length()) {
                            val obj = arr.getJSONObject(i)
                            allResults.add(SubtitleResult(
                                fileId = obj.getInt("file_id"),
                                language = obj.optString("language", lang),
                                release = obj.optString("release", ""),
                                downloadCount = obj.optInt("download_count", 0),
                            ))
                        }
                    }
                    connection.disconnect()
                } catch (e: Exception) {
                    android.util.Log.w("ExoPlayerPlatformView", "Subtitle search failed for lang=$lang: ${e.message}")
                }
            }

            mainHandler.post {
                progressDialog.dismiss()

                if (allResults.isEmpty()) {
                    android.widget.Toast.makeText(context, "No subtitles found", android.widget.Toast.LENGTH_SHORT).show()
                    if (wasPlaying) player.play()
                    return@post
                }

                val labels = mutableListOf("Off")
                for (r in allResults) {
                    val downloads = if (r.downloadCount > 0) " (↓${r.downloadCount})" else ""
                    labels.add("[${r.language.uppercase()}] ${r.release}$downloads")
                }

                AlertDialog.Builder(context)
                    .setTitle("Subtitles")
                    .setItems(labels.toTypedArray()) { _, which ->
                        if (which == 0) {
                            // Off — disable subtitles
                            injectedSrtId = null
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
                    .setOnCancelListener { if (wasPlaying) player.play() }
                    .show()
            }
        }.start()
    }

    @Suppress("DEPRECATION")
    private fun downloadAndInjectSubtitle(fileId: Int, lang: String, resumePlayback: Boolean) {
        val uri = streamUri ?: run {
            android.widget.Toast.makeText(context, "No stream URL available", android.widget.Toast.LENGTH_SHORT).show()
            if (resumePlayback) player.play()
            return
        }

        val progressDialog = ProgressDialog(context).apply {
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
                if (connection.responseCode == 200) {
                    srtText = connection.inputStream.bufferedReader().readText()
                }
                connection.disconnect()
            } catch (e: Exception) {
                android.util.Log.w("ExoPlayerPlatformView", "Subtitle download failed for file_id=$fileId: ${e.message}")
            }

            mainHandler.post {
                progressDialog.dismiss()
                if (!srtText.isNullOrBlank()) {
                    injectSrtSubtitle(uri, srtText!!, lang)
                    if (resumePlayback) player.play()
                } else {
                    android.widget.Toast.makeText(context, "Failed to download subtitle", android.widget.Toast.LENGTH_SHORT).show()
                    if (resumePlayback) player.play()
                }
            }
        }.start()
    }

    private fun injectSrtSubtitle(videoUri: Uri, srtContent: String, langCode: String) {
        try {
            val cacheDir = context.cacheDir
            val srtFile = File(cacheDir, "subtitle_${langCode}_${System.currentTimeMillis()}.srt")
            srtFile.writeText(srtContent)

            val savedPosition = player.currentPosition
            val wasPlaying = player.isPlaying

            val srtUri = Uri.fromFile(srtFile)
            val subtitleConfig = MediaItem.SubtitleConfiguration.Builder(srtUri)
                .setMimeType(MimeTypes.APPLICATION_SUBRIP)
                .setLanguage(langCode)
                .setSelectionFlags(C.SELECTION_FLAG_DEFAULT or C.SELECTION_FLAG_FORCED)
                .setId(srtUri.toString())
                .build()

            val newMediaItem = MediaItem.Builder()
                .setUri(videoUri)
                .setSubtitleConfigurations(listOf(subtitleConfig))
                .build()

            subtitleSelectionRunnable?.let { mainHandler.removeCallbacks(it) }
            subtitleSelectionRunnable = null

            injectedSrtId = srtUri.toString()

            player.trackSelectionParameters = player.trackSelectionParameters
                .buildUpon()
                .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, false)
                .clearOverridesOfType(C.TRACK_TYPE_TEXT)
                .build()

            player.setMediaItem(newMediaItem)
            player.prepare()
            player.seekTo(savedPosition)
            if (wasPlaying) player.play()

            android.util.Log.i("ExoPlayerPlatformView", "Subtitle injected: lang=$langCode uri=$srtUri")
        } catch (e: Exception) {
            android.widget.Toast.makeText(context, "Failed to load subtitles: ${e.message}", android.widget.Toast.LENGTH_SHORT).show()
        }
    }
}
