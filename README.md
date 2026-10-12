# Virtual-pipeline

## 이미 완성한 이미지 AI 원화 ZIP을 처리하는 Colab

**사용할 노트북:** [완성 원화 ZIP → 실제 Live2D / Inochi2D / 3D VRM 변환](notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb)

[Colab에서 직접 열기](https://colab.research.google.com/github/jujumelona/Virtual-pipeline/blob/main/notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb)

이 노트북은 이미지 생성용 지시 ZIP을 만들지 않습니다. **외부 대형 AI가 실제로 그린 결과 ZIP**을 업로드하여 선택한 엔진에 연결합니다.

| ZIP 제작 대상 | 연결되는 엔진 | 실제 산출 상태 |
|---|---|---|
| Live2D 상반신·전신 신체 | 이미지 파츠 ZIP → PSD → PSD2Live CLI | 실제 MOC3 / model3.json / 텍스처가 생성된 경우에만 네이티브 산출 성공 |
| Live2D 독립 헤어·의상·장식 | 원본 이미지/레이어 → PSD | 기존 Cubism 모델과 Editor에서 결합·추가 리깅 필요 |
| Inochi2D 신체 | 원본 파츠 → PSD/ORA → Inochi SDK exporter | 실제 바인딩/물리가 포함된 네이티브 INP 파일의 검사 통과 시에만 성공 |
| Inochi2D 독립 헤어·의상·장식 | 원본 이미지/레이어 → PSD | 기존 Inochi Creator 프로젝트에서 결합·추가 리깅 필요 |
| 3D 신체 | ZIP의 실제 앞·뒤·좌·우 4면도 → TripoSR/Blender → VRM validator | VRM 1.0 모델/본/표정 등 검증 통과 시에만 성공 |
| 3D 액세서리 | ZIP의 정면 원화 + 기존 VRM → 액세서리 복원/부착 | 기존 VRM을 실제로 수정·검사. ZIP의 다른 3개 면도는 이 단계에 미반영 |
| 3D 독립 헤어·의상 | **미지원** | 그림만으로 기존 VRM에 스킨/의상을 결합하는 제작 엔진 미연결. 가짜 VRM을 납품하지 않음 |

실행 순서: **완성 ZIP 업로드 → 파츠 PNG 또는 4면도 검사 → 필요한 모델/SDK만 준비 → 실제 제작/리깅 시도 → 원본·산출물 패키징 → 다운로드**.

PDF/PSD 편집 자산과 방송용 실제 네이티브 모델은 구분합니다. Cubism Editor, Inochi Session, VTube Studio 및 VRM 방송 프로그램에서의 실제 트래킹·표정·움직임 품질은 Colab의 파일 검증만으로 인증되지 않습니다. 독립 파츠가 모델에 자동으로 결합되었다고 주장하지 않습니다.

**완성 ZIP 업로드에는 위 통합 노트북을 사용하세요.** 아래 v8 Live2D 전용 노트북의 ⑤~⑨ 셀도 수정하여 PSD2Live 자동 리깅을 기본 실행합니다. 단독 헤어·의상·액세서리는 PSD만 만들며, 실제 앱 구동과 자연스러운 움직임은 미검증입니다.


지원 Python 버전: **3.12 또는 3.13** (코드·잠금 버전은 `pyproject.toml` 및 `third_party.lock.json`에 명시).

[![Open current Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jujumelona/Virtual-pipeline/blob/main/notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb)

## Live2D 전용 v8 노트북 (통합 노트북과 별도)

**①~④는 모드 선택 셀입니다.** Live2D 전용 ⑤~⑨에서 입력 업로드, 필요한 SDK 준비, PSD 제작, 신체의 PSD2Live 자동 리깅 및 결과 다운로드를 실행합니다. Inochi2D/3D는 상단 통합 노트북을 사용합니다. 실제 Colab/방송 앱 구동 품질은 별도 확인이 필요합니다.

### 상위 제작 모드

| 선택 | 적용 엔진 | 캐릭터 범위 |
|---|---|---|
| **Live2D 상반신** | Live2D | upper |
| **Live2D 전신** | Live2D | full |
| **Inochi2D 상반신** | Inochi2D | upper |
| **Inochi2D 전신** | Inochi2D | full |
| **3D** | 3D | full |

### 모든 상위 모드에 공통인 하위 자산

| 선택 | 영어 코드 | 의미 |
|---|---|---|
| **신체만** | `body` | 머리카락·별도 의상·액세서리 없이 재사용할 기초 신체·얼굴 자산 |
| **헤어만** | `hair` | 이미 만든 신체 기준에 정렬하는 머리카락 자산 |
| **액세서리만** | `accessory` | 기존 신체/의상 기준에 추가할 개별 장식 |
| **의상만** | `outfit` | 기존 기초 신체를 유지하면서 교체할 옷 |

**먼저 신체만 제작 → 나중에 헤어·의상·액세서리 추가/교체** 순으로 계획합니다. 고급 이미지 AI 지시서·파일명은 위 20종 ZIP에 반영했습니다. Live2D 원화 ZIP 가져오기→PSD→신체 자동 리깅 PSD2Live CLI 실행은 **⑤~⑨ 셀에 연결**했지만 실제 Colab GPU 및 방송 앱에서 동작 품질이 확인된 것은 아닙니다. 예전 FREE/PRO·액세서리 별도 상위 모드·복잡한 이미지 분리 옵션은 새 UI에 없습니다.

### 노트북 사용

[현재 Colab v8](notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb)의 **① GitHub main 동기화 → ② 상위 모드 → ③ 자산 → ④ 선택 확인**은 다운로드 없는 UI 선택 셀입니다. **Live2D를 선택한 경우 ⑤ FREE/PRO·입력 유형 → ⑥ 이미지 또는 파츠 ZIP 업로드 → ⑦ 필요한 런타임 준비 → ⑧ 실제 PSD 제작과 결과 ZIP 검사 → ⑨ 다운로드**를 수행합니다. FREE도 신체만 원화 ZIP이나 단일 이미지에서 제작할 수 있습니다. PRO는 독립 body/hair/outfit/accessory 자산 제작 기능을 제공하지만, 신체만 제작한다는 이유로 PRO가 필수인 것은 아닙니다. 탈착 자산은 같은 크기 기준 몸체 PNG가 필요합니다.

### 이미 받은 PSD 결과 ZIP을 다시 분해하지 않고 리깅하기

이미 `Live2D_FREE_upper.zip`처럼 `avatar.psd`가 들어 있는 **결과 ZIP**을 가지고 있다면, v8 Live2D 전용 Colab에서 **⑤ EDITION=free(사용자가 FREE를 선택한 경우), RIGGING=auto, INPUT_KIND=existing_psd_zip**을 선택합니다. **⑥ 결과 ZIP 업로드 → ⑦ PSD2Live CLI 설치/컴파일 → ⑧ 기존 PSD 바이트 재사용 후 네이티브 제작 → ⑨ ZIP 다운로드** 순서입니다. 이 경로는 See-through·Qwen을 다시 실행하거나 이미 저장된 파츠를 재생성하지 않습니다.

헤어·의상이 없는 신체 전용 PNG/PSD는 FREE/PRO 어느 에디션이든 **완성 캐릭터 원화가 아니라 신체 베이스**입니다. 네이티브 MOC3 생성에 성공하더라도 신체만 움직이는 모델이며, 헤어·의상을 추가하려면 결합 작업이 남습니다. 실제 VTube Studio 동작·키폼·물리 자연스러움은 결과 파일 검사만으로 입증되지 않습니다.

### FREE와 PRO 에디션 선택의 의미

**에디션은 사용자가 선택하는 Cubism 기능·라이선스 수준입니다.** `body`·`hair`·`outfit`·`accessory` 등 제작 종류와는 다른 항목입니다. **신체만 ZIP은 FREE에서도 처리**합니다. 이때 모델 파일 생성은 PSD2Live를 실행하고, FREE 전용 ArtMesh·아틀라스 등 제한을 적용합니다. 제한을 넘으면 임의로 PRO로 전환하지 않고 원인을 표시합니다. 사용자가 선택하지 않은 PRO로 자동 변경하지 않습니다.

### 사용하지 않는 것

- **앞의 네 선택 셀에서는** See-through/SAM/Qwen 다운로드나 추론이 없습니다. Live2D 후속 제작 셀에서는 FREE 완성 이미지와 PRO 신체 단일 이미지에 한해 See-through NF4 준비·추론 경로를 사용하고, 이미 분리된 이미지 AI ZIP은 중복 추론을 생략합니다.
- 이미지 생성 AI가 리깅·회전 테스트·MOC3 제작을 해야 한다고 요구하지 않습니다.
- 현재 변경은 Live2D 제작 코드의 연결입니다. 실제 GPU 추론·PSD 시각 품질·Cubism 리깅 완료를 주장하지 않습니다.

**이전 실험용 코드/구형 노트북 파일은 별개 파일로 남아 있지만, 새로운 v8 UI가 호출하거나 다운로드하지 않습니다.** 남아 있는 내부 레거시 코드의 삭제는 의존 관계를 제거한 뒤 순차적으로 진행해야 다른 미이관 기능을 무단 파손하지 않습니다.

## 2단계: 20개 이미지 AI 제작 지시서 ZIP (일본 애니풍·실제 공식 이미지 예시·반복 점검 포함)

[**5개 상위 모드 × 신체/헤어/의상/액세서리 개별 ZIP 목록**](docs/image_ai_kits_v2/README.md)에서 현재 선택에 맞는 **지시서 ZIP 한 개**를 내려받아 GPT·Gemini 등에 첨부합니다. **각 ZIP에 해당 모드용 고급 분리 원화 규칙·공식 예제 링크·이미지 파일명·결과 ZIP 구조가 모두 들어 있습니다.**

신체는 **불투명 기본 속옷을 입힌 노출 없는 베이스**이며 눈·코·입도 **신체 내부에서 처음부터 개별 원화로 생성**합니다. 완성 이미지 자동 마스킹 분리 방식은 사용하지 않고 **파츠 먼저 생성 → 실제 그림으로 마지막 합성**합니다. 머리장식 등 특정 액세서리를 요청했다면 그 물건만 제작하며 다른 장식 세트를 임의로 추가하지 않습니다. 이미지 AI에게 PSD/리깅/회전 테스트/VRM 생성을 요구하지 않습니다.

**ZIP 20개에 `10_ANIME_STYLE.md` 및 `11_OFFICIAL_IMAGE_EXAMPLES.md`도 추가했습니다.** 검정 계열의 또렷한 가변 굵기 외곽선·셀 셰이딩·애니풍 얼굴/눈·손 디테일을 기본값으로, Live2D 공식 Tsumiki·Izumi 샘플 그림을 **원격 이미지 미리보기 링크**로 제공합니다. 공식 이미지 원본 파일 자체가 ZIP에 담긴 것은 아닙니다.

**ZIP 20개에 `09_VISUAL_ART_QUALITY.md`를 추가해 실제 Live2D 공식 샘플/PSD 링크와 전문 원화의 선화·명암·비례·재료 표현 기준을 포함했습니다.** 그림을 단순 도형/SVG/Pillow로 만들고 파일 수만 채우는 결과를 최종으로 인정하지 않도록 했습니다. 공식 자료는 링크로 연결하되 샘플 그림·PSD 파일 자체는 배포하지 않습니다. 링크가 있다고 AI가 예제를 실제 열어 본 것은 아닙니다.

**외부 이미지 AI 지시서에는 제작자 실무 팁 적용과 그림·파일 반복 점검 후에만 최종 결과 ZIP을 납품하도록 명시했습니다.** 이것은 실제 이미지 작업의 자체 점검이며 리깅/회전 테스트나 품질 인증 요구가 아닙니다.

**현재 Colab v8의 Live2D ⑤~⑨ 셀은 이미지 AI 결과 ZIP → 실제 레이어 PSD → 신체 선택 시 PSD2Live 네이티브 리깅 시도 → 파일 검증 → 다운로드를 연결합니다.** ZIP 검사로 실제 그림 품질·가려진 면 복원·Cubism 리깅은 판정하지 않습니다. Inochi2D 및 3D/VRM 제작 경로는 이 셀에 포함하지 않습니다.

### 참고자료 (기존, 이 단계에서는 실행하지 않음)

- [이전 범용 이미지 AI 지시서 (참고용)](docs/live2d_image_ai_kit/README.md) — 신규 제작에는 위 **모드·자산별 ZIP**을 사용
- [Live2D 공식 출처 링크](docs/live2d_image_ai_kit/OFFICIAL_LINKS.md)
