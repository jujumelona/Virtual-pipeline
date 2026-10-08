# VTuber Commercial Pipeline

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jujumelona/Virtual-pipeline/blob/main/notebooks/VTuber_Commercial_Pipeline_Colab_v5.ipynb)
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

Accessory Mode는 검증된 **static bone-parented bake** 경로만 제공합니다.

## Commercial source policy

| Component | Pin | License |
|---|---|---|
| TripoSR source | `107cefdc244c39106fa830359024f6a2f1c78871` | MIT |
| Marching Cubes mesh extraction | `scikit-image==0.26.0` (prebuilt wheel) | BSD-3-Clause |
| TripoSR model snapshot | `c1cf7716aed5aa6c1c5e174657791ef0e1327bde` + verified `model.ckpt` SHA256 | model license in upstream repository |
| TripoSR nested DINO config | `facebook/dino-vitb16@f205d5d8e640a89a2b8ef0369670dfc37cc07fc2` | Apache-2.0 |
| rembg runtime | `2.0.85` | MIT |
| rembg background model | forced `u2net`, MD5 `60024c5c889badc19c04ad937298a77b` | Apache-2.0 |
| anime-face-detector package | `0.1.0` | MIT |
| anime face YOLOv3 weight | `afdd4226a79ae8bb81f334dbcffd34f8cc000c38` + SHA256 `23bbc708…b2c4` | MIT |
| anime face HRNetV2 weight | `9b3435248b26aeb82e2a8578fe9d86d5d57158af` + SHA256 `e7127137…7a4a` | MIT |
| MakeHuman base mesh | `a8bc2d54ff0ac92e78ff71431b1023eda42bf482` | CC0 |
| VRM writer | local `pygltflib` path | project dependency |

Commercial/production avatar reconstruction verifies the TripoSR git revision before running. The local deterministic TripoSR wrapper also pins the nested DINO config revision and overrides rembg's no-argument default so background removal always uses the Apache-2.0 `u2net` model rather than a changing rembg default. Cached/downloaded `u2net.onnx` bytes are checksum-verified before inference. The anime face path likewise resolves the exact YOLOv3 and HRNetV2 Hugging Face revisions and verifies both safetensors SHA256 values before constructing the detector.

`third_party.lock.json` separates source revisions from binary integrity hashes. `artifact_sha256` is never filled with a git SHA or package version. It is reserved for a real SHA256 of downloaded artifact bytes.

## Installation

로컬에서 설치할 경우 TripoSR의 오래된 `requirements.txt`를 그대로 설치하지 마세요. Colab launcher와 동일한 호환성 세트를 사용하는 것이 기준입니다.

```bash
git clone https://github.com/jujumelona/Virtual-pipeline.git
cd Virtual-pipeline

git clone https://github.com/VAST-AI-Research/TripoSR.git
git -C TripoSR checkout 107cefdc244c39106fa830359024f6a2f1c78871

python -m pip install -e . --no-deps
export TRIPOSR_DIR="$PWD/TripoSR"
```

지원 Python은 **3.12 또는 3.13**입니다.

## Google Colab

상단 **Open In Colab** 버튼으로 열고 **① 환경 설치 → ② 모델 다운로드·검증 → ③ 생성 UI** 순서대로 실행합니다.

### ① 캐릭터 / 얼굴 만들기

- 캐릭터 이미지 1장 업로드
- 출력 사용 범위 선택
- 얼굴/머리/상체 fitting
- blink / viseme / emotion morph
- eye-bone look-at
- hair SpringBone
- **캐릭터 VRM 생성**
- 결과 VRM 다운로드

### ② 악세사리 만들기

- 방금 만든 캐릭터 VRM 재사용 또는 기존 VRM 업로드
- 악세사리 슬롯 최대 8개
- 슬롯마다 이미지와 부착 위치를 **독립적으로 선택**
- 각 악세사리 3D 재구성 / fitting / collision / bone parenting
- **악세사리 적용**
- 결과 VRM 다운로드

## 이미지 생성 프롬프트 (Avatar / Accessory)

이 프로젝트는 **텍스트로 이미지를 직접 생성하지 않습니다.** 아래 프롬프트를 외부 이미지 생성 AI에 입력하여 PNG 등의 이미지를 만든 후, 해당 모드의 업로드 칸에 넣으세요. 아래 문구는 **권장 입력 예시**이며 이미지 생성기나 TripoSR에서 품질이 보장되거나 실제 GPU E2E 검증을 통과했다는 뜻은 아닙니다. 사용하려는 이미지 생성 모델과 모델 가중치, 생성 이미지의 상업적 사용 권한도 별도로 확인하세요.

### ① 캐릭터 / 얼굴 만들기 — 캐릭터 이미지 생성

**목표:** 얼굴 랜드마크 검출, 단일 이미지 3D 재구성, 템플릿 피팅, 리깅에 쓰기 쉬운 **정면 애니메이션 캐릭터 원본 1장**을 생성합니다. `[...]` 부분은 원하는 디자인으로 바꾸세요.

**Positive prompt (복사해서 사용)**

```text
Single original anime-style VTuber character, [character appearance, hairstyle,
hair color, eye color, clothing style and color palette],
clean professional character design, front-facing camera, straight-on view,
neutral expression, mouth closed, both eyes open and clearly visible,
symmetrical face, upright standing posture, relaxed neutral A-pose,
shoulders level, upper arms slightly separated from the torso,
face and hairstyle fully inside the frame, visible neck and shoulders,
upper body to waist clearly visible, clean readable clothing silhouette,
distinct separation between hair, face, arms and clothing,
consistent anatomy and proportions, crisp well-defined features,
soft even studio lighting, minimal shadows, simple uniform light background,
one character only, centered composition, high resolution, sharp image,
no text, no watermark
```

**Negative prompt (별도 입력란이 있을 때 사용)**

```text
side view, profile view, strong three-quarter view, looking away,
head tilt, extreme perspective, foreshortening, action pose,
closed eyes, wink, open mouth, face obscured by hair or accessories,
cropped head, cropped shoulders, hands covering face,
multiple characters, character sheet, collage, split panels,
busy background, scenery, dramatic shadows, backlighting,
low resolution, blurry face, distorted anatomy, extra limbs,
duplicate eyes, text, logo, signature, watermark
```

**업로드 전 확인**

- **정면의 애니메이션 얼굴 1개**가 명확히 보여야 합니다. 앞머리·마스크·장식이 눈과 얼굴 랜드마크를 가리지 않도록 하세요.
- 코드의 입력 품질 게이트는 **가로/세로 각각 256px 이상**, **가로÷세로 비율 0.5~2.0**, **검출된 얼굴 영역이 전체 이미지의 5~80%** 등을 검사합니다. 얼굴은 프레임 테두리에서 충분히 떨어져 있어야 합니다. 얼굴 인식 신뢰도·랜드마크 신뢰도·대칭성 검사도 통과해야 합니다.
- **상반신~허리 구도**를 우선 권장합니다. 전신이 필요하다면 프롬프트를 `full body, entire character visible, feet inside the frame`으로 변경할 수 있지만, 얼굴이 너무 작아지면 **얼굴 면적 5% 조건** 등으로 거부될 수 있습니다. 전신 결과가 자동으로 보장되지는 않습니다.
- 캐릭터 이미지는 **① 캐릭터 / 얼굴 만들기 → 캐릭터 이미지 1장**에 업로드합니다. 얼굴 검출 또는 3D 재구성이 실패하면 다른 정면 이미지로 다시 생성해야 할 수 있습니다.

### ② 악세사리 만들기 — 독립 액세서리 이미지 생성

**목표:** 기존 캐릭터 사진을 다시 만드는 것이 아니라, **부착할 물건 자체만** 단독 이미지로 생성합니다. 한 슬롯에는 **한 물건의 이미지 1장**을 사용하세요. `[...]` 부분을 왕관·머리핀·리본·귀걸이·목걸이 등 원하는 디자인으로 바꾸세요.

**Positive prompt (복사해서 사용)**

```text
One standalone [accessory type and detailed design], original stylized
anime VTuber accessory, isolated single physical object, clearly defined
three-dimensional form and thickness, coherent front and side surfaces,
clean three-quarter product view, centered object,
entire accessory completely inside the frame,
object occupies most of the image with comfortable empty margins,
clear silhouette, visible attachment-facing structure where applicable,
consistent materials and decorative details, sharp geometry,
even soft studio lighting, minimal shadows,
plain uniform light contrasting background, high resolution,
no human, no mannequin, no other objects, no text, no watermark
```

**Negative prompt (별도 입력란이 있을 때 사용)**

```text
person, face, head, body, hands, hair, mannequin, display stand,
model wearing the accessory, multiple accessories, collection,
duplicate objects, contact sheet, collage, multi-view sheet,
cut-off object, extreme close-up, floating disconnected pieces,
transparent or visually ambiguous geometry, complex scene,
busy background, harsh shadows, motion blur, low resolution,
text, labels, price tag, logo, signature, watermark
```

**액세서리별 프롬프트 치환 예시**

| 부착 위치 | `[accessory type and detailed design]` 예시 |
|---|---|
| `HEAD_TOP` | `a small silver crown with blue gemstones and a complete circular base` |
| `LEFT_EAR` / `RIGHT_EAR` | `a single star-shaped earring with one complete hook and pendant` |
| `CHEST` / `NECK` | `a decorative brooch with a clearly visible back plate` |
| `BACK` | `a single compact ribbon bow with visible loops and center knot` |
| `LEFT_HAND` / `RIGHT_HAND` | `a single handheld magic wand with complete handle and star tip` |

**업로드 전 확인**

- **액세서리 하나씩 따로 생성**하고, 각 이미지를 **② 악세사리 만들기 → 해당 슬롯 이미지**에 업로드하세요. 슬롯은 최대 8개이며, **부착 위치는 이미지마다 개별 지정**합니다.
- `HEAD_TOP`, `LEFT_EAR`, `CHEST` 등은 물건의 디자인을 뜻하는 게 아니라 **생성된 GLB를 기존 VRM의 어느 본에 연결할지** 정하는 옵션입니다. `CUSTOM`은 parent bone/node, offset, target size를 별도로 지정합니다.
- 이 모드는 이미 생성한 `avatar.vrm` 또는 외부에서 만든 기준 VRM이 필요합니다. **정적 bone-parented 액세서리**만 지원하며, 독립적으로 흔들리는 동적 물리·스키닝 액세서리는 지원하지 않습니다.
- TripoSR는 단일 뷰에서 보이지 않는 뒷면과 두께를 추정하므로, **복잡한 장신구·가느다란 연결 부위·투명 재질·반대편과 대칭이어야 하는 물체**는 재구성과 부착 후 검토가 필요합니다. 프롬프트만으로 실제 형상이나 위치의 정확도를 보장하지 않습니다.

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
  --anchor LEFT_EAR \
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
