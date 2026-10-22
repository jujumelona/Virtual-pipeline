# See-through 입력 원화: 정확한 제작·정렬 계약 (Live2D 상반신)

## 근본 원인

기존 여성 민트 눈 FACE 원본 `face__ARTWORK.zip/outputs/master.png`는 **1536×1920**입니다. 실제 알파 영역은 **X76~1484, Y69~1871**로, 목 아래쪽 여백이 **49px**뿐입니다. 이 큰 얼굴을 같은 1536×1920 상반신 원화에 그냥 합성하면 목/어깨/옷깃이 맞을 수 없습니다. 같은 캔버스 크기만 통일하는 것은 정합이 아닙니다.

## 확정된 한 가지 입력

**[See-through 전용 Colab](../notebooks/FACE_SeeThrough_OfficialAligned_v3.ipynb)** 에서는 다음 중 한 가지 방식만 사용합니다.

1. **권장** `complete_character__ARTWORK.zip` **한 개**를 업로드합니다. **ZIP의 `outputs/master.png`는 얼굴, 머리카락, 의상·어깨·팔까지 전부 그려진 여성 캐릭터의 정면 완성 PNG**입니다. 정확히 1536×2304, RGBA 진짜 투명 배경. 사용자가 승인한 큰 민트색 눈/고정 피부색/검정·백색 헤어. **마스크 OFF, 눈 OPEN, 입 CLOSED**.
2. 또는 동일한 **완성 캐릭터 원화 1장**을 `full_character_input.png` 이름으로 업로드합니다.
3. 고급 방식만: `face_registered_upper.png` + `outfit.png` + `hair.png` + `registration_contract.json`을 한꺼번에 올립니다. 이 네 파일은 상반신 **공통 1536×2304** 기준이어야 합니다. `face__ARTWORK.zip` 단독이나 `face_registered_upper.png` 단독 업로드는 실패합니다.

### 등록된 FACE의 유일한 기준

- SOURCE FACE ZIP: `face__ARTWORK.zip`의 `outputs/master.png`, 1536×1920 RGBA.
- OUTPUT UPPER CANVAS: **1536×2304** (원점 좌상단).
- FACE 원본 → 상반신 의도적 스케일 **0.55배**, 정수 오프셋 **(+339, +102)**, premultiplied-alpha Lanczos.
- 실제 등록 FACE의 알파 범위: **(380,140)~(1156,1132)**.
- 등록 이후 **얼굴·눈·귀·턱·목을 다른 모델로 새로 그리거나 이 FACE를 이동·리사이즈하지 않습니다.**
- 원본 FACE 12장 참고 원화는 변하지 않습니다. 등록된 FACE는 **상반신 합성용 사본**입니다. 바스트업/전신에서 동일 위치라고 주장하지 않습니다.

## GitHub에서 동일한 생성 지침 ZIP 재생성

지침 ZIP은 **완성 그림이 아니며** FACE ZIP을 소스로 만들어지는 원화 생성용 기준/참고팩입니다. 기존 민트색 FACE 최종 ZIP 파일을 준비한 뒤, GitHub 저장소 `main`에서:

```bash
python -m tools.build_face_upper_alignment_kits --face-zip face__ARTWORK.zip --output-dir output_alignment
```

결과: `face_registered_upper.png`, `registration_contract.json`, `GENERATOR_COMPLETE_CHARACTER_UPPER_REFERENCE.zip`, `GENERATOR_OUTFIT_UPPER_REFERENCE.zip`, `GENERATOR_HAIR_UPPER_REFERENCE.zip`, `GENERATOR_ACCESSORY_UPPER_REFERENCE.zip`.

모든 생성 ZIP에 **같은 등록 FACE 원본 바이트와 같은 픽셀 캔버스**를 넣습니다. FACE 원본 그림이 다르면 등록 좌표/해시가 달라질 수 있어, 이번 민트 FACE에 계산한 좌표를 모든 다른 캐릭터에 그대로 적용했다고 주장하지 않습니다.

## 외부 이미지 생성 단계 — 무엇을 어떤 순서로 만드는가

기존 FACE ZIP을 다시 만들 필요는 없습니다. 이 대화에서 제공한 `UPPER_ALIGNED_IMAGE_GENERATION_PACK.zip`에 고정 기준 `face_registered_upper.png`, 기준 그림, `registration_contract.json`, 4개 제작 지침 ZIP, 검증/포장 스크립트가 들어 있습니다.

1. **OUTFIT 생성:** `GENERATOR_OUTFIT_UPPER_REFERENCE.zip`을 이미지 제작 AI(이미지 편집 기능)에게 주고 `outfit.png` **한 장**을 생성합니다. 머리·얼굴은 다시 그리지 않습니다. 어깨/목깃은 등록된 FACE 목끝 y≈1132에 맞추고, 몸통·소매·팔은 아래쪽 y≈2210까지 이어집니다. 진짜 RGBA 투명 1536×2304. 검정/흰색 의상; 초록 의상 포인트 금지.
2. **HAIR 생성:** `GENERATOR_HAIR_UPPER_REFERENCE.zip` + **똑같은 `face_registered_upper.png`** 로 `hair.png` 한 장을 생성합니다. 흑백 반반 머리, 민트 눈 유지, 머리카락만 RGBA 투명 오버레이. **뒷머리 가림 순서는 별도로 시각 검수**합니다.
3. **전체 캐릭터 한 번에 편집하는 것을 더 권장:** `GENERATOR_COMPLETE_CHARACTER_UPPER_REFERENCE.zip` 기준으로 **등록된 FACE 레이어를 변형하지 않고** 의상과 헤어를 위아래 레이어에 그려서 정면 `full_character_input.png`를 완성합니다. 각각 독립적으로 text-to-image를 생성하고 단순 리사이즈해서 억지 합성하는 것보다 이 방식이 안전합니다.
4. **ACCESSORY는 선택:** `GENERATOR_ACCESSORY_UPPER_REFERENCE.zip`으로 미래형 역병의사 마스크를 별도 생성합니다. 마스크가 입을 가리므로 첫 See-through 분리에서는 마스크를 사용하지 않고, 후속 리깅에서 독립 액세서리로 추가합니다.

**절대 금지:** 12장 컨택트시트를 자르기, 이미지 생성 모델에 PSD·독립 눈/입 파츠·리깅까지 요구하기, 배경색을 RGBA로만 바꾸기, 임의 확대축소로 정렬한 척하기, 정면 얼굴 대신 다른 시점 사용하기.

## 이미지 출력 → Colab 입력까지

생성 도구에서 이미지 편집이 끝나면 `full_character_input.png`를 직접 저장합니다. 또는 `validate_and_package.py` 실행:

```bash
python validate_and_package.py --complete full_character_input.png --face face_registered_upper.png --contract registration_contract.json --output complete_character__ARTWORK.zip
# 혹은 FACE 등록 원화와 실제로 따로 그린 투명 오버레이가 있다면:
python validate_and_package.py --outfit outfit.png --hair hair.png --face face_registered_upper.png --contract registration_contract.json --output complete_character__ARTWORK.zip
```

그다음 [Colab 열기](https://colab.research.google.com/github/jujumelona/Virtual-pipeline/blob/main/notebooks/FACE_SeeThrough_OfficialAligned_v3.ipynb) → GPU 런타임 → 환경 설치 → **complete_character__ARTWORK.zip 하나만 업로드** → 완성 정면 프리뷰에서 얼굴/목/헤어/옷깃이 실제 이어지는지 확인 → `VISUAL_APPROVED=True` 승인 후 공식 See-through → PSD 검사.

## 검증 수준

- ZIP의 파일 구조, 원본 FACE 해시, 크기/알파/대략적인 상하 가시 영역은 **프로그램으로 확인**.
- **그림 자체의 픽셀 일치/피부 및 의상 자연스러운 연결은 수동 또는 이미지 비교를 별도로 확인**. ZIP의 규격 검사가 이를 증명하지 않습니다.
- 자동 See-through PSD 생성과 Cubism 움직임/리깅 합격은 **별도 실측**이며, 이미지 생성 ZIP만 있다고 보증할 수 없습니다.
