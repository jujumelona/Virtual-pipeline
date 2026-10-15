# 이미지 AI 제작 지시서 ZIP — 6개 지시 모드 × 4개 자산 = 24종

**각 ZIP 하나에 해당 작업의 실제 제작 문서 14개를 넣었습니다.** 사용자는 아래에서 모드와 자산 종류를 조합해 한 개를 내려받아 실제 이미지 생성·파일 저장 도구를 갖춘 GPT/Gemini에 그대로 첨부하고, 원하는 디자인을 설명하면 됩니다.

| 상위 모드 | 신체만 | 헤어만 | 의상만 | 액세서리만 |
|---|---|---|---|---|
| **Live2D 바스트업 (방송용)** | [ZIP](zips/live2d_bust_up__body.zip) | [ZIP](zips/live2d_bust_up__hair.zip) | [ZIP](zips/live2d_bust_up__outfit.zip) | [ZIP](zips/live2d_bust_up__accessory.zip) |
| **Live2D 상반신** | [ZIP](zips/live2d_upper__body.zip) | [ZIP](zips/live2d_upper__hair.zip) | [ZIP](zips/live2d_upper__outfit.zip) | [ZIP](zips/live2d_upper__accessory.zip) |
| **Live2D 전신** | [ZIP](zips/live2d_full__body.zip) | [ZIP](zips/live2d_full__hair.zip) | [ZIP](zips/live2d_full__outfit.zip) | [ZIP](zips/live2d_full__accessory.zip) |
| **Inochi2D 상반신** | [ZIP](zips/inochi2d_upper__body.zip) | [ZIP](zips/inochi2d_upper__hair.zip) | [ZIP](zips/inochi2d_upper__outfit.zip) | [ZIP](zips/inochi2d_upper__accessory.zip) |
| **Inochi2D 전신** | [ZIP](zips/inochi2d_full__body.zip) | [ZIP](zips/inochi2d_full__hair.zip) | [ZIP](zips/inochi2d_full__outfit.zip) | [ZIP](zips/inochi2d_full__accessory.zip) |
| **3D** | [ZIP](zips/3d__body.zip) | [ZIP](zips/3d__hair.zip) | [ZIP](zips/3d__outfit.zip) | [ZIP](zips/3d__accessory.zip) |

**README 다운로드 경로는 고정됩니다.** 아래 24개는 모두 `docs/image_ai_kits_v2/zips/`에 한 개씩 존재하며 동일 모드/자산의 구형 버전 ZIP을 별도로 두지 않습니다. 신체 BODY는 기존 PSD 템플릿의 실제 레이어·팔·손·어깨·몸통을 바탕으로 완성 애니풍 원화를 제작하고, 이후 Hair/Outfit/Accessory는 같은 기준 캔버스에 정렬합니다. 회색 도형 프록시는 최종 납품 금지입니다. 공식 이미지는 실제 열람 기록이 없으면 시각검수 PASS로 판정하지 않습니다.


## [2026-10-13] 이미지 생성 전 필수 전수 열람 — 24개 ZIP 공통

**이미지 생성 AI는 ZIP을 받자마자 이미지를 생성하면 안 됩니다.** 먼저 압축 내부 **14개 MD 전부**, 사용자 첨부 이미지/기준 신체 이미지, 05·06·11 문서와 다른 MD의 **모든 참고 이미지 및 작품 링크의 실제 그림**을 열고 내용·디자인·충돌을 확인합니다. **최초 출력은 생성 이미지가 아닌 자료 열람 결과와 제작 계획**이어야 합니다. 실제로 열 수 없던 외부 참고 페이지는 열람 완료라고 기록하지 않고, 접근 가능한 다른 참고 이미지를 확보해 검토합니다. 실제 확인 가능한 시각 참고가 없거나, 기존 캐릭터와 동일성을 요구하지만 식별할 자료가 없는 경우에만 해당 작업을 보류합니다. 신규 캐릭터 제작은 사용자 PSD/원화 업로드를 필수 조건으로 삼지 않습니다. 이 게이트 이후에만 고품질 마스터 원화를 생성하고 합격한 원화에서 파츠를 분리합니다.

정식 24개 ZIP의 00_MASTER_FIRST/00_READ_FIRST/00_DELIVERY_AND_RECHECK/07_REVIEW_BEFORE_FINAL_ZIP/11_OFFICIAL_IMAGE_EXAMPLES 맨 앞에는 동일한 생성 전 게이트가 삽입됩니다. 검사기는 [tools/image_ai_read_first_gate.py](../../tools/image_ai_read_first_gate.py)로, MD 14개의 SHA256 및 참고 URL 목록과 제공된 검토 기록을 대조합니다. **해시와 작성된 검토 기록은 AI가 실제로 픽셀을 관찰했다는 자동 증거가 아닙니다.** 외부 GPT/Gemini 도구 호출을 기술적으로 차단하려면 생성 오케스트레이터가 이 게이트를 호출·준수해야 합니다.

## 외부 입력이 없어도 신규 캐릭터 제작

- **신규 창작:** 사용자 PSD·기존 BODY·완성 원화가 없어도 모드·자산 규칙과 실제 열어 본 버튜버 참고 사례에서 새로운 캐릭터 설정을 만들고, 완성 마스터를 실제로 작화합니다. 이후 독립 PNG/알파/레이어 PSD/검증 JSON으로 분리합니다.
- **기존 디자인 유지:** 똑같은 캐릭터를 유지하려면 식별 가능한 참조 이미지나 실제 기존 BODY가 필요합니다. PSD 확장자 자체가 필요한 것은 아닙니다.
- **독립 PRO 자산:** 이전 BODY 없이도 새 캐릭터 공통 캔버스·앵커를 먼저 정할 수 있습니다. 이 경우 기존 BODY에 맞췄다는 검사 PASS는 금지하고, 나중에 실제 BODY와 합성해 검증합니다.
- **링크 실패:** 모든 공개 웹 URL이 성공해야 한다고 주장하지 않습니다. 실패 링크와 사유를 기록하고 다른 실제로 볼 수 있는 시각 참고를 확보해야 합니다. 전혀 이미지를 확인하지 못했다면 미술 검증은 보류합니다.
- **능력 제한:** 생성 환경에 PSD 레이어 쓰기 도구가 없으면 도구 부재를 정확하게 보고합니다. 사용자에게 임의의 원본 PSD를 달라는 것으로 대체하지 않습니다.

## 기존 버튜버 템플릿 활용 — 24개 모드/자산별 슬롯 채우기

24개 ZIP은 기존 **실제 템플릿**의 출처·다운로드 유형·라이선스·사용할 부위·동일 캔버스 슬롯을 각각 연결합니다. [전체 선택표](source/EXISTING_TEMPLATE_SLOT_REGISTRY.json). 배포 ZIP 14개 MD의 최상위 제작 지시와 각 자산 제작 설명에 들어 있습니다.

- **Live2D:** [공식 Boy/Girl PSD 템플릿](https://docs.live2d.com/en/cubism-editor-tutorials/template/), [Haru 분리 전후 PSD](https://www.live2d.com/en/learn/sample/haru-receptionist/), [Mark-kun FREE 샘플 PSD](https://www.live2d.com/en/learn/sample/mark/), [Haru 팔·의상 교체 예제](https://www.live2d.com/en/learn/sample/haru/). 기존 캐릭터 디자인을 복제하지 말고 파츠 구조만 참고합니다.
- **Inochi2D:** [Aka 튜토리얼 PSD](https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html), [Aka·Midori 원본 예제](https://github.com/Inochi2D/example-models). Aka 튜토리얼 PSD는 머리 위주이므로 팔·손·복부 템플릿이라고 주장하지 않습니다.
- **3D:** [VRoid Studio 기본 프리셋](https://vroid.com/en/studio)으로 신체·헤어·의상·부착 액세서리를 각자 선택·조절하고 전후좌우 3D 참고도를 확보합니다. 이 프리셋은 PSD나 VRM 완성품으로 ZIP에 들어 있지 않습니다.

**저작권/실물 파일:** 타사 PSD·프리셋·모델 파일 자체는 이 공개 지침 ZIP에 복제하지 않습니다. 외부 템플릿 PSD는 사용 가능하면 실제 열람하고 레이어 구조를 참고하지만, 신규 캐릭터는 다운로드 불가 시 다른 적절한 실물 시각 참고와 프로젝트의 파츠/비례 계약에 따라 **독창적인 원화부터 제작하고 최종 실제 PSD로 분리**합니다. 새 캐릭터 제작을 위해 사용자 PSD 첨부를 강제하지 않습니다. BODY는 팔·손·어깨·복부를 포함하고 회색 도형으로 대체할 수 없습니다. 2D PRO는 기준 BODY와 동일 캔버스를 따르며 FREE는 승인된 완성 원화에서 분리합니다. 자동으로 Cubism 리깅을 수행하지 않습니다.

## 각 ZIP 내부 구성

- 00_MASTER_FIRST.md — 제작 시작 시 먼저 적용할 마스터 지시서
- 00_DELIVERY_AND_RECHECK.md — 원화 생성·재점검 후 결과 ZIP을 납품하기 위한 지시서
- 00_READ_FIRST.md — **해당 모드+자산에만** 적용되는 실제 이미지 생성 AI 지시
- 01_COMMON_RULES.md — **완성 기준 원화를 먼저 그린 뒤** 실제 필요한 파츠를 추출하고 숨은 부위를 보완·합성; 신체는 완성된 고품질 애니풍 불투명 중립 원화 베이스
- 02_ADVANCED_PARTS.md — 해당 자산의 눈·코·입·머리/옷/장식별 **고급 분리** 또는 3D 다각도 그림 명세
- 03_MODE_RULES.md — Live2D/Inochi2D용 2D 원화 / 3D 참조 시점 차이
- 04_OUTPUT_FILES.md — 실제 생성할 독립 그림·미리보기의 구체적 파일명
- 05_OFFICIAL_REFERENCES.md — 해당 엔진의 공식 예제 링크/핵심 설명
- 06_ADVANCED_OFFICIAL_COMMUNITY.md — **재조사한 최신 공식 문서와 비공식 제작 실무를 구분한 고급 그림 기법**. 2D 눈/입/헤어/관절·마스킹·Glue/Skinning의 원화 요구, 3D VRM/Blender 참고 그림·다각도 정합 지침
- 07_REVIEW_BEFORE_FINAL_ZIP.md — **실제 원화·PNG·합성본을 확인하고 문제가 있는 파츠를 수정·재생성해 반복 점검**, 해당 요구를 모두 충족한 뒤에만 최종 결과 ZIP 납품
- 08_PRACTICAL_TIPS.md — **비공식 제작자의 실전 원화 팁**: 완성 원화 먼저, 해당 자산만 분리·보완, L/R 명칭, 숨은 그림·알파·합성 비교
- 09_VISUAL_ART_QUALITY.md — 고품질 원화와 선화/명암/비례 기준, 단순 도형식 그림 금지
- 10_ANIME_STYLE.md — **전문 일본 애니풍 VTuber 기본 스타일: 검정에 가까운 굵기 가변 외곽선·가늘어지는 끝·얼굴/손·2~3톤 셀 셰이딩**
- 11_OFFICIAL_IMAGE_EXAMPLES.md — **Live2D 공식 캐릭터 실사례 이미지 2장의 직접 URL + Markdown 원격 미리보기** (공식 이미지 파일 자체 재배포 아님)

## [2026-10-15] BODY 기본 수영복의 목·어깨 개방 — 24개 ZIP 공통 역할 정합

- **BODY 6종:** 가슴을 충분히 가리는 **불투명·끈 없는 일자형 반도/튜브형 수영복 상의**를 기본 가림으로 사용한다. 목 앞·옆·뒤와 양쪽 목-어깨 연결부, 어깨 윗면·외곽선, 상완 시작 부분을 가리지 않는다. 홀터넥·목끈·어깨끈·레이서백·하이넥 스포츠브라·탱크톱은 BODY 기본 가림으로 불합격이다. 전신/하반신이 실제 보이는 경우 하이웨이스트 쇼츠형 하의도 사용한다.
- **2D:** 수영복을 몸체 피부와 병합하지 않고 독립 가림 파츠로 두되, 최종 원화/합성에서는 불투명하게 착용한다. 목 회전용 언더페인트·어깨 피부도 별도로 그린다. **3D:** 동일한 수영복을 8방향+가림 세부 참조도 전체에 유지한다.
- **HAIR 6종:** 목·어깨 BODY 원형을 삭제하지 않는다. **OUTFIT 6종:** 사용자가 주문한 의상에는 하이넥·어깨끈 등이 있을 수 있으나 BODY 원형을 변경하지 않는다. **ACCESSORY 6종:** 주문하지 않은 목/어깨 가림 장식을 임의로 추가하지 않는다.
- ZIP 안의 해당 규칙은 00_MASTER_FIRST, 00_READ_FIRST, 07_REVIEW_BEFORE_FINAL_ZIP, 09_VISUAL_ART_QUALITY에 개별 역할대로 작성되어 있다. 생성 후 검수에서 목·어깨를 가리는 결과는 재생성한다. [반복 배포·검사 코드](../../tools/enforce_body_neckline_kits.py).

## 신체만 제작의 최상위 시각 조건 — 실제 모델 사례 반영

**전신 신체의 정확히 6등신은 프로젝트의 별도 디자인 계약이다.** **Live2D 바스트업 신체 ZIP은 머리부터 배 바로 위~배까지 완성된 상체 방송 컷**으로 제작한다. 눈·얼굴을 위해 팔·손·어깨·복부를 잘라내지 않으며, 두상 화면 점유율을 52~61%로 강제하지 않는다. 두상(머리카락 제외) 정수리~턱 1에 키 전체 6, 출발 배치 **머리 1 : 상체 2 : 하체 3**. 상반신 ZIP에서도 같은 6등신 전신 비례 가이드에서 상반신 범위만 제작한다. **두 눈과 홍채는 실제 사람보다 뚜렷하게 큰 애니풍**, 중립 입·코는 작고 간결하며 귀 내부/갈비뼈/흉근·복근 음영은 단순화한다. 신체는 부위와 관절이 완성된 애니풍 선화·셀 셰이딩으로 그리며, 회색 마네킹 몸통은 허용하지 않는다. **파츠 27개나 특정 숫자는 한도가 아니다.** 필요한 눈·입·목·관절/숨은 면 파츠는 더 늘릴 수 있다. 원화와 실제 좌우 3/4·측면, 닫힌/열린 입 한 개씩, 목 underpaint 참고를 남긴다. 좌우 측면 이미지가 있다고 Cubism/VRM 측면 키폼이 자동 완성됐다고 주장하지 않는다.

참고: [일러스트 작화 6등신 가이드](https://atam-academy.com/blog/49102/) · [Live2D 공식 모모세 히요리 샘플](https://www.live2d.com/en/learn/sample/momose-hiyori/). 특정 기존 캐릭터의 외형을 복제하지 않는다. 일반적인 모든 버추얼 캐릭터의 절대 규칙이 아니라 **현재 프로젝트용 고정 디자인 조건**이다.

## 반드시 구분할 작업

**신체만:** 실제 PSD 템플릿의 머리·눈·귀·목·어깨·양팔·손·몸통 구조를 기준으로 완성 원화를 제작한다. 바스트업에서는 배 위까지, 전신에서는 양다리·발끝까지 자연스럽게 연결한다. 단색 2D 도형 프록시는 미술 완성품으로 금지한다. BODY에 튜브탑·속옷·옷깃을 고정 작화하지 않는다. 
**헤어만:** 사용자가 말한 헤어스타일 하나만. **의상만:** 해당 의상만, 옷에 고정된 장식은 의상 안의 부위. **액세서리만:** 사용자가 말한 머리장식/안경/귀걸이 등 해당 종류 하나만 — **액세서리 세트 생성 금지.**

**Live2D/Inochi2D:** 먼저 고품질 기준 원화를 완성한 뒤 움직임/가림별 실제 RGBA 파츠를 추출하고 숨은 피부를 추가 작화하여 마지막에 합성. **3D:** 앞/뒤/좌/우·얼굴 눈코입 등의 실제 그림을 각도별로 별도 생성; **VRM 모델을 이미지 AI에 생성시키지 않음**.

**이 24개 ZIP은 제작 지시서이지 실제 완성 그림 ZIP이 아닙니다.** 각 작업의 외부 이미지 AI는 고급 파츠/각도 그림을 만든 후 **07의 적용 가능한 이미지·파일 기준을 반복 점검하고 부족한 그림을 고쳐**, 전부 충족됐을 때만 별도 **결과 원화 ZIP**을 최종 납품하도록 지시받습니다. 실제 리깅/구동 검증을 시키지 않으며 미완성 결과를 거짓으로 완료 처리하지 않습니다.

**Colab v8의 새 모드별 결과 ZIP 업로드·제작 경로는 아직 연결되지 않았습니다.** 지시서 배포/점검과 노트북 제작 엔진의 동작을 혼동하지 마세요.

## 재조사한 공식·비공식 고급 원화 기법

- **공식 Live2D:** [일러스트 파츠 분리](https://docs.live2d.com/en/cubism-editor-tutorials/psd/), [클리핑](https://docs.live2d.com/en/cubism-editor-manual/clipping-mask/), [Skinning](https://docs.live2d.com/en/cubism-editor-manual/skinning/), [Glue](https://docs.live2d.com/en/cubism-editor-manual/glue/), [Blend Shape](https://docs.live2d.com/en/cubism-editor-manual/blend-shape/). 실제 적용은 후속 모델링이며, 이미지 AI는 독립적으로 움직일 **그림 자체**를 먼저 만든다.
- **공식 Inochi2D:** [PSD 예제](https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html), [Node와 Sorting](https://docs.inochi2d.com/en/latest/creator/nodes/node.html), [FAQ](https://docs.inochi2d.com/en/latest/inochi2d/faq.html). 그림 자산은 별도 노드로 쓸 수 있지만 Live2D 리깅 데이터는 호환되지 않는다.
- **공식 3D:** [VRM Humanoid](https://vrm.dev/en/vrm1/humanoid/), [VRM 기능](https://vrm.dev/en/vrm/vrm_features/), [Blender UV](https://docs.blender.org/manual/en/latest/modeling/meshes/uv/unwrapping/introduction.html). 이미지 AI는 모델이 아닌 4면도와 부분 원화만 만든다.
- **비공식 실무:** [Live2D 작화/파츠 그룹](https://www.reddit.com/r/Live2D/comments/15lc7ku/), [세밀한 레이어 구분](https://www.reddit.com/r/Live2D/comments/1140xr5/), [숨은 옷감 보완](https://www.reddit.com/r/Live2D/comments/1myir8h), [3D 참조 시트](https://virmii.com/blog/tutorial/how-to-make-vtuber-reference-sheet). 개인 작업 노하우이며 공식 고정 규격이 아니다.

**24개 ZIP 전체 전용 범위 검사:** `tests/test_image_ai_kits_v2.py` 및 `tests/test_image_ai_kits_scope_contract.py`에서 24개 파일 존재·CRC·14종 문서·모드/자산별 범위 잠금·공식/비공식 그림 참고·다른 자산의 제작 지시 유입 방지·반복 시각검수·출력 파일명을 검증한다. 공통 원칙만 공유하고 서로 다른 자산의 본문을 동일하게 강제하지 않는다. **이 검사는 생성된 캐릭터 그림의 실제 시각 품질 검사가 아니다.**

## 최종 그림 ZIP 납품 전에 AI가 해야 할 반복 작업

1. 먼저 기준 캐릭터의 완성 원화를 그리고 2D 독립 PNG 추출·숨은 원화 보완 또는 3D 실제 다각도 참조 그림을 생성
2. 비공식 제작 팁을 적용해 **실제 생성 그림과 합성 미리보기/4면도를 비교**
3. 잘린 관절, 뒤쪽 가림 누락, 좌우/색/배율 불일치, 잘못된 투명 알파·파일명 등을 발견하면 **해당 이미지를 재생성·보완**
4. 다시 합성·시점 비교를 수행하고 모든 해당 그림·파일 요구가 충족될 때까지 반복
5. **이미지 생성·파일 저장 범위에서 적용 가능한 모든 조건이 충족된 경우에만 결과 ZIP을 최종 제공.** 구현하거나 확인할 수 없다면 만들어지지 않은 ZIP을 완료로 꾸미지 말고 미완료 사항을 밝힘

이 과정에 PSD·리깅·모션 테스트·3D 모델 파일 제작이나 형식적 인증서 작성은 들어가지 않습니다.

## 실사례 기반 원화 품질 보강 — 2026-10-12

업로드된 `live2d_upper__body__ARTWORK(1).zip` 사례에서는 PNG 파일 35개가 있었지만 실제 합성은 평면 도형형 얼굴, 분절된 팔과 부자연스러운 신체 비례, 속옷 대신 길게 내려오는 회색 상의로 나타났습니다. **개별 파일 수·ZIP 무결성만으로 미술적 합격을 판단할 수 없다는 사실**이 확인되어 다음 사항을 수정했습니다.

- ZIP 20개 각각의 `00_READ_FIRST.md`가 새 **09_VISUAL_ART_QUALITY.md**를 가장 먼저 적용하게 합니다.
- 사용자 제공 캐릭터 기준이 우선이며, 없으면 섬세한 애니/Vtuber 원화의 선화·색채·명암·비례·관절 연결을 기준으로 합니다.
- **얼굴·헤어·의상 등 고품질 캐릭터 그림은 단순 SVG/Pillow 도형으로 대체하지 않습니다.** 단, 교체 의상을 얹기 위한 BODY 몸통 실루엣은 옷주름·가슴/겨드랑이·쇄골 사실묘사를 막기 위해 도형 생성 코드를 정상 사용합니다. 표정/눈/귀 원화와 투명 PNG 검수는 별도로 수행합니다.
- 단순 개념도 `references/ARTWORK_FLOW.svg`는 외부 그림 생성 AI의 **잘못된 작화 기준으로 쓰일 우려**가 있어 20개 ZIP에서 제외했습니다.
- **[Live2D 공식 원화 가공 튜토리얼](https://docs.live2d.com/en/cubism-editor-tutorials/psd/)**, **[공식 튜토리얼 샘플 PSD ZIP](https://cubism.live2d.com/editor-tutorial/momose1/momose_tutorial01.zip)**, **[실제 캐릭터 샘플 갤러리](https://www.live2d.com/en/learn/sample/)**를 직접 가리키되, 저작권/소재 이용 조건을 확인하고 **공식 캐릭터의 외형을 복제하지 않도록** 합니다.
- **공식 링크가 들어 있다는 사실 자체가 이미지 AI가 공식 예제 원화를 실제 열어 봤다는 뜻은 아닙니다.** 웹/첨부 파일 접근이 불가능하면 봤다고 주장하지 않도록 합니다. 따라서 원화 품질 기준을 링크 없이도 사용할 수 있게 ZIP 안에 직접 작성했습니다.

이 ZIP들에 실제 공식 PSD나 저작권 있는 샘플 원화의 복사본을 동봉한 것은 아닙니다. 그림 AI가 납품할 결과 원화의 미술적 완성도는 **나중에 실제 생성·검토**해야 하며 GitHub CI의 텍스트·ZIP 검사 PASS가 이를 보장하지 않습니다.

## 애니풍 기본값과 실제 공식 시각 예시 (2026-10-12)

모든 ZIP의 첫 실행 프롬프트는 이제 **고급 일본 애니메이션풍 버튜버 원화**, **검정에 가까운 짙은 외곽선(가변 선폭·테이퍼)**, **2~3단 셀 셰이딩**, **홍채·얼굴·손·헤어/옷의 애니풍 디테일**을 명시합니다. 피부/머리 내부선에 순수 검정을 똑같이 굵게 사용하지 말고 소재에 맞는 짙은 색선과 가는 보조선을 활용하도록 합니다. 사용자 스타일이 분명한 경우 그 스타일을 우선합니다.

**실제 미리보기 링크:** [Tsumiki 공식 이미지](https://www.live2d.com/wp-content/themes/cubism_new/assets/img/sample/sample-img-tsumiki.png), [Izumi 공식 이미지](https://www.live2d.com/wp-content/themes/cubism_new/assets/img/sample/sample-img-izumi.jpg), [공식 샘플 모델](https://www.live2d.com/en/learn/sample/). [전체 시각 참고 설명](source/OFFICIAL_VISUAL_EXAMPLES.md)에도 두 그림이 Markdown 이미지로 링크됩니다.

**주의:** 이미지 파일 자체는 저작권·재배포 규정 때문에 지시서 ZIP에 복사하지 않았습니다. 원격 이미지를 열 수 없는 이미지 AI에는 실제 예시가 시각적으로 전달되지 않을 수 있습니다. ZIP에 링크가 있다는 것과 그림을 실제 보았다는 것은 별개입니다.

**바스트업 ZIP 4종의 심화 문서에 공식 매뉴얼과 제작자 실무 노하우를 반영했습니다.** 실제 원화의 눈/입/목, PSD RGB 8bit, FREE 7가지 제한, 머리 3/4 원근, 가림 복원, 방송 크기 시각검수 지침을 포함합니다. Photoshop 플러그인이나 Editor 실행은 이미지 AI 필수가 아닙니다.

## 바스트업 ZIP 4종은 부위별로 서로 다른 노하우를 적용합니다

| 자산 | 해당 ZIP 전용 고급 제작 기법 |
|---|---|
| **신체** | 얼굴·홍채·눈·입 내부·목 뒤 underpaint·어깨·불투명 베이스 |
| **헤어** | 앞·옆·뒤 가닥, 머리카락 뿌리·귀 뒤 가림·흔들리는 덩어리·테이퍼 |
| **의상** | 옷깃 안쪽·카라·좌우 소매·어깨 연결·옷감 명암과 불투명 가림 |
| **액세서리** | 요청된 한 종류만, 부착 앵커·앞뒤/좌우 정합·얇은 체인과 반투명 알파 |

네 ZIP의 `02_ADVANCED_PARTS.md`, `06_ADVANCED_OFFICIAL_COMMUNITY.md`, `07_REVIEW_BEFORE_FINAL_ZIP.md`, `08_PRACTICAL_TIPS.md`는 각 자산에 맞게 따로 작성했습니다. 다른 자산을 새로 생성하거나 특정 디자인을 강제하지 않습니다.

## Live2D 바스트업 — 상반신과 독립된 이미지 AI 제작 지시

- 방송용 구도는 **머리 1높이 : 화면에 보이는 목·어깨·상체 약 1~2높이**를 시작점으로 하되, 복장·포즈에 맞게 조정합니다. 전신 6등신 조건을 이 잘린 화면 안에 강제로 적용하지 않습니다.
- 원화 첫 생성부터 머리~가슴 상부에 집중하며 하체를 생성해 자르는 방식을 기본으로 하지 않습니다. 별도의 `live2d_upper`와 `live2d_full` ZIP은 유지합니다.
- 큰 애니풍 홍채·눈과 부드러운 얼굴 윤곽, 목 회전 시 보이는 옆목·뒷목 underpaint, 어깨·옷깃 겹침 여유를 우선합니다. 측면 참조는 필요한 만큼만 요청하며 완전 측면/전신 6방향을 의무화하지 않습니다.
- 신체 기본 베이스는 **실제 PSD 템플릿을 따르는 완성 애니풍 일러스트 베이스**입니다. 불투명 안전 이너를 활용할 수 있지만 회색 도형·몸통 잘림은 최종 FAIL입니다. 불필요한 부분은 프레임 밖으로 두거나 별도 불투명 마스킹하며, 아래 피부를 생성·복원하라고 요구하지 않습니다. 민감한 표현을 피할 수 있도록 구도와 의복도 조정합니다.
- PRO `hair/outfit/accessory` 지시서는 **이미 있는 기준 몸체의 동일 캔버스·원점·스케일**을 요구하며 몸체를 재생성하지 않습니다.
- 이 네 ZIP은 **이미지 AI용 그림 제작 지시서**입니다. 실제 PNG·PSD·Cubism Editor 모델 파일이 담긴 결과물이 아니며, 현재 Colab에는 별도의 `bust_up` 런타임 분기가 아직 연결되지 않았습니다.
- [바스트업 지시 ZIP 검증](../../tests/test_live2d_bust_up_kits.py)은 ZIP 구문·문서 계약만 검사합니다. 실제 애니풍 미술 품질이나 리깅은 인증하지 않습니다.

## 24개 ZIP 자산 독립성 유지 (2026-10-13)

각 ZIP은 **자기 자산 하나의 제작 지시서**다. 다른 ZIP의 필수 파츠를 복사해 넣지 않는다.

- 신체: 얼굴·눈·입·목·어깨·필요한 팔·손·다리·발의 완성 애니 원화만. 의복·가슴 굴곡·팔 옆 살접힘·리얼한 귀 연골 구조를 BODY에 생성하지 않는다.
- 헤어: 지정 헤어스타일 하나만; 얼굴·피부·의상은 부착 위치 참조용이지 새로 제작할 파츠가 아니다.
- 의상: 사용자가 요청한 의상 한 벌만; 몸/머리/탈착형 액세서리를 새로 제작하지 않는다. 전신일 때 실제 있는 하의만 추가한다.
- 액세서리: 요청한 소품 한 종류만, 부착 앵커와 연결부만. 예시의 소품을 전부 세트로 만들지 않는다.

2D 결과는 자기 파츠의 RGBA PNG·같은 캔버스/원점·레이어 순서·실제 합성본을 요구한다. 3D 결과는 자기 자산의 실제 전후좌우 시점 원화·turnaround를 요구하며 2D 파츠나 VRM/메시 생성은 요구하지 않는다. Live2D/Inochi2D 공식 기능 설명은 그림에서 필요한 구조를 **참고**할 뿐 이미지 AI가 해당 편집기 기능을 실행하라는 요구가 아니다.

기존에 여러 ZIP에 같은 본문을 복제하던 테스트를 폐기하고, 이제는 각 ZIP의 제작 대상 및 금지 대상이 일치하는지를 검사한다. **이 테스트는 그림 자체의 예술적 완성도를 증명하지 않는다.**

## 24개 ZIP의 교차 오염 회귀 검사

[자산·모드 독립성 회귀 검사](../../tests/test_image_ai_kits_cross_contamination.py)가 게시된 24개 ZIP의 14개 문서, CRC, 자산 경계 및 이전 제작 순서 충돌을 검사합니다. 특히 **바스트업 신체의 직접 제작**, **2D에 3D 참조 제작 지시가 섞이지 않는지**, **3D에는 각 자산의 독립된 4면도만 요구하는지**, **액세서리 파일명이 머리장식으로 고정되지 않았는지**를 확인합니다.

파츠의 실제 얼굴·헤어·옷·소품 픽셀 품질은 그림 생성 후 시각 검수가 필요합니다. 이 텍스트/ZIP 검사만으로 고급 원화 품질, GPU 추론이나 모델 리깅을 통과했다고 선언하지 않습니다.

## 24종 자산별 공식·비공식 심화 작화 반영 (2026-10-13)

**완료 범위:** Live2D 바스트업·상반신·전신, Inochi2D 상반신·전신, 3D 참조 원화의 **각 4종 자산 ZIP = 24개** 모두 기존 14개 MD를 유지했습니다. ZIP마다 **02 고급 파츠, 03 모드·비율, 06 공식/개인 작가 근거, 07 시각검수, 08 제작 실무, 09 미술 품질, 10 애니풍 이미지 프롬프트**에 해당 자산의 고유 설명을 넣었습니다.

| 자산 | ZIP에 직접 보강한 작화·검수 지침 |
|---|---|
| 신체 | 프로젝트 전신 6등신/바스트업 화면 구도의 구별, 큰 홍채·입안·눈꺼풀·턱 뒤 목, 실제 보이는 관절, 3/4·측면의 먼 눈·귀 위치, 불투명 기본 가림 |
| 헤어 | 모근 방향, 큰 실루엣과 앞·옆·뒤 가닥, 테이퍼·광택·숨은 면, 실제 없는 묶음머리/장식의 강제 생성 금지 |
| 의상 | 요청된 옷 하나의 옷깃·소매·안감·숨은 옷감, 원단별 솔기·주름·반사, 디자인에 없는 하의/신발·탈착 장식 추가 금지 |
| 액세서리 | 요청된 물건 **한 종류**의 앵커·앞뒤·좌우·투명/금속·얇은 연결, 임의 액세서리 세트 생성 금지 |

**기술별 차이:** Live2D 문서는 공식 일러스트 분리/원화 보완과 이후 Cubism Editor 기능을 구분합니다. Inochi2D 문서는 공식 PSD 그림자 중첩 예시 및 Node Sorting을 **후속 Creator 작업 참고**로만 다룹니다. 3D 문서는 동일 자산의 실제 정면/후면/좌우 작화와 형태·두께 정합만 요구하며 메시·UV·VRM·본을 이미지 AI의 산출물로 요구하지 않습니다.

**근거 구분:** [Live2D 공식 일러스트 분리](https://docs.live2d.com/en/cubism-editor-tutorials/psd/), [Inochi Creator 공식 PSD 예제](https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html), [VRM 공식 3D 변환 과정](https://vrm.dev/en/vrm/how_to_make_vrm/convert_from_humanoid_model/)을 기술 참고로 사용했습니다. [CLIP STUDIO TIPS 개인 작가 얼굴/각도 팁](https://tips.clip-studio.com/en-us/articles/7379), [헤어 작화 팁](https://tips.clip-studio.com/en-us/articles/5958)은 **아티스트 경험칙**으로 분류했으며 공식 리깅 사양이 아닙니다. 얼굴/눈의 고정 픽셀 비율, 모든 장식이나 헤어스타일, 파츠 개수를 강제하지 않습니다.

**재생성 원본 보존:** `source/BODY_2D.md` 등 부위별 원본과 `builder_inputs/2D.json`·`3D.json`에도 자산 전용 노하우와 완성 원화 우선 계약을 맞췄습니다. [24종 회귀 검사](../../tests/test_image_ai_kits_cross_contamination.py)는 각 ZIP의 14개 MD/CRC와 7개 전문 문서, 올바른 공식 자료 구분 및 원본 계약을 확인합니다.

**검증 한계:** 이것은 이미지 AI에 대한 정확한 제작 지시와 ZIP 텍스트/구조 검증입니다. 외부 이미지 생성 모델의 실제 그림 결과를 테스트한 것은 아니며, 생성된 그림의 미술적 품질이나 Cubism/Inochi/VRM 리깅 통과를 보증하지 않습니다.

## 눈 비율·바스트업 구도·목 회전 원화 보강 (2026-10-13)

24개 자산별 ZIP 모두에 **정량 추천과 옆얼굴·목 접합 개선** 항목을 추가했습니다. [정식 원본 소스](source/FACE_NECK_GEOMETRY_GUIDANCE.json)는 6가지 모드와 신체/헤어/의상/액세서리의 범위를 구분합니다. 눈 숫자·목 피부는 신체 ZIP만, 모근은 헤어, 옷깃 안감은 의상, 실제 부착점은 단일 소품 ZIP만 담당합니다.

- **추천 시작값 — 공식 규격/업계 평균 아님:** 일반 신체의 한눈 폭/얼굴폭 18~22% 참고치와 구분하여, **바스트업 신체는 23~29%**, 양눈 간격/눈 폭 0.65~0.95, 보이는 홍채 폭/눈 폭 62~80%를 얼굴 중심 애니풍 선택값으로 둡니다. 얼굴폭은 눈높이 관자놀이 사이(귀 제외), 눈폭은 눈꺼풀 외곽(속눈썹 돌출 제외)으로 정의합니다. 사용자 원화를 우선합니다.
- **바스트업만:** 머리부터 배 위~허리 위까지 완성된 상체와 양쪽 어깨·상완·전완·양손을 포함합니다. 얼굴의 화면 점유율은 사용자 캐릭터와 방송 구도에 맞추고 특정 수치로 강제하지 않습니다. 머리카락은 별도 HAIR, 의상은 별도 OUTFIT으로 작업하며 BODY 기준 캔버스와 앵커를 유지합니다.
- **공식 목 연결:** [Live2D 일러스트 가공](https://docs.live2d.com/ko/cubism-editor-tutorials/psd/)에서 숨은 목 피부를 입 높이 근처까지 넉넉히 그릴 것을 안내합니다. 턱 아래·귀 뒤·뒷목은 신체, 목깃 안쪽 천은 의상, 뒤통수 모근은 헤어 ZIP 소유입니다.
- **옆모습:** [CLIP STUDIO TIPS 개인 작가](https://tips.clip-studio.com/en-us/articles/8014)와 [애니 눈 작화](https://tips.clip-studio.com/ko-kr/articles/11807)는 측면 코·턱·귀·눈의 형태 및 3/4 원근의 참고입니다. 3D는 실제 4방향 독립 참조 원화가 필요하지만 2D ZIP에 측면 리깅/키폼 완료를 강제하지 않습니다.

ZIP 재생성 후에는 `python tools/sync_image_ai_geometry_guidance.py --write`로 해당 고급 노하우의 **누락된 문단만 보완**하고 `--check`로 24개 ZIP의 문서/CRC를 읽기 전용 검사합니다. 기존 문구를 덮어쓰지 않습니다. [정합 테스트](../../tests/test_image_ai_geometry_guidance.py)는 24개 ZIP 내부에 실제로 반영되어 있는지 검사합니다. 이미지 AI의 실제 생성 품질·에디터 리깅은 별도 실물 검증이 필요합니다.

## 고급 그림자·모근·소재·선폭 실무 가이드 (2026-10-13)

기존 24개 이미지 생성 AI용 ZIP **전부**에 해당 자산만의 고급 제작/검수 내용을 반영했습니다. 각 ZIP의 **02 고급 파츠, 03 모드 범위, 06 공식/개인 기법 근거, 07 시각검수, 08 실전 노하우, 09 미술 완성도, 10 애니풍** 총 7개 MD에 직접 들어 있습니다.

| 자산 | 실제 적용된 고급 노하우 |
|---|---|
| **신체** | 피부 자체 음영과 움직이는 앞머리의 투사 그림자 소유권 구분; 눈꼬리·윗속눈썹 분리 조건; 원화/재합성의 선화·알파 중복 검사 |
| **헤어** | 모근이 두피 곡면에서 자연스럽게 출발하는지, 귀 앞/뒤 가닥의 깊이, 끝선 테이퍼·광택, 움직임이 실제 필요한 경우에만 헤어 소유의 선택적 투사 그림자 |
| **의상** | 어깨·팔꿈치·허리의 장력점에서 시작하는 주름, 실제 요청된 체크·줄무늬의 연속성, 반투명 소재가 있을 때만 안감·겹침·이중 그림자 검사 |
| **액세서리** | 요청된 한 물건의 실제 고정부, 얇은 체인·끈·렌즈의 알파/선폭, 유연한 부속에 후속 움직임이 필요한 경우에만 중립 형태의 참고 원화 |
| **3D** | 각 자산의 정면·후면·좌우 실루엣·재질·문양·반사광·선폭 일치, 독립 4방향 원화만. 2D 그림자 레이어/리깅 지시 없음 |

**자료 근거:** [Live2D 공식 원화 가공](https://docs.live2d.com/en/cubism-editor-tutorials/psd/)은 실제 필요한 파츠의 분리와 가려진 영역 보완을 설명합니다. [공식 Cubism 가져오기 PSD 제작](https://docs.live2d.com/en/cubism-editor-manual/reimport-psd/)은 후속 PSD 가져오기에서 파츠별 선화·채색을 합쳐 준비하도록 안내합니다. [Inochi2D 공식 PSD 튜토리얼](https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html)은 그림자 레이어가 합쳐질 때 이중 음영 문제가 발생할 수 있음을 보여 줍니다. 선폭 위계, 주름 장력, 체인의 중립 원화 등은 특정 프로그램의 기술 규격이 아닌 **조건부 작가 노하우**입니다.

**재생성 누락 방지:** [정식 고급 노하우 원본](source/ADVANCED_ARTWORK_CRAFT_GUIDANCE.json), 기존 [비율/목 원본](source/FACE_NECK_GEOMETRY_GUIDANCE.json), [ZIP 동기화 스크립트](../../tools/sync_image_ai_geometry_guidance.py)를 함께 사용합니다. ZIP을 새로 만들었을 때 명령 python tools/sync_image_ai_geometry_guidance.py --write 는 누락된 섹션만 추가합니다. python tools/sync_image_ai_geometry_guidance.py --check 는 24개 ZIP 내부에 실제 원본 내용이 들어 있는지 확인합니다. 기존 내용을 덮어쓰기보다 변경된 문단을 명시적으로 정리하도록 보호합니다.

[24개 ZIP 고급 노하우 회귀 검사](../../tests/test_image_ai_advanced_craft_guidance.py)는 모든 ZIP의 14개 MD/압축 CRC, 해당 자산의 실제 문단, 재생성 입력 파일과 원본의 일치, 복원 작업의 멱등성을 확인합니다. 이는 이미지 생성 AI의 실제 원화 품질이나 Cubism/Inochi/VRM 리깅 완료의 증명이 아닙니다.

### ZIP 24개 자산·모드 혼입 재점검

[2026-10-13 ZIP별 점검표](AUDIT_ASSET_SCOPE_2026-10-13.md)에 각 ZIP의 잘못 들어간 지시와 고친 문서 번호를 기록했습니다. 2D 상반신의 불필요한 전신 가이드 생성, 비신체 자산의 몸체 재설계, 3D의 타 자산 세부도 강제, Live2D/Inochi2D 공식 자료 혼합을 정정하고 재생성용 원본·CI 검사도 갱신했습니다.

## [바스트업 일반 상반신/실사화 문제 수정 — 2026-10-13]
바스트업 ZIP의 과거 얼굴 초근접·회색 프록시 지시는 폐기하고 **완성된 상복부 BODY와 양팔·양손을 포함하는 정합 구도**를 적용했습니다. 최종 결과 ZIP은 실제 다층 PSD·RGBA PNG·알파 마스크·원본/합성·검증 JSON·Cubism 안내 MD까지 필수이며, 중간 PNG 검사와 최종 납품 검사를 구분합니다. [원본 계약](source/BUST_UP_FACE_FIRST_CONTRACT.json)을 따릅니다.

## 2D 최종 결과 ZIP 레이어 불일치 사전 방지 (2026-10-13)

20개 2D 제작 지시 ZIP(Live2D 바스트업/상반신/전신 및 Inochi2D 상반신/전신 × 신체·헤어·의상·액세서리)에 최종 ZIP 경로와 파일명·레이어 순서 1:1 계약을 삽입했다. 3D 4개는 본 계약 대상이 아니다.

- 생성 AI는 기준 원화부터 제작하고, 실제 독립 파츠마다 정확한 `isolated_parts/<part_id>.png` 경로와 캐릭터 뒤→앞 레이어 순서를 유지해야 한다. `layer_order.txt`에 다른 PNG나 누락·중복이 있으면 납품할 수 없다.
- 각 ZIP의 `04_OUTPUT_FILES.md`에 실물 결과 ZIP을 다시 열어 검사하는 Python 코드가 들어 있다. 검사 PASS 전에 ZIP을 완료라고 선언하지 않으며 이미지 자체의 작화 검수는 별도로 수행한다.
- 검사 원본: [2D 최종 경로·순서 계약](source/ARTWORK_LAYER_ORDER_CONTRACT.md) 및 [구조 검증 코드](../../tools/validate_image_ai_artwork_zip.py). 검사 대상은 **생성 AI가 만든 결과 원화 ZIP**이지 제작 지시 ZIP이 아니다.
- 20개 지시 ZIP 자체의 구조·검증 코드 삽입은 [회귀 테스트](../../tests/test_image_ai_layer_order_delivery.py)로 보호한다. 외부 이미지 AI가 명령을 실제 실행하는지, 이미지 원화가 예술적으로 합격인지까지 텍스트 지시서만으로 보증하지 않는다.
