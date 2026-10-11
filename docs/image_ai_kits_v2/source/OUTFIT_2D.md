# 의상만 — 요청받은 의상의 고급 구성 파츠를 처음부터 생성

옷 종류를 묻거나 사용자의 설명(원피스/재킷/셔츠/교복/드레스 등)에 따른다. **옷 한 벌의 실제 구조만** 그린다. 몸·헤어·별도 귀걸이/안경 세트는 생성하지 않는다.

| 파츠 예 | 별도 생성 기준 |
|---|---|
| outfit_front.png / outfit_back.png | 앞·뒤 옷감이 깊이가 다른 경우, 팔/목 아래 가린 안감 보완 |
| sleeve_L_upper.png / sleeve_R_upper.png | 어깨부터 팔꿈치까지 별도 움직일 소매 |
| sleeve_L_lower.png / sleeve_R_lower.png | 팔꿈치/손목에서 실제 별도 움직이는 구조면 분리 |
| collar_L.png / collar_R.png / hood.png | 옷깃/후드가 다른 깊이·독립 움직임이면 분리 |
| frill_01.png / outfit_ribbon.png | **옷에 부착된** 프릴·리본: 액세서리 ZIP이 아닌 **의상 내부**의 해당 부품 |
| skirt_front.png / skirt_back.png / pants_L.png / pants_R.png | **전신이고 실제 있는 하의만** 제작. 없는 치마/바지를 상상해서 추가하지 않음 |
| belt.png / shoe_L.png / shoe_R.png | 그 의상에 실제 포함될 때만 |

옷의 고정 문양, 자수, 인쇄는 다른 움직임이 없으면 옷감 파츠에 남긴다. 프릴·리본/카디건 안쪽처럼 독립 움직임/깊이가 있으면 **처음부터 별도 이미지로 그린다**. 기준 몸의 크기·원점과 맞추며 **신체 픽셀을 의상 파츠에 섞지 않는다**.
