// Original launcher for the external GPL-3.0 application. No upstream code is
// copied here. Generation, atlas fitting, rigging and export are upstream APIs.
package io.github.psd2live.vtsbridge

import io.github.psd2live.core.AtlasBudget
import io.github.psd2live.core.MeshUnits
import io.github.psd2live.core.PipelineConfig
import io.github.psd2live.core.PSD2LivePipeline
import io.github.psd2live.core.ProgressListener
import io.github.psd2live.core.TextureUpscaleConfig
import io.github.psd2live.i18n.AppLanguage
import io.github.psd2live.i18n.I18n
import kotlinx.serialization.json.*
import org.umamo.format.art.LayerBounds
import org.umamo.format.art.SourceArt
import org.umamo.format.art.SourceLayer
import org.umamo.format.psd.PsdReader
import java.nio.file.Files
import java.nio.file.Path
import kotlin.math.roundToInt

/**
 * AtlasLayout can enlarge a requested page to hold a layer's canvas extent.
 * For oversized FREE art, normalize only the canvas coordinate system. The
 * upstream dense-raster source abstraction keeps every original raster byte
 * and lets the official packer resample textures exactly once at the final fit.
 * Typical 1280px See-through art follows the unchanged path (scale=1).
 */
private fun canvasForBudget(source: SourceArt, budget: AtlasBudget): Pair<SourceArt, Double> {
    if (budget.maxPages != 1) return source to 1.0
    val largest = source.layers.maxOfOrNull { maxOf(it.bounds.width, it.bounds.height) } ?: 0
    val available = budget.pageSize - 2 * budget.padding
    if (largest <= available) return source to 1.0
    val scale = (available - 1).toDouble() / largest
    fun coordinate(value: Int) = (value * scale).roundToInt()
    val scaledLayers = source.layers.map { layer ->
        val b = layer.bounds
        val left = coordinate(b.left)
        val top = coordinate(b.top)
        val width = if (b.width == 0) 0 else (coordinate(b.left + b.width) - left).coerceAtLeast(1)
        val height = if (b.height == 0) 0 else (coordinate(b.top + b.height) - top).coerceAtLeast(1)
        object : SourceLayer by layer {
            override val bounds = LayerBounds(left, top, width, height)
        }
    }
    val normalized = object : SourceArt by source {
        override val layers = scaledLayers
        override val widthPx = coordinate(source.widthPx).coerceAtLeast(1)
        override val heightPx = coordinate(source.heightPx).coerceAtLeast(1)
    }
    return normalized to scale
}

fun main(arguments: Array<String>) {
    require(arguments.size % 2 == 0) { "Every VTS launcher option requires a value" }
    val options = arguments.toList().chunked(2).associate { it[0] to it[1] }
    require(options.size * 2 == arguments.size) { "Duplicate VTS launcher option" }
    val allowed = setOf("--input", "--output", "--atlas", "--atlas-pages", "--lang",
        "--mesh-spacing", "--mesh-wrap", "--head-strength", "--body-strength", "--upscale",
        "--upscale-python", "--nunif-dir", "--upscale-model", "--mouth-outline")
    require(options.keys.all { it in allowed }) { "Unknown VTS launcher option" }
    fun value(key: String) = requireNotNull(options[key]) { "Missing $key" }
    I18n.setLanguage(requireNotNull(AppLanguage.fromTag(value("--lang"))))
    val input = Path.of(value("--input"))
    val output = Path.of(value("--output"))
    val budget = AtlasBudget(value("--atlas").toInt(), value("--atlas-pages").toInt(), 2)
    val config = PipelineConfig(
        atlasSize = budget.pageSize,
        atlasBudget = budget,
        textureUpscale = TextureUpscaleConfig(
            scale = value("--upscale").toInt(),
            python = options["--upscale-python"] ?: TextureUpscaleConfig.defaultPython,
            nunifDirectory = options["--nunif-dir"] ?: "",
            modelDirectory = options["--upscale-model"] ?: "",
        ),
        meshSpacing = value("--mesh-spacing").toInt(),
        meshUnits = MeshUnits.DOCUMENT,
        meshWrap = value("--mesh-wrap").toFloat(),
        headTurnStrength = value("--head-strength").toFloat(),
        bodyStrength = value("--body-strength").toFloat(),
        // Authored mouth/lip art is already drawn. Auto-generated lip outlines
        // superimpose another mouth over those pixels.
        mouthOutlineEnabled = when (value("--mouth-outline")) {
            "true" -> true
            "false" -> false
            else -> error("--mouth-outline must be true or false")
        },
    )
    val original = PsdReader.read(Files.readAllBytes(input))
    val (source, canvasScale) = canvasForBudget(original, budget)
    println("[VTS ATLAS BUDGET] size=${budget.pageSize} pages=${budget.maxPages} padding=${budget.padding} canvasScale=$canvasScale")
    val progress = ProgressListener { stage, fraction ->
        println("%3d%%  %s".format((fraction * 100).toInt(), stage))
    }
    val pipeline = PSD2LivePipeline()
    val model = pipeline.buildPreview(source, config, progress)
    val atlas = model.atlas
    // Check the actual solution before writing any model, including the
    // upstream emergency fallback that can exceed an unsatisfiable budget.
    require(atlas.pages.isNotEmpty() && atlas.pages.size <= budget.maxPages &&
        atlas.pages.all { it.image.width <= budget.pageSize && it.image.height <= budget.pageSize }) {
        "PSD2LIVE_ATLAS_BUDGET_UNSATISFIED: ${atlas.notices.joinToString()}"
    }
    val result = pipeline.export(model, input.fileName.toString(), output, progress)
    val report = buildJsonObject {
        put("schema", "vtuber/psd2live-atlas-v1")
        put("page_size", budget.pageSize); put("max_pages", budget.maxPages); put("padding", budget.padding)
        put("fit", atlas.fit)
        put("source_layer_count", original.layers.size); put("packed_layer_count", atlas.placementByLayerId.size)
        put("canvas_coordinate_scale", canvasScale)
        put("source_rasters_preserved", true); put("artwork_resized", false)
        putJsonArray("pages") {
            atlas.pages.forEach { page -> add(buildJsonObject {
                putJsonArray("size") { add(page.image.width); add(page.image.height) }
            }) }
        }
        putJsonArray("warnings") { (atlas.notices + result.warnings).distinct().forEach { add(it) } }
    }
    Files.writeString(output.resolve("vts_atlas.json"), Json { prettyPrint = true }.encodeToString(JsonElement.serializer(), report))
    println("[VTS ATLAS FIT] layers=${atlas.placementByLayerId.size} pages=${atlas.pages.size} fit=${atlas.fit}")
    result.exportedFiles.forEach { println("  ${it.path.toAbsolutePath()} (${it.bytes} bytes)") }
    (atlas.notices + result.warnings).distinct().forEach { System.err.println(it) }
}
