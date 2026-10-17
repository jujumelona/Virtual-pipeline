# 버추얼 원화 제작 ZIP — 18개

## 2D 공통 FACE 1개

[**공통 2D FACE 원화 ZIP**](zips/face.zip) — `face.zip`

얼굴·눈·귀·턱·목을 한 번만 제작하고 Live2D/Inochi2D의 바스트업·상반신·전신에 공통 사용합니다. 의상·머리카락·어깨·팔은 그리지 않습니다. 입표정·정면·좌우 고개 회전 참고를 포함합니다.

**3D 모드는 이 FACE ZIP을 사용하지 않습니다.** 얼굴을 캐릭터 전체 2D 원화에 포함하여 3D 복원합니다.

## FACE 화풍·품질 기준 (2026-10-17 강화)

이 ZIP을 외부 이미지 생성 AI에 입력하는 목적은 **실제 방송용 2D 애니 VTuber 얼굴 원화**입니다. 파일 수만 맞춘 기본 벡터 얼굴이나 타원·선·원통 목으로 조합한 프록시 캐릭터를 제출해서는 안 됩니다.

`00_MASTER_FIRST.md`에 바로 사용할 수 있는 영어 **PRIMARY MASTER IMAGE PROMPT**를 넣었습니다. 따뜻한 주황 홍채·동공·빛 반사·개별 속눈썹·눈꺼풀, 둥근 성인 애니 얼굴, 귀·턱·목 곡선, 섬세한 선 굵기 변화와 2~3단계 전문 셀 명암을 요구합니다.

**작업 순서:** 먼저 `outputs/master.png` 정면 고품질 원화를 **한 장만** 완성·검수 → 합격한 동일 캐릭터로 45°/90°/상하 회전과 표정 참고 PNG 개별 제작 → 총 12개 PNG 검수 후 `face__ARTWORK.zip` 납품. 단순 그림 12칸을 한 번에 만들고 잘라내는 방식은 금지합니다.

**반려:** 스티커 같은 단순 눈, 달걀형 도형 얼굴, 직선으로 자른 목, 90° 옆모습인데 정면 눈 두 개가 보이는 그림, 좌우 반전만 한 회전도, 캐릭터 정체성이 다른 시점, 이미지 생성 모델 대신 SVG/기하 도형으로 만든 프록시. 실제 시각 품질은 생성된 이미지를 보고 판단하며 ZIP의 문구만으로 품질을 보장할 수 없습니다.

## 2D 구도별 자산 15개

| 2D 제작 모드 | FACE (공통, 동일 ZIP) | HAIR | OUTFIT (착의 몸통·팔·손) | ACCESSORY |
|---|---|---|---|---|
| Live2D 바스트업 | [공통 FACE ZIP](zips/face.zip) | [ZIP](zips/live2d_bust_up__hair.zip) | [ZIP](zips/live2d_bust_up__outfit.zip) | [ZIP](zips/live2d_bust_up__accessory.zip) |
| Live2D 상반신 | [공통 FACE ZIP](zips/face.zip) | [ZIP](zips/live2d_upper__hair.zip) | [ZIP](zips/live2d_upper__outfit.zip) | [ZIP](zips/live2d_upper__accessory.zip) |
| Live2D 전신 | [공통 FACE ZIP](zips/face.zip) | [ZIP](zips/live2d_full__hair.zip) | [ZIP](zips/live2d_full__outfit.zip) | [ZIP](zips/live2d_full__accessory.zip) |
| Inochi2D 상반신 | [공통 FACE ZIP](zips/face.zip) | [ZIP](zips/inochi2d_upper__hair.zip) | [ZIP](zips/inochi2d_upper__outfit.zip) | [ZIP](zips/inochi2d_upper__accessory.zip) |
| Inochi2D 전신 | [공통 FACE ZIP](zips/face.zip) | [ZIP](zips/inochi2d_full__hair.zip) | [ZIP](zips/inochi2d_full__outfit.zip) | [ZIP](zips/inochi2d_full__accessory.zip) |

**FACE 열의 다섯 링크는 모두 동일한 `face.zip` 한 파일입니다.** 바스트업·상반신·전신별 FACE ZIP이 따로 존재한다는 의미가 아닙니다. 2D FACE를 한 번 만든 뒤 선택한 구도의 HAIR·OUTFIT·ACCESSORY에 정렬합니다.

OUTFIT은 별도 2D FACE와 목깃을 맞춰 의상을 착용한 몸통·팔·손을 그립니다. 전신 모드에서는 착의 하체까지 그립니다. HAIR와 ACCESSORY는 해당 자산만 제작합니다. 원화 생성 AI에 파츠 분리·PSD·리깅 완료를 요구하지 않습니다.

## 3D: 완성 캐릭터 원화 1개 + 액세서리 1개

| 3D 제작 항목 | FACE 처리 | 생성 입력 | ZIP |
|---|---|---|---|
| **3D 전체 캐릭터** | **완성 캐릭터에 얼굴 포함** (FACE ZIP 불필요) | 얼굴·헤어·의상 착용 전신이 모두 포함된 **2D 캐릭터의 정면·후면·좌·우·대각도** 원화 | [3D CHARACTER](zips/3d__character.zip) |
| **3D 액세서리** | 별도 얼굴 원화 불필요 | 기존 VRM에 부착할 소품의 2D 다각도 원화 | [3D ACCESSORY](zips/3d__accessory.zip) |

3D 작업은 2D 원화를 입력으로 3D 메시·재질/텍스처를 복원하고 Blender/VRM 경로를 사용합니다. 현재 제작기는 4개 직교 시점을 활용하고 대각도 참조는 추가 검수에만 사용합니다. 별도 3D 헤어/의상 메쉬 제작은 아직 연결되지 않았으므로 3D HAIR·OUTFIT ZIP을 배포하지 않습니다.

**총계: 2D FACE 1 + 2D 전용 15 + 3D 2 = 18 ZIP.**

[Colab 제작 노트북](../../notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb)에서 3D는 `전체 캐릭터`를 선택하고, 2D 공통 FACE는 `얼굴만`을 선택합니다.

`node tools/build_source_only_kits_v7.js --check`와 `python -m tools.audit_24_image_kits --strict`로 압축파일 및 문서 계약을 검사합니다. 과거 `__body.zip`과 `3d__hair.zip`·`3d__outfit.zip`, 프레이밍별 FACE ZIP은 폐기됩니다.

**현재 한계:** 2D 원화 생성·ZIP 검증 자체가 3D 모델 생성 성공을 보장하지 않습니다. 실제 메시·리깅·VRM 검증 및 방송 앱 동작 검사가 별도로 필요합니다.
