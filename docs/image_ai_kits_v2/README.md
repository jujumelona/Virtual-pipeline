# 이미지 AI 원화 제작 ZIP — 19개 (공통 FACE 1개 + 모드별 자산 18개)

**FACE는 바스트업/상반신/전신별로 나뉘지 않습니다.** 얼굴·눈·귀·입·턱·목은 동일 캐릭터의 공통 원화이며 Live2D, Inochi2D, 3D에서 재사용합니다.

## FACE — 모드와 구도 선택 없이 한 번만 생성

- **[공통 FACE 제작 지침 ZIP](zips/face.zip)** — 이름: `face.zip`
- 민머리 얼굴·귀·눈·입·턱·목만 생성. 어깨·몸통·팔·손·의상 없음.
- 2D용 정면 마스터·좌우 45°·90°·상하 회전·입표정 참고와 3D용 머리·목 8방향 참조를 **하나의 ZIP**으로 지시합니다.
- 결과 원화의 정면 얼굴·목은 구도가 달라도 재생성하지 않고 동일 캐릭터를 기준으로 정렬합니다. 3D 전용 머리·목 참조가 자동으로 VRM 형상이 되는 것은 아닙니다.

## 구도가 실제로 달라지는 자산 — 18개

| 제작 모드 | HAIR | OUTFIT (의상 입은 몸통·팔·손) | ACCESSORY |
|---|---|---|---|
| Live2D 바스트업 | [ZIP](zips/live2d_bust_up__hair.zip) | [ZIP](zips/live2d_bust_up__outfit.zip) | [ZIP](zips/live2d_bust_up__accessory.zip) |
| Live2D 상반신 | [ZIP](zips/live2d_upper__hair.zip) | [ZIP](zips/live2d_upper__outfit.zip) | [ZIP](zips/live2d_upper__accessory.zip) |
| Live2D 전신 | [ZIP](zips/live2d_full__hair.zip) | [ZIP](zips/live2d_full__outfit.zip) | [ZIP](zips/live2d_full__accessory.zip) |
| Inochi2D 상반신 | [ZIP](zips/inochi2d_upper__hair.zip) | [ZIP](zips/inochi2d_upper__outfit.zip) | [ZIP](zips/inochi2d_upper__accessory.zip) |
| Inochi2D 전신 | [ZIP](zips/inochi2d_full__hair.zip) | [ZIP](zips/inochi2d_full__outfit.zip) | [ZIP](zips/inochi2d_full__accessory.zip) |
| 3D VRM 참조 | [ZIP](zips/3d__hair.zip) | [ZIP](zips/3d__outfit.zip) | [ZIP](zips/3d__accessory.zip) |

OUTFIT은 선택된 방송 구도에 맞춰 의상을 실제로 착용한 몸통·어깨·양팔·양손을 제작합니다. 전신 모드에는 착의 하체가 추가됩니다. 별도의 의상을 벗은 신체 원화는 요구하지 않습니다. HAIR와 ACCESSORY는 자신이 소유한 자산 픽셀만 생성합니다.

**권장 순서:** 공통 FACE → 해당 구도 OUTFIT → HAIR → ACCESSORY → 얼굴·목·옷깃 앵커 확인 → 후속 Colab 실제 합성·파츠 분리·PSD·리깅.

**Colab:** [완성 원화 ZIP 입력 노트북](../../notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb). UI에서 FACE는 모드별 선택이 아닌 독립 공통 선택으로 취급합니다.

**ZIP 관리:** `node tools/build_source_only_kits_v7.js`와 `node tools/build_source_only_kits_v7.js --check`로 총 19개(각 문서 14개) 일치 여부를 검사합니다. 원화 ZIP은 이미지 생성 지침이며 완성 이미지나 실제 분리·리깅 산출물이 아닙니다.

**구현 경계:** FACE·OUTFIT 연결/자동 눈·입 세부분리/실제 Live2D·Inochi2D·VRM 리깅 성공은 아직 검증되지 않았습니다. 참고 2D/3D 캔버스 좌표의 결합도 제작 단계에서 따로 검사해야 합니다. 안전 판정 우회나 노출된 신체 생성은 요구하지 않습니다.

오래된 `__body.zip` 6개 및 `<mode>__face.zip` 6개는 배포에서 삭제됐습니다. source/BODY_2D.md 등의 구문은 과거 기록으로 현행 지침에 적용되지 않습니다.
