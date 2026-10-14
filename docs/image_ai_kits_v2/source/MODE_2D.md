# 2D 전용 출력 규칙 (Live2D / Inochi2D)

- **완성된 기준 원화 한 장부터** 만들고, 실제 독립 움직임 파츠를 그 원화에서 추출·보완해 각각 **RGBA 투명 PNG**로 저장한다. 가려져 있던 피부·목·눈·관절은 새로 그린다. 정면 기준 캐릭터의 원점과 동일한 캔버스·배율에 파츠를 놓고 파츠 밖은 투명으로 비운다.
- **상반신 신체 ZIP일 때만** 실제 프레임에 보이는 머리·목·상체와 팔/손을 그린다. 프레임 밖 팔/손·하체를 자동 요구하지 않는다. 전신 신체 ZIP일 때만 골반·다리·발을 포함한다. 헤어/의상/소품 ZIP에서는 피부·눈·팔·손을 새로 그리지 않는다.
- 눈/코/입 등은 신체 안에 포함한다. 헤어·옷·액세서리를 신체와 함께 세트로 출력하지 않는다.
- 실제 생성된 개별 PNG의 상대 경로를 뒤쪽→앞쪽 순으로 layer_order.txt에 한 줄씩 기록한다. 시트를 생성 중 사용해도 최종 단독 파일을 필수로 작성한다.
- previews/composite_preview.png 또는 previews/overlay_preview.png는 **실제 생성된 파츠를 마지막에 합성한 결과**다.
- 이미지 AI가 Cubism/Inochi Creator PSD 가져오기·메시 변형·키폼·리깅 작업을 했다고 주장하지 않는다.

- **전신 신체 ZIP은 프로젝트 기준 정확히 6등신**, 상반신 신체 ZIP은 그 두상·어깨 상대 비율과 큰 애니풍 눈을 참고하여 **상반신 원화부터 직접 제작**한다. 상반신 가이드 때문에 실제 보이지 않는 전신 신체나 전신 참고 그림을 새로 그리지 않는다. 바스트업은 별도 바스트업 방송 프레임 조건을 따르며 전신을 크롭하지 않는다. 헤어·의상·소품은 기준 신체 원점만 참조한다.


## [결과 2D ZIP 필수 구조 게이트 — 2026-10-13]
- 실제 독립 파츠 PNG가 최종 완성된 뒤 `layer_order.txt`를 누락·중복 없이 파일명 대소문자까지 동일하게 유지한다. `isolated_parts/`의 모든 PNG만 정확히 한 번씩 뒤→앞 순서로 기록하며, 마스터·참고·합성 이미지는 기록하지 않는다.
- 최종 출력은 같은 ZIP 루트 또는 최상위 폴더 하나 아래의 `outputs/master.png`, `isolated_parts/<part_id>.png`, `layer_order.txt`여야 한다. 경로 접두·폴더 중첩/혼합 금지. 단순 이미지 ZIP에 `manifest.json` 자동생성 금지.
- 지시 ZIP의 `04_OUTPUT_FILES.md`에는 실행 가능한 Python 검증 코드가 내장되어 있다. 이미지를 생성하는 AI는 **압축 완료 후 그 실제 ZIP을 검사**하여 PASS가 확인되기 전에는 납품하지 않는다. 테스트 불가를 성공이라고 주장하지 않는다. 알파/캔버스와 원화 품질은 별도 점검한다.
- 파츠 변화가 있으면 실제 파일과 순서를 함께 바꾼다. 임의 정렬이나 비어 있는 가짜 PNG로 검사기를 속이지 않는다.
## [BUSTUP_COMPLETE_BODY_FINAL_PSD_V4]
완성된 방송용 바스트업은 큰 얼굴·눈을 화면의 중심에 두고 상복부·양어깨·양팔·양손을 자연스럽게 포함한다. 얼굴만 잘린 과도한 크롭, 얼굴이 작아지는 팔 벌림, 회색 도형 프록시는 금지.
사용자가 요구한 고유 애니풍 얼굴형과 큰 눈·좌우 홍채 정합을 유지한다. 턱 뒤 목 언더페인트, 양어깨·상완·전완·양손·복부를 실제 일러스트로 그린다. 귀·입·코는 간결한 애니풍으로 유지하고 하나의 U형 턱으로 고정하지 않는다.
회색 단색 몸통, 프록시 도형, 끊긴 목, 누락된 팔/손, 짧은 상체는 최종 FAIL. 완성 원화→파츠 분리 순서. 최종 ZIP은 실제 다층 PSD·투명 파츠 PNG·알파 마스크·원본 입력·미리보기·레이어 좌표·분리/검증 JSON·Cubism 안내 필수. 중간 PNG 검사 통과만으로 납품 성공 주장 금지.
High quality finished anime VTuber upper-body BODY illustration down to the abdomen with natural neck, both shoulders, upper arms, forearms and hands, individual face and aligned irises, separate minimal neutral modesty-cover overlay, NO attached clothing. No gray polygon torso, no missing hands, no head-only crop, no fake PSD.
