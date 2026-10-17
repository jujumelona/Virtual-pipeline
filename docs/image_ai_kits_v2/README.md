# 이미지 생성 AI 전용 원화 ZIP — 24종 FACE/HAIR/OUTFIT/ACCESSORY

2026-10-17부터 BODY 원화 생성 ZIP은 폐기하고 FACE ZIP 6개로 교체했습니다. 24개 ZIP은 각 14개 지침을 갖는 SOURCE_ART_ONLY_V7 명세입니다.

**FACE:** 성인 애니 VTuber의 민머리 얼굴·눈·귀·입·턱·목만 생성합니다. 몸통·어깨·팔·손·의상은 어떤 FACE 이미지에도 포함하지 않습니다. 고개 좌우 45°·90°와 상하 각도 참고를 포함하며, 입 닫힘/벌림도 FACE 쪽에서 제작합니다.

**OUTFIT:** 별도 FACE의 목끝과 같은 앵커·캔버스를 사용해 의상 입은 어깨·몸통·양팔·양손(전신은 하체까지)을 제작합니다. 몸통의 피부 원화는 생성하지 않습니다. 머리·눈·얼굴은 OUTFIT 이미지에 그리지 않습니다.

**HAIR:** 기존 FACE 두상에 정렬된 헤어만 제작합니다. **ACCESSORY:** 지정 소품만 제작합니다.

**제작 순서:** FACE 확정 → 같은 앵커의 OUTFIT → HAIR → ACCESSORY → 합성 및 연결 검수 → Colab에서 파츠 분리·PSD·리깅. 원화 생성 AI에는 별도 파츠 PNG·PSD·MOC3 제작을 요구하지 않습니다.

**구현 경계:** 현재 Colab은 FACE 독립 PNG 검사와 원화 포장을 지원하지만 FACE/OUTFIT 간 원화 합성, 눈·입 세부 자동 분리 및 2D 네이티브 리깅 완성은 검증되지 않았습니다. 3D 얼굴 원화가 자동으로 VRM에 결합된다고 주장하지 않습니다.

| 모드 | FACE | HAIR | OUTFIT(착의 몸통·팔·손) | ACCESSORY |
|---|---|---|---|---|
| Live2D 바스트업 | [ZIP](zips/live2d_bust_up__face.zip) | [ZIP](zips/live2d_bust_up__hair.zip) | [ZIP](zips/live2d_bust_up__outfit.zip) | [ZIP](zips/live2d_bust_up__accessory.zip) |
| Live2D 상반신 | [ZIP](zips/live2d_upper__face.zip) | [ZIP](zips/live2d_upper__hair.zip) | [ZIP](zips/live2d_upper__outfit.zip) | [ZIP](zips/live2d_upper__accessory.zip) |
| Live2D 전신 | [ZIP](zips/live2d_full__face.zip) | [ZIP](zips/live2d_full__hair.zip) | [ZIP](zips/live2d_full__outfit.zip) | [ZIP](zips/live2d_full__accessory.zip) |
| Inochi2D 상반신 | [ZIP](zips/inochi2d_upper__face.zip) | [ZIP](zips/inochi2d_upper__hair.zip) | [ZIP](zips/inochi2d_upper__outfit.zip) | [ZIP](zips/inochi2d_upper__accessory.zip) |
| Inochi2D 전신 | [ZIP](zips/inochi2d_full__face.zip) | [ZIP](zips/inochi2d_full__hair.zip) | [ZIP](zips/inochi2d_full__outfit.zip) | [ZIP](zips/inochi2d_full__accessory.zip) |
| 3D VRM 참조 | [ZIP](zips/3d__face.zip) | [ZIP](zips/3d__hair.zip) | [ZIP](zips/3d__outfit.zip) | [ZIP](zips/3d__accessory.zip) |

**Colab:** [완성 원화 ZIP 입력 노트북](../../notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb)

**정확한 ZIP 재생성:** `node tools/build_source_only_kits_v7.js` 및 `node tools/build_source_only_kits_v7.js --check`. 24개 파일이 모두 같은 생성기로 만들어졌는지 검증합니다.

기존 source/BODY_2D.md, BODY_3D.md 및 과거 BODY 계약 문서는 **사용 중단된 역사적 자료**입니다. 24개 배포 ZIP과 현재 생성기·Colab 선택 키가 우선합니다.

본 저장소는 특정 이미지 생성 서비스의 안전 필터를 끄거나 우회하지 않습니다. 노출된 신체 원화를 요청하지 않는 별도 FACE + 착의 OUTFIT 구성이 목적입니다.
