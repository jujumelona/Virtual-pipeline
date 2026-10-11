# GPT/Gemini 대형 이미지 AI용 실제 작업 지시서

**반드시 사용자 캐릭터 브리프, 이 디렉터리의 README, OFFICIAL_REFERENCES, PARTS_AND_ROTATION_SPEC와 manifest.template.json을 함께 제공하라.** 이 지시는 이미지 생성/파일 저장/ZIP 기능을 실제로 가진 환경에서만 실행 가능하다.

당신의 작업은 **프롬프트 몇 문장이 아니라 실제 PNG/manifest/ZIP 자산을 납품**하는 것이다.

## 수행 순서

1. 사용자의 얼굴, 헤어, 의상, 액세서리, 신체 범위를 확인한다. 없는 요구사항을 지어내어 강제하지 않는다.
2. OFFICIAL_REFERENCES.md의 공식 문서를 읽을 수 있으면 확인한다. 링크 접근 권한이 없다면 제공된 문서 요약을 쓰고 읽었다고 주장하지 않는다. 실제 공식 예제 이미지를 참고하려면 사용자가 라이선스에 맞게 받은 파일을 첨부하도록 한다.
3. 완성 정면 원화 **outputs/master.png**를 이미지 생성 도구로 실제 만든다. 이후 모든 호출에 이 PNG **파일 자체**를 reference image로 붙인다.
4. PARTS_AND_ROTATION_SPEC.md의 대상 신체 부위 ID 목록을 바탕으로 **각 ID별 독립 PNG**를 만든다. 그룹 작업은 머리, 얼굴/목, 눈/눈썹, 입, 몸통/의상, 왼팔, 오른팔, 전신이면 하체, 필요한 장식으로 묶어 실행할 수 있다. 그룹 수를 공식 이미지 장수로 쓰지 않는다.
5. 작은 눈/입/장식은 시트 제작 허용. 그러나 **반드시 식별 가능한 비중첩 rect, 원본 master 좌표 및 실제 별도 파츠 PNG**를 출력한다. 하나의 그룹 PNG만 납품하고 팔 상완/전완/손을 분리했다고 보고하지 않는다.
6. 헤어뿌리/가려진 이마·귀, 목 연장, 입안, 홍채 아래 흰자, 의상 아래 몸통, 어깨/팔꿈치/손목 등을 **원화에 준비한다**. Cubism AngleX/Y 키폼을 이미지 AI가 이미 구현했다고 주장하지 않는다.
7. 실제 출력 PNG의 투명 알파 채널·이름·배치 좌표·누락 여부를 확인한다. 단색 배경은 투명 PNG가 아니다.
8. manifest.template.json의 TEMPLATE/미확인 값들을 실제 검증 결과로만 수정해서 **manifest.json**으로 저장한다. quality_review.md에 PASS / FAIL / UNKNOWN / NOT_TESTED를 기록한다.
9. **outputs/master.png, isolated_parts/*.png, manifest.json, quality_review.md, README, 공식 링크 문서를 실제 ZIP에 넣어 압축 파일 내부를 검사**한다. 실제 파일이 없으면 완료라고 말하지 않는다.

## 모든 파츠 생성 호출에 넣을 텍스트

Use the actual attached master image as the **fixed reference image**. Maintain identical character anatomy, proportions, hair colors, outfit motifs, expressive eye shape, line weight and cel-shading. Produce only the named independently movable Live2D illustrated part. Keep correct hidden extensions beneath bangs, cheek, hair roots, neck, sleeve, and limb joints so that moving layers does not open empty gaps. No additional character parts, false transparency checkerboards, unrelated features, labels baked into artwork, duplicated hands or floating fragments. Export real RGBA if supported. Preserve master canvas coordinates; if cropped, provide precise left/top placement. Do not claim an AI-generated raster is a finished Cubism ArtMesh or Angle X/Y keyform.

## 그룹별 구체 작업

- **Hair:** 앞/좌우 옆/뒤 머리, 따로 흔들리는 가닥. 실제 reference의 헤어스타일/뿌리 유지.
- **Face/neck:** 얼굴 피부 backing, 필요 시 코/귀 따로, 위로 충분히 그린 목.
- **Eyes:** 좌우 각각 속눈썹·흰자·홍채·눈썹을 별도 PNG로, 눈동자가 이동해도 완전한 흰자.
- **Mouth:** 윗입술/아랫입술/입안 따로. 닫을 때 입안이 가려지는 구조.
- **Torso:** 팔 아래 몸통·의상 연결부, 필요할 때만 리본/옷깃 분리.
- **Arms:** 왼쪽/오른쪽 각각 상완·전완·손. 긴팔은 실제 보이는 옷 구조를 그대로 보존.
- **Full body:** 사용자가 전신을 원할 때만 다리/치마/신발을 추가.

**성공 기준:** 실제 파일 유무/알파/파트 ID를 기계적으로 확인. 캐릭터 일치·회전 품질은 실제 이미지 및 모델링을 검토한 범위만 PASS. **PSD import, 회전 리깅, FREE ArtMesh 예산은 테스트 전 NOT_TESTED**.
