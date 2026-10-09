"""Build honest, editable Cubism PSD artwork; never claim native rigging.

Qwen is used as a *mask proposal* on See-through layers. Visible pixels are
copied from the high-resolution See-through input without regeneration. A Qwen
proposal is adopted only when it makes a nontrivial, valid partition and the
reconstructed source layer is pixel-equivalent. No synthetic ArtMeshes, physics
or .moc3 files are emitted.
"""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
from PIL import Image

ASSETS = ("body", "hair", "outfit", "accessory")
FREE_LIMIT = 100
FREE_BUDGET = {
    "art_mesh_max": 100, "part_folders_max": 30, "deformers_max": 50,
    "parameters_max": 30, "blendshape_parameters_max": 3,
    "art_paths_max": 3, "texture_atlas_count_max": 1,
    "texture_atlas_edge_px_max": 2048,
}


def _read_registered(path: Path):
    with ZipFile(path) as z:
        files = [n for n in z.namelist() if n.endswith(".png")]
        layers = []
        size = None
        for name in files:
            with Image.open(BytesIO(z.read(name))) as image:
                image.load()
                if image.mode != "RGBA":
                    raise ValueError("Layer must have actual RGBA transparency")
                if size is not None and image.size != size:
                    raise ValueError("Layers do not share an aligned canvas")
                size = image.size
                if image.getchannel("A").getbbox():
                    layers.append({"name": Path(name).stem, "image": image.copy(),
                                   "depth": 0})
    if not layers:
        raise ValueError("PSD extraction produced no nonempty drawable layers")
    return layers, size


def _candidate_score(part):
    name = part["name"].lower()
    group = name.split(".", 1)[0]
    if group not in {"hair", "eye", "eyebrow", "mouth", "face", "cloth", "body",
                     "ornament", "accessory", "sleeve", "arm", "hand", "leg",
                     "foot", "ear", "neck", "nose", "shoe", "outfit", "head"}:
        return -1
    if not group:
        return -1
    alpha = np.asarray(part["image"].getchannel("A"))
    pixel_count = int(np.count_nonzero(alpha > 16))
    if pixel_count < 64:
        return -1
    priority = {"hair": 5, "eye": 5, "mouth": 5, "face": 4,
                "cloth": 4, "sleeve": 4, "body": 3,
                "ornament": 3, "accessory": 3}.get(group, 0)
    return priority * 10**9 + pixel_count


def _partition_part(part, suggestions):
    """Use Qwen alpha as labels, preserve all observed original RGBA pixels.

    This does not pretend to reconstruct missing occluded imagery; See-through
    remains responsible for its own hidden-layer restoration.
    """
    source = part["image"]
    bbox = source.getchannel("A").getbbox()
    if bbox is None or len(suggestions) < 2:
        return None
    crop = source.crop(bbox)
    ow, oh = crop.size
    if ow < 4 or oh < 4:
        return None
    proposal_masks = []
    inference_scale = 640 / max(ow, oh)
    rounded_size = tuple(max(int(round(dim * inference_scale / 16)) * 16, 16)
                         for dim in (ow, oh))
    for path in suggestions:
        with Image.open(path) as im:
            im.load()
            if im.mode != "RGBA":
                raise ValueError("Qwen output must be genuine RGBA")
            # Reject a prediction with a changed aspect, rather than
            # silently stretching a different character's output.
            ratio_error = abs(im.width / im.height - ow / oh) / (ow / oh)
            # The pinned worker rounds each dimension to a multiple of 16.
            # Thin strands can therefore differ in aspect by much more than
            # 8%, while still being registered to this exact source crop.
            if ratio_error > .08 and im.size != rounded_size:
                return None
            region = im.getchannel("A").resize((ow, oh), Image.Resampling.BILINEAR)
            proposal_masks.append(np.asarray(region, dtype=np.uint8))
    candidate = np.stack(proposal_masks, axis=0)
    original = np.asarray(crop, dtype=np.uint8)
    valid = original[:, :, 3] > 8
    if int(valid.sum()) < 64:
        return None
    has_proposal = candidate.max(axis=0) > 24
    if (valid & has_proposal).sum() < .75 * valid.sum():
        return None
    # Stable-Layers' published order is background first, then foreground
    # objects. The background alpha can be opaque across the whole crop,
    # so a plain argmax would absorb foreground into the background.
    objects = candidate[1:]
    object_best = np.max(objects, axis=0)
    # Foreground objects are ordered back-to-front. Equal alpha must go
    # to the last (frontmost) proposal, not swallow it into an opaque rear.
    index = (len(objects) - np.argmax(objects[::-1], axis=0)).astype(np.int32)
    index[object_best <= 24] = 0
    distribution = [int(np.count_nonzero(valid & (index == i)))
                    for i in range(len(proposal_masks))]
    relevant = [i for i, amount in enumerate(distribution)
                if amount >= max(24, int(.04 * valid.sum()))]
    if len(relevant) < 2:
        return None
    # Re-assign all pixels (including translucent edge pixels) to accepted
    # masks. Source RGBA values are copied, not upscaled Qwen colors.
    # When small fragments are filtered out, recover their visible pixels
    # by assigning them to the nearest accepted *semantic* mask, not by
    # painting over the source RGB/alpha.
    accepted = np.zeros_like(index, dtype=np.int32)
    for rank, original_index in enumerate(relevant):
        accepted[index == original_index] = rank
    unassigned = ~np.isin(index, np.asarray(relevant, dtype=np.int32))
    if np.any(unassigned):
        accepted[unassigned] = candidate[relevant][:, unassigned].argmax(axis=0)
    children = []
    for rank, original_index in enumerate(relevant):
        segment = np.zeros_like(original)
        segment[accepted == rank] = original[accepted == rank]
        if not np.any(segment[:, :, 3]):
            continue
        canvas = Image.new("RGBA", source.size, (0, 0, 0, 0))
        canvas.paste(Image.fromarray(segment, "RGBA"), bbox[:2])
        children.append({"name": part["name"] + ".q" + str(rank + 1),
                         "image": canvas, "depth": part["depth"] + 1})
    if len(children) < 2:
        return None
    # Disjoint masks must reproduce every original source pixel exactly.
    verified = np.zeros_like(original)
    for child in children:
        frag = np.asarray(child["image"].crop(bbox), dtype=np.uint8)
        occupied = frag[:, :, 3] > 0
        verified[occupied] = frag[occupied]
    if not np.array_equal(verified, original):
        return None
    return children


def _write_psd(parts, target: Path, *, free: bool):
    """Preserve the original visual z-order while adding navigable part groups.

    Group by contiguous semantic runs only. Consolidating all "hair" parts
    globally changes interleaved eyes/bangs/face drawing order.
    """
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    psd = PSDImage.new("RGB", parts[0]["image"].size, depth=8)
    group = None
    active_family = None
    groups = 0
    for part in reversed(parts):  # input is top-to-bottom, PSD appends bottom-up
        family = part["name"].split(".", 1)[0].upper()
        if family != active_family and (not free or groups < 30):
            group = psd.create_group(name=family)
            active_family = family
            groups += 1
        if group is None:
            raise RuntimeError("No PSD group for part")
        # psd-tools 1.14.x exposes PixelLayer.frompil(parent=group).
        # Some versions do not expose Group.create_pixel_layer.
        PixelLayer.frompil(part["image"], parent=group,
                           name=part["name"], top=0, left=0)
    target.parent.mkdir(parents=True, exist_ok=True)
    psd.save(str(target))
    if target.read_bytes()[:4] != b"8BPS":
        raise RuntimeError("Output is not a native layered PSD")
    document = PSDImage.open(str(target))
    leaves = [x for x in document.descendants() if not x.is_group()]
    if len(leaves) != len(parts):
        raise RuntimeError("PSD lost drawable layers on serialization")
    return groups


def _texture_budget(layers, edition: str):
    """Necessary area/edge bounds, never a claim of successful Editor packing."""
    padding = 2  # estimate only; Editor mesh margins may need more
    sizes = []
    for layer in layers:
        left, top, right, bottom = layer["image"].getchannel("A").getbbox()
        sizes.append((right - left, bottom - top))
    area = sum(w * h for w, h in sizes)
    padded_area = sum((w + 2 * padding) * (h + 2 * padding) for w, h in sizes)
    edge = 2048 if edition == "free" else None
    impossible = None
    scale = None
    if edge is not None:
        impossible = area > edge * edge or any(max(w, h) > edge for w, h in sizes)
        # Ignore padding for a strict necessary upper bound; including fixed
        # padding inside sqrt(area) would not be a valid scaling bound.
        scale = min(1.0, (edge * edge / area) ** .5,
                    min(edge / max(w, h) for w, h in sizes))
    report = {
        "schema": "vtuber/artwork-texture-budget-v1",
        "free_limit_applied": edge is not None, "atlas_edge_px": edge,
        "atlas_count_max": 1 if edge else None,
        "cropped_area_px": area, "estimated_padding_px": padding,
        "padded_area_px": padded_area,
        "native_scale_impossible": impossible,
        "uniform_scale_upper_bound": scale,
        "editor_packing_verified": False, "artwork_resized": False,
        "note": "Bounds on cropped raster rectangles only. Mesh UVs, margins "
                "and packing can require a smaller scale. Verify in Cubism Editor.",
    }
    message = ("현재 크기는 2048px 한 장에 들어갈 수 없습니다. Editor에서 텍스처 배율을 "
               "조정하되 얼굴·눈의 디테일을 우선하세요." if impossible else
               "면적만으로 실제 패킹 성공을 확정할 수 없습니다. Editor에서 확인하세요.")
    if edge is None:
        message = "PRO에는 FREE의 2048px 한 장 제한을 적용하지 않습니다."
    md = ("# 텍스처 면적 예산\n\n" + message + "\n\n"
          + f"알파 경계 사각형 합계: {area:,} px² / 여백 2px 추정 합계: {padded_area:,} px².\n\n"
          + "metadata/texture_budget.json에 면적·변 길이의 필요조건을 기록했습니다. "
          "PSD와 PNG를 자동 축소하지 않았습니다. 이 값은 네이티브 아틀라스 또는 "
          "패킹 통과 증명이 아니며 실제 메시·UV·여백은 Editor에서 확인합니다.\n")
    return report, md


def _reference_bundle(layers, *, edition: str, scope: str, asset_kind: str | None,
                      qwen_attempts: list, split_names: list, group_count: int):
    """Produce useful *observed* companions, not fictitious Cubism keyforms."""
    import hashlib

    width, height = layers[0]["image"].size
    preview = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for layer in reversed(layers):
        preview.alpha_composite(layer["image"])
    out = BytesIO()
    preview.save(out, format="PNG")
    entries = [("preview/composite.png", out.getvalue())]
    records = []
    for index, layer in enumerate(layers):
        name = layer["name"]
        image = layer["image"]
        alpha = image.getchannel("A")
        bbox = alpha.getbbox()
        if bbox is None:
            raise ValueError("An empty layer reached artwork packaging")
        img_data = BytesIO()
        image.save(img_data, format="PNG")
        image_bytes = img_data.getvalue()
        mask_data = BytesIO()
        alpha.save(mask_data, format="PNG")
        alpha_bytes = mask_data.getvalue()
        stem = f"{index:04d}_{name}"
        image_path = f"layers_png/{stem}.png"
        mask_path = f"alpha_masks/{stem}_alpha.png"
        entries.extend(((image_path, image_bytes), (mask_path, alpha_bytes)))
        # No 2x full-canvas coordinate grid: 32MP layers must remain
        # processable on constrained Colab RAM.
        mask = np.asarray(alpha, dtype=np.uint8)
        x_masses = mask.sum(axis=0, dtype=np.float64)
        y_masses = mask.sum(axis=1, dtype=np.float64)
        total = float(x_masses.sum())
        if total <= 0:
            raise ValueError("Invalid empty alpha mask")
        centroid = [
            round(float(x_masses @ np.arange(mask.shape[1], dtype=np.float64) / total), 3),
            round(float(y_masses @ np.arange(mask.shape[0], dtype=np.float64) / total), 3),
        ]
        records.append({
            "z_index_top_first": index,
            "semantic_name": name,
            "semantic_family": name.split(".", 1)[0],
            "source_split_depth": layer["depth"],
            "rgba_png": image_path,
            "alpha_mask_png": mask_path,
            "canvas_xyxy_bbox": list(bbox),
            "visible_alpha_centroid_xy": centroid,
            "visible_pixel_count": int(np.count_nonzero(mask)),
            "rgba_png_sha256": hashlib.sha256(image_bytes).hexdigest(),
            "mask_png_sha256": hashlib.sha256(alpha_bytes).hexdigest(),
        })
    manifest = {
        "schema": "vtuber/cubism-artwork-reference-v1",
        "kind": "non_native_artwork_metadata",
        "edition": edition, "scope": scope, "asset_kind": asset_kind,
        "canvas_width": width, "canvas_height": height,
        "layer_order": "top_to_bottom",
        "drawable_layer_count": len(records),
        "psd_group_count": group_count,
        "all_layers_same_canvas": True,
        "layers": records,
        "warning": "Observed layer geometry only. Not a native Cubism rig.",
    }
    # Provide this separately for editors and users who want coordinates,
    # with zero claims that a generic JSON can animate the model.
    manual_guide = {
        "schema": "vtuber/cubism-manual-rig-reference-v1",
        "native_cubism_import": False,
        "auto_rigged": False, "has_native_keyforms": False,
        "has_physics_binds": False,
        "instruction": "Use the PSD in Cubism Editor. Coordinates below are "
                       "alpha observations, not optimized rotation pivots.",
        "suggested_layer_entries": [
            {"semantic_name": x["semantic_name"],
             "family": x["semantic_family"],
             "observed_bounds_xyxy": x["canvas_xyxy_bbox"],
             "observed_center_xy": x["visible_alpha_centroid_xy"]}
            for x in records
        ],
    }
    trace = {
        "schema": "vtuber/layer-segmentation-trace-v1",
        "accepted_source_names": split_names,
        "attempts": qwen_attempts,
        "note": "Rejected candidates are not included in the final PSD.",
    }
    for name, value in (
        ("metadata/layer_manifest.json", manifest),
        ("metadata/manual_rig_reference.json", manual_guide),
        ("metadata/segmentation_trace.json", trace),
    ):
        entries.append((name, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")))
    # Integrity requirements are testable even without Cubism Editor.
    integrity = {
        "schema": "vtuber/artwork-integrity-v1",
        "transparent_rgba_png": True,
        "non_empty_masks": True,
        "canvas_registration": True,
        "layer_count": len(records),
        "layers_under_free_artmesh_ceiling": edition != "free" or len(records) <= FREE_LIMIT,
        "native_cubism_artmesh_deformer_keyforms_checked": False,
        "native_cubism_texture_atlas_checked": False,
        "moc3_exported": False,
    }
    entries.append(("metadata/integrity_report.json",
                    json.dumps(integrity, ensure_ascii=False, indent=2).encode("utf-8")))
    texture, texture_md = _texture_budget(layers, edition)
    entries.append(("metadata/texture_budget.json",
                    json.dumps(texture, ensure_ascii=False, indent=2).encode("utf-8")))
    entries.append(("TEXTURE_BUDGET.md", texture_md.encode("utf-8")))
    return entries


def _editor_readme(edition, asset_kind, count, qwen_count):
    label = "FREE finished character" if edition == "free" else "PRO independent " + asset_kind
    limits = "\n".join("- %s: %s" % item for item in FREE_BUDGET.items())
    return (
        "# Live2D Cubism layered artwork — " + label + "\n\n"
        "This ZIP contains **separated illustration layers, not a rigged model**.\n"
        "It does NOT contain .moc3, .cmo3, deformers, keyforms or physics.\n\n"
        "## Files included\n\n"
        "- Editable PSD: avatar.psd (FREE) or body/hair/outfit/accessory.psd (PRO).\n"
        "- layers_png/: every registered transparent full-canvas RGBA layer.\n"
        "- alpha_masks/: grayscale alpha masks for each layer.\n"
        "- preview/composite.png: top-to-bottom layer composite for checking.\n"
        "- preview/input_vs_psd_comparison.png: original/input vs split PSD check.\n"
        "- metadata/layer_manifest.json: observed IDs, coordinates, alpha coverage.\n"
        "- metadata/manual_rig_reference.json: non-native reference ONLY.\n"
        "- metadata/segmentation_trace.json: applied/rejected Qwen splits.\n"
        "- metadata/integrity_report.json: checks verified before packaging.\n"
        "- input_reference/: the provided input and optional PRO body reference.\n"
        "None of these JSON files create animation inside Cubism.\n\n"
        "## In Cubism Editor\n\n"
        "1. Import the PSD. Check layer order, hidden edges and exact artwork identity.\n"
        "2. Refine ArtMeshes using the Editor's mesh tools; apply model templates"
        " or create deformers and animation keyforms as appropriate.\n"
        "3. Add eyes, mouth, head/body motion, hair/clothing dynamics and physics in the Editor.\n"
        "4. Save the editable .cmo3 and use the official Editor to export .moc3,"
        " .model3.json, textures and any needed physics/expression data.\n"
        "5. Open the exported model in VTube Studio and check tracking and clipping.\n\n"
        "## Observed artwork\n\n"
        "- Transparent PSD leaves: " + str(count) + "\n"
        "- Accepted Qwen splits: " + str(qwen_count) + "\n"
        + ("- Cubism FREE limits (the 7 final-object constraints must be checked"
           " **inside the Editor**):\n" + limits + "\n"
           "- Allocate the single 2048px atlas to face/eyes/outline detail first.\n"
           if edition == "free" else
           "- PRO has no FREE ArtMesh/parts/deformer/parameter limit, but"
           " Editor/GPU memory and runtime quality still matter.\n"
           "- Import each new asset PSD into the matching existing body project;"
           " preserve canvas origin and dimensions.\n")
        + "\n## No automatic completion claim\n\n"
        "Layer separation does not create animation. No auto-generated physics"
        " or JSON in this package should be mistaken for a native Cubism rig.\n"
    )


def _review_regions(edition: str, asset_kind: str | None, scope: str) -> list[str]:
    """Review only the selected artwork, without inventing absent features."""
    regions = []
    if edition == "free" or asset_kind == "body":
        regions.extend([
            "얼굴 윤곽·피부, 좌우 눈 각각의 흰자·홍채·동공·하이라이트·속눈썹·눈꺼풀, "
            "좌우 눈썹, 코·귀·목의 독립 표현과 의미 ID를 확인하세요.",
            "입 바깥 윤곽·입술·입 안쪽·치아·혀, 눈·입 움직임으로 보이는 가려진 화소와 "
            "머리카락 뒤 이마·얼굴·귀 복원을 확인하세요.",
            "목·상체·어깨·좌우 팔·양손 및 움직일 때 드러나는 가려진 몸 영역을 확인하세요.",
        ])
        if scope == "full":
            regions.append("전신 하체·좌우 다리·양발이 잘리지 않고 독립 표현에 필요한 영역을 갖추었는지 확인하세요.")
        if asset_kind == "body":
            regions.append("PRO 신체의 불투명 베이스와 탈착 의상·헤어·액세서리가 하나로 구워져 있지 않은지 확인하세요.")
    if edition == "free" or asset_kind == "hair":
        regions.extend([
            "앞머리·좌우 옆머리·뒷머리, 흔들릴 가닥·잔머리 및 헤어 장식의 독립 표현을 확인하세요.",
            "이미지에 있는 땋은 머리·묶은 머리·트윈테일·포니테일과 가닥 뒤 뿌리·뒷면 복원을 확인하세요.",
        ])
    if edition == "free" or asset_kind == "outfit":
        regions.append("옷 몸통·앞뒤 면·좌우 소매·옷깃·옷자락·리본·장식, 몸과의 경계·소매 안쪽·가려진 뒤쪽 원단을 확인하세요.")
        if scope == "full":
            regions.append("전신 의상의 치마·밑단·바지·신발 중 실제 있는 요소의 분리와 움직임 영역을 확인하세요.")
    if edition == "free" or asset_kind == "accessory":
        regions.append("각 액세서리·소품이 독립 레이어이며 부착 위치·좌우·앞뒤 순서가 맞는지 확인하세요.")
    return regions


def _guide_md(edition: str, scope: str, asset_kind: str | None,
              count: int, groups: int, qwen_attempts: list) -> str:
    title = ("FREE 완성 캐릭터" if edition == "free" else
             {"body": "PRO 신체", "hair": "PRO 헤어",
              "outfit": "PRO 의상", "accessory": "PRO 액세서리"}[asset_kind])
    kind = "상반신(양손 포함)" if scope == "upper" else "전신(양발 포함)"
    area = "\n\n".join(_review_regions(edition, asset_kind, scope))
    limits = (
        "\n## FREE 제한 7항목\n\n"
        "| 항목 | 공식 상한 | 확정 검증 위치 |\n"
        "|---|---:|---|\n"
        "| ArtMesh | 100 | PSD에서는 후보 수, 실제 객체는 Editor |\n"
        "| 파츠 폴더 | 30 | Editor |\n"
        "| 디포머 | 50 | Editor |\n"
        "| 파라미터 | 30 | Editor |\n"
        "| 블렌드셰이프 파라미터 | 3 | Editor |\n"
        "| ArtPath | 3 | Editor |\n"
        "| 텍스처 아틀라스 | 2048px 1장 | Editor |\n"
        "100개 후보를 최대한 의미 있는 움직임에 활용하되 강제 분할하거나 "
        "화질·움직임을 파괴하는 병합을 하지 마세요.\n"
        if edition == "free" else
        "\n## PRO 제한\n\nFREE의 7개 상한을 적용하지 않습니다. "
        "단, 실제 성능과 GPU 메모리는 무제한이 아니며 "
        "신체 기준 PSD와의 시각 정합이 필요합니다.\n"
    )
    mode = ("완성된 옷·헤어·액세서리를 착용한 이미지 한 장으로 제작한 원화입니다."
            if edition == "free" else
            "선택 자산 한 종류만 제작한 원화입니다. 다른 자산을 동시에 요구하지 "
            "않으며 같은 캔버스 기준으로 기존 신체 프로젝트에 추가합니다.")
    return (
        "# Live2D 제작 결과 및 Cubism Editor 안내\n\n"
        f"**모드:** {title} / {kind}\n\n"
        f"**PSD 실물 레이어:** {count}개 / 그룹 {groups}개 / "
        f"Qwen 시도 {len(qwen_attempts)}회\n\n"
        "## 이미지 제작 계약\n\n" + mode + "\n\n"
        "파이프라인은 고품질 분리 PSD까지 제작합니다. 실제 ArtMesh, 디포머, "
        "표정·움직임 키폼, 물리, 모션, 편집 원본 .cmo3와 실행용 .moc3는 "
        "공식 Cubism Editor에서 사용자가 제작합니다.\n\n"
        "## 제공한 파일\n\n"
        "- PSD: 편집·리깅을 위한 기본 파일\n"
        "- source_psd/: See-through 원본 분해 PSD\n"
        "- layers_png/: 원본 크기·좌표의 각 투명 PNG\n"
        "- alpha_masks/: 각 파츠의 알파 마스크\n"
        "- preview/: 합성 미리보기 및 PRO 정합 미리보기(제공될 경우)\n"
        "- input_reference/: 실제 제작 입력 및 PRO 기준 신체\n"
        "- metadata/layer_manifest.json: 관측된 이름·순서·좌표·마스크 해시\n"
        "- metadata/manual_rig_reference.json: 수동 참고용 데이터이며 "
        "Cubism 공식 리깅 JSON이 아님\n"
        "- metadata/segmentation_trace.json: Qwen 분해 채택/거절 정보\n"
        "- metadata/integrity_report.json: 자동 확인 범위\n"
        "- metadata/texture_budget.json 및 TEXTURE_BUDGET.md: 실제 파츠 면적 예산; "
        "Editor 패킹 통과 증명이 아님\n"
        "- logs/: 실행한 모델의 로그(해당할 경우)\n"
        "- QUALITY_REVIEW.md: 사람의 실제 그림 검수 목록\n"
        "- README_CUBISM.md: 간략 Editor 사용법\n\n"
        "## 세부 파츠 확인\n\n"
        "아래 항목은 실제 외형에 있거나 움직임을 위해 복원이 필요한 경우에만 적용합니다. "
        "없는 디테일을 새로 그리거나 고정 파츠 수를 강요하지 않습니다.\n\n" + area + "\n\n"
        "원본에서 가려진 면의 복원, 누락된 눈/입/헤어 가닥, "
        "이동 시 드러나는 투명 틈, 선화·색상·좌표 동일성은 "
        "기계적인 PNG 무결성 검사만으로 입증되지 않습니다.\n"
        + limits
        + "\n## Cubism Editor 단계\n\n"
        "1. PSD를 가져와 레이어 순서·투명도를 검수합니다.\n"
        "2. 실제 ArtMesh·디포머를 생성하고 필요하면 공식 모델 템플릿을 적용합니다.\n"
        "3. 눈·입·얼굴·몸의 키폼 및 파라미터를 실제로 작성합니다.\n"
        "4. 머리·의상·액세서리의 흔들림 키폼을 생성한 뒤 "
        "공식 물리 프리셋을 적용하고 조절합니다.\n"
        "5. FREE는 7개 객체 수 제한을 Editor에서 확인합니다. "
        "PRO는 독립 PSD를 기존 신체와 정합합니다.\n"
        "6. .cmo3를 저장하고 공식 Editor에서 .moc3, .model3.json, "
        "텍스처 및 필요한 물리·표정 파일을 내보냅니다.\n"
        "7. VTube Studio에서 실제 눈·입·헤어·의상의 움직임과 클리핑을 확인합니다.\n\n"
        "## 모델 설정 참고\n\n"
        "See-through는 의미 분할과 가려진 영역 복원, Qwen은 선택 파츠의 "
        "재귀 분할 후보 생성에 사용합니다. Stable-Layers 경로의 "
        "기본 수치는 Heun 50 steps / CFG 1.0 / 640px / 4 layers입니다. "
        "Qwen 저해상도 색상은 최종 원본을 대체하지 않습니다. "
        "원본 Qwen의 추천값과 Stable-Layers 설정을 혼동하면 안 됩니다.\n"
    )


def _quality_md(parts: list, edition: str, asset_kind: str | None,
                qwen_attempts: list, scope: str = "upper") -> str:
    families = sorted({x["name"].split(".", 1)[0] for x in parts})
    checks = [
        "각 RGBA·알파 마스크가 동일 캔버스에 정합하는가?",
        "위치를 움직였을 때 빈 픽셀·윤곽 틈·색 번짐이 없는가?",
        "원화와 얼굴·머리 모양·장식·선화·색감이 일치하는가?",
        "배경이 실제로 투명하고 불필요한 배경 픽셀이 없는가?",
        "전신/상반신 범위에 필요한 손·발·옷이 잘리지 않았는가?",
        "실제 Editor에서 FREE 7개 제한/PRO 메모리를 만족하는가?",
    ]
    checks.extend(_review_regions(edition, asset_kind, scope))
    if edition == "pro":
        checks.append("기존 신체와 자산의 부착 위치·각도·스케일·정체성이 일치하는가?")
    return (
        "# Live2D 시각적 검수 - 실제 그림을 확인해야 하는 항목\n\n"
        "자동 분해 성공이나 PSD 저장 성공은 방송용 완성 품질을 증명하지 않습니다. "
        "실제 외형에 있거나 움직임 복원이 필요한 요소만 검수하고, 없는 요소는 해당 없음으로 기록하세요.\n\n"
        f"- 실물 PSD 레이어: {len(parts)}개\n"
        f"- 의미 분류: {', '.join(families)}\n"
        f"- Qwen 시도: {len(qwen_attempts)}회\n\n"
        + "\n".join("- [ ] " + x for x in checks)
        + "\n\n미확인 항목을 자동 PASS로 표시하지 마세요. "
        "수정 후 다시 PSD 및 PNG를 확인하세요.\n"
    )


def validate_artwork_request(*, edition: str, scope: str, asset_kind: str | None = None,
                             per_pass_layers: int = 4, max_qwen_passes: int = 4):
    """Validate the same contract before inference and before packaging."""
    if edition not in ("free", "pro") or scope not in ("upper", "full"):
        raise ValueError("Invalid Cubism edition/framing")
    if edition == "pro" and asset_kind not in ASSETS:
        raise ValueError("PRO must select exactly one body/hair/outfit/accessory asset")
    if edition == "free" and asset_kind is not None:
        raise ValueError("FREE is one complete fixed-look character")
    if not 2 <= per_pass_layers <= 10 or not 0 <= max_qwen_passes <= 12:
        raise ValueError("Invalid Qwen recursion budget")


def build_artwork_package(registered_zip: Path, output: Path, *, edition: str,
                          scope: str, asset_kind: str | None = None,
                          qwen: bool = False, qwen_infer=None, third_party=None,
                          python_path=None, max_qwen_passes: int = 4,
                          per_pass_layers: int = 4) -> dict:
    """Build one FREE character or one independently authored PRO asset PSD."""
    validate_artwork_request(edition=edition, scope=scope, asset_kind=asset_kind,
                             per_pass_layers=per_pass_layers, max_qwen_passes=max_qwen_passes)
    layers, canvas = _read_registered(registered_zip)
    if edition == "pro":
        # One asset is the complete input here. See-through's classifier may
        # call hair a clothing layer or label basewear as removable clothing.
        # Keep ALL of this one asset's pixels; do not erase mistaken classes.
        prefixes = {
            "body": ("body", "face", "eye", "eyebrow", "mouth", "nose",
                     "ear", "neck", "arm", "hand", "leg", "foot", "head"),
            "hair": ("hair",),
            "outfit": ("cloth", "sleeve", "shoe", "boot", "outfit"),
            "accessory": ("ornament", "accessory", "hat"),
        }[asset_kind]
        for layer in layers:
            family = layer["name"].split(".", 1)[0]
            if family not in prefixes:
                layer["name"] = asset_kind + ".other." + layer["name"]
    if edition == "free" and len(layers) > FREE_LIMIT:
        raise ValueError("FREE ArtMesh budget exceeded by source PSD; no silent merging")
    output.mkdir(parents=True, exist_ok=True)
    generated = []
    attempted = []
    runtime_logs = []
    if qwen:
        if qwen_infer is None:
            from tools.vts_qwen_refine import infer as qwen_infer
        tried = set()
        family_attempts = {}
        for serial in range(max_qwen_passes):
            selectable = [
                (idx, layer) for idx, layer in enumerate(layers)
                if layer["name"] not in tried and layer["depth"] < 3
                and _candidate_score(layer) > 0
            ]
            if not selectable or (edition == "free" and len(layers) >= FREE_LIMIT):
                break
            # Cover the other observed regions before spending every pass
            # recursively on one large hairstyle. Within a family retain
            # the existing detail/area priority.
            index, item = max(selectable, key=lambda pair: (
                -family_attempts.get(pair[1]["name"].split(".", 1)[0], 0),
                _candidate_score(pair[1])))
            family = item["name"].split(".", 1)[0]
            family_attempts[family] = family_attempts.get(family, 0) + 1
            tried.add(item["name"])
            stem = "qwen_" + str(serial).zfill(3)
            crop = item["image"].crop(item["image"].getchannel("A").getbbox())
            source = output / "qwen_work" / (stem + ".png")
            source.parent.mkdir(parents=True, exist_ok=True)
            crop.save(source)
            run_dir = output / "qwen_work" / stem
            family = item["name"].split(".", 1)[0]
            # Heuristic per-part budgets, not official guaranteed part counts.
            suggested = {"hair": 8, "eye": 5, "eyebrow": 3,
                         "mouth": 5, "face": 4, "body": 4,
                         "cloth": 6, "sleeve": 4, "ornament": 4,
                         "accessory": 4}.get(family, 4)
            requested = max(2, min(per_pass_layers, suggested))
            if edition == "free":
                requested = min(requested, FREE_LIMIT - len(layers) + 1)
            kw = {"layer_count": requested}
            if third_party is not None:
                kw["third_party"] = third_party
            if python_path is not None:
                kw["python"] = python_path
            result = qwen_infer(source, run_dir, **kw)
            if result.get("log"):
                log_path = Path(result["log"])
                if log_path.is_file():
                    runtime_logs.append(("logs/" + stem + ".log", log_path.read_bytes()))
            proposed = _partition_part(item, result["layers"])
            accepted = bool(proposed and
                            (edition != "free" or len(layers) + len(proposed) - 1 <= FREE_LIMIT))
            attempted.append({"source_layer": item["name"], "accepted": accepted,
                              "requested_count": requested,
                              "candidate_count": len(result["layers"])})
            if accepted:
                layers[index:index+1] = proposed
                generated.append(item["name"])
    if edition == "free" and len(layers) < 2:
        raise ValueError("FREE output is a single flattened character image, not separated artwork")
    if edition == "free" and len(layers) > FREE_LIMIT:
        raise ValueError("FREE ArtMesh ceiling exceeded")
    name = "avatar" if edition == "free" else asset_kind
    psd_path = output / (name + ".psd")
    group_count = _write_psd(layers, psd_path, free=edition == "free")
    package = output / ("Live2D_" + edition.upper() +
                         ("_" + scope if edition == "free" else "_" + asset_kind)
                         + ".zip")
    readme = _editor_readme(edition, asset_kind, len(layers), len(generated))
    extras = _reference_bundle(
        layers, edition=edition, scope=scope, asset_kind=asset_kind,
        qwen_attempts=attempted, split_names=generated, group_count=group_count)
    extras.extend(runtime_logs)
    with ZipFile(package, "w", ZIP_DEFLATED, compresslevel=6) as z:
        z.write(psd_path, name + ".psd")
        z.writestr("README_CUBISM.md", readme)
        z.writestr("LIVE2D_ARTWORK_GUIDE.md", _guide_md(
            edition, scope, asset_kind, len(layers), group_count, attempted))
        z.writestr("QUALITY_REVIEW.md", _quality_md(
            layers, edition, asset_kind, attempted, scope=scope))
        for filename, content in extras:
            z.writestr(filename, content)
    return {
        "status": "artwork_ready_editor_rig_required",
        "package": str(package), "art_psd": str(psd_path),
        "layer_count": len(layers), "psd_group_count": group_count,
        "supporting_files": [x[0] for x in extras] +
        ["README_CUBISM.md", "LIVE2D_ARTWORK_GUIDE.md", "QUALITY_REVIEW.md"],
        "edition": edition, "scope": scope,
        "asset_kind": asset_kind, "canvas": list(canvas),
        "qwen_attempts": attempted, "qwen_splits_accepted": generated,
        "moc3_generated": False, "editor_required": True,
    }
