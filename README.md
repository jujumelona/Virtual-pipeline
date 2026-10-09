# VTuber Commercial Pipeline

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jujumelona/Virtual-pipeline/blob/main/notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)

외부 이미지 생성 AI가 만든 캐릭터 이미지를 입력받아 **Inochi2D**, **Live2D**, **3D VRM** 모델을 제작합니다. 모드별 이미지 생성 사양과 프롬프트는 아래에 정리되어 있습니다.

## 모드별 이미지 생성 프롬프트 — 고해상도 시트 방식

동일한 캐릭터를 유지하도록 **기준 정면 이미지를 먼저 제작**하고, 나머지 시트마다 그 이미지를 첨부합니다. 각 시트는 외부 이미지 생성 모델에서 **한 장의 이미지**로 제작하며, 지정된 파일명·해상도·격자·상대 좌표를 준수합니다. 파츠를 독립적으로 가운데 정렬하면 안 됩니다. 2D는 고정 좌표로 파츠를 잘라 **파츠별 Real-ESRGAN 신경망 초해상도(x4 추론 → 최종 x2)**를 적용해 리깅 입력으로 변환합니다.

### 캐릭터 설정 (모든 시트에 동일하게 적용)

```text
ORIGINAL VTUBER CHARACTER IDENTITY:
Gender / gender presentation: {gender}
Hair color and HEX: {hair_color}
Hairstyle, length, bangs, roots and decorations: {hairstyle}
Eye color, pupils, iris pattern and highlights: {eyes}
Face shape, skin tone, ears and marks: {face}
Outfit, fabric textures, seams, fasteners: {outfit}
Palette / precise HEX colors: {palette}
Accessories: {accessories}
Other permanent features and body proportions: {other_details}

CONSISTENCY LOCK:
Use the original front reference image for every additional sheet.
Same single character, unchanged gender presentation, identity, costume,
colors, line-art style, light direction, anatomy and outline thickness.
Do not mirror the character, improvise different accessories or change
proportions. Each sprite cell must depict ONLY its named semantic part.
Output the image itself, never a collage of other characters, text, labels,
tile indices, borders or watermarks.
```

### 2D: 기준 이미지 + 고해상도 시트 3장

| ZIP 내부 PNG | 해상도 (가로×세로) | 격자 | 셀 크기 |
|---|---:|---|---:|
| `front_master.png` | 2048×3072 | 전체 정면 기준 | — |
| `sheet_face.png` | 4096×4096 | 4열 × 4행 | 1024×1024 |
| `sheet_hair.png` | 4096×6144 | 2열 × 2행 | 2048×3072 |
| `sheet_body_outfit.png` | 4096×6144 | 2열 × 4행 | 2048×1536 |

**공통 좌표 규격:** 정면 기준 원본은 2048×3072. 왼쪽 위 (0,0), +X 오른쪽, +Y 아래쪽. 캐릭터 중심 x=1024, 정수리 y≈240, 눈 y≈1110, 코 y≈1280, 입 y≈1380, 턱 y≈1510, 목 y≈1590, 어깨 y≈1730, 허리 y≈2700. 각 시트의 셀은 *기준 이미지의 특정 사각형*을 복사해 옮겨 놓는 역할입니다. **셀에서 파츠 위치를 새로 중앙 배치하지 않습니다.** 격자 좌표와 해당 파츠의 원래 좌표가 정확하게 대응해야 자른 뒤 리깅 위치가 유지됩니다.

**모든 2D 시트 프롬프트에 추가할 공통 지시:**

```text
EXACT RESOLUTION and EXACT GRID as specified below.
TRUE TRANSPARENT RGBA PNG. Alpha=0 for all pixels outside the named
part. No white, black, gray, or checkerboard fake transparency.
All cell boundaries are mathematical coordinates, NOT drawn lines.
Every cell represents the specified ABSOLUTE ROI in the 2048x3072
front master. Preserve the relative pixel positions of that ROI exactly.
No moving a part to the center; no independently changing part scale.
Complete hidden artwork underneath other parts: skin under hair,
hair roots under other hair, arms beneath fabric, and clothing seams.
Maintain all original color swatches, texture, anti-aliased edges
and linework. Reserved cells must be totally empty (alpha=0).
Render a single high-resolution sheet; do not include titles, numbers,
dividers, backgrounds, annotations, perspective, or other characters.
If the image model cannot output the exact dimensions / RGBA, correct
the generated file before packaging; enlarged export alone does not
reconstruct missing fine detail.
```

#### 2D ① `front_master.png` — 기준 이미지

```text
Render one complete, clean orthographic FRONT VTuber reference.
Canvas EXACTLY 2048x3072 PNG. Neutral upright pose, visible face,
open eyes, closed mouth, clothing and long hair fully within frame.
Head center x=1024; crown y=240; eyes y=1110; mouth y=1380;
shoulders y=1730; waist y=2700. Flat transparent background preferred.
No crop, perspective, title, other character, text or watermark.
```

#### 2D ② `sheet_face.png` — 얼굴·눈·입 확대 시트

```text
Render EXACTLY 4096x4096 PNG RGBA. 4 columns x 4 rows.
Each 1024x1024 tile is an unchanged pixel-coordinate crop of the
2048x3072 master, not an independently recentered illustration.
Row1: ear_left | ear_right | neck | face
Row2: eye_left_white | eye_left_iris | eye_left_lid | brow_left
Row3: eye_right_white | eye_right_iris | eye_right_lid | brow_right
Row4: nose | mouth_closed | mouth_open | COMPLETELY TRANSPARENT
Preserve exact master-space position within each tile's assigned ROI;
paint full occluded portions. Left/right mean CHARACTER left/right
(character-left eye appears on viewer-right in a front-facing image).
Do not place the entire face in eye-only/iris-only tiles.
```

셀 안에서 파츠가 차지할 **원본 이미지 좌표** (왼쪽·위·오른쪽·아래, 우측·하단은 포함하지 않음):

| 파츠 | 원본 기준 ROI: (x0,y0,x1,y1) |
|---|---|
| `ear_left`, `eye_left_white`, `eye_left_iris`, `eye_left_lid`, `brow_left` | (1024,650,2048,1674) |
| `ear_right`, `eye_right_white`, `eye_right_iris`, `eye_right_lid`, `brow_right` | (0,650,1024,1674) |
| `face` | (512,512,1536,1536) |
| `neck` | (512,1420,1536,2444) |
| `nose`, `mouth_closed`, `mouth_open` | (512,900,1536,1924) |

#### 2D ③ `sheet_hair.png` — 머리카락 시트

```text
Render EXACTLY 4096x6144 PNG RGBA. 2 columns x 2 rows.
Each 2048x3072 tile has exactly the same FULL CANVAS coordinates
as front_master.png. No cropped or recentered hair pieces.
Row1 col1: hair_front | col2: hair_back
Row2 col1: hair_left  | col2: hair_right
Render each layer with all invisible roots and covered tips completed.
Only that hair segment is visible in its tile; rest alpha=0.
```

#### 2D ④ `sheet_body_outfit.png` — 신체·의상 시트

```text
Render EXACTLY 4096x6144 PNG RGBA. 2 columns x 4 rows.
Each cell is 2048x1536. Preserve the master-space ROI coordinates below.
Row1: body | outfit_front
Row2: outfit_back | arm_left
Row3: arm_right | hand_left
Row4: hand_right | COMPLETELY TRANSPARENT
Draw the whole indicated part inside its matching cropped master ROI.
Do not center the part inside the cell or invent adjacent limbs.
Paint unseen fabric, sleeves and hidden seams; true alpha background.
```

| 파츠 | 원본 기준 ROI: (x0,y0,x1,y1) |
|---|---|
| `body`, `outfit_front`, `outfit_back` | (0,1300,2048,2836) |
| `arm_left`, `arm_right` | (0,1100,2048,2636) |
| `hand_left`, `hand_right` | (0,1400,2048,2936) |

**2D ZIP 폴더 구성:**

```text
character_2d_sheet_pack.zip
└── character_2d_sheet_pack/
    ├── front_master.png
    ├── sheet_face.png
    ├── sheet_hair.png
    └── sheet_body_outfit.png
```

파일 네 개를 ZIP 최상위에 바로 넣는 구조도 지원합니다. 업로드 시 프로그램이 시트 크기·파일명·RGBA·모든 파츠 칸·비어 있어야 할 칸을 검사합니다. **자르기 → 실제 알파 바운딩 박스 추출 → 파츠별 AI 초해상도 → 기준 좌표에 복원 → 네이티브 레이어 제작** 순서이며, 2D 최종 캔버스는 **4096×6144**입니다. ③ 모델 다운로드 단계에서 별도 초해상도 가중치를 받아 두고 ⑤에서 임시 GPU 프로세스로 실행합니다. FLUX/SAM/Florence로 가려진 부분을 다시 생성하지 않습니다.

### 3D VRM: 4방향 전신 시트 + 얼굴 확대 이미지

| ZIP 내부 PNG | 해상도 | 내용 |
|---|---:|---|
| `sheet_body_views.png` | 4096×6144 | 2×2 격자로 전신 4방향, 셀별 2048×3072 |
| `face.png` | 2048×2048 | 같은 캐릭터의 정면 얼굴 확대 |

```text
Render sheet_body_views.png, exact 4096x6144 PNG.
2 columns x 2 rows; each cell exact 2048x3072 pixels.
Upper-left: FRONT, upper-right: BACK (180 degrees).
Lower-left: LEFT SIDE (90 degrees), lower-right: RIGHT SIDE (90 degrees).
The SAME character, same gender presentation, shape, facial proportions,
hair silhouette, costume folds, palette and lighting in all four views.
Use ORTHOGRAPHIC level cameras, neutral A-pose and aligned body scale.
For every cell independently: crown y=150, neck y=600, shoulders y=730,
waist y=1550, knees y=2330, ground-contact y=2930, body axis x=1024.
No perspective, cropping, ground shadow, text, separator or frame.
Transparent background preferred; do not change the pixel arrangement.
```

```text
Render face.png, exact 2048x2048 PNG, separate from the multiview sheet.
Same character and gender presentation as the FRONT master.
Orthographic FRONT close-up of head, hairline, full eyes, ears and jaw;
face center x=1024, y=1050, unchanged colors and facial anatomy.
No perspective, exaggerated face changes, watermark or text.
```

**3D ZIP 폴더 구성:**

```text
character_3d_sheet_pack.zip
└── character_3d_sheet_pack/
    ├── sheet_body_views.png
    └── face.png
```

프로그램이 4개 전신 이미지를 원본 해상도로 정확히 분할합니다. 얼굴 확대에만 AI 초해상도를 적용한 뒤 기존 3D 복원·다중 뷰 텍스처·리깅 검증 경로로 전달합니다. 다른 시점을 AI로 임의로 만들어내지는 않습니다.

### 액세서리 이미지

기존 VRM에 부착할 액세서리 1~8개를 각각 별도 PNG로 준비합니다. 이미지 한 장마다 물건 한 개, 실제 부착 부위와 두께가 식별되는 단독 정면/사선 제품 뷰. 외부 이미지 프롬프트: `An isolated original {accessory_type}, {material}, {color}, {decoration}, full visible geometry and attachment point, no human/model, clean contrasting background, no text or watermark.`

**품질 한계:** AI 초해상도는 픽셀 수를 늘릴 수 있지만 학습된 텍스처를 추정하기 때문에 원본에 없던 실제 디테일을 보장하지 않습니다. 큰 PNG 시트 생성도 사용하는 이미지 모델의 실제 해상도 제한을 받습니다. 프롬프트만으로 픽셀 단위 정합성은 보장되지 않으므로 입력 검사와 최종 시각 검증이 필요합니다.


## 작업 모드

| UI 모드 | 오픈소스 기반 준비 도구 | 현재 실제 출력 | 완성 방송 모델의 포맷 | 구현 상태 |
|---|---|---|---|---|
| **Inochi2D** | Florence-2 / SAM2 / FLUX + Inochi2D SDK | 실제 레이어 PSD/ORA, 메시·키폼·물리 JSON | `.inp` | **네이티브 구현 및 SDK E2E PASS**: 공식 0.8.7 SDK로 변형·물리 `.inp`를 실제 생성/재로딩. 입력 모델별 SDK 검증 성공 시에만 `complete`, 실패 시 `prepared` |
| **Live2D** | 동일 2D 레이어·리깅 중간 표현 + 정식 Cubism Editor | `avatar.psd`, `cubism_handoff.zip` | `.moc3` + `.model3.json` + 텍스처/물리 | **needs_editor_export**: 공식 Editor에서 출력한 폴더만 검증·수집. 자동 MOC3 인코더 없음 |
| **3D VRM** | TripoSR, Depth Anything V2 Small, MakeHuman, Blender VRM Add-on | 피팅/텍스처/리깅 자료 및 검증 시 `avatar.vrm` + `avatar_rigged.blend` | `.vrm` | **상업용 모델 교체 반영**: InstantMesh 제외, MIT TripoSR 정면·후면·좌우 독립 복원으로 대체. 실제 Colab T4 E2E 검증은 별도 |

**2D 중간 준비 ZIP은 최종 모델이 아닙니다.** Inochi2D는 SDK가 검증한 `.inp`만 방송 모델로 인정하며, Live2D는 정식 Cubism Editor에서 내보낸 `.moc3`만 최종 모델로 인정합니다. 준비된 PSD/ORA는 보완·후속 수정을 위한 편집 자료입니다.

### Inochi2D

- 입력: 외부 AI 기준 이미지 1장 + 개별 투명 파츠 PNG 26장. 관련 이미지 사양은 위 프롬프트에 정의되어 있습니다.
- 현재 출력: `avatar.psd`, `avatar.ora`, `meshes2d.json`, `keyforms.json`, `physics2d.json`, `puppet_spec.json`. SDK 네이티브 출력에 성공한 경우에만 `avatar.inp`를 `complete`로 보고합니다.
- 네이티브 자동화: 공식 BSD-2 **Inochi2D SDK 0.8.7**의 실제 `MeshData`·`Part`·`DeformationParameterBinding`·`SimplePhysics`를 구성하고 SDK의 `inWriteINPPuppet`로 **실제 INP1**을 출력합니다. SDK로 다시 읽어 애니메이션·물리 바인딩을 검사합니다. 0.9 개발판은 현재 변형 바인딩이 비활성화되어 본선에 사용하지 않습니다.
- 실제 컴파일+SDK 네이티브 INP 재임포트 검증: [GitHub Actions PASS](https://github.com/jujumelona/Virtual-pipeline/actions/runs/37878238975). 이 검증은 SDK 프로그램의 정상 작동을 증명하며 **사용자별 AI 파츠 품질을 보증하지는 않습니다.**
- Colab Inochi2D 선택 시 DUB/LDC·SDL2/Xvfb 런타임을 준비합니다. CLI는 필요할 때 자동 SDK 빌드를 시도합니다. 유효한 실행 파일 또는 메시·키폼·물리 바인딩이 없으면 중간 PSD/ORA를 `prepared`로 반환하고, 네이티브 `.inp` 완성을 가장하지 않습니다. [공식 Inochi2D 문서](https://docs.inochi2d.com/en/latest/) 참조.

### Live2D

- 입력: 기준 이미지 + 고해상도 파츠 시트 3장이 들어 있는 ZIP 1개
- 현재 출력: `avatar.psd`, `avatar.ora`, `cubism_handoff.zip`, `cubism_spec.json`. 공식 Editor 내보내기 결과의 MOC3·텍스처·physics·model3 참조는 별도 `live2d-import-export`에서 확인합니다.
- 목표: **Live2D Cubism Editor에서 리깅 후 `.moc3`, `.model3.json`, 텍스처/물리 출력**, VTube Studio에서 로드.
- **Live2D Cubism Editor는 비오픈소스**입니다. 공식 모델 바이너리 생성은 [Cubism 내보내기 문서](https://docs.live2d.com/en/cubism-editor-manual/export-moc3-motion3-files/)에 기술돼 있습니다. 검증된 상업용 오픈소스 MOC3 인코더가 없어 이 프로젝트는 완성된 Live2D 모델을 자동 생성한다고 주장하지 않습니다.
- Inochi2D의 `.inp`는 Live2D의 `.moc3`로 자동 호환되지 않습니다.

### 2D CLI

```bash
vtuber-pipeline inochi2d --image character.png --layers-zip layers.zip --output output/inochi2d
vtuber-pipeline live2d --image character.png --output output/live2d
vtuber-pipeline live2d-import-export --official-export-dir ./cubism-output --output output/live2d
```

사용자 원본 이미지 자체의 상업적 사용 권한은 별도로 확보해야 합니다. 앱·프레임워크의 소스 라이선스와 모델 가중치·데이터 라이선스도 개별 확인해야 합니다.

3D VRM 및 액세서리의 기존 실행·검증 기능은 아래와 같습니다.

## Mainline

### Avatar Mode

```text
front full-body image + independent face reference
+ optional real back / left / right reference images
→ reference quality and 28-point facial landmark validation
→ ISNet foreground segmentation + Depth Anything V2 relative depth
→ pinned MIT TripoSR reconstruction for front and each observed extra view
→ fixed camera-role yaw registration + rejection of inconsistent views
→ evidence-aware multiview alignment (front-only remains inferred geometry)
→ pinned MakeHuman CC0 canonical topology fitting and limited surface refinement
→ 2048-texel multiview atlas (front/face/back/left/right)
→ explicitly identified inferred appearance only for unobserved UV polygons
→ humanoid skin + eye bones + skinned independent hair geometry
→ blink / visemes / emotions / eye-bone gaze / VRMC_springBone
→ initial VRM 1.0 → native Blender VRM Add-on round-trip and .blend project
→ strict VRM product validator
→ avatar.vrm + avatar_rigged.blend
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

## 3D 상업용 경로: 사용권이 제한된 모델의 실제 교체 (2026-10-09)

이 저장소의 **활성 3D 본선에는 이제 InstantMesh와 Zero123++가 포함되지 않습니다.** 사용자에게 없는 상업용 사용권을 요구하지 않도록, 이미 상업적 이용이 가능한 소스/가중치가 확인된 **TripoSR(MIT)** 로 각 실제 입력 시점을 따로 재구성한 뒤, Depth Anything V2 Small 및 canonical MakeHuman 피팅에 연결했습니다.

- 필수: 정면 전신 이미지와 얼굴 확대 이미지. 정면만 있어도 배경 제거·정면 메시·상대 깊이·표면 정합을 실행합니다.
- 품질 향상: 실제 후면·좌/우 측면 사진을 올리면 각 입력으로 **독립 TripoSR 메시**를 만들고, 고정 카메라 방향과 오차 임계값으로 등록 가능한 메시만 결합합니다. 세 측면 전부가 필수는 아닙니다.
- 색상: 정면·얼굴·후면·측면 참조로 각 UV 텍셀을 투영합니다. 입력에서 보이지 않는 표면은 투명하게 방치하지 않고 **추정 색상**으로 보완하며, 관측/추정 픽셀 통계를 별도로 보관합니다.
- 본: MakeHuman topology, 얼굴 Shape Keys, 시선 및 SpringBone, 별도 스킨 적용 머리카락 메시, Blender 네이티브 검증을 유지합니다.
- **정확도 한계:** 서로 다른 그림의 카메라는 실제로 보정되지 않았습니다. 추가 참조가 있어도 3D 형태 및 의상 뒤쪽이 측정되었다고 주장하지 않습니다. 이미지 일관성이 나쁘면 보조 메시를 거절합니다.
- **실행 검증:** CPU 계약 CI와 별개로 Colab T4에서 전체 모델·Blender 실행을 최종 통과해야 방송 품질을 확정할 수 있습니다.

기존 `tools/model_workers/instantmesh_worker.py` 및 연구용 원본 어댑터는 상업용 본선에서 제외하고 사용권 감사 목적으로만 유지합니다. Zero123++ 공개 가중치는 [CC BY-NC 4.0](https://github.com/SUDO-AI-3D/zero123plus#license)이며 Nvidia 코드의 별도 사용 제한도 [nvdiffrast 라이선스](https://github.com/NVlabs/nvdiffrast/blob/main/LICENSE.txt)에 명시되어 있습니다. 우회 추정 뷰를 넣는 것만으로 Nvidia 코드 사용권이 해결되는 것은 아니므로 해당 접근은 본선에 채택하지 않았습니다.

### 선택형 SkinTokens 스키닝 개선과 라이선스 경계

`rigging.provider=skintokens`는 기본 휴머노이드 결과를 먼저 만든 후 **선택한 경우에만** 별도 프로세스에서 SkinTokens를 실행합니다. 동일한 메시·UV·관절 이름과 머리카락 본 바인딩이 유지되는 경우에만 스킨 가중치를 교체하며, 실행 환경이나 체크포인트가 없으면 실패를 보고합니다. 기본 `canonical` 경로는 해당 모델에 의존하지 않습니다.

SkinTokens의 주 저장소와 배포 가중치는 MIT로 안내되지만, [업스트림 상업 배포 문의 #9](https://github.com/VAST-AI-Research/SkinTokens/issues/9)에서 관리자는 **Michelangelo 하위 폴더에는 GPL 표시가 적용된다**고 밝혔습니다. GPL은 상업적 이용 자체를 금지하지 않지만 배포 방식에 따라 소스 제공 의무가 발생할 수 있습니다. 본 저장소는 SkinTokens 코드·가중치를 기본 패키지에 동봉하거나 상업용 기본 모델로 자동 선택하지 않습니다. 해당 개선 옵션의 별도 배포·상업 이용 시 실제 사용 파일의 라이선스 및 GPL 준수 여부를 확인해야 합니다. SkinTokens가 전신 캐릭터의 스키닝 정확도를 반드시 향상시킨다는 보장은 없으며, 실제 추론 및 애니메이션 품질 검증 전에는 완성 판정을 대체하지 않습니다.

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

## Optional Blender bone-heat body skinning (Colab T4 compatible)

The avatar builder now supports a second experimental open-source weight
provider. It reuses the **already-installed Blender** native
`bpy.ops.object.parent_set(type="ARMATURE_AUTO")` bone-heat solver on the
actual canonical rig/mesh. Blender returns named per-vertex top-four weight
groups; our adapter maps them back to the unchanged VRM joint palette.

Only **body vertices below the neck** can be modified. Head, eyes, facial
shapes and independent spring-driven hair ribbons stay on their canonical
weights and hierarchy. The original mesh topology, original texture and
UV coordinates are preserved and verified after saving the new GLB.
Unweighted or foreign-joint body vertices, a solver failure or a changed
vertex count produces an explicit failed stage; no silent downgrade is
reported as a finished model. The user can choose canonical when the
optional heat solver is not suitable for an individual character.

Colab native notebook: ③ 생성 셀에서 `generate(..., rigging_provider="blender_heat")`를 선택합니다. 기본값은 검증 경로 `canonical`입니다.
CLI:

```bash
vtuber-pipeline avatar --image character.png --output output/avatar \
  --face-image face.png --full-body --rigging-provider blender_heat
```

Unlike SkinTokens, this alternative does not require Ampere or
FlashAttention-2 and can run on the standard Colab T4 configuration.
The CPU integration test verifies geometry/UV/hair preservation and
rejected invalid weights. Actual native Blender bone-heat deformation
quality on complex meshes and full Colab T4 broadcast playback are
still unverified; this option is **not the default**.

## Optional SkinTokens / TokenRig auto-skinning

**Implemented, experimental; not part of the default T4 workflow.**
The [SkinTokens upstream](https://github.com/VAST-AI-Research/SkinTokens) is MIT licensed
and the published model is MIT tagged. Its source is pinned to
`273b691d35989d71cd17ff2895fdc735097b92d1`.

On a compatible GPU the optional stage invokes the upstream `demo.py` with
`--use_skeleton --use_transfer` in an isolated Python environment. It validates
source/candidate vertex positions, UV order, skeleton names, normalized
weights and preserved head/hair binding; **only JOINTS_0 and WEIGHTS_0**
are transplanted into the canonical rigged GLB. The original mesh, texture,
VRM bone hierarchy, face morphs, hair chains and look-at remain authoritative.
Any mismatch is a build failure, never a fabricated or silently degraded rig.

**Colab T4 warning:** upstream SkinTokens hardcodes BF16 and FlashAttention-2;
the official kernels require Ampere+ (SM >= 8.0). NVIDIA T4 (SM 7.5) is
therefore not compatible, notwithstanding 16 GB VRAM. Preflight blocks
unsupported GPUs before checkpoint download or expensive TripoSR stages.
Use **canonical** 3D rigging on T4. On a supported GPU, SkinTokens
requires >=14 GiB of *free* VRAM. Real GPU end-to-end quality is not yet verified.

SkinTokens 별도 설치·검증은 고급 CLI의 명시적 작업으로만 수행하고, 기본 Colab 노트북은 자동 설치하지 않습니다
and select **SkinTokens 실험적 스키닝**. The explicit installer never runs
during generation. Equivalent CLI setup on an Ampere+ GPU:

```bash
python -m pip install uv
python tools/setup_skintokens_runtime.py --directory /content/third_party/SkinTokens
export VTUBER_SKINTOKENS_DIR=/content/third_party/SkinTokens
export VTUBER_SKINTOKENS_PYTHON=/content/third_party/SkinTokens/.venv/bin/python
vtuber-pipeline avatar --image character.png --output output/avatar \
  --face-image face.png --full-body --rigging-provider skintokens
```

The installer checks out pinned source, creates a Python 3.11 virtual
environment, installs upstream dependencies, fetches the official two
checkpoints and verifies actual artifact hashes in the runtime identity.
TripoSR, FLUX and Colab base PyTorch packages are not replaced.

**Licensing caution:** the model card describes training on ArticulationXL,
VRoid Hub and ModelsResource. The MIT license declaration on the model
does not independently audit rights in every source training asset.
Check applicable dataset and model terms before commercial deployment.

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

상단 **Open In Colab** 버튼에서 v8 노트북을 엽니다. 2D와 전신 3D 고화질 입력은 각각 이 README의 ZIP 파일 구조와 정확한 파일명을 따릅니다. ③ 셀에서 얼굴 검출 및 Real-ESRGAN 초해상도 모델을 준비하고, ④ 셀에서는 선택 모드의 시트 ZIP 하나를 받습니다. ⑤ 셀은 시트를 검증된 격자로 분할한 뒤 필요한 파츠에 GPU 초해상도를 적용하고 해당 GPU 작업자를 종료하여 다음 모델로 넘어갑니다. **① 저장소 준비 → ② 모드 선택 → ③ 필수 프로그램·Python 의존성·AI 모델 병렬 다운로드 및 검증 → ④ 사진·VRM·액세서리 업로드 → ⑤ 제작 → ⑥ 제작 결과 파일 다운로드 → ⑦ 상태·로그 진단 → ⑧ 마지막 셀** 순서입니다. **모든 단계가 서로 다른 Colab 셀**입니다. ③ 셀은 **선택한 모드의** 독립적인 프로그램 설치·모델 다운로드를 최대 3개 병렬로 실행하고, 작업 검증이 끝난 다음에만 완료됩니다. 동일한 Python 환경을 공유하는 pip 변경은 충돌 방지를 위해 직렬화합니다. ④ 업로드가 완료되면 ⑤ 제작은 업로드 창을 다시 열지 않으며, **제작 셀에서 프로그램·모델을 자동 설치하지 않습니다.** ⑥ 결과 파일 다운로드는 `DOWNLOAD_NOW=True`를 선택한 경우에만 실행됩니다. 작업 실패 시 ⑤ 셀은 오류를 표시하고 완성 파일로 취급하지 않습니다. ⑧은 별도의 마지막 셀입니다. Gradio나 별도 웹 서버는 실행하지 않습니다. **⑤ 제작 셀을 중지하면 AI 작업자와 하위 GPU 작업에 종료를 요청합니다.** 전체 로그는 `/content/vtuber_builder/jobs/`에 보존됩니다(런타임이 삭제되면 `/content`의 임시 파일은 유지되지 않을 수 있음). **Colab이 GPU 할당량이나 메모리 문제로 런타임 자체를 끊는 상황은 마지막 셀 추가로 방지할 수 없습니다.**

### ① 캐릭터 / 얼굴 만들기

- 기본 다중 시점 모드: `character_3d_sheet_pack.zip` 1개 업로드 (전신 시트 4방향 + 얼굴 확대)
- 2D 모드: `character_2d_sheet_pack.zip` 1개 업로드 (정면 기준 + 얼굴/머리/의상 시트)
- 출력 사용 범위 선택
- 얼굴/머리/상체 fitting
- blink / viseme / emotion morph
- eye-bone look-at
- hair SpringBone
- **캐릭터 VRM 생성**
- 검증된 `avatar.vrm`은 `/content/vtuber_builder/avatar.vrm`에도 복사합니다. Colab **왼쪽 파일 탐색기**에서 다운로드하거나, 생성 종료 후 **⑥ 결과 다운로드 전용 셀**에서 `DOWNLOAD_NOW=True`를 선택하여 내려받을 수 있습니다. 브라우저 다운로드 요청을 생성 셀 내부에서 강제로 시작하지 않습니다.

### ② 악세사리 만들기

Colab의 `TASK`를 **액세서리 제작**으로 선택할 때만 실행합니다. 일반 캐릭터 생성은 `TASK=캐릭터 생성`이 기본이고, `MODE`에서 3D VRM/Inochi2D/Live2D를 선택합니다. 액세서리 `ACCESSORY_ANCHOR=AUTO`는 파일명에 포함된 hat/glasses/shoes 등의 키워드에 따라 개별 부착 위치를 지정하며, 판별할 수 없는 파일명은 적용 전에 오류로 알려줍니다. `ALL`은 업로드한 각 액세서리를 **모든 지원 부착 위치에 각각 적용**합니다. 이는 업로드 이미지 전체를 한 번에 받는 기능과 별개이며, 총 적용 횟수가 커질 수 있습니다. 원본 이미지 3D 복원 결과는 중복 계산하지 않고 재사용합니다.

- 방금 만든 캐릭터 VRM 재사용 또는 기존 VRM 업로드
- 악세사리 슬롯 최대 8개
- 슬롯마다 이미지와 부착 위치를 **독립적으로 선택**
- 각 악세사리 3D 재구성 / fitting / collision / bone parenting
- **악세사리 적용**
- 결과 VRM 다운로드

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
