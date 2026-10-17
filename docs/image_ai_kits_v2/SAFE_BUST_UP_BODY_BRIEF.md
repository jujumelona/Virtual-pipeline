# Live2D 바스트업 BODY — 안전하고 완성도 높은 원화 지침

> 이 문서는 2026-10-17 현재 `live2d_bust_up__body.zip`의 배포 교체가 완료되지 않아 임시로 제공하는 최신 BODY 원화 지침입니다. 구버전 ZIP 내용과 충돌하면 이 문서가 우선합니다.

## 제작 대상

- **성인(20세 이상)의 비성적 방송용 애니 VTuber**. 머리카락과 별도 패션 의상 및 소품을 아직 제작하지 않는 BODY 기초 모델.
- 정수리부터 상복부까지의 바스트업. 두 어깨와 양팔, 손가락 끝이 보이는 구도. 턱 아래 자연스러운 목과 어깨 접합, 큰 주황 홍채·흰자·속눈썹, 짧고 둥근 U형 얼굴.
- 얼굴·목·귀·두피·양손의 기준 피부색은 모두 `FACE_SKIN_BASE=#F2D4BE`. 변경 시 전체 시점에서 같은 색을 사용.
- 가슴·등·복부·어깨·팔은 **불투명 무광 청회색 `#526B83`의 목둘레가 뚜렷한 긴팔 제작용 보호 슈트**로 덮는다. 목선, 손목의 소맷단, 옷감의 외곽선이 그림에서 실제로 보이게 한다. 이는 BODY 생성 과정에서 사용할 간소한 보호 커버이며 별도의 OUTFIT 디자인이 아님.
- 2~3단계 셀 음영과 깔끔한 선화·눈의 표현을 갖춘 전문 애니 일러스트. 프록시 도형·사진 질감·텍스트 안내문·여러 시점 콜라주는 제출하지 않는다.

## 각도와 연결

몸통·어깨는 정면 기준 위치를 유지한다. `head_three_quarter_L/R`은 고개만 약 45° 돌아간 형태, `head_profile_L/R`은 고개만 옆으로 도는 별도 형태로 실제 얼굴·귀·코·턱의 투영이 변해야 한다. `head_pitch_up/down`에서도 턱과 목 사이, 목과 의복 목선 사이 연결을 끊지 않는다. 동일한 성인 캐릭터, 동일한 보호 슈트와 색을 모든 그림에 적용한다.

## 납품 범위: 원화와 참고 시점 12개 PNG

- `outputs/master.png`
- `reference_views/body_front.png`
- `reference_views/head_three_quarter_L.png`
- `reference_views/head_three_quarter_R.png`
- `reference_views/head_profile_L.png`
- `reference_views/head_profile_R.png`
- `reference_views/head_pitch_up.png`
- `reference_views/head_pitch_down.png`
- `reference_views/neck_underpaint.png`
- `reference_views/body_joint_overlaps.png`
- `expression_refs/mouth_closed.png`
- `expression_refs/mouth_open.png`

각 파일은 원화 전체 캔버스의 한 시점 또는 표정 참고만 포함한다. PNG 완성을 확인하고 `live2d_bust_up__body__ARTWORK.zip`에 넣는다. 생성 단계에서는 파츠 분리·PSD·MOC3·리깅을 수행했다고 주장하지 않는다. 후속 Colab에서는 실제 원화 픽셀을 검증하며, 보호 슈트 아래의 미생성 신체 픽셀이 복원되었다고 가정하지 않는다.

## 품질 검수

성인 애니 VTuber로 자연스럽게 보이는 얼굴, 일관된 주황 홍채, 맞는 손가락·어깨 비율, 각도 변화에 따른 실제 얼굴 형태, 커버의 명확한 목선·소매, 얼굴·목·손 색상 일치를 확인한다. 안전 필터가 요청을 거부하면 제한을 회피하는 지시를 추가하지 않고 의복과 인물 묘사가 명확한 요청으로 다시 작성한다.
