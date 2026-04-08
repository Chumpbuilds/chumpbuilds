package com.x87player.x87_mobile

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.view.WindowManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {

    companion object {
        private const val CHANNEL = "com.x87player/native_player"
        private const val REQUEST_CODE_NATIVE_PLAYER = 1001
    }

    private var pendingResult: MethodChannel.Result? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        applyOpaqueSystemBars()
    }

    override fun onResume() {
        super.onResume()
        // Re-apply after resume since Flutter may reset flags
        applyOpaqueSystemBars()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) {
            // Re-apply when window regains focus (after notification shade dismissed)
            applyOpaqueSystemBars()
        }
    }

    /**
     * Forces the status bar and navigation bar backgrounds to solid black
     * by working at the native Window level, overriding Flutter's edge-to-edge
     * flags that cause SUPPRESS_SCRIM.
     */
    private fun applyOpaqueSystemBars() {
        val window = window ?: return

        // Clear translucent flags that force transparency
        window.clearFlags(WindowManager.LayoutParams.FLAG_TRANSLUCENT_STATUS)
        window.clearFlags(WindowManager.LayoutParams.FLAG_TRANSLUCENT_NAVIGATION)

        // Ensure the window draws system bar backgrounds
        window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS)

        // Set opaque black colors at the native window level
        window.statusBarColor = Color.BLACK
        window.navigationBarColor = Color.BLACK
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                if (call.method == "launchPlayer") {
                    val url = call.argument<String>("url") ?: run {
                        result.error("INVALID_ARGS", "url is required", null)
                        return@setMethodCallHandler
                    }
                    val title = call.argument<String>("title") ?: ""
                    val contentType = call.argument<String>("contentType") ?: "live"
                    val year = call.argument<String>("year")
                    val tmdbId = call.argument<String>("tmdbId")

                    pendingResult = result
                    val intent = Intent(this, NativePlayerActivity::class.java).apply {
                        putExtra(NativePlayerActivity.EXTRA_URL, url)
                        putExtra(NativePlayerActivity.EXTRA_TITLE, title)
                        putExtra(NativePlayerActivity.EXTRA_CONTENT_TYPE, contentType)
                        if (year != null) putExtra(NativePlayerActivity.EXTRA_YEAR, year)
                        if (tmdbId != null) putExtra(NativePlayerActivity.EXTRA_TMDB_ID, tmdbId)
                    }
                    startActivityForResult(intent, REQUEST_CODE_NATIVE_PLAYER)
                } else if (call.method == "isTvDevice") {
                    result.success(ExoPlayerFactory.isTvOrAmlogicDevice(this))
                } else {
                    result.notImplemented()
                }
            }

        // ── Embedded inline player (AndroidView / PlatformView) ───────────────
        flutterEngine.platformViewsController.registry
            .registerViewFactory(
                "com.x87player/exo_player_view",
                ExoPlayerPlatformViewFactory(flutterEngine.dartExecutor.binaryMessenger)
            )
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_CODE_NATIVE_PLAYER) {
            val result = pendingResult
            pendingResult = null
            if (resultCode == Activity.RESULT_OK) {
                result?.success("completed")
            } else {
                result?.success("dismissed")
            }
        }
    }
}

