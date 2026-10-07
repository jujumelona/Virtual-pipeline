# VTuber Commercial Pipeline

[![Notebook Source](https://img.shields.io/badge/notebook-open%20source-blue.svg)](https://github.com/jujumelona/Virtual-pipeline/blob/main/notebooks/VTuber_Commercial_Pipeline_Colab.ipynb)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)

외부에서 만든 캐릭터 이미지를 입력으로 받아 상업용 VTuber VRM과 액세서리 변형을 만드는 fail-closed 파이프라인입니다.

## Mainline

### Avatar Mode

```text
character image
→ input quality gate + anime face landmarks
→ pinned TripoSR reconstruction
→ pinned MakeHuman CC0 canonical topology
→ rigid + sparse non-rigid fitting
→ source-image texture transfer
→ humanoid skin + eye bones + secondary hair chain
→ blink / visemes / emotions
→ look-at
→ VRMC_springBone
→ VRM 1.0 export
→ strict product validator
→ avatar.vrm
```

필수 stage가 실패하거나 필수 artifact가 없으면 최종 상태는 `failed`입니다. canonical template이나 placeholder 결과로 조용히 대체하지 않습니다.

### Accessory Mode

```text
completed avatar.vrm
+ accessory images
→ pinned TripoSR reconstruction per item
→ GLB normalization
→ real VRM bone anchor extraction
→ scale / transform fitting
→ penetration check + push-out
→ static GLB merge with index/buffer remapping
→ bone parenting
→ combined.vrm
```

동적 accessory physics는 선택 기능입니다. 현재 static bake가 기본이며, physics를 명시적으로 활성화한 경우 skin/bone merge가 완성되지 않았으면 `partial`로 표시합니다.

## Commercial source policy

| Component | Pin | License |
|---|---|---|
| TripoSR | `107cefdc244c39106fa830359024f6a2f1c78871` | MIT |
| anime-face-detector | `0.1.0` | MIT |
| MakeHuman base mesh | `a8bc2d54ff0ac92e78ff71431b1023eda42bf482` | CC0 |
| VRM writer | local `pygltflib` path | project dependency |

Commercial/production avatar reconstruction verifies the TripoSR git revision before running.

`third_party.lock.json` separates source revisions from binary integrity hashes. `artifact_sha256` is never filled with a git SHA or package version. It is reserved for a real SHA256 of downloaded artifact bytes.

## Installation

```bash
git clone https://github.com/jujumelona/Virtual-pipeline.git
cd Virtual-pipeline

git clone https://github.com/VAST-AI-Research/TripoSR.git
git -C TripoSR checkout 107cefdc244c39106fa830359024f6a2f1c78871
python -m pip install -r TripoSR/requirements.txt

python -m pip install -e .
export TRIPOSR_DIR="$PWD/TripoSR"
```

Python 3.12 이상이 필요합니다.

## Google Colab

현재 저장소가 **private**이면 Colab의 `/github/...` URL이 GitHub Contents API에서 404를 받을 수 있으므로 README에는 깨지는 direct Colab 버튼을 두지 않습니다.

위 **Notebook Source** 버튼으로 최신 `main/notebooks/VTuber_Commercial_Pipeline_Colab.ipynb`를 엽니다.

### 저장소가 public인 경우

토큰이 전혀 필요 없습니다.

노트북 Setup은 먼저 **익명 clone/fetch**를 시도하고 그대로 최신 `origin/main`을 설치합니다. 저장소를 public으로 전환하면 다음 direct Colab URL도 정상적으로 사용할 수 있습니다.

```text
https://colab.research.google.com/github/jujumelona/Virtual-pipeline/blob/main/notebooks/VTuber_Commercial_Pipeline_Colab.ipynb
```

### 저장소가 private인 경우

노트북 자체를 Colab에 업로드한 뒤 실행하면 됩니다. Setup은 익명 clone을 먼저 시도하고, 그게 실패할 때만 `GITHUB_TOKEN`을 찾습니다.

즉 **토큰은 private 저장소 접근 때문에만 필요하고, public이면 요청하지 않습니다.**

### 사용자 UI

설치가 끝난 뒤에는 코드 셀을 직접 편집할 필요 없이 하나의 UI에서 실행합니다.

- **Avatar 만들기 / Accessory 붙이기** 모드 선택
- 캐릭터 이미지 업로드
- commercial usage 선택
- base VRM 업로드 또는 방금 생성한 Avatar VRM 재사용
- 악세사리 이미지 여러 장 업로드
- 악세사리 파일별 anchor 드롭다운
- 실행 버튼
- 진행 로그
- 성공 후 VRM 다운로드 버튼

Setup은 매 실행마다 최신 `origin/main`으로 reset한 뒤 그 checkout을 editable install하므로, 노트북 사본이 조금 오래돼도 실제 실행 코드는 최신 main입니다.

## CLI

### Avatar

```bash
vtuber-pipeline avatar \
  --image my_character.png \
  --output output/avatar \
  --profile commercial \
  --commercial-usage corporation
```

### Accessory

```bash
vtuber-pipeline accessory \
  --base-vrm output/avatar/avatar.vrm \
  --images crown.png \
  --images ribbon.png \
  --anchor HEAD_TOP \
  --output output/accessories
```

## Python API

```python
from vtuber_pipeline.avatar import build_avatar
from vtuber_pipeline.accessory import reconstruct_accessories, AccessoryPipeline

avatar = build_avatar(
    image_path="character.png",
    output_dir="output/avatar",
    config={
        "profile": "commercial",
        "commercial_usage": "corporation",
    },
)
if avatar["status"] != "complete":
    raise RuntimeError(avatar)

reconstructed = reconstruct_accessories(
    ["crown.png"],
    "output/accessory_reconstruction",
)
mesh = reconstructed[0]["mesh"]

variant = AccessoryPipeline("output/crown").build(
    base_vrm=avatar["vrm_path"],
    accessory_glb=mesh,
    config={
        "anchor_name": "HEAD_TOP",
        "physics": {"enabled": False},
    },
)
```

## Canonical template

Production does not use the old sphere/cylinder/box template. `get_template_path()` resolves an explicit `VTUBER_TEMPLATE_PATH`, an existing repository template, or creates a cached template from the pinned MakeHuman CC0 `base.obj`.

Facial expression vertex groups are derived from the active fitted/rigged mesh topology by default. Historical fixed vertex-index maps are not used in production.

## Validation contract

A completed avatar requires all of the following:

- VRMC_vrm 1.0 extension
- required humanoid bone bindings
- skin + `JOINTS_0` + `WEIGHTS_0`
- embedded material / texture / image
- blink, blinkLeft, blinkRight
- aa, ih, ou, ee, oh
- happy, angry, sad, relaxed, surprised
- morph-target binds that point to real targets
- valid look-at configuration
- at least one valid SpringBone chain

## Repository layout

```text
notebooks/
  VTuber_Commercial_Pipeline_Colab.ipynb
tools/
  audit_third_party.py
  fetch_cc0_assets.py
vtuber_pipeline/
  avatar/
    build.py
    input_gate.py
    face_detector.py
    reconstruction.py
    template_mesh.py
    template_fitting.py
    texture_transfer.py
    rigging.py
    expressions.py
    gaze.py
    springbone.py
    vrm_builder.py
    vrm_export.py
    validator.py
  accessory/
    reconstruction.py
    normalize.py
    anchors.py
    fitting.py
    collision.py
    physics.py
    bake.py
    build.py
tests/
third_party.lock.json
```

## Integrity audit

```bash
python tools/audit_third_party.py
```

감사 도구는 실제 다운로드된 파일이 있을 때만 SHA256을 계산합니다. 외부 artifact가 로컬에 없으면 hash를 만들어내지 않습니다.

## License

프로젝트 코드는 MIT입니다. 외부 구성요소의 라이선스와 고정 revision은 `third_party.lock.json` 및 canonical asset provenance 문서에서 별도로 관리합니다.
