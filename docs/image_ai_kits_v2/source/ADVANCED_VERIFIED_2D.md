# 2D 원화 고급 기법 — 공식 기능에서 역산한 그림 요구

**읽는 대상: 이미지 생성 AI.** 모든 "기능"은 나중 모델링 엔진의 가능성일 뿐, 이 ZIP에서는 **완성 기준 원화를 먼저 그리고 해당 움직임·가림 단위로 분리한 뒤 숨은 면을 새로 그리는 것만** 한다. PSD/리깅·키폼·애니메이션·테스트를 수행하지 않는다.

## 공식 Live2D 근거 → 이미지 작업에 적용할 그림 규칙

1. **눈: 흰자·홍채·윗/아랫속눈썹·눈꼬리.** 홍채가 이동할 전체 범위의 흰자를 그린다. 눈꼬리의 튀어나온 속눈썹은 별도로 움직여야 할 때만 분리. 눈꺼풀 피부는 감을 때 노출되는 영역을 채운다. 별도 동공/눈 반짝임/홍채 음영은 각기 다른 움직임·색 변화가 필요할 때만 별도 PNG. 눈 흰자가 홍채의 마스킹에 쓰일 수 있도록 형태를 온전하게 그린다. [공식 일러스트 가공](https://docs.live2d.com/en/cubism-editor-tutorials/psd/) / [클리핑](https://docs.live2d.com/en/cubism-editor-manual/clipping-mask/)
2. **입: 위·아래 입선과 입안.** 입안은 넉넉하게 그림을 그리되 입술·입가의 피부색 채움으로 닫힐 때 완전히 가려지게 한다. 공식 튜토리얼은 입에서 클리핑만으로 모든 가림을 해결하면 부하/경계/수정 부담이 생길 수 있다고 설명한다. **윗니·아랫니·혀·목구멍 그림**은 실제 표정·발음에 보이는 경우에만 추가. [공식](https://docs.live2d.com/en/cubism-editor-tutorials/psd/)
3. **얼굴 윤곽·귀·목.** 앞머리 아래 이마/눈가/볼을 실제로 그린다. 귀는 회전·표정에서 별도 이동할 때 독립. 목은 고개가 움직일 때 잘리지 않도록 턱 아래보다 충분히 위까지 연장. [공식](https://docs.live2d.com/en/cubism-editor-tutorials/psd/)
4. **헤어.** 앞·옆·뒤, 실제 흔들릴 아호게·트윈테일·옆머리 묶음만 독립. 후두부와 머리뿌리, 숨은 가닥의 안쪽을 미리 그린다. **한 가닥이 길게 휘는 것 자체는 여러 PNG로 강제 분할할 이유가 없음** — Live2D Skinning은 하나의 긴 ArtMesh도 연속적으로 휘게 만든다. 이미지는 하나의 온전한 가닥으로 그릴 수 있다. [공식 소재 분리](https://docs.live2d.com/en/cubism-editor-tutorials/psd/) / [Skinning](https://docs.live2d.com/en/cubism-editor-manual/skinning/)
5. **팔·다리·의상.** 어깨/팔꿈치/손목·허벅지/무릎/발목에 겹침 여유; 목/팔 아래에 가려진 몸통/옷 안감. 소매·깃·리본·프릴이 별도 흔들리는 경우만 부품 이미지 분리. 장식이 옷에 붙어 있으면 **의상 내부 부품**, 별도 액세서리 세트 아님. [공식](https://docs.live2d.com/en/cubism-editor-tutorials/psd/)
6. **그림자·반사광·별도 라인.** 별도 표시/깜빡임·깊이 차이가 있을 때만 독립 생성. 움직임이 같은 고정 무늬·인쇄 문양은 본래 물체에 포함. Cubism의 Clipping/Blend Mode는 **후속 모델링 기능**이므로 이미지 AI에 작동 설정을 요청하지 않는다. [Blend modes](https://docs.live2d.com/en/cubism-editor-manual/blend-mode/)

## 공식 모델링 기능은 별도 PNG 생성 의무와 다름

- Cubism **Glue**는 겹친 ArtMesh 정점을 붙인다. 원화 단계에서는 잘리는 관절·원단 연결부를 겹쳐 그리는 것이 해야 할 일. [Glue](https://docs.live2d.com/en/cubism-editor-manual/glue/)
- **Warp/Rotation Deformer / Blend Shape**로 기존 파츠 변형을 만들 수 있다. "표정 9장"이나 "회전 프레임 9장"을 반드시 그릴 필요는 없다. [Deformers](https://docs.live2d.com/en/cubism-editor-manual/deformer/) / [Blend Shape](https://docs.live2d.com/en/cubism-editor-manual/blend-shape/)
- Inochi Creator도 **독립 2D 파츠와 노드 계층**을 사용하므로 원화의 움직임 단위 분리는 비슷하나, Cubism 설정·리깅 데이터를 이전할 수는 없다. Inochi PSD 예제: https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html
- Inochi Part/Node의 정렬 값은 Live2D의 정렬 구현과 같다고 가정하지 않는다. **이미지 AI에게 수치 기반 엔진 정렬값을 생성시키지 말고, 뒤→앞 PNG 파일 목록만 요청**한다. [Inochi Node](https://docs.inochi2d.com/en/latest/creator/nodes/node.html)

## 비공식 현업·커뮤니티 노하우 (공식 필수 아님)

- **좌우 눈을 그룹별로 관리하는 아티스트 노하우**: https://www.reddit.com/r/Live2D/comments/15lc7ku/ . 원화 완성 이전 파츠부터 그리는 방식은 다른 제작 워크플로의 사례로, 이 ZIP에서는 사용하지 않는다.
- **고급 얼굴·눈 하이라이트·옆머리·가려진 뒤통수·독립 장식**: https://www.reddit.com/r/Live2D/comments/1140xr5/
- **입안/혀/치아의 움직임별 레이어 예**: https://www.reddit.com/r/Live2D/comments/19dey22/ / https://github.com/JayIsDed/guides/blob/main/live2d-mouth-rigging-guide-v4.md
- **가려진 옷 안감과 지퍼/관절을 초기 원화에서 모두 그리는 이유**: https://www.reddit.com/r/Live2D/comments/1myir8h
- **레이어 수 과다로 작업 비용 증가, PSD로 조립·정렬하는 별도 공정이 필요**: https://www.reddit.com/r/Live2D/comments/1kq38kk

### 중요한 선택 규칙

**필수**: 실제 요청 자산의 완성 원화를 확정한 다음, 독립 이동/가림이 필요한 구조만 분리하고 숨은 영역을 추가 작화한다.
**선택**: 그림자/반짝임/손가락/입안 치아/추가 가닥 등은 해당 캐릭터 디자인과 독립 동작이 요구될 때만 추가.
**금지**: 단순 파일 수 늘리기, 파츠 수 고정, 마스터에서 잘라낸 조각만 내고 가린 부분을 보완하지 않기, 이미지 생성 AI에게 실제 리깅이나 동작 테스트를 요구하기.
