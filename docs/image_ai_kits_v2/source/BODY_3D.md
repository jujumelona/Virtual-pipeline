# 3D 신체만 — 고급 다각도 신체·눈·코·입 참조를 따로 생성

**이미지 생성 AI가 작성하는 것은 참조 원화 이미지**다. 실제 3D 모델, 메쉬, VRM, FBX, GLB, 뼈대, 리깅/텍스처 페인팅/동작 테스트는 요청하지 않는다.

## 불투명한 기본 속옷 착용 신체

나체 그림이 아니라 **선정적이지 않은 불투명 기본 속옷을 입은 전신 캐릭터**로 제작한다. 속옷을 교체 가능한 의상 레이어나 별도 ZIP으로 분리하지 않는다. 모든 각도에서 같은 기본 속옷과 체형을 유지한다.

## 처음부터 각각 생성할 고급 참고 이미지

- views/body_front.png, views/body_back.png, views/body_left.png, views/body_right.png: 동일 캐릭터, 같은 높이/체형, A/T pose, 정투영에 가까운 서로 다른 각도의 전신.
- details/face_front.png, details/face_three_quarter_L.png, details/face_three_quarter_R.png: 얼굴 원화와 볼·턱·귀의 볼륨 표현. 새 헤어를 만들지 않음.
- details/eyes_L_R.png: 눈매·흰자·홍채·동공·눈썹 등을 확대해 **전신 캡처를 잘라내지 않고** 상세 그림으로 새로 그린 이미지.
- details/nose.png, details/mouth_open_closed.png, details/ears_L_R.png: 코의 윤곽과 입 개폐·치아·혀가 실제로 필요한 모습의 독립 참조.
- details/hands_front_back.png, details/hands_palm.png, details/feet.png: 손/손가락과 발을 자세히 설명하는 참조 그림.
- previews/turnaround_sheet.png: **실제로 위에서 생성한 정·후·좌·우 그림들을 마지막에 배열**한 4면도.

서로 다른 각도에 같은 피부색, 얼굴 비율, 손가락, 속옷, 체형을 유지한다. 완성 정면을 기계적으로 미러링해서 실제 좌우 측면 그림이라고 제출하지 않는다.
