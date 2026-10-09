"""CPU-only checks for the Colab notebook without an HTTP/Gradio UI."""
from pathlib import Path

import pytest
from tools import colab_native as native


def test_photo_only_2d_generation_uses_native_uploader(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "WORK", tmp_path)
    artifact = tmp_path / "export.zip"
    artifact.write_bytes(b"actual test package")
    invocations = []

    def runner(mode, args, on_event):
        invocations.append((mode, args))
        on_event(("stage", "segmentation", "running", "original photo"))
        return ("needs_editor_export", "layers created", str(artifact))

    result = native.generate(
        "live2d", "personalProfit", upload=lambda: {"character.png": b"photo"},
        runner=runner,
    )
    assert result == str(artifact)
    assert len(invocations) == 1
    mode, args = invocations[0]
    assert mode == "live2d"
    assert args[1] == "personalProfit"
    assert Path(args[0]).read_bytes() == b"photo"
    assert len(args) == 2  # photo + usage, no manual parts ZIP


def test_3d_default_uploads_only_one_photo(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "WORK", tmp_path)
    monkeypatch.setattr(native, "OUTPUT", tmp_path / "output")
    target = native.OUTPUT / "sample" / "avatar.vrm"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"glTF" + bytes(80))
    uploads = []
    received = []

    def upload():
        uploads.append(True)
        return {"full_body.jpg": b"portrait"}

    def runner(mode, args, on_event):
        received.append((mode, args))
        return ("success", "complete", str(target))

    assert native.generate(
        "3d", upload=upload, runner=runner,
    ) == str(target)
    assert len(uploads) == 1
    mode, args = received[0]
    assert mode == "avatar"
    assert args[3:6] == [None, None, False]
    assert args[6:] == [2048, None, None, "canonical"]
    assert (tmp_path / "avatar.vrm").read_bytes() == target.read_bytes()


def test_accessory_mode_uses_separate_vrm_and_multiple_accessory_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "WORK", tmp_path)
    monkeypatch.setattr(native, "OUTPUT", tmp_path / "output")
    vrm = tmp_path / "character.vrm"
    vrm.write_bytes(b"glTF" + bytes(70))
    monkeypatch.setattr(native, "_latest_avatar", lambda: str(vrm))
    result = tmp_path / "accessories.vrm"
    result.write_bytes(b"glTF" + bytes(80))
    seen = []

    def runner(mode, args, on_event):
        seen.append((mode, args))
        return ("accessories complete", "ok", str(result))

    assert native.generate(
        "accessory", upload=lambda: {"hat.png": b"hat", "glasses.png": b"glasses"},
        accessory_anchor="HEAD_TOP", runner=runner,
    ) == str(result)
    kind, args = seen[0]
    assert kind == "accessory"
    assert args[:3] == [True, None, str(vrm)]
    assert len(args) == 17  # 3 base arguments + 7 fields per accessory
    assert args[4] == "HEAD_TOP"
    assert args[11] == "HEAD_TOP"


def test_upload_cancel_does_not_start_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "WORK", tmp_path)
    with pytest.raises(ValueError, match="취소"):
        native.generate("inochi2d", upload=lambda: {},
                        runner=lambda *a, **kw: pytest.fail("must not start subprocess"))


def test_reject_extra_character_uploads_before_start(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "WORK", tmp_path)
    with pytest.raises(ValueError, match="한 장"):
        native.generate("live2d", upload=lambda: {"one.png": b"1", "two.png": b"2"},
                        runner=lambda *a, **kw: pytest.fail("must not start subprocess"))


def test_user_interrupt_is_propagated_not_reported_as_success(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "WORK", tmp_path)
    photo = tmp_path / "photo.png"
    photo.write_bytes(b"image")
    def stop(mode, args, on_event):
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        native.generate("inochi2d", image_path=str(photo), runner=stop)


def test_auto_accessory_batch_assigns_each_photo_its_own_anchor(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "WORK", tmp_path)
    vrm = tmp_path / "base.vrm"
    vrm.write_bytes(b"glTF" + bytes(80))
    monkeypatch.setattr(native, "_latest_avatar", lambda: str(vrm))
    result = tmp_path / "updated.vrm"
    result.write_bytes(b"glTF" + bytes(80))
    seen = []
    def runner(mode, args, on_event):
        seen.append((mode, args))
        return ("accessories complete", "", str(result))
    assert native.generate("accessory", runner=runner, upload=lambda: {
        "hat.png": b"hat", "glasses.png": b"glasses",
        "shoes.png": b"shoes",
    }) == str(result)
    mode, args = seen[0]
    assert mode == "accessory"
    pairs = [(args[i], args[i + 1]) for i in range(3, len(args), 7)]
    assert len(pairs) == 4
    assert [(Path(p).name.split("_", 2)[-1], anchor)
            for p, anchor in pairs] == [
        ("hat.png", "HEAD_TOP"),
        ("glasses.png", "FACE"),
        ("shoes.png", "LEFT_FOOT"),
        ("shoes.png", "RIGHT_FOOT"),
    ]


def test_all_accessory_positions_are_explicitly_batched_without_skipping(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "WORK", tmp_path)
    vrm = tmp_path / "base.vrm"
    vrm.write_bytes(b"glTF" + bytes(80))
    monkeypatch.setattr(native, "_latest_avatar", lambda: str(vrm))
    result = tmp_path / "updated.vrm"
    result.write_bytes(b"glTF" + bytes(80))
    got = []
    def runner(mode, args, on_event):
        got.append((mode, args))
        return ("accessories complete", "", str(result))
    native.generate("accessory", accessory_anchor="ALL",
                    upload=lambda: {"unknown.png": b"unclassified"},
                    runner=runner)
    mode, args = got[0]
    assert mode == "accessory"
    assert len(args) == 3 + 7 * len(native.ANCHORS)
    assert [args[i] for i in range(4, len(args), 7)] == list(native.ANCHORS)


def test_ambiguous_auto_accessory_names_fail_before_model_loading(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "WORK", tmp_path)
    vrm = tmp_path / "base.vrm"
    vrm.write_bytes(b"glTF" + bytes(80))
    monkeypatch.setattr(native, "_latest_avatar", lambda: str(vrm))
    with pytest.raises(ValueError, match="자동 위치 판정 불가"):
        native.generate(
            "accessory", upload=lambda: {"image.png": b"unknown"},
            runner=lambda *a, **kw: pytest.fail("No unverified accessory placement"),
        )


def test_character_mode_rejects_accessory_only_mode_in_ui_dispatch():
    import ast
    import json
    repo = Path(__file__).resolve().parents[1]
    notebook = json.loads((repo / "notebooks" /
                           "VTuber_Commercial_Pipeline_Colab_v8.ipynb").read_text())
    cells = ["".join(cell["source"]) for cell in notebook["cells"]
             if cell["cell_type"] == "code"]
    assert 'TOP_MODE = "live2d" #@param' in cells[1]
    assert 'ACCESSORY_ANCHOR_OPTION = "AUTO" #@param' in cells[5]
    assert 'elif TASK == "액세서리 제작":' in cells[8]
    tree = ast.parse(cells[8])
    branches = [node for node in ast.walk(tree) if isinstance(node, ast.If)]
    work = next(node for node in branches if
                ast.unparse(node.test) == "TASK == '캐릭터 생성'")
    character_code = ast.unparse(ast.Module(body=work.body, type_ignores=[]))
    assert "accessory_anchor=" not in character_code
    assert "accessory_image_paths=" not in character_code


def test_v8_notebook_cells_are_independent_and_failure_is_not_success():
    import ast
    import json
    repo = Path(__file__).resolve().parents[1]
    notebook = json.loads((repo / "notebooks" /
                           "VTuber_Commercial_Pipeline_Colab_v8.ipynb").read_text())
    cells = ["".join(c["source"]) for c in notebook["cells"]
             if c["cell_type"] == "code"]
    assert len(cells) == 12
    for cell in cells:
        ast.parse(cell)
    setup, selection, prefetch, upload, build, download, diagnostics, last = cells
    assert "build_prompts(" not in "\n".join(cells)
    assert "write_prompt_package" not in "\n".join(cells)
    assert "store_uploaded_zip" in upload
    assert "SHEET_PACK_PATH" in upload
    assert "sheet_zip_path=" in build
    assert "prepare_2d_image_uploads" in upload  # optional legacy mode
    assert "LAYER_ZIP_PATH" in upload
    assert "layers_zip_path=" in build
    assert "--sheet-pack" in prefetch
    assert 'TWO_D_INPUT = "sheets"' in selection
    assert "colab_mode_prepare.py" in prefetch
    assert "--mode" in prefetch
    assert "generate(" not in prefetch
    assert "files.upload" in upload
    assert "_stored_uploads" in upload
    assert "generate(" not in upload
    assert "generate(" in build
    assert "files.upload" not in build
    assert "files.download" not in build
    assert 'VTUBER_NOTEBOOK_EXPLICIT_DOWNLOAD' in build
    assert "if not RESULT_FILE:" in build
    assert "raise RuntimeError(" in build
    assert "DOWNLOAD_NOW = False" in download
    assert "files.download(" in download
    assert "generate(" not in download
    assert "status.json" in diagnostics
    assert "generation.log" in diagnostics
    assert "generate(" not in diagnostics
    assert "generate(" not in last
    assert "files.download" not in last
    assert "files.upload" not in last
    assert "gradio" not in "\n".join(cells).lower()


def test_notebook_event_printer_displays_unfiltered_logs_including_early_errors(capsys):
    from tools.colab_native import _event_printer
    lines = (
        "ERROR: pip's dependency resolver does not currently take into account...\n"
        "source/app.d(120,55): Error: undefined reference to symbol\n"
        + "Z" * 1200 + "\n"
        + "/usr/bin/cc failed with status: 1\n"
    )
    _event_printer(("log", lines))
    assert capsys.readouterr().out == lines


def test_notebook_prints_entire_failure_details_not_last_2200_only(
    tmp_path, monkeypatch, capsys,
):
    monkeypatch.setattr(native, "WORK", tmp_path)
    image = tmp_path / "picture.png"
    image.write_bytes(b"input")
    early = "EARLY LINKER ERROR: undefined reference"
    details = early + "\n" + ("verbose-build-line\n" * 400)
    def failed(_mode, _args, *, on_event):
        return ("inochi2d 제작 실패", details, None)
    assert native.generate("inochi2d", image_path=str(image), runner=failed) is None
    output = capsys.readouterr().out
    assert early in output
    assert output.count("verbose-build-line") == 400



@pytest.mark.parametrize("status", [
    "❌ Avatar 생성 실패: rigging error",
    "inochi2d: 제작 실패 (임시 그림 파일을 모델 완성으로 표시하지 않음)",
    "live2d 제작 실패: invalid segmentation",
])
def test_failed_callback_never_publishes_leftover_artifact(
    tmp_path, monkeypatch, capsys, status,
):
    """A failed model can still leave a valid-looking intermediate artifact."""
    monkeypatch.setattr(native, "WORK", tmp_path)
    monkeypatch.setattr(native, "OUTPUT", tmp_path / "output")
    image = tmp_path / "character.png"
    image.write_bytes(b"input")
    leftover = native.OUTPUT / "old-result.zip"
    leftover.parent.mkdir(parents=True)
    leftover.write_bytes(b"stale output")

    def failed(_mode, _args, *, on_event):
        return (status, "first actionable traceback line", str(leftover))

    assert native.generate(
        "inochi2d", image_path=str(image), runner=failed,
    ) is None
    displayed = capsys.readouterr().out
    assert "first actionable traceback line" in displayed
    assert "결과 파일을 완성 모델로 제공하지 않습니다" in displayed
    assert leftover.is_file()


def _write_minimal_glb_container(path, *, vrm=True):
    """Minimal valid GLB structure for quick preflight, not a rigged avatar."""
    import json
    import struct
    document = {
        "asset": {"version": "2.0"},
        "extensions": {"VRMC_vrm": {"specVersion": "1.0"}} if vrm else {},
        "extensionsUsed": ["VRMC_vrm"] if vrm else [],
    }
    data = json.dumps(document).encode("utf-8")
    data += b" " * ((4 - len(data) % 4) % 4)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        struct.pack("<4sII", b"glTF", 2, 20 + len(data))
        + struct.pack("<II", len(data), 0x4E4F534A)
        + data
    )


def test_latest_avatar_rejects_corrupt_stable_copy_and_uses_valid_output(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(native, "WORK", tmp_path)
    monkeypatch.setattr(native, "OUTPUT", tmp_path / "output")
    stable = tmp_path / "avatar.vrm"
    stable.write_bytes(b"glTF" + bytes(100))  # old code accepted magic alone
    verified = native.OUTPUT / "avatar-test" / "avatar.vrm"
    _write_minimal_glb_container(verified)
    assert native._has_vrm_container(stable) is False
    assert native._has_vrm_container(verified) is True
    assert native._latest_avatar() == str(verified)


def test_cached_avatar_preflight_rejects_non_vrm_and_malformed_json(tmp_path):
    file = tmp_path / "avatar.vrm"
    _write_minimal_glb_container(file, vrm=False)
    assert not native._has_vrm_container(file)
    file.write_bytes(b"glTF" + bytes(100))
    assert not native._has_vrm_container(file)
