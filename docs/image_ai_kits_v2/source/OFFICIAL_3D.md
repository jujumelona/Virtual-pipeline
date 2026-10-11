# 3D 캐릭터 모델용 그림 참조 — 공식 규격과 역할 분리

- VRM 공식 기능(자세·시선·표정·SpringBone): https://vrm.dev/en/vrm/vrm_features/
- VRM 1.0 Humanoid 뼈대: https://vrm.dev/en/vrm1/humanoid/
- Humanoid 3D → VRM 제작 개요: https://vrm.dev/en/vrm/how_to_make_vrm/convert_from_humanoid_model/
- SpringBone 가이드: https://vrm.dev/en/vrm1/springbone/
- Live2D 독립 원화 예시(2D 비교 자료): https://docs.live2d.com/en/cubism-editor-tutorials/psd/

VRM은 실제 3D 메시·뼈대·표정·시선·재질 등을 포함하는 규격이다. 따라서 **2D 그림/시트를 생성하는 AI에게 VRM·FBX·GLB·메시·스킨닝·본 설정·움직임 검증을 만들라고 지시하지 않는다.**

이미지 AI의 정확한 임무는 **같은 캐릭터/물건의 앞·뒤·좌·우 정투영에 가까운 시점 그림**과 필요한 얼굴·눈·코·입·손·옷/헤어/장식 세부 확대 그림을 각각 직접 그리는 것이다. 서로 다른 각도에서 신체비율·색·무늬·장식 위치를 일치시킨 뒤 미리보기 턴어라운드 시트로 합친다. 이미지를 만들었다고 실제 3D 모델이 완성된 것은 아니다.
