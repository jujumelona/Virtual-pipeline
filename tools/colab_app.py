"""Colab Gradio UI for the VTuber pipeline.

This file is intentionally loaded from the freshly synchronized main branch by
the notebook bootstrap. The notebook itself stays tiny so stale Colab copies
still execute the current UI and pipeline code.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import traceback
import uuid
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr


REPO_URL = "https://github.com/jujumelona/Virtual-pipeline.git"
REPO_DIR = pathlib.Path("/content/Virtual-pipeline")
TRIPOSR_DIR = pathlib.Path("/content/third_party/TripoSR")
TRIPOSR_COMMIT = "107cefdc244c39106fa830359024f6a2f1c78871"
TRIPOSR_MODEL_REVISION = "c1cf7716aed5aa6c1c5e174657791ef0e1327bde"
TRIPOSR_MODEL_WEIGHT_SHA256 = "429e2c6b22a0923967459de24d67f05962b235f79cde6b032aa7ed2ffcd970ee"
TORCHMCUBES_COMMIT = "879926d0ef58e6ce0ac2630fdecb5e53af7ed3ff"
GRADIO_VERSION = "6.3.0"
RUNTIME_CONTRACT = "colab-runtime-v6"
WORK_ROOT = pathlib.Path("/content/vtuber_builder")
OUTPUT_ROOT = WORK_ROOT / "output"

ANCHORS = [
    "HEAD_TOP",
    "FACE",
    "LEFT_EAR",
    "RIGHT_EAR",
    "NECK",
    "CHEST",
    "BACK",
    "LEFT_SHOULDER",
    "RIGHT_SHOULDER",
    "LEFT_HAND",
    "RIGHT_HAND",
    "LEFT_FOOT",
    "RIGHT_FOOT",
    "HIPS",
    "CUSTOM",
]

_RUNTIME_READY_HEAD: Optional[str] = None


def _run(
    cmd: List[str],
    *,
    timeout: int,
    cwd: Optional[pathlib.Path] = None,
) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-6000:]
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{tail}"
        )
    return proc


def _sync_repo() -> str:
    if (REPO_DIR / ".git").is_dir():
        _run(
            ["git", "-C", str(REPO_DIR), "remote", "set-url", "origin", REPO_URL],
            timeout=60,
        )
        _run(
            ["git", "-C", str(REPO_DIR), "fetch", "--prune", "origin", "main"],
            timeout=180,
        )
    else:
        if REPO_DIR.exists():
            shutil.rmtree(REPO_DIR)
        _run(
            [
                "git",
                "clone",
                "--branch",
                "main",
                "--single-branch",
                REPO_URL,
                str(REPO_DIR),
            ],
            timeout=300,
        )

    _run(
        ["git", "-C", str(REPO_DIR), "checkout", "-B", "main", "origin/main"],
        timeout=60,
    )
    _run(
        ["git", "-C", str(REPO_DIR), "reset", "--hard", "origin/main"],
        timeout=60,
    )

    head = _run(
        ["git", "-C", str(REPO_DIR), "rev-parse", "HEAD"],
        timeout=30,
    ).stdout.strip()
    origin_head = _run(
        ["git", "-C", str(REPO_DIR), "rev-parse", "origin/main"],
        timeout=30,
    ).stdout.strip()
    if head != origin_head:
        raise RuntimeError(
            f"Latest-main synchronization failed: local={head}, origin/main={origin_head}"
        )
    return head


def _sync_triposr() -> None:
    TRIPOSR_DIR.parent.mkdir(parents=True, exist_ok=True)
    if (TRIPOSR_DIR / ".git").is_dir():
        _run(
            ["git", "-C", str(TRIPOSR_DIR), "fetch", "--prune", "origin"],
            timeout=180,
        )
    else:
        if TRIPOSR_DIR.exists():
            shutil.rmtree(TRIPOSR_DIR)
        _run(
            [
                "git",
                "clone",
                "https://github.com/VAST-AI-Research/TripoSR.git",
                str(TRIPOSR_DIR),
            ],
            timeout=300,
        )

    _run(
        ["git", "-C", str(TRIPOSR_DIR), "checkout", "--detach", TRIPOSR_COMMIT],
        timeout=60,
    )
    actual = _run(
        ["git", "-C", str(TRIPOSR_DIR), "rev-parse", "HEAD"],
        timeout=30,
    ).stdout.strip()
    if actual != TRIPOSR_COMMIT:
        raise RuntimeError(
            f"TripoSR pin mismatch: expected={TRIPOSR_COMMIT}, actual={actual}"
        )


def _install_runtime(head: str) -> None:
    python_tag = f"py{sys.version_info.major}{sys.version_info.minor}"
    marker = WORK_ROOT / f".runtime-{RUNTIME_CONTRACT}-{python_tag}.ready"
    if marker.is_file():
        os.environ["TRIPOSR_DIR"] = str(TRIPOSR_DIR)
        if str(REPO_DIR) not in sys.path:
            sys.path.insert(0, str(REPO_DIR))
        # Editable installation points at the stable /content/Virtual-pipeline
        # path, so a git reset to a newer main immediately exposes new source.
        return

    if not ((3, 12) <= sys.version_info[:2] <= (3, 13)):
        raise RuntimeError(
            "Supported Colab Python versions are 3.12 and 3.13; "
            f"current={sys.version.split()[0]}"
        )

    WORK_ROOT.mkdir(parents=True, exist_ok=True)

    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-U",
            "pip",
            "setuptools",
            "wheel",
        ],
        timeout=600,
    )

    # Colab already provides CUDA-enabled torch/torchvision. Never let the
    # resolver replace them with a different build.
    _run(
        [
            sys.executable,
            "-c",
            (
                "import torch, torchvision; "
                "print('python', __import__('sys').version); "
                "print('torch', torch.__version__); "
                "print('torchvision', torchvision.__version__); "
                "print('cuda', torch.version.cuda, torch.cuda.is_available())"
            ),
        ],
        timeout=60,
    )

    # Native packages: wheel-only. This deliberately prevents silent source
    # builds such as Pillow==10.1.0 on newer Colab Python runtimes.
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--only-binary=:all:",
            "Pillow==12.3.0",
            "xatlas==0.0.11",
            "moderngl==5.12.0",
            "onnxruntime==1.30.0",
            "opencv-python-headless>=4.10.0.84",
            "safetensors>=0.5.3",
        ],
        timeout=1200,
    )

    # TripoSR + local pipeline runtime. These versions retain TripoSR's used
    # APIs while supporting the current 3.12/3.13 Colab runtime.
    runtime_packages = [
        "omegaconf==2.3.0",
        "einops==0.7.0",
        "transformers==4.57.6",
        "trimesh==4.12.2",
        "rembg==2.0.85",
        "huggingface-hub>=0.34.0,<1.0",
        "imageio[ffmpeg]>=2.34.0",
        "PyYAML>=6.0",
        "scipy>=1.13",
        "click>=8.0",
        "pygltflib==1.16.5",
        "packaging>=24.0",
    ]
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--prefer-binary",
            *runtime_packages,
        ],
        timeout=1800,
    )

    # anime-face-detector depends on the existing torch/torchvision pair.
    # Install its package without dependency resolution so pip cannot replace
    # Colab's CUDA-enabled PyTorch.
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "anime-face-detector==0.1.0",
        ],
        timeout=600,
    )

    # torchmcubes must compile against the already-installed PyTorch.
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-U",
            "scikit-build-core>=1.0",
            "pybind11>=2.10",
            "cmake>=3.18",
            "ninja",
        ],
        timeout=600,
    )

    os.environ.setdefault("MAX_JOBS", "2")
    os.environ.setdefault("CMAKE_BUILD_PARALLEL_LEVEL", "2")
    if pathlib.Path("/usr/local/cuda").is_dir():
        os.environ.setdefault("CUDA_HOME", "/usr/local/cuda")

    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-build-isolation",
            f"git+https://github.com/tatsy/torchmcubes.git@{TORCHMCUBES_COMMIT}",
        ],
        timeout=1800,
    )

    # Install the freshly synchronized repository without re-running the
    # dependency resolver and undoing the compatibility set above.
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "-e",
            str(REPO_DIR),
        ],
        timeout=600,
    )

    # Resolve the exact Hugging Face snapshot and verify model.ckpt before the
    # UI can start. reconstruct_avatar() reuses the same cached snapshot.
    _run(
        [
            sys.executable,
            "-c",
            (
                "from vtuber_pipeline.avatar.reconstruction "
                "import resolve_triposr_model; "
                "print('triposr-model', resolve_triposr_model())"
            ),
        ],
        timeout=2400,
    )

    # End-to-end import smoke test for every external runtime edge used before
    # the first model inference.
    _run(
        [
            sys.executable,
            "-c",
            (
                "import PIL, xatlas, moderngl, onnxruntime, cv2, safetensors; "
                "import omegaconf, einops, trimesh, rembg, imageio, scipy; "
                "import huggingface_hub, pygltflib, torch, torchvision, torchmcubes, gradio; "
                "from transformers.models.vit.modeling_vit import ViTModel; "
                "from anime_face_detector import create_detector; "
                "print('runtime-smoke-ok'); "
                "print('Pillow', PIL.__version__); "
                "print('trimesh', trimesh.__version__); "
                "print('onnxruntime', onnxruntime.__version__); "
                "print('gradio', gradio.__version__)"
            ),
        ],
        timeout=120,
    )

    # Audit the actually resolved dependency graph before caching this runtime.
    _run(
        [
            sys.executable,
            str(REPO_DIR / "tools" / "audit_runtime_environment.py"),
        ],
        timeout=180,
    )

    os.environ["TRIPOSR_DIR"] = str(TRIPOSR_DIR)
    if str(REPO_DIR) not in sys.path:
        sys.path.insert(0, str(REPO_DIR))

    marker.write_text(
        "\n".join(
            [
                f"runtime_contract={RUNTIME_CONTRACT}",
                f"installed_from_main={head}",
                f"python={sys.version.split()[0]}",
                f"triposr={TRIPOSR_COMMIT}",
                f"triposr_model_revision={TRIPOSR_MODEL_REVISION}",
                f"triposr_model_sha256={TRIPOSR_MODEL_WEIGHT_SHA256}",
                f"torchmcubes={TORCHMCUBES_COMMIT}",
                f"gradio={GRADIO_VERSION}",
                "pillow=12.3.0",
                "xatlas=0.0.11",
                "moderngl=5.12.0",
                "onnxruntime=1.30.0",
                "transformers=4.57.6",
                "trimesh=4.12.2",
                "rembg=2.0.85",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _reload_pipeline_modules() -> None:
    for name in list(sys.modules):
        if name == "vtuber_pipeline" or name.startswith("vtuber_pipeline."):
            del sys.modules[name]


def ensure_runtime(
    progress: Optional[gr.Progress] = None,
) -> Tuple[str, List[str]]:
    global _RUNTIME_READY_HEAD

    logs: List[str] = []

    if progress:
        progress(0.04, desc="최신 main 확인")
    head = _sync_repo()
    logs.append(f"최신 main: {head[:12]}")

    if _RUNTIME_READY_HEAD == head:
        os.environ["TRIPOSR_DIR"] = str(TRIPOSR_DIR)
        return head, logs

    if progress:
        progress(0.12, desc="TripoSR 준비")
    _sync_triposr()
    logs.append(f"TripoSR: {TRIPOSR_COMMIT[:12]}")

    if progress:
        progress(0.20, desc="필요 패키지 준비")
    _install_runtime(head)
    logs.append("Python 환경 준비 완료")

    _reload_pipeline_modules()
    _RUNTIME_READY_HEAD = head
    return head, logs


def _pipeline_imports():
    from vtuber_pipeline.avatar import build_avatar
    from vtuber_pipeline.accessory import reconstruct_accessories, AccessoryPipeline

    return build_avatar, reconstruct_accessories, AccessoryPipeline


def _stage_log(stages: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for name, result in stages.items():
        if not isinstance(result, dict):
            continue
        status = result.get("status", "unknown")
        detail = result.get("error") or result.get("warning")
        mark = "✓" if status == "complete" else "·" if status in {"cached", "skipped"} else "✗"
        line = f"{mark} {name}: {status}"
        if detail:
            line += f" — {detail}"
        lines.append(line)
    return lines


def build_avatar_ui(
    image_path: Optional[str],
    commercial_usage: str,
    latest_avatar: Optional[str],
    progress: gr.Progress = gr.Progress(),
):
    del latest_avatar

    logs: List[str] = []
    try:
        if not image_path:
            return "❌ 캐릭터 이미지를 선택하세요.", "", None, None

        head, setup_logs = ensure_runtime(progress)
        logs.extend(setup_logs)

        progress(0.30, desc="Avatar 생성 시작")
        build_avatar, _, _ = _pipeline_imports()

        run_id = uuid.uuid4().hex[:10]
        output_dir = OUTPUT_ROOT / f"avatar-{run_id}"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = build_avatar(
            image_path=str(image_path),
            output_dir=str(output_dir),
            config={
                "profile": "commercial",
                "commercial_usage": commercial_usage,
            },
        )
        logs.extend(_stage_log(result.get("stages", {})))

        if result.get("status") != "complete":
            reason = (
                result.get("failed_reason")
                or result.get("failed_stages")
                or result.get("status")
            )
            return (
                f"❌ Avatar 생성 실패: {reason}",
                "\n".join(logs),
                None,
                None,
            )

        vrm_path = pathlib.Path(result["vrm_path"])
        if not vrm_path.is_file():
            raise RuntimeError(f"VRM output missing: {vrm_path}")

        progress(1.0, desc="완료")
        logs.append(f"완료: {vrm_path.name}")
        return (
            f"✅ 캐릭터 VRM 생성 완료 · main {head[:12]}",
            "\n".join(logs),
            str(vrm_path),
            str(vrm_path),
        )
    except Exception as exc:
        logs.append(traceback.format_exc())
        return (
            f"❌ 실패: {exc}",
            "\n".join(logs),
            None,
            None,
        )


def _normalize_file_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    name = getattr(value, "name", None)
    return str(name) if name else None


def build_accessories_ui(
    use_latest_avatar: bool,
    base_vrm: Any,
    latest_avatar: Optional[str],
    *slot_values: Any,
    progress: gr.Progress = gr.Progress(),
):
    logs: List[str] = []

    try:
        head, setup_logs = ensure_runtime(progress)
        logs.extend(setup_logs)
        _, reconstruct_accessories, AccessoryPipeline = _pipeline_imports()

        base_path: Optional[str] = None
        if use_latest_avatar and latest_avatar and pathlib.Path(latest_avatar).is_file():
            base_path = latest_avatar
        else:
            base_path = _normalize_file_value(base_vrm)

        if not base_path or not pathlib.Path(base_path).is_file():
            return (
                "❌ 기준 캐릭터 VRM을 선택하세요.",
                "\n".join(logs),
                None,
            )

        slot_width = 7
        if len(slot_values) % slot_width != 0:
            raise RuntimeError("Accessory slot contract mismatch")

        slots: List[Dict[str, Any]] = []
        for i in range(0, len(slot_values), slot_width):
            image_value = slot_values[i]
            anchor = str(slot_values[i + 1] or "HEAD_TOP")
            image_path = _normalize_file_value(image_value)
            if not image_path:
                continue

            slot: Dict[str, Any] = {
                "image": image_path,
                "anchor": anchor,
            }
            if anchor == "CUSTOM":
                parent_bone = str(slot_values[i + 2] or "").strip()
                if not parent_bone:
                    raise RuntimeError(
                        "CUSTOM 부착 위치는 parent bone/node 이름이 필요합니다."
                    )
                try:
                    offset = [
                        float(slot_values[i + 3]),
                        float(slot_values[i + 4]),
                        float(slot_values[i + 5]),
                    ]
                    target_size = float(slot_values[i + 6])
                except (TypeError, ValueError) as exc:
                    raise RuntimeError(
                        "CUSTOM offset/size는 숫자여야 합니다."
                    ) from exc
                if target_size <= 0.0:
                    raise RuntimeError("CUSTOM target size는 0보다 커야 합니다.")
                slot["custom_anchor"] = {
                    "parent_bone": parent_bone,
                    "offset": offset,
                    "target_size": target_size,
                }
            slots.append(slot)

        if not slots:
            return (
                "❌ 악세사리 이미지를 1개 이상 선택하세요.",
                "\n".join(logs),
                None,
            )

        progress(0.30, desc="악세사리 3D 재구성")
        source_paths = [slot["image"] for slot in slots]
        recon_dir = OUTPUT_ROOT / f"accessory-recon-{uuid.uuid4().hex[:10]}"
        reconstructed = reconstruct_accessories(
            source_paths,
            str(recon_dir),
            profile="commercial",
        )
        if len(reconstructed) != len(slots):
            raise RuntimeError(
                f"Accessory reconstruction count mismatch: {len(reconstructed)} != {len(slots)}"
            )

        current_vrm = base_path
        total = len(slots)

        for index, (slot, item) in enumerate(
            zip(slots, reconstructed),
            start=1,
        ):
            source_path = slot["image"]
            anchor = slot["anchor"]
            if item.get("status") != "complete" or not item.get("mesh"):
                raise RuntimeError(
                    f"{pathlib.Path(source_path).name} 3D 재구성 실패: "
                    f"{item.get('error') or item}"
                )

            progress(
                0.35 + 0.55 * (index - 1) / max(total, 1),
                desc=f"악세사리 {index}/{total} 적용",
            )
            logs.append(
                f"[{index}/{total}] {pathlib.Path(source_path).name} → {anchor}"
            )

            item_dir = OUTPUT_ROOT / f"accessory-{uuid.uuid4().hex[:10]}"
            result = AccessoryPipeline(str(item_dir)).build(
                base_vrm=current_vrm,
                accessory_glb=item["mesh"],
                config={
                    "anchor_name": anchor,
                    "custom_anchor": slot.get("custom_anchor"),
                    "bake": True,
                },
            )
            logs.extend(
                _stage_log(
                    {
                        f"{pathlib.Path(source_path).name}/{name}": stage
                        for name, stage in result.get("stages", {}).items()
                    }
                )
            )

            if result.get("status") != "complete":
                raise RuntimeError(
                    f"{pathlib.Path(source_path).name} 적용 실패: "
                    f"{result.get('failed_stages') or result.get('failed_reason') or result.get('status')}"
                )
            current_vrm = result["output_vrm"]

        final_path = pathlib.Path(current_vrm)
        if not final_path.is_file():
            raise RuntimeError(f"Combined VRM output missing: {final_path}")

        progress(1.0, desc="완료")
        logs.append(f"완료: {final_path.name}")
        return (
            f"✅ 악세사리 적용 완료 · {total}개 · main {head[:12]}",
            "\n".join(logs),
            str(final_path),
        )
    except Exception as exc:
        logs.append(traceback.format_exc())
        return (
            f"❌ 실패: {exc}",
            "\n".join(logs),
            None,
        )


CSS = """
.gradio-container {
  max-width: 1120px !important;
  margin: 0 auto !important;
}
#hero {
  border: 1px solid #d9dce1;
  border-radius: 16px;
  padding: 18px 22px;
  margin-bottom: 14px;
}
.mode-tab button {
  font-size: 18px !important;
  font-weight: 700 !important;
  min-height: 54px !important;
}
.section-note {
  border: 1px solid #e2e5ea;
  border-radius: 12px;
  padding: 12px 14px;
}
.run-button {
  min-height: 48px !important;
  font-size: 16px !important;
  font-weight: 700 !important;
}
"""


def build_app() -> gr.Blocks:
    with gr.Blocks(
        title="VTuber Builder",
        css=CSS,
        theme=gr.themes.Soft(),
    ) as demo:
        latest_avatar = gr.State(value=None)

        gr.HTML(
            """
            <div id="hero">
              <div style="font-size:30px;font-weight:800">VTuber Builder</div>
              <div style="color:#5f6368;margin-top:4px">
                만들 작업을 선택하고 파일을 올린 뒤 실행하세요.
              </div>
            </div>
            """
        )

        with gr.Tabs(elem_classes=["mode-tab"]):
            with gr.Tab("① 캐릭터 / 얼굴 만들기", id="avatar"):
                gr.Markdown(
                    """
                    ### 캐릭터 이미지 → VTuber VRM
                    얼굴·머리·상체 fitting, 표정·립싱크·눈동자·헤어 물리까지 포함한 VRM을 만듭니다.
                    """,
                    elem_classes=["section-note"],
                )

                with gr.Row():
                    avatar_image = gr.Image(
                        label="캐릭터 이미지 1장",
                        sources=["upload"],
                        type="filepath",
                        height=360,
                    )
                    with gr.Column():
                        usage = gr.Dropdown(
                            label="출력 사용 범위",
                            choices=[
                                ("기업/수익 사용 허용", "corporation"),
                                ("개인 수익 사용", "personalProfit"),
                                ("개인 비영리", "personalNonProfit"),
                            ],
                            value="corporation",
                        )
                        avatar_run = gr.Button(
                            "캐릭터 VRM 생성",
                            variant="primary",
                            elem_classes=["run-button"],
                        )
                        avatar_status = gr.Markdown("대기 중")
                        avatar_result = gr.File(
                            label="완성 VRM 다운로드",
                            interactive=False,
                        )

                avatar_log = gr.Textbox(
                    label="진행 로그",
                    lines=14,
                    max_lines=24,
                    interactive=False,
                )

                avatar_run.click(
                    fn=build_avatar_ui,
                    inputs=[avatar_image, usage, latest_avatar],
                    outputs=[
                        avatar_status,
                        avatar_log,
                        avatar_result,
                        latest_avatar,
                    ],
                    show_progress="full",
                )

            with gr.Tab("② 악세사리 만들기", id="accessory"):
                gr.Markdown(
                    """
                    ### 기존 VRM + 악세사리 이미지 → 악세사리 적용 VRM
                    각 악세사리를 개별적으로 3D 재구성하고 원하는 위치에 붙입니다.
                    """,
                    elem_classes=["section-note"],
                )

                use_latest = gr.Checkbox(
                    label="이 세션에서 방금 만든 캐릭터 VRM 사용",
                    value=True,
                )
                base_vrm = gr.File(
                    label="또는 기준 캐릭터 VRM 업로드",
                    file_types=[".vrm"],
                    type="filepath",
                )

                gr.Markdown("### 악세사리 슬롯")
                accessory_inputs: List[Any] = []

                for slot in range(8):
                    with gr.Accordion(
                        f"악세사리 {slot + 1}",
                        open=(slot == 0),
                    ):
                        with gr.Row():
                            image = gr.Image(
                                label=f"악세사리 {slot + 1} 이미지",
                                sources=["upload"],
                                type="filepath",
                                height=220,
                            )
                            anchor = gr.Dropdown(
                                label="부착 위치",
                                choices=ANCHORS,
                                value="HEAD_TOP",
                            )
                        gr.Markdown(
                            "CUSTOM 선택 시 아래 값만 사용합니다. "
                            "offset 단위는 meter이며 parent bone/node의 로컬 좌표입니다."
                        )
                        custom_parent = gr.Dropdown(
                            label="CUSTOM parent bone/node",
                            choices=[
                                "head", "neck", "chest", "upperChest", "hips",
                                "leftShoulder", "rightShoulder",
                                "leftHand", "rightHand",
                                "leftFoot", "rightFoot",
                            ],
                            value="head",
                            allow_custom_value=True,
                        )
                        with gr.Row():
                            custom_x = gr.Number(label="CUSTOM X", value=0.0)
                            custom_y = gr.Number(label="CUSTOM Y", value=0.0)
                            custom_z = gr.Number(label="CUSTOM Z", value=0.0)
                            custom_size = gr.Number(
                                label="CUSTOM target size",
                                value=0.12,
                                minimum=0.001,
                            )
                        accessory_inputs.extend([
                            image,
                            anchor,
                            custom_parent,
                            custom_x,
                            custom_y,
                            custom_z,
                            custom_size,
                        ])

                accessory_run = gr.Button(
                    "악세사리 적용",
                    variant="primary",
                    elem_classes=["run-button"],
                )
                accessory_status = gr.Markdown("대기 중")
                accessory_result = gr.File(
                    label="완성 VRM 다운로드",
                    interactive=False,
                )
                accessory_log = gr.Textbox(
                    label="진행 로그",
                    lines=14,
                    max_lines=24,
                    interactive=False,
                )

                accessory_run.click(
                    fn=build_accessories_ui,
                    inputs=[
                        use_latest,
                        base_vrm,
                        latest_avatar,
                        *accessory_inputs,
                    ],
                    outputs=[
                        accessory_status,
                        accessory_log,
                        accessory_result,
                    ],
                    show_progress="full",
                )

    return demo


def launch() -> None:
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    demo = build_app()
    demo.queue(default_concurrency_limit=1)

    # Gradio 6.3.0 is pinned by the notebook because later 6.x releases have
    # a documented Colab share=False regression. Keep the cell alive while
    # the inline UI server is running.
    demo.launch(
        inline=True,
        share=False,
        debug=True,
        prevent_thread_lock=False,
        show_error=True,
        height=1100,
        allowed_paths=[str(WORK_ROOT), str(OUTPUT_ROOT)],
    )


if __name__ == "__main__":
    launch()
