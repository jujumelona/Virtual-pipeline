# RE:ARCHIVE 민트눈 여성 캐릭터 — 4개 설정 시트 활용 계약

## 사용자 제공 레퍼런스 (이 문서는 이미지 파일을 저장소에 공개하지 않음)

- `sheet_04_live2d_design_PRIMARY.png`: 최우선 정체성·얼굴/헤어/복장, 정면/45도/측면의 스타일
- `sheet_02_re_archive.png`: DNA 캡슐 재질, 미래형 메카 장식
- `sheet_03_cyber_goth.png`: 흑백 의상과 실루엣, 헤어 파츠 그림
- `sheet_01_fantasy_vtuber.png`: 보조 헤어 컬러·리본·장식
- 원래 FACE는 `face__ARTWORK.zip`의 정면 마스터에서 등록한 `face_registered_upper.png`를 픽셀 기준으로 사용

설정 시트는 **여러 패널의 합성 이미지**입니다. 알파 채널이 있다고 해서 실제 PSD용 독립 헤어/의상 파츠가 아닙니다. **See-through에 직접 업로드하지 않습니다.**

## 입력/출력 단계 구분

1. 외부 이미지 편집/생성 도구에는 사용자가 업로드한 네 시트를 디자인 참고로 주고, **동일한 등록 FACE PNG**를 수정 가능한 원본으로 함께 줍니다. 네 시트를 전부 한 번에 모자이크처럼 합쳐 출력하지 않습니다.
2. **정면 완성 캐릭터 한 장부터** 만듭니다: `full_character_input.png`, 정확히 **1536×2304 RGBA**, 민트색 눈 여성 FACE를 그대로 두고 흑백 트윈테일+핑크/민트 리본, 흑백 사이버 고딕 의상, 앞가슴 DNA 보존 캡슐을 배치합니다. 입/눈 분리를 방해하는 역병의사 마스크는 이 시점에 사용하지 않습니다.
3. 원래 FACE의 중앙 코/입 보호 영역의 실제 픽셀을 비교해 재생성 여부를 판정합니다. 캐릭터 외형, 목/옷깃/앞뒤 머리카락 연결은 수동 검수도 필요합니다.
4. 합격한 완성 PNG만 `complete_character__ARTWORK.zip/outputs/master.png`로 포장합니다.
5. **[공식 See-through Colab](../notebooks/FACE_SeeThrough_OfficialAligned_v3.ipynb)** 에는 **완성 ZIP 하나**를 업로드하고, 시각적 합성 승인을 거쳐 GPU 추론/PSD 구조 검사를 실행합니다.

## 고급 원본 레이어를 만들 경우

가능하면 마스터를 기준으로 `hair_back.png` → `outfit_body.png` → 잠금 FACE → `outfit_collar_front.png` → `hair_front.png` 순서로 **동일 캔버스에** 칠합니다. DNA 캡슐은 몸체의 전면 또는 독립 액세서리로 만들고, 마스크는 나중에 추가합니다. 파츠 분리 자동화만으로 숨은 영역/눈 깜빡임/입 개폐가 완성되지는 않습니다.

검증에는 1536×2304 캔버스·RGBA 알파·몸체 하단 존재·잠긴 FACE 일부 픽셀 일치가 포함되어야 합니다. 이는 미적 일관성의 충분조건은 아닙니다.

## 실제 파일

- 사용자에게 별도로 전달하는 `RE_ARCHIVE_MINT_FOUR_SHEET_GENERATION_PACK.zip`에 **원본 4장(사용자 제공), 확대 참조, 역할별 생성 ZIP, 잠긴 FACE, 픽셀 검사·포장 도구**가 포함됩니다.
- 원본 4장을 이 **공개 저장소에 무단 업로드하지 않습니다**. 실제 참고 그림은 사용자가 생성 도구에 직접 제공합니다.
- 이 생성 참조 팩은 **완성된 캐릭터 원화 ZIP도, 실제 리깅/PSD도 아닙니다.**

상반신 기준의 고정 얼굴 좌표와 캔버스 제작 원리는 [기존 등록 규격](SEE_THROUGH_REGISTERED_UPPER_INPUT_2026-10-22.md)을 참조하십시오.
