package com.x87player.x87_mobile

import android.content.Context
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.StandardMessageCodec
import io.flutter.plugin.platform.PlatformView
import io.flutter.plugin.platform.PlatformViewFactory

/**
 * Factory that creates [ExoPlayerPlatformView] instances on behalf of the
 * Flutter engine. Registered in [MainActivity.configureFlutterEngine] under
 * the view type `com.x87player/exo_player_view`.
 */
class ExoPlayerPlatformViewFactory(
    private val messenger: BinaryMessenger,
) : PlatformViewFactory(StandardMessageCodec.INSTANCE) {

    override fun create(context: Context, viewId: Int, args: Any?): PlatformView {
        @Suppress("UNCHECKED_CAST")
        val params = args as? Map<*, *>
        return ExoPlayerPlatformView(context, viewId, messenger, params)
    }
}
