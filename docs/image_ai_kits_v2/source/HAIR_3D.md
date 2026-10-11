# 3D 헤어만 — 요청 헤어스타일의 다각도 상세 그림

기준 캐릭터의 두상/얼굴 이미지를 참고하여 **사용자가 지정한 헤어스타일 하나만** 만든다. 새 몸, 새 의상, 장신구 묶음을 만들지 않는다.

- views/hair_front.png, views/hair_back.png, views/hair_left.png, views/hair_right.png: 같은 헤어의 각 방향 모양·볼륨·헤어라인·가림 깊이를 새 그림으로 각각 만든다.
- details/hairline_roots.png: 이마·옆머리·뒤통수의 머리 뿌리 위치, 부위가 가려져도 연결되는 원화.
- details/hair_strands.png: 앞머리 묶음, 길게 움직이는 가닥/아호게/트윈테일/땋은 머리 등 **사용자 스타일에 실제 있는 요소만** 세부 그림으로.
- previews/turnaround_sheet.png: 위 실제 생성 이미지들을 이용해 마지막에 만드는 다각도 미리보기.

3D 도구가 헤어 메시·커브·SpringBone을 이미 구현했다고 주장하지 않는다. 이미지 AI는 형상과 구조를 설명하는 그림을 제작한다.
