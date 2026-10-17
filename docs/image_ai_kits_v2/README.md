# 버추얼 원화 제작 ZIP — 18개

## 2D 공통 FACE 1개

[**공통 2D FACE 원화 ZIP**](zips/face.zip) — `face.zip`

얼굴·눈·귀·턱·목을 한 번만 제작하고 Live2D/Inochi2D의 바스트업·상반신·전신에 공통 사용합니다. 의상·머리카락·어깨·팔은 그리지 않습니다. 입표정·정면·좌우 고개 회전 참고를 포함합니다.

**3D 모드는 이 FACE ZIP을 사용하지 않습니다.** 얼굴을 캐릭터 전체 2D 원화에 포함하여 3D 복원합니다.

## 2D 구도별 자산 15개

| 2D 제작 모드 | HAIR | OUTFIT (착의 몸통·팔·손) | ACCESSORY |
|---|---|---|---|
| Live2D 바스트업 | [ZIP](zips/live2d_bust_up__hair.zip) | [ZIP](zips/live2d_bust_up__outfit.zip) | [ZIP](zips/live2d_bust_up__accessory.zip) |
| Live2D 상반신 | [ZIP](zips/live2d_upper__hair.zip) | [ZIP](zips/live2d_upper__outfit.zip) | [ZIP](zips/live2d_upper__accessory.zip) |
| Live2D 전신 | [ZIP](zips/live2d_full__hair.zip) | [ZIP](zips/live2d_full__outfit.zip) | [ZIP](zips/live2d_full__accessory.zip) |
| Inochi2D 상반신 | [ZIP](zips/inochi2d_upper__hair.zip) | [ZIP](zips/inochi2d_upper__outfit.zip) | [ZIP](zips/inochi2d_upper__accessory.zip) |
| Inochi2D 전신 | [ZIP](zips/inochi2d_full__hair.zip) | [ZIP](zips/inochi2d_full__outfit.zip) | [ZIP](zips/inochi2d_full__accessory.zip) |

OUTFIT은 별도 2D FACE와 목깃을 맞춰 의상을 착용한 몸통·팔·손을 그립니다. 전신 모드에서는 착의 하체까지 그립니다. HAIR와 ACCESSORY는 해당 자산만 제작합니다. 원화 생성 AI에 파츠 분리·PSD·리깅 완료를 요구하지 않습니다.

## 3D: 완성 캐릭터 원화 1개 + 액세서리 1개

| 3D 제작 항목 | 생성 입력 | ZIP |
|---|---|---|
| **3D 전체 캐릭터** | 얼굴·헤어·의상 착용 전신이 모두 포함된 **2D 캐릭터의 정면·후면·좌·우·대각도** 원화 | [3D CHARACTER](zips/3d__character.zip) |
| **3D 액세서리** | 기존 VRM에 부착할 소품의 2D 다각도 원화 | [3D ACCESSORY](zips/3d__accessory.zip) |

3D 작업은 2D 원화를 입력으로 3D 메시·재질/텍스처를 복원하고 Blender/VRM 경로를 사용합니다. 현재 제작기는 4개 직교 시점을 활용하고 대각도 참조는 추가 검수에만 사용합니다. 별도 3D 헤어/의상 메쉬 제작은 아직 연결되지 않았으므로 3D HAIR·OUTFIT ZIP을 배포하지 않습니다.

**총계: 2D FACE 1 + 2D 전용 15 + 3D 2 = 18 ZIP.**

[Colab 제작 노트북](../../notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb)에서 3D는 `전체 캐릭터`를 선택하고, 2D 공통 FACE는 `얼굴만`을 선택합니다.

`node tools/build_source_only_kits_v7.js --check`와 `python -m tools.audit_24_image_kits --strict`로 압축파일 및 문서 계약을 검사합니다. 과거 `__body.zip`과 `3d__hair.zip`·`3d__outfit.zip`, 프레이밍별 FACE ZIP은 폐기됩니다.

**현재 한계:** 2D 원화 생성·ZIP 검증 자체가 3D 모델 생성 성공을 보장하지 않습니다. 실제 메시·리깅·VRM 검증 및 방송 앱 동작 검사가 별도로 필요합니다.
