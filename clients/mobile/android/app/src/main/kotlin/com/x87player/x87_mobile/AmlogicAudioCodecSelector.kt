package com.x87player.x87_mobile

import android.media.MediaCodecList
import android.os.Build
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.mediacodec.MediaCodecInfo
import androidx.media3.exoplayer.mediacodec.MediaCodecSelector

/**
 * Custom [MediaCodecSelector] that force-discovers hidden Amlogic audio decoders
 * for AC3, EAC3, and DTS MIME types.
 *
 * Many Amlogic/Droidlogic TV boxes have working hardware decoders for Dolby audio
 * (e.g. `OMX.amlogic.ac3.decoder.awesome`, `OMX.amlogic.eac3.decoder.awesome`)
 * that are not returned by [MediaCodecList.REGULAR_CODECS] because they don't pass
 * Android's standard compatibility tests. However, they work perfectly for IPTV
 * playback — apps like XCIPTV use these decoders successfully.
 *
 * DTS streams ([MimeTypes.AUDIO_DTS], [MimeTypes.AUDIO_DTS_HD],
 * [MimeTypes.AUDIO_DTS_EXPRESS]) are also intercepted so that the FFmpeg
 * software decoder extension can be discovered when no hardware DTS decoder
 * is present on the device.
 *
 * This selector uses [MediaCodecList.ALL_CODECS] to find these hidden decoders
 * and returns them to ExoPlayer. For all other MIME types it falls back to
 * [MediaCodecSelector.DEFAULT].
 */
@UnstableApi
class AmlogicAudioCodecSelector : MediaCodecSelector {

    override fun getDecoderInfos(
        mimeType: String,
        requiresSecureDecoder: Boolean,
        requiresTunnelingDecoder: Boolean
    ): List<MediaCodecInfo> {
        // Only intercept AC3, EAC3, and DTS audio
        if (mimeType != MimeTypes.AUDIO_AC3 &&
            mimeType != MimeTypes.AUDIO_E_AC3 &&
            mimeType != MimeTypes.AUDIO_E_AC3_JOC &&
            mimeType != MimeTypes.AUDIO_DTS &&
            mimeType != MimeTypes.AUDIO_DTS_HD &&
            mimeType != MimeTypes.AUDIO_DTS_EXPRESS) {
            return MediaCodecSelector.DEFAULT.getDecoderInfos(
                mimeType, requiresSecureDecoder, requiresTunnelingDecoder
            )
        }

        val result = mutableListOf<MediaCodecInfo>()

        // First: try the default selector — if it finds decoders, use them
        val defaultDecoders = MediaCodecSelector.DEFAULT.getDecoderInfos(
            mimeType, requiresSecureDecoder, requiresTunnelingDecoder
        )
        result.addAll(defaultDecoders)

        // If we already have decoders from the default selector, return them
        if (result.isNotEmpty()) {
            android.util.Log.i("AmlogicCodecSelector",
                "Default selector found ${result.size} decoder(s) for $mimeType: " +
                result.joinToString { it.name })
            return result
        }

        // Default selector found nothing — enumerate ALL codecs to find hidden ones
        android.util.Log.i("AmlogicCodecSelector",
            "No default decoders for $mimeType — scanning ALL_CODECS...")

        val allCodecs = MediaCodecList(MediaCodecList.ALL_CODECS).codecInfos
        for (codecInfo in allCodecs) {
            if (codecInfo.isEncoder) continue

            // Check if this codec supports our MIME type
            val supportsMime = codecInfo.supportedTypes.any {
                it.equals(mimeType, ignoreCase = true)
            }
            if (!supportsMime) continue

            // isVendor and isSoftwareOnly require API 29+
            val isVendor = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && codecInfo.isVendor
            val isSoftwareOnly = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && codecInfo.isSoftwareOnly
            val isHardware = !isSoftwareOnly

            android.util.Log.i("AmlogicCodecSelector",
                "Found decoder: ${codecInfo.name} for $mimeType (vendor=$isVendor)")

            try {
                val exoInfo = MediaCodecInfo.newInstance(
                    /* name= */ codecInfo.name,
                    /* mimeType= */ mimeType,
                    /* codecMimeType= */ mimeType,
                    /* capabilities= */ codecInfo.getCapabilitiesForType(mimeType),
                    /* hardwareAccelerated= */ isHardware,
                    /* softwareOnly= */ isSoftwareOnly,
                    /* vendor= */ isVendor,
                    /* forceDisableAdaptive= */ false,
                    /* forceSecure= */ false
                )
                result.add(exoInfo)
            } catch (e: Exception) {
                android.util.Log.w("AmlogicCodecSelector",
                    "Failed to create MediaCodecInfo for ${codecInfo.name}: ${e.message}")
            }
        }

        if (result.isEmpty()) {
            android.util.Log.w("AmlogicCodecSelector",
                "No decoders found for $mimeType even in ALL_CODECS")

            // Last resort: if the MIME is EAC3, try finding an AC3 decoder
            // since EAC3 is backward-compatible with AC3
            if (mimeType == MimeTypes.AUDIO_E_AC3 || mimeType == MimeTypes.AUDIO_E_AC3_JOC) {
                android.util.Log.i("AmlogicCodecSelector",
                    "Trying AC3 decoders as fallback for EAC3...")
                val ac3Decoders = getDecoderInfos(
                    MimeTypes.AUDIO_AC3, requiresSecureDecoder, requiresTunnelingDecoder
                )
                result.addAll(ac3Decoders)
            }

            // Last resort: if the MIME is DTS-HD or DTS-Express, try finding a
            // base DTS decoder since DTS-HD carries a backward-compatible DTS core.
            if (mimeType == MimeTypes.AUDIO_DTS_HD || mimeType == MimeTypes.AUDIO_DTS_EXPRESS) {
                android.util.Log.i("AmlogicCodecSelector",
                    "Trying DTS decoders as fallback for $mimeType...")
                val dtsDecoders = getDecoderInfos(
                    MimeTypes.AUDIO_DTS, requiresSecureDecoder, requiresTunnelingDecoder
                )
                result.addAll(dtsDecoders)
            }
        }

        android.util.Log.i("AmlogicCodecSelector",
            "Returning ${result.size} decoder(s) for $mimeType: " +
            result.joinToString { it.name })

        return result
    }
}
