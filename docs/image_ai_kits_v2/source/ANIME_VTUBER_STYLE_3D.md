# 3D용 애니메이션 스타일 캐릭터 참조 그림

사용자가 별도 스타일을 요청하지 않으면 **일본 애니메이션풍 VTuber / VRoid 캐릭터 원화**를 기본으로 사용한다. 그림은 3D 메시가 아니며, 네 방향 2D 참조 그림을 만든다.

- 검정에 가까운 **선명하고 세련된 짙은 외곽선**, 너무 두꺼운 검은 벡터 테두리가 아닌 **가변 굵기/가늘어지는 테이퍼 선화**. 피부 내부는 짙은 갈색, 머리는 암색을 활용한 색선.
- **선택한 자산의 전후좌우 실루엣**과 깊이·두께를 유지한다. 신체라면 애니풍 얼굴·눈매, 헤어라면 모근·큰 가닥, 의상이라면 옷감의 구조, 장식이라면 부착점·연결부의 형상이 일치해야 한다.
- **신체 ZIP에서만** 애니풍 홍채·윤곽·코/입·눈꺼풀·어깨·팔·손발과 A/T 포즈를 직접 작화한다. 다른 자산 ZIP은 몸체를 기준선/부착 위치용으로만 참조하고 신체·얼굴·손발을 그리지 않는다.
- 해당 자산 소재에 맞는 깨끗한 2~3단계 **셀 셰이딩**을 사용한다. 피부는 신체, 머릿결은 헤어, 옷감 장력·주름은 의상, 소재 반사와 연결은 장식 ZIP에서만 직접 생성한다. 조명/색을 네 시점에서 일관되게.
- **치비/SD, 막대 인간·회색 도형 바디, 단순 SVG 템플릿** 금지(사용자가 SD/그 스타일을 요청한 경우 제외). 속옷을 입은 신체 베이스는 긴 티셔츠로 덮지 않는다.
- 헤어/의상/액세서리는 사용자가 정한 그 종류만. 다른 자산 세트를 멋대로 포함하지 않는다.

**이미지 생성 호출에 적용할 영어 프롬프트:**

> **Professional anime VTuber reference artwork of ONLY the requested asset (body OR hair OR outfit OR a single specified accessory), independently drawn front, back, left and right views, consistent silhouette and connection points, clean dark variable-weight tapered ink, 2–3 tone cel shading, high-detail original illustration; never add other asset categories or create a 3D mesh. No simplistic flat clipart.**

후속 3D 모델 메시·본·UV·리깅 결과를 이미지 AI에게 요구하지 않는다.
