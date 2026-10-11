# Virtual-pipeline

[![Open current Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jujumelona/Virtual-pipeline/blob/main/notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb)

## 구조 개편 — 1단계: 모드 UI 및 AI 자동 분리 제거

**이번 단계는 UI와 제작 선택 구조를 먼저 정리한 단계입니다.** 기존 이미지 자동 분리용 모델 다운로드/추론이 새 노트북에서 실행되지 않습니다. **프롬프트, 업로드와 실제 제작·리깅은 아직 연결되지 않았으며 후속 단계에서 순서대로 구현합니다.**

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

**먼저 신체만 제작 → 나중에 헤어·의상·액세서리 추가/교체** 순으로 계획합니다. 자산 ID와 파일명, 그림 AI 프롬프트, 출력 ZIP 계약은 **다음 단계에서 확정**합니다. 예전 FREE/PRO·액세서리 별도 상위 모드·복잡한 이미지 분리 옵션은 새 UI에 없습니다.

### 노트북 사용

[현재 Colab v8](notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb)에서 **① GitHub main 동기화 → ② 상위 5개 모드 중 하나 → ③ 공통 4개 자산 중 하나 → ④ 현재 선택 확인**을 진행합니다. 현재 단계에 다운로드/제작 셀은 없으며 선택 결과를 확인할 뿐입니다.

### 사용하지 않는 것

- 새 노트북 경로에서 **기존 See-through, SAM, Qwen 등의 이미지 자동 분리 다운로드와 추론을 사용하지 않습니다.**
- 이미지 생성 AI가 리깅·회전 테스트·MOC3 제작을 해야 한다고 요구하지 않습니다.
- 이 단계에서 신체·헤어·의상·장식 제작이 동작한다고 주장하지 않습니다.

**이전 실험용 코드/구형 노트북 파일은 별개 파일로 남아 있지만, 새로운 v8 UI가 호출하거나 다운로드하지 않습니다.** 남아 있는 내부 레거시 코드의 삭제는 의존 관계를 제거한 뒤 순차적으로 진행해야 다른 미이관 기능을 무단 파손하지 않습니다.

### 참고자료 (기존, 이 단계에서는 실행하지 않음)

- [이전 이미지 AI 원화 지시서](docs/live2d_image_ai_kit/README.md) — **새 신체 중심 제작 구조의 최종 지시서가 아니며 다음 단계에서 교체**
- [Live2D 공식 출처 링크](docs/live2d_image_ai_kit/OFFICIAL_LINKS.md)
