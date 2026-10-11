# 이미지 AI 제작 지시서 ZIP — 5개 상위 모드 × 4개 자산 = 20종

**각 ZIP 하나에 그 작업에 필요한 문서를 전부 넣었습니다.** 사용자는 아래에서 모드와 자산 종류를 조합해 한 개를 내려받아 실제 이미지 생성·파일 저장 도구를 갖춘 GPT/Gemini에 그대로 첨부하고, 원하는 디자인을 설명하면 됩니다.

| 상위 모드 | 신체만 | 헤어만 | 의상만 | 액세서리만 |
|---|---|---|---|---|
| **Live2D 상반신** | [ZIP](zips/live2d_upper__body.zip) | [ZIP](zips/live2d_upper__hair.zip) | [ZIP](zips/live2d_upper__outfit.zip) | [ZIP](zips/live2d_upper__accessory.zip) |
| **Live2D 전신** | [ZIP](zips/live2d_full__body.zip) | [ZIP](zips/live2d_full__hair.zip) | [ZIP](zips/live2d_full__outfit.zip) | [ZIP](zips/live2d_full__accessory.zip) |
| **Inochi2D 상반신** | [ZIP](zips/inochi2d_upper__body.zip) | [ZIP](zips/inochi2d_upper__hair.zip) | [ZIP](zips/inochi2d_upper__outfit.zip) | [ZIP](zips/inochi2d_upper__accessory.zip) |
| **Inochi2D 전신** | [ZIP](zips/inochi2d_full__body.zip) | [ZIP](zips/inochi2d_full__hair.zip) | [ZIP](zips/inochi2d_full__outfit.zip) | [ZIP](zips/inochi2d_full__accessory.zip) |
| **3D** | [ZIP](zips/3d__body.zip) | [ZIP](zips/3d__hair.zip) | [ZIP](zips/3d__outfit.zip) | [ZIP](zips/3d__accessory.zip) |

## 각 ZIP 내부 구성

- 00_READ_FIRST.md — **해당 모드+자산에만** 적용되는 실제 이미지 생성 AI 지시
- 01_COMMON_RULES.md — **처음부터 독립 파츠를 생성**하고 마지막에 합성; 신체는 불투명 속옷 기본 베이스
- 02_ADVANCED_PARTS.md — 해당 자산의 눈·코·입·머리/옷/장식별 **고급 분리** 또는 3D 다각도 그림 명세
- 03_MODE_RULES.md — Live2D/Inochi2D용 2D 원화 / 3D 참조 시점 차이
- 04_OUTPUT_FILES.md — 실제 생성할 독립 그림·미리보기의 구체적 파일명
- 05_OFFICIAL_REFERENCES.md — 해당 엔진의 공식 예제 링크/핵심 설명
- 06_ADVANCED_OFFICIAL_COMMUNITY.md — **재조사한 최신 공식 문서와 비공식 제작 실무를 구분한 고급 그림 기법**. 2D 눈/입/헤어/관절·마스킹·Glue/Skinning의 원화 요구, 3D VRM/Blender 참고 그림·다각도 정합 지침
- references/ARTWORK_FLOW.svg — 프로젝트 자체 제작 개념도(공식 예제 그림 아님)

## 반드시 구분할 작업

**신체만:** 얼굴·눈·눈썹·코·입·귀·목·몸통·팔다리까지 포함. **나체 이미지를 요구하지 않기 위한 불투명한 기본 속옷**만 착용. 속옷 교체 파츠 별도 생성은 지시하지 않음.
**헤어만:** 사용자가 말한 헤어스타일 하나만. **의상만:** 해당 의상만, 옷에 고정된 장식은 의상 안의 부위. **액세서리만:** 사용자가 말한 머리장식/안경/귀걸이 등 해당 종류 하나만 — **액세서리 세트 생성 금지.**

**Live2D/Inochi2D:** 처음부터 파츠마다 실제 RGBA 원화로 그리고 마지막에 합성. **3D:** 앞/뒤/좌/우·얼굴 눈코입 등의 실제 그림을 각도별로 별도 생성; **VRM 모델을 이미지 AI에 생성시키지 않음**.

**여기 올린 ZIP은 제작 지시서이며 실제 그림 결과 ZIP이 아닙니다.** 2026-10-11 기준 Colab v8은 상위/하위 선택 UI만 마련된 1단계 상태이며, 이 20종 지시서에 맞는 이미지 AI **결과 ZIP의 모드별 업로드·제작 연결은 아직 구현되지 않았습니다**.

## 재조사한 공식·비공식 고급 원화 기법

- **공식 Live2D:** [일러스트 파츠 분리](https://docs.live2d.com/en/cubism-editor-tutorials/psd/), [클리핑](https://docs.live2d.com/en/cubism-editor-manual/clipping-mask/), [Skinning](https://docs.live2d.com/en/cubism-editor-manual/skinning/), [Glue](https://docs.live2d.com/en/cubism-editor-manual/glue/), [Blend Shape](https://docs.live2d.com/en/cubism-editor-manual/blend-shape/). 실제 적용은 후속 모델링이며, 이미지 AI는 독립적으로 움직일 **그림 자체**를 먼저 만든다.
- **공식 Inochi2D:** [PSD 예제](https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html), [Node와 Sorting](https://docs.inochi2d.com/en/latest/creator/nodes/node.html), [FAQ](https://docs.inochi2d.com/en/latest/inochi2d/faq.html). 그림 자산은 별도 노드로 쓸 수 있지만 Live2D 리깅 데이터는 호환되지 않는다.
- **공식 3D:** [VRM Humanoid](https://vrm.dev/en/vrm1/humanoid/), [VRM 기능](https://vrm.dev/en/vrm/vrm_features/), [Blender UV](https://docs.blender.org/manual/en/latest/modeling/meshes/uv/unwrapping/introduction.html). 이미지 AI는 모델이 아닌 4면도와 부분 원화만 만든다.
- **비공식 실무:** [Live2D 작화/파츠 그룹](https://www.reddit.com/r/Live2D/comments/15lc7ku/), [세밀한 레이어 구분](https://www.reddit.com/r/Live2D/comments/1140xr5/), [숨은 옷감 보완](https://www.reddit.com/r/Live2D/comments/1myir8h), [3D 참조 시트](https://virmii.com/blog/tutorial/how-to-make-vtuber-reference-sheet). 개인 작업 노하우이며 공식 고정 규격이 아니다.

**20개 ZIP 검증:** `tests/test_image_ai_kits_v2.py`에서 ZIP 20개 파일 존재·CRC 무결성·문서 8종·고급 공식/비공식 원문 동봉 여부·모드/자산별 파일 계약을 검사한다. **이 검사는 생성된 캐릭터 그림의 실제 시각 품질 검사가 아니다.**
