"""Cross-file runtime, model, notebook, and packaging lock contracts."""

from __future__ import annotations

import ast
import json
import pathlib
import re
import tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = pathlib.Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _constants(path: str) -> dict[str, object]:
    tree = ast.parse(_read(path), filename=path)
    result: dict[str, object] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
        ):
            result[node.targets[0].id] = node.value.value
    return result


def _requirement_contract(raw: str) -> tuple[str, tuple[str, ...], str]:
    req = Requirement(raw)
    return (
        canonicalize_name(req.name),
        tuple(sorted(req.extras)),
        str(req.specifier),
    )


def test_python_support_contract_matches_ci_and_readme():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    workflow = _read(".github/workflows/ci.yml")
    readme = _read("README.md")

    assert pyproject["project"]["requires-python"] == ">=3.12,<3.14"
    assert 'python-version: ["3.12", "3.13"]' in workflow
    assert "3.12 또는 3.13" in readme


def test_requirements_and_pyproject_direct_dependencies_match():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    project_deps = {
        _requirement_contract(raw)
        for raw in pyproject["project"]["dependencies"]
    }
    requirements = {
        _requirement_contract(line.strip())
        for line in _read("requirements.txt").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert requirements == project_deps


def test_all_source_and_model_pins_agree():
    from vtuber_pipeline.avatar.face_detector import ANIME_FACE_MODEL_PINS
    from vtuber_pipeline.avatar.reconstruction import (
        TRIPOSR_MODEL_CONFIG,
        TRIPOSR_MODEL_ID,
        TRIPOSR_MODEL_REVISION,
        TRIPOSR_MODEL_WEIGHT_SHA256,
        TRIPOSR_PINNED_COMMIT,
    )
    from vtuber_pipeline.avatar.template_mesh import (
        MAKEHUMAN_BASE_GIT_BLOB_SHA1,
        MAKEHUMAN_CC0_COMMIT,
    )
    from vtuber_pipeline.avatar.triposr_runner import (
        DINO_MODEL_ID,
        DINO_MODEL_REVISION,
    )

    lock = json.loads(_read("third_party.lock.json"))
    tools = lock["tools"]
    colab = _constants("tools/colab_app.py")
    readme = _read("README.md")
    requirements = _read("requirements.txt")

    assert tools["triposr"]["source_commit"] == TRIPOSR_PINNED_COMMIT
    assert tools["triposr"]["model_id"] == TRIPOSR_MODEL_ID
    assert tools["triposr"]["model_revision"] == TRIPOSR_MODEL_REVISION
    assert tools["triposr"]["model_weight_sha256"] == TRIPOSR_MODEL_WEIGHT_SHA256
    assert colab["TRIPOSR_COMMIT"] == TRIPOSR_PINNED_COMMIT
    assert colab["TRIPOSR_MODEL_REVISION"] == TRIPOSR_MODEL_REVISION
    assert colab["TRIPOSR_MODEL_WEIGHT_SHA256"] == TRIPOSR_MODEL_WEIGHT_SHA256
    assert TRIPOSR_PINNED_COMMIT in requirements
    assert TRIPOSR_PINNED_COMMIT in readme

    assert tools["makehuman_cc0"]["source_commit"] == MAKEHUMAN_CC0_COMMIT
    assert (
        tools["makehuman_cc0"]["git_blob_sha1"]
        == MAKEHUMAN_BASE_GIT_BLOB_SHA1
    )
    assert re.fullmatch(r"[0-9a-f]{40}", MAKEHUMAN_BASE_GIT_BLOB_SHA1)
    assert MAKEHUMAN_CC0_COMMIT in readme

    assert "torchmcubes" not in tools
    assert "TORCHMCUBES_COMMIT" not in colab
    assert tools["scikit_image"]["package"] == "scikit-image"
    assert tools["scikit_image"]["package_version"] == "0.26.0"

    assert tools["dino_vitb16"]["model_id"] == DINO_MODEL_ID
    assert tools["dino_vitb16"]["source_commit"] == DINO_MODEL_REVISION
    assert (
        TRIPOSR_MODEL_CONFIG["image_tokenizer"][
            "pretrained_model_name_or_path"
        ]
        == DINO_MODEL_ID
    )

    from vtuber_pipeline.avatar.reconstruction import REMBG_U2NET_MD5
    assert tools["rembg"]["model_name"] == "u2net"
    assert tools["rembg"]["model_md5"] == REMBG_U2NET_MD5
    assert re.fullmatch(r"[0-9a-f]{32}", REMBG_U2NET_MD5)

    for value in (
        TRIPOSR_MODEL_WEIGHT_SHA256,
        tools["gradio"]["published_wheel_sha256"],
    ):
        assert re.fullmatch(r"[0-9a-f]{64}", value)


def test_pinned_package_versions_agree_with_runtime_surfaces():
    from vtuber_pipeline.avatar.face_detector import ANIME_FACE_MODEL_PINS

    lock = json.loads(_read("third_party.lock.json"))
    pyproject = tomllib.loads(_read("pyproject.toml"))
    requirements = _read("requirements.txt")
    colab_source = _read("tools/colab_app.py")
    notebook = json.loads(_read("notebooks/VTuber_Commercial_Pipeline_Colab.ipynb"))
    notebook_code = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    )

    project_deps = pyproject["project"]["dependencies"]

    anime_entry = lock["tools"]["anime_face_detector"]
    anime = anime_entry["package_version"]
    assert anime_entry["models"]["yolov3"] == {
        "model_id": "hysts/anime-face-detector-yolov3",
        "revision": ANIME_FACE_MODEL_PINS[
            "hysts/anime-face-detector-yolov3"
        ]["revision"],
        "weight_sha256": ANIME_FACE_MODEL_PINS[
            "hysts/anime-face-detector-yolov3"
        ]["sha256"],
        "license": "MIT",
    }
    assert anime_entry["models"]["hrnetv2"] == {
        "model_id": "hysts/anime-face-detector-hrnetv2",
        "revision": ANIME_FACE_MODEL_PINS[
            "hysts/anime-face-detector-hrnetv2"
        ]["revision"],
        "weight_sha256": ANIME_FACE_MODEL_PINS[
            "hysts/anime-face-detector-hrnetv2"
        ]["sha256"],
        "license": "MIT",
    }
    for pin in ANIME_FACE_MODEL_PINS.values():
        assert re.fullmatch(r"[0-9a-f]{40}", pin["revision"])
        assert re.fullmatch(r"[0-9a-f]{64}", pin["sha256"])

    assert f"anime-face-detector=={anime}" in project_deps
    assert f"anime-face-detector=={anime}" in requirements
    assert f"anime-face-detector=={anime}" in colab_source

    pygltf = lock["tools"]["pygltflib"]["package_version"]
    assert f"pygltflib=={pygltf}" in project_deps
    assert f"pygltflib=={pygltf}" in requirements
    assert f"pygltflib=={pygltf}" in colab_source

    # Every exact runtime package pin in the lock must match the Colab
    # installation surface instead of drifting independently.
    for key in (
        "anime_face_detector",
        "pygltflib",
        "pillow",
        "xatlas",
        "moderngl",
        "onnxruntime",
        "transformers",
        "trimesh",
        "rembg",
        "scikit_image",
    ):
        item = lock["tools"][key]
        package = item["package"]
        version = item["package_version"]
        assert f"{package}=={version}" in colab_source, (key, package, version)

    # Direct project dependencies that are exact-pinned in the lock must also
    # resolve to the exact version in package metadata. Compare normalized PEP
    # 508 names so Pillow/pillow and extras such as trimesh[easy] are handled
    # without weakening the version contract.
    project_requirements = [
        Requirement(raw) for raw in project_deps
    ]
    requirements_requirements = [
        Requirement(line.strip())
        for line in requirements.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    for key in ("anime_face_detector", "pygltflib", "pillow", "trimesh"):
        item = lock["tools"][key]
        expected_name = canonicalize_name(item["package"])
        expected_specifier = f"=={item['package_version']}"
        for surface_name, surface in (
            ("pyproject", project_requirements),
            ("requirements", requirements_requirements),
        ):
            matches = [
                req for req in surface
                if canonicalize_name(req.name) == expected_name
            ]
            assert len(matches) == 1, (
                key,
                surface_name,
                [str(req) for req in matches],
            )
            assert str(matches[0].specifier) == expected_specifier, (
                key,
                surface_name,
                str(matches[0]),
                expected_specifier,
            )

    gradio = lock["tools"]["gradio"]["package_version"]
    assert _constants("tools/colab_app.py")["GRADIO_VERSION"] == gradio
    assert f"gradio=={gradio}" in notebook_code



def test_readme_open_in_colab_badge_targets_canonical_three_step_notebook():
    """Keep README's primary Colab launch button wired to the updated file."""
    readme = _read("README.md")
    notebook_file = "notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb"
    badge = (
        "[![Open In Colab]"
        "(https://colab.research.google.com/assets/colab-badge.svg)]"
    )
    launch_url = (
        "https://colab.research.google.com/github/"
        "jujumelona/Virtual-pipeline/blob/main/" + notebook_file
    )
    assert badge + "(" + launch_url + ")" in readme
    assert readme.count(launch_url) == 1
    notebook = json.loads(_read(notebook_file))
    code_cells = [
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    ]
    assert len(code_cells) == 3
    assert "setup_python" in code_cells[0]
    # The second cell is intentionally lazy: the model set is determined by
    # choosing Inochi2D, Live2D or VRM in the third-cell Gradio UI.
    assert "모드별 모델 준비" in code_cells[1]
    assert "prepare_models(" not in code_cells[1]
    assert "subprocess.Popen(" not in code_cells[1]
    app = _read("tools/colab_app.py")
    assert "prepare_models(mode)" in app
    assert "_model_marker(scope)" in app
    assert "colab_ui_launcher.py" in code_cells[2]
    assert 'run_name="__main__"' in code_cells[2]
    assert "del _launcher_globals" in code_cells[2]


def test_colab_notebook_has_separate_environment_models_and_ui_cells():
    notebook = json.loads(_read("notebooks/VTuber_Commercial_Pipeline_Colab.ipynb"))
    code_cells = [
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    ]
    code = "\n".join(code_cells)

    assert len(code_cells) == 3
    setup, models, launch = code_cells
    assert '"fetch", "--prune", "origin", "main"' in setup
    assert '"reset", "--hard", "origin/main"' in setup
    assert "REPO_DIR / 'tools' / 'colab_app.py'" in setup
    assert "app['ensure_runtime']()" in setup
    assert 'run([sys.executable, "-u", "-c", setup_python], 9000)' in setup
    assert "prepare_models" in models
    assert '"pip", "install"' not in models
    assert "runpy.run_path" in launch
    assert 'run_name="__main__"' in launch
    assert "ensure_runtime" not in launch
    assert '"pip", "install"' not in launch

    # The notebook must not carry a stale second implementation of the app.
    for forbidden in (
        "class AvatarPipeline",
        "class AccessoryPipeline",
        "def reconstruct_avatar",
        "def build_avatar_ui",
        "def build_accessories_ui",
    ):
        assert forbidden not in code


def test_lock_entries_are_fail_closed_and_complete():
    lock = json.loads(_read("third_party.lock.json"))
    tools = lock.get("tools")
    assert isinstance(tools, dict) and tools

    for name, item in tools.items():
        # Retain a known non-commercial dependency in the source lock as a
        # quarantine record; never rewrite its commercial flag to pass tests.
        expected_safe = name != "instantmesh_large"
        assert item.get("commercial_safe") is expected_safe, name
        assert isinstance(item.get("license"), str) and item["license"], name

        has_package_pin = bool(
            item.get("package") and item.get("package_version")
        )
        has_source_pin = bool(item.get("source_commit"))
        assert has_package_pin or has_source_pin, (
            name,
            "entry has neither package version nor source revision",
        )

    triposr = tools["triposr"]
    assert re.fullmatch(r"[0-9a-f]{40}", triposr["model_revision"])
    assert re.fullmatch(r"[0-9a-f]{64}", triposr["model_weight_sha256"])

    anime_models = tools["anime_face_detector"].get("models")
    assert isinstance(anime_models, dict) and {
        "yolov3",
        "hrnetv2",
    } <= set(anime_models)
    for model_name, model in anime_models.items():
        assert isinstance(model.get("model_id"), str) and model["model_id"], model_name
        assert re.fullmatch(r"[0-9a-f]{40}", model.get("revision", "")), model_name
        assert re.fullmatch(r"[0-9a-f]{64}", model.get("weight_sha256", "")), model_name
        assert model.get("license") == "MIT", model_name

    rembg = tools["rembg"]
    assert rembg["model_name"] == "u2net"
    assert re.fullmatch(r"[0-9a-f]{32}", rembg["model_md5"])
    assert rembg["model_license"] == "Apache-2.0"

    makehuman = tools["makehuman_cc0"]
    assert re.fullmatch(r"[0-9a-f]{40}", makehuman["source_commit"])
    assert re.fullmatch(r"[0-9a-f]{40}", makehuman["git_blob_sha1"])


def test_commercial_lock_rejects_blocked_license_families():
    lock = json.loads(_read("third_party.lock.json"))
    blocked_patterns = (
        re.compile(r"\\bAGPL\\b", re.I),
        re.compile(r"GNU Affero General Public License", re.I),
        re.compile(r"\\bGPL(?:-|\\b)", re.I),
        re.compile(r"GNU General Public License", re.I),
        re.compile(r"non[- ]commercial", re.I),
        re.compile(r"CC[- ]BY[- ]NC", re.I),
    )

    blocked = {}
    for name, item in lock["tools"].items():
        texts = [
            str(item.get("license") or ""),
            str(item.get("model_license") or ""),
        ]
        models = item.get("models")
        if isinstance(models, dict):
            texts.extend(
                str(model.get("license") or "")
                for model in models.values()
                if isinstance(model, dict)
            )
        hits = [
            text
            for text in texts
            if any(pattern.search(text) for pattern in blocked_patterns)
        ]
        if hits:
            blocked[name] = hits

    # Restricted components are allowed in the manifest only when explicitly
    # quarantined and prevented from executing in commercial pipelines.
    assert set(blocked) <= {"instantmesh_large"}
    assert lock["tools"]["instantmesh_large"]["commercial_safe"] is False
    worker = _read("tools/model_workers/instantmesh_worker.py")
    assert "require_commercial_compatible_upstream(upstream)" in worker
    prefetch = _read("tools/prefetch_model_assets.py")
    assert 'name == "instantmesh_large"' in prefetch


def test_ci_actions_are_immutable_sha_pinned_and_full_suite_is_gated():
    workflow = _read(".github/workflows/ci.yml")

    checkout_sha = "3d3c42e5aac5ba805825da76410c181273ba90b1"
    setup_python_sha = "5fda3b95a4ea91299a34e894583c3862153e4b97"

    assert f"actions/checkout@{checkout_sha}" in workflow
    assert f"actions/setup-python@{setup_python_sha}" in workflow
    assert "actions/checkout@v" not in workflow
    assert "actions/setup-python@v" not in workflow

    # A new main commit must not cancel a full verification already in
    # progress; GitHub coalesces pending runs within this concurrency group.
    assert "group: ci-${{ github.workflow }}-${{ github.ref }}" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "full-suite:" in workflow
    assert "python -m pytest -q tests" in workflow
    assert "- full-suite" in workflow
    assert 'test "$FULL_SUITE" = success' in workflow


def test_colab_runtime_marker_is_dependency_fingerprinted():
    source = _read("tools/colab_app.py")

    assert "def _runtime_contract_fingerprint()" in source
    assert 'REPO_DIR / "pyproject.toml"' in source
    assert 'REPO_DIR / "requirements.txt"' in source
    assert 'REPO_DIR / "third_party.lock.json"' in source
    assert "inspect.getsource(_install_runtime)" in source
    assert "runtime_fingerprint[:16]" in source
    assert 'f"runtime_fingerprint={runtime_fingerprint}"' in source
