# Virtual-pipeline

## 이미 완성한 이미지 AI 원화 ZIP을 처리하는 Colab

**사용할 노트북:** [완성 원화 ZIP → 실제 Live2D / Inochi2D / 3D VRM 변환](notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb)

[Colab에서 직접 열기](https://colab.research.google.com/github/jujumelona/Virtual-pipeline/blob/main/notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb)

이 노트북은 이미지 생성용 지시 ZIP을 만들지 않습니다. **외부 대형 AI가 실제로 그린 결과 ZIP**을 업로드하여 선택한 엔진에 연결합니다.

| ZIP 제작 대상 | 연결되는 엔진 | 실제 산출 상태 |
|---|---|---|
| Live2D 상반신·전신 신체 | 입력 이미지/파츠 → 실제 분리 PSD 제작·검증 | 기본 산출물은 리깅 전 PSD. ArtMesh·디포머·키폼·물리·모션·내보내기는 공식 Cubism Editor 사용자 작업 |
| Live2D 독립 헤어·의상·장식 | 원본 이미지/레이어 → PSD | 기존 Cubism 모델과 Editor에서 결합·추가 리깅 필요 |
| Inochi2D 신체 | 원본 파츠 → PSD/ORA → Inochi SDK exporter | 실제 바인딩/물리가 포함된 네이티브 INP 파일의 검사 통과 시에만 성공 |
| Inochi2D 독립 헤어·의상·장식 | 원본 이미지/레이어 → PSD | 기존 Inochi Creator 프로젝트에서 결합·추가 리깅 필요 |
| 3D 신체 | ZIP의 실제 앞·뒤·좌·우 4면도 → TripoSR/Blender → VRM validator | VRM 1.0 모델/본/표정 등 검증 통과 시에만 성공 |
| 3D 액세서리 | ZIP의 정면 원화 + 기존 VRM → 액세서리 복원/부착 | 기존 VRM을 실제로 수정·검사. ZIP의 다른 3개 면도는 이 단계에 미반영 |
| 3D 독립 헤어·의상 | **미지원** | 그림만으로 기존 VRM에 스킨/의상을 결합하는 제작 엔진 미연결. 가짜 VRM을 납품하지 않음 |

실행 순서: **완성 ZIP 업로드 → 파츠 PNG 또는 4면도 검사 → 필요한 모델/SDK만 준비 → 실제 제작/리깅 시도 → 원본·산출물 패키징 → 다운로드**.

**현재 통합 Colab 입력은 제작 방식, 제작 자산, Live2D 에디션뿐입니다.** 과거의 `USAGE` 라이선스 구분 UI는 제거했습니다. 서로 다른 라이선스 선택값 때문에 변환 엔진이나 기능이 달라지지 않도록 기존 내부 호환 기본값으로 실행합니다. 이 설정은 원화·모델의 이용 허가를 대체하지 않습니다. `ANCHOR` 공통 UI도 제거했습니다. 3D 액세서리 부착 위치는 납품 ZIP의 액세서리 종류가 드러나는 파일명 또는 `metadata/attachment.json`의 `{"attachment":{"anchor":"NECK"}}`처럼 근거가 있는 정보에서만 결정하며, 정보가 없는 일반 `accessory_front.png`라면 잘못된 머리 부착 대신 구체적인 입력 누락으로 중단합니다. Live2D/Inochi2D/3D 신체 작업에는 부착 위치 옵션 자체가 없습니다.

PDF/PSD 편집 자산과 방송용 실제 네이티브 모델은 구분합니다. Cubism Editor, Inochi Session, VTube Studio 및 VRM 방송 프로그램에서의 실제 트래킹·표정·움직임 품질은 Colab의 파일 검증만으로 인증되지 않습니다. 독립 파츠가 모델에 자동으로 결합되었다고 주장하지 않습니다.

**완성 ZIP 업로드에는 위 통합 노트북을 사용하세요.** 별도 Live2D 노트북의 ⑤~⑨ 셀은 기본적으로 분리 PSD를 제작·검증합니다. PSD2Live는 명시적으로 `RIGGING=auto`를 선택하는 별도 경로이며 공식 Cubism Editor 리깅을 대체하지 않습니다. 실제 앱 움직임은 미검증입니다.


지원 Python 버전: **3.12 또는 3.13** (코드·잠금 버전은 `pyproject.toml` 및 `third_party.lock.json`에 명시).

[![Open current Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jujumelona/Virtual-pipeline/blob/main/notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb)

## Live2D 전용 v8 노트북 (통합 노트북과 별도)

**①~④는 모드 선택 셀입니다.** Live2D 전용 ⑤~⑨에서 입력 업로드, 필요한 모델 준비, PSD 제작·검증·다운로드를 수행합니다. 신체의 PSD2Live CLI 시도는 명시적인 `RIGGING=auto` 선택일 때만 가능합니다. Inochi2D/3D는 상단 통합 노트북을 사용합니다. 실제 Colab/방송 앱 구동 품질은 별도 확인이 필요합니다.

### 제작 선택 (FACE는 2D에서만 구도 공통)

| 선택 | 적용 엔진 | 캐릭터 범위 |
|---|---|---|
| **FACE 공통(구도 없음)** | Live2D·Inochi2D 공통 | 얼굴·귀·눈·입·턱·목만. 구도 선택 불필요 |
| **Live2D 바스트업 (방송용)** | Live2D | bust_up — 머리~가슴 윗부분 전용 원화 지시서 (기존 Colab 제작 모드와 별도) |
| **Live2D 상반신** | Live2D | upper |
| **Live2D 전신** | Live2D | full |
| **Inochi2D 상반신** | Inochi2D | upper |
| **Inochi2D 전신** | Inochi2D | full |
| **3D** | 3D | **전체 캐릭터**(얼굴·헤어·착의 전신)의 다각도 2D 원화 → 3D 복원 또는 액세서리 추가 |

### 실제 생성 ZIP 표 — FACE 포함

| 제작 모드 | FACE | HAIR | OUTFIT | ACCESSORY |
|---|---|---|---|---|
| Live2D 바스트업 | [공통 FACE](docs/image_ai_kits_v2/zips/face.zip) | [HAIR](docs/image_ai_kits_v2/zips/live2d_bust_up__hair.zip) | [OUTFIT](docs/image_ai_kits_v2/zips/live2d_bust_up__outfit.zip) | [ACCESSORY](docs/image_ai_kits_v2/zips/live2d_bust_up__accessory.zip) |
| Live2D 상반신 | [공통 FACE](docs/image_ai_kits_v2/zips/face.zip) | [HAIR](docs/image_ai_kits_v2/zips/live2d_upper__hair.zip) | [OUTFIT](docs/image_ai_kits_v2/zips/live2d_upper__outfit.zip) | [ACCESSORY](docs/image_ai_kits_v2/zips/live2d_upper__accessory.zip) |
| Live2D 전신 | [공통 FACE](docs/image_ai_kits_v2/zips/face.zip) | [HAIR](docs/image_ai_kits_v2/zips/live2d_full__hair.zip) | [OUTFIT](docs/image_ai_kits_v2/zips/live2d_full__outfit.zip) | [ACCESSORY](docs/image_ai_kits_v2/zips/live2d_full__accessory.zip) |
| Inochi2D 상반신 | [공통 FACE](docs/image_ai_kits_v2/zips/face.zip) | [HAIR](docs/image_ai_kits_v2/zips/inochi2d_upper__hair.zip) | [OUTFIT](docs/image_ai_kits_v2/zips/inochi2d_upper__outfit.zip) | [ACCESSORY](docs/image_ai_kits_v2/zips/inochi2d_upper__accessory.zip) |
| Inochi2D 전신 | [공통 FACE](docs/image_ai_kits_v2/zips/face.zip) | [HAIR](docs/image_ai_kits_v2/zips/inochi2d_full__hair.zip) | [OUTFIT](docs/image_ai_kits_v2/zips/inochi2d_full__outfit.zip) | [ACCESSORY](docs/image_ai_kits_v2/zips/inochi2d_full__accessory.zip) |
| 3D | **캐릭터 원화에 얼굴 포함** ([전체 캐릭터](docs/image_ai_kits_v2/zips/3d__character.zip)) | 전체 캐릭터에 포함 | 전체 캐릭터에 포함 | [3D 액세서리](docs/image_ai_kits_v2/zips/3d__accessory.zip) |

**2D FACE는 모든 구도에서 동일한 `face.zip` 한 개를 사용합니다.** 3D는 별도 FACE를 만들지 않고 얼굴·머리·의상이 모두 그려진 완성 2D 캐릭터 원화를 복원합니다. 총 18개 ZIP입니다.

### FACE를 제외한 제작 모드의 하위 자산

| 선택 | 영어 코드 | 의미 |
|---|---|---|
| **헤어만** | `hair` | 같은 FACE의 두상 앵커에 정렬한 헤어 자산 |
| **액세서리만** | `accessory` | FACE/의상의 앵커 기준에 정렬한 소품 |
| **의상만** | `outfit` | 의상을 입은 몸통·팔·손을 선택한 구도로 그리는 자산 |

**2D 작업에서만** 제작 구도와 무관한 **FACE 공통(구도 없음)** 모드를 먼저 선택해 얼굴·목 원화를 한 번 생성합니다. **3D 작업은 FACE 없이 완성 캐릭터 전체가 그려진 2D 원화**를 사용합니다. 노트북에서 이 독립 FACE 항목의 자산 표시는 **얼굴만**이며, 바스트업·전신 모드의 하위 FACE 자산이 아닙니다.

**2D 추천 순서: FACE(얼굴·목) → OUTFIT(옷 입은 몸통·양팔·양손) → HAIR → ACCESSORY.** 18개 원화 ZIP으로 정리했습니다: 2D FACE 1개 + 2D 자산 15개 + 3D 완성 캐릭터/액세서리 2개. 얼굴·목과 옷깃을 동일한 좌표에서 합성하고 후속 단계에서 실제 파츠 분리·PSD·리깅을 검증합니다.
**3D 추천 순서: 의상 착용 완성 캐릭터의 전·후·좌·우 2D 원화 → TripoSR/Blender → VRM 변환·검증. 별도 FACE·HAIR·OUTFIT 자산을 먼저 생성하지 않습니다.**

### 노트북 사용

**현재 이미지 AI 제작 경로:** [완성 원화 ZIP 입력 노트북](notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb). 이 노트북은 2D 공통 `FACE(face)` 또는 다섯 가지 2D 구도별 `hair/outfit/accessory`, 3D의 `character/accessory`를 선택합니다. FACE는 독립 원화 자료이고 완성 캐릭터 리깅이 아닙니다. 과거 v8 데모 노트북은 별도 구형 실험 자료입니다.

### 이미 받은 PSD 결과 ZIP을 다시 분해하지 않고 재사용하기

이미 `Live2D_FREE_upper.zip`처럼 실제 PSD·투명 PNG·마스크·제작 안내가 포함된 **완성된 원화 결과 ZIP**이 있다면, v8 Colab에서 **⑤ RIGGING=artwork_only, INPUT_KIND=existing_psd_zip**을 선택합니다. ⑥ ZIP을 업로드하고 ⑧ 구조 검사를 통과하면 ⑨에서 **입력 ZIP의 원래 바이트를 그대로 다운로드**합니다. See-through·Qwen 재추론, PSD 재출력, PSD2Live/네이티브 리깅을 실행하지 않습니다.

기존 PSD를 별도 PSD2Live로 처리하려는 경우에만 사용자가 **RIGGING=auto를 명시적으로 선택**할 수 있습니다. 이는 독립된 서드파티 CLI 경로로 공식 Cubism Editor에서 키폼·물리·모션을 완료하는 것과 같지 않으며, 기본 제작 경로도 아닙니다. PSD 원화가 완성되었다고 `.moc3`가 자동으로 완성됐다고 주장하지 않습니다.

### FREE와 PRO 에디션 선택의 의미

**원화와 리깅의 분리:** 얼굴·목 FACE ZIP만으로 완성된 캐릭터라고 판단하지 않습니다. 옷 입은 몸통·팔·손 OUTFIT과 합성한 뒤 파츠 분리 및 Live2D/Inochi2D 네이티브 모델을 따로 검증해야 합니다. 이 결합·자동 눈/입 분리는 아직 검증 완료되지 않았습니다.

### 사용하지 않는 것

- **앞의 네 선택 셀에서는** See-through/SAM/Qwen 다운로드나 추론이 없습니다. Live2D 후속 제작 셀에서는 FREE 완성 이미지와 PRO 신체 단일 이미지에 한해 See-through NF4 준비·추론 경로를 사용하고, 이미 분리된 이미지 AI ZIP은 중복 추론을 생략합니다.
- 이미지 생성 AI가 리깅·회전 테스트·MOC3 제작을 해야 한다고 요구하지 않습니다.
- 현재 변경은 Live2D 제작 코드의 연결입니다. 실제 GPU 추론·PSD 시각 품질·Cubism 리깅 완료를 주장하지 않습니다.

**이전 실험용 코드/구형 노트북 파일은 별개 파일로 남아 있지만, 새로운 v8 UI가 호출하거나 다운로드하지 않습니다.** 남아 있는 내부 레거시 코드의 삭제는 의존 관계를 제거한 뒤 순차적으로 진행해야 다른 미이관 기능을 무단 파손하지 않습니다.


**실제 Colab GPU** 환경에서의 FACE/OUTFIT 합성, 눈·입 세부 분리, Live2D 동작 품질은 아직 검증되지 않았습니다. 원화 ZIP 계약 검사 통과만으로 MOC3/VRM 제작이 성공한 것으로 보고하지 않습니다.

**정식 배포:** [18개 이미지 AI 지침 ZIP](docs/image_ai_kits_v2/README.md). 2D 공통 `face.zip` 1개 + 2D 구도별 15개 + 3D 완성 캐릭터/액세서리 2개를 배포합니다. 기존 `__body.zip` 및 각 모드별 `__face.zip`은 폐기했습니다.

## 2단계: 18개 이미지 AI 제작 지시서 ZIP (일본 애니풍·실제 공식 이미지 예시·반복 점검 포함)

[**2D 공통 FACE 1개 + 2D 자산 15개 + 3D 캐릭터/액세서리 2개 ZIP 목록**](docs/image_ai_kits_v2/README.md)에서 현재 선택에 맞는 **지시서 ZIP 한 개**를 내려받아 GPT·Gemini 등에 첨부합니다. **각 ZIP에 해당 모드용 고급 분리 원화 규칙·공식 예제 링크·이미지 파일명·결과 ZIP 구조가 모두 들어 있습니다.**

**바스트업** 지시서는 전신을 축소·크롭하는 대신 얼굴·눈의 애니풍 인상과 목 연결을 유지하면서 배 위까지 양어깨·양팔·양손이 포함된 원화를 처음부터 제작합니다. 얼굴·눈·입·헤어·목 연결에 디테일을 집중하며 골반·다리 파츠를 요구하지 않습니다. **기존 Colab의 `upper` 모드가 새 `bust_up` 범위를 자동으로 처리하는 것은 아닙니다.** 현재 추가되는 것은 이미지 AI 전용 지시 ZIP입니다.

**FACE는 얼굴·귀·눈·코·입·턱·목만** 실제 애니 일러스트로 생성합니다. 어깨 아래의 몸통·팔·손·의복은 FACE 원화에 포함하지 않습니다. **OUTFIT은 몸통·팔·손을 의복을 착용한 모습으로** 그리며 피부색 신체 베이스를 별도로 생성하지 않습니다.

**ZIP의 `10_ANIME_STYLE.md` 및 `11_OFFICIAL_IMAGE_EXAMPLES.md`에는** 검정 계열의 또렷한 가변 굵기 외곽선·셀 셰이딩·애니풍 얼굴/눈·손 디테일을 기본값으로, Live2D 공식 Tsumiki·Izumi 샘플 그림을 **원격 이미지 미리보기 링크**로 제공합니다. 공식 이미지 원본 파일 자체가 ZIP에 담긴 것은 아닙니다.

**18개 ZIP은 원화와 시점별 참고 이미지만 생성합니다.** HAIR는 FACE에 정렬, OUTFIT은 얼굴과 목의 앵커에 정렬, ACCESSORY는 지정 소품만 생성합니다. 파츠 분리·PSD·리깅은 이미지 생성 AI가 완료했다고 주장하지 않습니다.

**외부 이미지 AI 지시서에는 제작자 실무 팁 적용과 그림·파일 반복 점검 후에만 최종 결과 ZIP을 납품하도록 명시했습니다.** 이것은 실제 이미지 작업의 자체 점검이며 리깅/회전 테스트나 품질 인증 요구가 아닙니다.

**현재 Live2D Colab의 ⑤~⑨ 셀 기본 경로는 입력 이미지/ZIP → 실제 레이어 PSD → 파일 검증 → 다운로드입니다.** `RIGGING=auto`를 명시적으로 선택한 경우만 별도 PSD2Live CLI를 시도하며, 공식 Editor 리깅 완료로 간주하지 않습니다. ZIP 검사로 실제 그림 품질·가려진 면 복원·Cubism 리깅은 판정하지 않습니다. Inochi2D 및 3D/VRM 제작 경로는 이 셀에 포함하지 않습니다.

### 참고자료 (기존, 이 단계에서는 실행하지 않음)

- [이전 범용 이미지 AI 지시서 (참고용)](docs/live2d_image_ai_kit/README.md) — 신규 제작에는 위 **모드·자산별 ZIP**을 사용
- [Live2D 공식 출처 링크](docs/live2d_image_ai_kit/OFFICIAL_LINKS.md)

### 바스트업 모드의 노출 방지

**바스트업 FACE**는 애니풍 민머리 얼굴·눈·귀·목을 생성하고 **바스트업 OUTFIT**은 의상 입은 어깨·몸통·양팔·양손을 생성합니다. 몸통의 노출이 필요한 생성 요청 자체가 없습니다. 목과 옷깃은 합성 단계에서 연결 검수합니다.

### Live2D Colab v8 기본 PSD 제작 계약

- 기본 선택은 **FREE / 완성 캐릭터 PNG 1장 / `artwork_only`**입니다. 상반신/전신 프레임은 기존 모드 선택에 따릅니다.
- `parts_zip`은 이미 실제로 분리한 원화 파츠가 있을 때만 선택합니다. `existing_psd_zip`과 `artwork_only` 조합은 업로드한 기존 PSD 결과 ZIP을 **재추론·PSD 재출력·리깅 없이 그대로 재사용**하고 내부 ZIP 구조를 다시 점검합니다.
- 업로드할 PNG/ZIP의 확장자와 빈 파일 여부를 **디스크에 저장하기 전에** 검사합니다. PRO 탈착 자산에는 별도의 같은 캔버스 기준 몸체 PNG를 사용합니다.
- PSD2Live는 이전 코드 호환용 **명시적 opt-in**이며, 정상적인 Live2D 원화 제작 경로에는 필요하지 않습니다. PSD 결과는 리깅된 `.cmo3`/`.moc3` 모델이 아닙니다. ArtMesh·디포머·키폼·물리·모션·내보내기는 공식 Cubism Editor 사용자 작업입니다.


## 이미지 AI 18종 ZIP과 Colab 오픈소스 런타임 — 역할 분리 (2026-10-17)

- **18개 이미지 지침 ZIP** (`docs/image_ai_kits_v2/zips/`): 2D 공통 FACE 1 + 구도별 HAIR/OUTFIT/ACCESSORY 15 + 3D 완성 캐릭터/액세서리 2. 외부 이미지 생성 AI에는 **완성 원화와 다각도 참고 PNG만** 요구하고 파츠 분리·RGBA 레이어·PSD를 생성하라고 요구하지 않는다. 이 ZIP에는 실행 스크립트가 들어 있지 않다.
- **Colab 실행** (`notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb`): 외부 AI 원화 ZIP을 업로드받아 입력 구조를 검사한다. FACE는 원화·회전도·입표정 참고자료를 전달할 뿐 현재 자동 눈·입 파츠 분리/실제 리깅 완성까지 인증하지 않는다. 다른 2D·3D 제작 분기는 별도 제약과 검증 기준을 적용한다.
- **입력 QA** (`tools/vts_source_only_pack.py`, `tools/vts_multiview_runtime.py`): FACE 원화 12개 PNG·두 입표정 차이·시점 복제·캔버스 정렬·기본 해상도를 검사한다. 검사를 통과해도 일본 애니 VTuber 화풍의 미적 품질은 확인되지 않으며 시각 수동 검수가 필요하다.
- **대체 백엔드**: image2live2d는 자체 nijilive INP 모델과 보조 렌더를 생성한다. 이 결과가 PSD2Live에서 생성한 Cubism MOC3의 품질을 인증하지 않는다.
- **실제 모델 자세** (`tools/vts_native_moc_pose_worker.py`): 별도 라이선스 조건을 충족한 live2d-py/Cubism Core와 OpenGL 환경에서 네이티브 MOC3의 회전·눈·입 자세를 렌더링한다. 필요한 런타임이 없거나 움직임이 없으면 미검증/오류를 기록한다.
- **남은 한계**: 참조 시점 PNG가 PSD2Live 디포머 키폼에 자동으로 매핑되는 것은 아니며, 눈·목의 시각적 완성도나 VTube Studio 실제 트래킹이 자동 인증되는 것도 아니다. 독립 3D 헤어/의상 VRM 생성은 아직 미지원이다. 미검증을 성공으로 표시하지 않는다.
