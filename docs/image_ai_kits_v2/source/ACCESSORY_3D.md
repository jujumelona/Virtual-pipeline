# 3D 액세서리만 — 사용자가 지정한 물건 하나의 4면도

액세서리 종류를 사용자 지시대로 해석한다. **'머리장식'을 요구받으면 머리장식만** 만들고, 안경·귀걸이·왕관·목걸이를 덧붙여 액세서리 세트로 만들지 않는다.

- views/accessory_front.png, views/accessory_back.png, views/accessory_left.png, views/accessory_right.png: 그 물건의 형태·두께·부착 방향·재질·앞뒤 모양을 보여주는 서로 다른 시점 그림.
- details/accessory_components.png: 체인·달린 리본·매달린 보석 등 **그 한 물건 내부에서** 실제 분리해 움직일 부분이 있는 경우만 별도 상세 이미지.
- previews/turnaround_sheet.png: 앞서 만든 정·후·좌·우 그림을 마지막에 배열한 합성 미리보기.

기준 캐릭터 이미지가 제공됐을 때 실제 부착 위치와 크기를 맞춘다. 몸·머리·의상 자체를 이 ZIP의 신규 생성 대상에 추가하지 않는다. 3D 장착·물리·본·리깅은 이미지 AI의 출력 대상이 아니다.
