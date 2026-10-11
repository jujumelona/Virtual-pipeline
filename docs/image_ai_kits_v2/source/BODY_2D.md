# 신체만 — 고급 파츠를 처음부터 직접 따로 생성 (Live2D/Inochi2D)

**신체 범위:** 얼굴·눈·눈썹·코·입·귀·목·몸통·양팔·손, 전신이면 골반·양다리·발. 사용자에게 헤어/의상/액세서리를 함께 제공하는 세트가 아니다.

**불투명 속옷:** 캐릭터를 나체로 묘사하지 않고 선정적이지 않은 불투명 기본 속옷을 입힌다. 이는 그림 AI의 노출 문제를 피하려는 조건이지 속옷을 교체용 의상으로 **별도 생성·분리하라는 요구가 아니다**.

### 얼굴 베이스·눈·입 (신체 카테고리 내부 고급 파츠)

| 독립 파츠 이름 | 처음부터 그려야 할 실제 원화 |
|---|---|
| face_skin.png | 이마·양쪽 볼·턱·눈/입 아래의 피부. 눈·입을 겹쳐 그리지 않음 |
| ear_L.png / ear_R.png | 독립 움직임/가림이 있는 귀, 머리카락 아래 드러날 피부 보강 |
| nose.png | 얼굴 피부와 별도 그림인 코/코 그림자; 캐릭터 스타일에 맞춤 |
| brow_L.png / brow_R.png | 각 눈썹 |
| eye_L_white.png / eye_R_white.png | 홍채가 움직여도 드러날 전체 흰자 영역 |
| eye_L_iris.png / eye_R_iris.png | 홍채. 동공·무늬가 실제로 별도 움직이면 그 단계도 분리 |
| eye_L_pupil.png / eye_R_pupil.png | 필요 시 동공을 처음부터 독립 생성 |
| eye_L_upper_lash.png / eye_R_upper_lash.png | 눈 깜빡임용 윗속눈썹 |
| eye_L_lower_lash.png / eye_R_lower_lash.png | 별도 표정 움직임이 있는 아랫속눈썹 |
| eye_L_corner.png / eye_R_corner.png | 눈꼬리 구조가 실제로 독립 변형할 때 추가 |
| eye_L_lid.png / eye_R_lid.png | 눈꺼풀 피부가 움직이며 새로 보일 때 |
| eye_L_highlight.png / eye_R_highlight.png | 별도 조절될 경우만 하이라이트 |
| mouth_upper.png / mouth_lower.png | 위/아래 입술 및 경계 피부 |
| mouth_inside.png | 크고 온전히 그려진 입안. 닫으면 입술 아래로 가려짐 |
| mouth_tongue.png / mouth_upper_teeth.png | 실제 입 열림·표정에서 필요한 경우에만 독립 원화 |

### 몸통·관절 (신체 내부)

| 독립 파츠 이름 | 제작 조건 |
|---|---|
| neck.png | 턱 아래에서 고개를 돌려도 끊기지 않도록 숨은 목 부분 충분히 |
| torso.png | 어깨와 팔 아래 몸통. **불투명 기본 속옷 착용 상태**를 포함 |
| arm_L_upper.png / arm_R_upper.png | 어깨·팔꿈치 연결부 겹침을 그려 둠 |
| arm_L_forearm.png / arm_R_forearm.png | 팔꿈치·손목 연장과 손목 접합 고려 |
| hand_L.png / hand_R.png | 실제 손가락 형태; 독립 손가락 포즈가 필요할 때만 세분화 |
| pelvis.png / thigh_L.png / thigh_R.png | **전신에서만**, 골반/양 허벅지 |
| shin_L.png / shin_R.png / foot_L.png / foot_R.png | **전신에서만**, 무릎·발목·발 부분 |

**중요:** 위 항목은 고급 그림 분리를 위한 세부 지도. 모두 강제 고정 PNG 수가 아니다. 각 부위가 다른 움직임·앞뒤 가림·표정·표시 전환을 갖는다면 **그 순간 개별 이미지로 생성**한다. 실제 움직임이 같은 머리카락 없는 피부 무늬를 불필요하게 조각내지 않는다.

### 실제 생성 순서

베이스 배치 가이드(완성 원화가 아님) → 얼굴 피부·목·몸통·어깨·팔·전신 하체 → **눈 흰자/홍채/동공/속눈썹/눈꺼풀·눈썹과 코·입술/입안/혀**를 각각 직접 원화로 생성 → 모든 실제 PNG를 원래 위치에 놓고 **마지막에 합성**.

완성 캐릭터 그림을 먼저 만든 뒤 눈·입을 자동으로 분리하는 흐름은 금지한다.
