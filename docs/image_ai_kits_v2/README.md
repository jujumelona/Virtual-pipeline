# 이미지 AI 제작 지시서 ZIP — 5개 상위 모드 × 4개 자산 = 20종

**각 ZIP 하나에 해당 작업의 실제 제작 문서 10개를 넣었습니다.** 사용자는 아래에서 모드와 자산 종류를 조합해 한 개를 내려받아 실제 이미지 생성·파일 저장 도구를 갖춘 GPT/Gemini에 그대로 첨부하고, 원하는 디자인을 설명하면 됩니다.

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
- 07_REVIEW_BEFORE_FINAL_ZIP.md — **실제 원화·PNG·합성본을 확인하고 문제가 있는 파츠를 수정·재생성해 반복 점검**, 해당 요구를 모두 충족한 뒤에만 최종 결과 ZIP 납품
- 08_PRACTICAL_TIPS.md — **비공식 제작자의 실전 원화 팁**: 겹침 여유, 선화부터 파츠별 제작, L/R 명칭, 동일 기준선, 숨은 그림, 알파·합성 비교
- 09_VISUAL_ART_QUALITY.md — **고품질 원화·자연스러운 인체/선화/명암·실제 이미지 생성 도구 사용 필수**, 단순 도형식 마네킹 금지, 실제 Live2D 공식 샘플 캐릭터 갤러리·공식 PSD ZIP 경로

## 반드시 구분할 작업

**신체만:** 얼굴·눈·눈썹·코·입·귀·목·몸통·팔다리까지 포함. **나체 이미지를 요구하지 않기 위한 불투명한 기본 속옷**만 착용. 속옷 교체 파츠 별도 생성은 지시하지 않음.
**헤어만:** 사용자가 말한 헤어스타일 하나만. **의상만:** 해당 의상만, 옷에 고정된 장식은 의상 안의 부위. **액세서리만:** 사용자가 말한 머리장식/안경/귀걸이 등 해당 종류 하나만 — **액세서리 세트 생성 금지.**

**Live2D/Inochi2D:** 처음부터 파츠마다 실제 RGBA 원화로 그리고 마지막에 합성. **3D:** 앞/뒤/좌/우·얼굴 눈코입 등의 실제 그림을 각도별로 별도 생성; **VRM 모델을 이미지 AI에 생성시키지 않음**.

**이 20개 ZIP은 제작 지시서이지 실제 완성 그림 ZIP이 아닙니다.** 각 작업의 외부 이미지 AI는 고급 파츠/각도 그림을 만든 후 **07의 적용 가능한 이미지·파일 기준을 반복 점검하고 부족한 그림을 고쳐**, 전부 충족됐을 때만 별도 **결과 원화 ZIP**을 최종 납품하도록 지시받습니다. 실제 리깅/구동 검증을 시키지 않으며 미완성 결과를 거짓으로 완료 처리하지 않습니다.

**Colab v8의 새 모드별 결과 ZIP 업로드·제작 경로는 아직 연결되지 않았습니다.** 지시서 배포/점검과 노트북 제작 엔진의 동작을 혼동하지 마세요.

## 재조사한 공식·비공식 고급 원화 기법

- **공식 Live2D:** [일러스트 파츠 분리](https://docs.live2d.com/en/cubism-editor-tutorials/psd/), [클리핑](https://docs.live2d.com/en/cubism-editor-manual/clipping-mask/), [Skinning](https://docs.live2d.com/en/cubism-editor-manual/skinning/), [Glue](https://docs.live2d.com/en/cubism-editor-manual/glue/), [Blend Shape](https://docs.live2d.com/en/cubism-editor-manual/blend-shape/). 실제 적용은 후속 모델링이며, 이미지 AI는 독립적으로 움직일 **그림 자체**를 먼저 만든다.
- **공식 Inochi2D:** [PSD 예제](https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html), [Node와 Sorting](https://docs.inochi2d.com/en/latest/creator/nodes/node.html), [FAQ](https://docs.inochi2d.com/en/latest/inochi2d/faq.html). 그림 자산은 별도 노드로 쓸 수 있지만 Live2D 리깅 데이터는 호환되지 않는다.
- **공식 3D:** [VRM Humanoid](https://vrm.dev/en/vrm1/humanoid/), [VRM 기능](https://vrm.dev/en/vrm/vrm_features/), [Blender UV](https://docs.blender.org/manual/en/latest/modeling/meshes/uv/unwrapping/introduction.html). 이미지 AI는 모델이 아닌 4면도와 부분 원화만 만든다.
- **비공식 실무:** [Live2D 작화/파츠 그룹](https://www.reddit.com/r/Live2D/comments/15lc7ku/), [세밀한 레이어 구분](https://www.reddit.com/r/Live2D/comments/1140xr5/), [숨은 옷감 보완](https://www.reddit.com/r/Live2D/comments/1myir8h), [3D 참조 시트](https://virmii.com/blog/tutorial/how-to-make-vtuber-reference-sheet). 개인 작업 노하우이며 공식 고정 규격이 아니다.

**20개 ZIP 검증:** `tests/test_image_ai_kits_v2.py`에서 ZIP 20개 파일 존재·CRC 무결성·문서 10종, 이미지 퀄리티 계약·고급 공식/비공식 원문·반복 점검 지시·모드/자산별 파일 계약을 검사한다. **이 검사는 생성된 캐릭터 그림의 실제 시각 품질 검사가 아니다.**

## 최종 그림 ZIP 납품 전에 AI가 해야 할 반복 작업

1. 처음부터 독립 PNG 또는 3D 다각도 참조 그림을 생성
2. 비공식 제작 팁을 적용해 **실제 생성 그림과 합성 미리보기/4면도를 비교**
3. 잘린 관절, 뒤쪽 가림 누락, 좌우/색/배율 불일치, 잘못된 투명 알파·파일명 등을 발견하면 **해당 이미지를 재생성·보완**
4. 다시 합성·시점 비교를 수행하고 모든 해당 그림·파일 요구가 충족될 때까지 반복
5. **이미지 생성·파일 저장 범위에서 적용 가능한 모든 조건이 충족된 경우에만 결과 ZIP을 최종 제공.** 구현하거나 확인할 수 없다면 만들어지지 않은 ZIP을 완료로 꾸미지 말고 미완료 사항을 밝힘

이 과정에 PSD·리깅·모션 테스트·3D 모델 파일 제작이나 형식적 인증서 작성은 들어가지 않습니다.

## 실사례 기반 원화 품질 보강 — 2026-10-12

업로드된 `live2d_upper__body__ARTWORK(1).zip` 사례에서는 PNG 파일 35개가 있었지만 실제 합성은 평면 도형형 얼굴, 분절된 팔과 부자연스러운 신체 비례, 속옷 대신 길게 내려오는 회색 상의로 나타났습니다. **개별 파일 수·ZIP 무결성만으로 미술적 합격을 판단할 수 없다는 사실**이 확인되어 다음 사항을 수정했습니다.

- ZIP 20개 각각의 `00_READ_FIRST.md`가 새 **09_VISUAL_ART_QUALITY.md**를 가장 먼저 적용하게 합니다.
- 사용자 제공 캐릭터 기준이 우선이며, 없으면 섬세한 애니/Vtuber 원화의 선화·색채·명암·비례·관절 연결을 기준으로 합니다.
- **SVG/Pillow/Matplotlib 도형 인형 등 단순 프로그래밍 그림은 최종 고품질 원화로 제출하지 않습니다.** 파일 정렬·투명 PNG/ZIP 보조에는 코드를 쓸 수 있지만 실제 캐릭터 그림은 이미지 생성/편집 기능으로 작업하도록 합니다.
- 단순 개념도 `references/ARTWORK_FLOW.svg`는 외부 그림 생성 AI의 **잘못된 작화 기준으로 쓰일 우려**가 있어 20개 ZIP에서 제외했습니다.
- **[Live2D 공식 원화 가공 튜토리얼](https://docs.live2d.com/en/cubism-editor-tutorials/psd/)**, **[공식 튜토리얼 샘플 PSD ZIP](https://cubism.live2d.com/editor-tutorial/momose1/momose_tutorial01.zip)**, **[실제 캐릭터 샘플 갤러리](https://www.live2d.com/en/learn/sample/)**를 직접 가리키되, 저작권/소재 이용 조건을 확인하고 **공식 캐릭터의 외형을 복제하지 않도록** 합니다.
- **공식 링크가 들어 있다는 사실 자체가 이미지 AI가 공식 예제 원화를 실제 열어 봤다는 뜻은 아닙니다.** 웹/첨부 파일 접근이 불가능하면 봤다고 주장하지 않도록 합니다. 따라서 원화 품질 기준을 링크 없이도 사용할 수 있게 ZIP 안에 직접 작성했습니다.

이 ZIP들에 실제 공식 PSD나 저작권 있는 샘플 원화의 복사본을 동봉한 것은 아닙니다. 그림 AI가 납품할 결과 원화의 미술적 완성도는 **나중에 실제 생성·검토**해야 하며 GitHub CI의 텍스트·ZIP 검사 PASS가 이를 보장하지 않습니다.
