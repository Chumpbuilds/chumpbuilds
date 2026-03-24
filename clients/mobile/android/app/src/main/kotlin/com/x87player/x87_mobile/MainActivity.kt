package com.x87player.x87_mobile

import android.app.Activity
import android.content.Intent
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {

    companion object {
        private const val CHANNEL = "com.x87player/native_player"
        private const val REQUEST_CODE_NATIVE_PLAYER = 1001
    }

    private var pendingResult: MethodChannel.Result? = null

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

                    pendingResult = result
                    val intent = Intent(this, NativePlayerActivity::class.java).apply {
                        putExtra(NativePlayerActivity.EXTRA_URL, url)
                        putExtra(NativePlayerActivity.EXTRA_TITLE, title)
                        putExtra(NativePlayerActivity.EXTRA_CONTENT_TYPE, contentType)
                    }
                    startActivityForResult(intent, REQUEST_CODE_NATIVE_PLAYER)
                } else {
                    result.notImplemented()
                }
            }
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

