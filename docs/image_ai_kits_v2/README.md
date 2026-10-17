# 이미지 생성 AI 전용 원화 ZIP — 24종 SOURCE_ART_ONLY_V7

2026-10-17 기준 **이미지 생성 AI는 파츠를 분리하지 않습니다.** 원화와 시점별 참고 그림만 제작합니다.

**배포 주의:** 24개 중 **23개 ZIP만 안전한 작업용 커버/단일 자산 지침으로 갱신**되었습니다. `live2d_bust_up__body.zip`은 전송 안전 검사에 차단되어 이전 지침이 남아 있습니다. 이 ZIP을 사용하지 말고 [최신 Live2D 바스트업 BODY 지침](SAFE_BUST_UP_BODY_BRIEF.md)을 따르세요. 전체 24개 재생성 검사는 이 1개 불일치 때문에 아직 통과하지 않습니다.

**역할 계약**
- **이미지 생성 AI:** 선택된 단일 자산의 `outputs/master.png`(2D)와 `reference_views/*.png`, BODY의 `expression_refs/*.png`를 실제 이미지로 제작합니다. 3D는 `views/*.png` 8방향+가림 참고 1장입니다.
- **Colab 노트북:** 업로드한 실제 이미지에서 분리 모델 실행·레이어 가공·PSD 저장·가능한 네이티브 모델 생성·실행 검증을 담당합니다. 생성 AI에 개별 파츠 PNG/PSD/마스크/리깅을 요구하지 않습니다.
- **정확한 상태:** 2D BODY는 See-through를 호출하지만 세부 눈/목/팔 분리는 아직 자동 품질 보장이 되지 않습니다. 독립 HAIR/OUTFIT/ACCESSORY는 단일 알파 레이어 후 세부 분리가 아직 필요하며, 3D 헤어·의상의 독립 VRM 자동 결합은 미구현입니다.

**완성 원화 ZIP을 Colab에 업로드:** [노트북](../../notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb)

모든 지시 ZIP에는 14개 MD가 있고, 모두 원화 전용 `SOURCE_ART_ONLY_V7` 계약입니다. 과거 `ONE_PART_PER_GENERATION`, `ART_SOURCE_AND_SEPARATION_V3`, `GPT_ARTWORK_SEGMENTER_HANDOFF_V5`, `MODE_ASSET_SEETHROUGH_V3_ROUTING_V6` 규칙은 이 24개 배포 ZIP에는 적용되지 않습니다. 모델 처리 방식은 **Colab 코드**에서 관리합니다.

| 모드 | BODY | HAIR | OUTFIT | ACCESSORY |
|---|---|---|---|---|
| Live2D 바스트업 | [구버전 ZIP 사용 보류 — 안전한 BODY 지침](SAFE_BUST_UP_BODY_BRIEF.md) | [ZIP](zips/live2d_bust_up__hair.zip) | [ZIP](zips/live2d_bust_up__outfit.zip) | [ZIP](zips/live2d_bust_up__accessory.zip) |
| Live2D 상반신 | [ZIP](zips/live2d_upper__body.zip) | [ZIP](zips/live2d_upper__hair.zip) | [ZIP](zips/live2d_upper__outfit.zip) | [ZIP](zips/live2d_upper__accessory.zip) |
| Live2D 전신 | [ZIP](zips/live2d_full__body.zip) | [ZIP](zips/live2d_full__hair.zip) | [ZIP](zips/live2d_full__outfit.zip) | [ZIP](zips/live2d_full__accessory.zip) |
| Inochi2D 상반신 | [ZIP](zips/inochi2d_upper__body.zip) | [ZIP](zips/inochi2d_upper__hair.zip) | [ZIP](zips/inochi2d_upper__outfit.zip) | [ZIP](zips/inochi2d_upper__accessory.zip) |
| Inochi2D 전신 | [ZIP](zips/inochi2d_full__body.zip) | [ZIP](zips/inochi2d_full__hair.zip) | [ZIP](zips/inochi2d_full__outfit.zip) | [ZIP](zips/inochi2d_full__accessory.zip) |
| 3D VRM 참조 | [ZIP](zips/3d__body.zip) | [ZIP](zips/3d__hair.zip) | [ZIP](zips/3d__outfit.zip) | [ZIP](zips/3d__accessory.zip) |

**캐릭터 범위:** BODY는 머리카락과 패션 의상·독립 장식 없이 얼굴·목·손의 자연 피부색을 통일하고, 몸통·팔·다리에는 눈에 보이는 청회색 무광 작업용 보호 슈트를 적용합니다. 이는 최종 OUTFIT 자산이 아니며, 원화에서 표현되지 않은 커버 아래 신체 픽셀이 생성됐다고 주장할 수 없습니다. HAIR/OUTFIT/ACCESSORY는 각각 자기 자산만 생성하고, BODY 그림은 정렬 참조로만 사용합니다. 사용자가 기존 캐릭터 참조를 제공했다면 동일성·색상·크기를 우선합니다.

**문서 재생성:** `node tools/build_source_only_kits_v7.js` 명령은 배포된 24개 ZIP을 재현합니다. `node tools/build_source_only_kits_v7.js --check`로 추적된 ZIP 바이트와 생성 결과를 비교합니다. 현재 바스트업 BODY 1개는 배포 교체가 차단되어 이 명령이 불일치를 보고하는 것이 정상이며, 24개 일치로 보고해서는 안 됩니다.

실제 GPU 분리·시각 품질·리깅 성공은 이 지시서 ZIP의 정적 검증만으로 보장되지 않습니다.
