# Live2D 원화·독립 파츠 대형 AI 제작 문서

**2026-10-11 / Cubism FREE·PRO / GPT·Gemini 등 이미지 및 ZIP을 실제로 생성하는 환경**

이 디렉터리의 문서들은 외부 대형 이미지 AI로 **마스터 원화 + 실제 분리 파츠 PNG + manifest + ZIP**을 만들게 하는 작업 지시서다. 원화만 잘라 See-through/SAM이 임의로 조각낸 결과가 맞다고 가정하지 않는다. 현재 Live2D가 공식적으로 추천한 AI 이미지 8장, 파츠 24개/60개라는 고정값은 없다.

## 전달 및 작업 순서

1. 사용자가 캐릭터 디자인(헤어, 의상, 얼굴, 상반신/전신)을 제공한다.
2. 외부 대형 AI에 이 README와 **LARGE_AI_EXECUTION_INSTRUCTIONS.md, OFFICIAL_REFERENCES.md, PARTS_AND_ROTATION_SPEC.md, manifest.template.json**을 모두 첨부하고 실제 이미지 생성/파일 저장 기능이 있는지 확인한다.
3. 완성 원화 outputs/master.png 한 장을 **먼저 실제 생성**하고 캐릭터 기준으로 확정한다.
4. 모든 이후 이미지 생성 요청에 master PNG 자체를 이미지 참조로 입력한다. 움직임별 파츠 ID마다 isolated_parts/{part_id}.png를 **각각 독립 PNG**로 만든다.
5. 작은 부위는 시트로 묶어서 생성해도 되지만, 시트 내부 파츠별 겹치지 않는 사각형 범위, 원래 캔버스 위치, 실제 분리된 PNG를 납품해야 한다. 하나의 시트는 여러 ArtMesh가 아니다.
6. 파일 존재/투명도/좌표/디자인의 확인된 사실과 Cubism에서 검증하지 않은 내용을 구분한 quality_review.md를 작성한다.
7. **진짜 PNG와 manifest 및 문서를 ZIP에 포함**시킨다. 문서 파일만 제공하고 이미지까지 생성했다고 말하지 않는다.

## 원화 분리의 근거

공식 Live2D는 모델의 움직임에 따라 머리(앞/옆/뒤, 좌우 가닥), 눈(좌우 속눈썹/흰자/홍채), 입(상하 입술과 입 안), 얼굴/귀/목, 몸통, 좌우 상완/전완/손 등을 소재로 분리하는 예제를 제공한다. 크게 움직이거나 다른 부위의 움직임으로 드러나는 부분은 가려진 영역까지 그린다. 실제 파츠 개수는 캐릭터별로 달라진다.

## 회전과 그림을 구분한다

공식 ParamAngleX/Y/Z의 표준은 **-30, 0, +30**. X -45~+45 등으로 넓힐 수 있다는 공식 예시는 **별도 모델링으로 뒷받침해야 한다**. X/Y 3×3 키폼은 9장의 AI 입력 이미지를 의미하지 않는다. 이미지 AI는 머리·귀·목·눈·입·의상 가림 영역의 충분한 원화 재료를 만들고, 키폼/디포머/메시/가림 테스트는 후속 Cubism/PSD2Live에서 진행한다. 완전 측면 ±90 구현을 자동 보장하지 않는다.

## FREE와 PSD의 공식 조건

Cubism FREE: **ArtMesh ≤100 / Parameter ≤30 / Deformer ≤50 / 텍스처 아틀라스 2048px 한 장 / Parts 폴더 ≤30**. 그림 생산 단계의 파일 8장 한도라는 의미가 아니다. Cubism 가져오기 PSD는 **RGB / 채널당 8비트 / sRGB 권장 / 파츠별 선화·채색·효과 병합 / PSD 레이어 명 중복 주의**.

## 실제 저장소 연결 범위

현재 기존 프롬프트 ZIP에서 한 장의 master 이미지를 요구하는 기능은 유지한다. 이번 문서는 **외부 AI가 다중 독립 파츠 ZIP을 실제 생성하기 위한 추가 작업 계약**이다. 아직 프로젝트 런타임에 다중 ZIP→PSD importer가 없으므로, 제출한 ZIP이 즉시 자동 리깅되는 것처럼 주장하지 않는다.

- [공식 일러스트 분리 예제/모모세 히요리 PSD 다운로드 안내](https://docs.live2d.com/en/cubism-editor-tutorials/psd/)
- [공식 소재 분리](https://docs.live2d.com/en/cubism-editor-manual/divide-the-material/)
- [공식 FREE/PRO 제한](https://www.live2d.com/en/cubism/comparison/)

## 현재 Colab v8와의 실제 입력 연결

- `③ Live2D 입력`: `master_image`(기존 한 장 See-through/SAM 분리) 또는 `ai_asset_zip`(대형 AI가 그린 독립 파츠 ZIP)을 선택한다.
- `ai_asset_zip`을 선택했다면 `⑦`에서 원화 자동 분리 모델 준비를 생략하고 PSD/PSD2Live 설치만 한다. `⑧`에서 ZIP 하나를 올리고, `⑨`에서 각 `isolated_parts/*.png`를 manifest의 `draw_order`/`placement`에 따라 실제 RGB8 PSD로 만든 뒤 **See-through/SAM 없이** PSD2Live로 전달한다.
- 실제 ZIP 내부 파일명은 `outputs/master.png`, `manifest.json`, `isolated_parts/<part_id>.png`. 각 파츠 `draw_order`는 필수이며 템플릿의 `null`을 사용하면 **명확한 오류**가 난다.
- 이전 이미지 한 장 경로는 그대로 지원한다. 아직 시각적 파츠 퀄리티나 리깅 회전 품질을 자동 인증할 수는 없다.
