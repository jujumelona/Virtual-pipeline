# 3D 의상만 — 한 벌의 실제 복장을 여러 시점의 상세 그림으로 생성

사용자가 지정한 옷 유형(셔츠/원피스/재킷 등)만 그림으로 만든다. **신체·헤어·별도 액세서리 세트를 새로 생성하지 않는다**. 기준 신체를 제공받았으면 그 체형·A/T pose에 대응해 맞춘다.

- views/outfit_front.png, views/outfit_back.png, views/outfit_left.png, views/outfit_right.png: 같은 옷의 정면/후면/좌우. 실루엣·무늬·색·봉제 위치가 각도별로 정확히 이어져야 한다.
- details/garment_construction.png: 옷깃·소매·허리·치마/바지·후드·프릴·안감·고정 장식 중 실제 복장에 있는 구조만 자세히 새 그림으로 제작한다.
- details/material_color.png: 실제 의상의 원단 표면, 색상, 배색, 패턴 위치를 설명하는 참조 이미지.
- previews/turnaround_sheet.png: 독립적으로 생성한 위 시점 그림을 마지막에 배열.

옷에 붙은 리본·프릴은 **의상 범주**다. 귀걸이·안경 등 사용자가 지시하지 않은 액세서리는 만들지 않는다. 이미지 그림을 3D 스킨드 의상 메시나 착용 완료 VRM이라고 주장하지 않는다.
