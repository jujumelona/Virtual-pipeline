# 대형 이미지 AI 최종 납품 폴더 규격

최종 `Live2D_Character_Artwork.zip`은 아래처럼 실제 PNG 파일이 든 ZIP입니다.

```text
Live2D_Character_Artwork/
  outputs/
    master.png
  isolated_parts/
    face_skin.png
    hair_back.png
    hair_side_L.png
    hair_side_R.png
    hair_front.png
    brow_L.png
    brow_R.png
    eye_L_white.png
    eye_L_iris.png
    eye_L_lash.png
    eye_R_white.png
    eye_R_iris.png
    eye_R_lash.png
    mouth_inside.png
    mouth_upper.png
    mouth_lower.png
    neck.png
    torso.png
    arm_L_upper.png
    arm_L_forearm.png
    hand_L.png
    arm_R_upper.png
    arm_R_forearm.png
    hand_R.png
    ... 필요한 실제 디자인 파츠만 추가
  layer_order.txt
  reference_views/              # 선택: 동일 인물 좌우 3/4 그림
    head_three_quarter_L.png
    head_three_quarter_R.png
```

- `master.png`: RGB 또는 RGBA 기준 원화.
- `isolated_parts/*.png`: **각각 독립적인 RGBA 투명 8비트 PNG**, 다른 신체 부위와 섞지 않음.
- **캔버스 규칙**: 모든 독립 파츠 PNG는 `master.png`와 같은 크기, 같은 원점. 그림의 파츠가 기준 캐릭터에서 실제 놓인 곳에 위치하고 바깥 영역은 투명. **좌표 숫자·rect JSON을 추측해 작성할 필요 없음**.
- `layer_order.txt`: 뒤쪽→앞쪽으로 `isolated_parts/hair_back.png` 같은 **상대 경로를 한 줄씩** 기록. 모든 독립 PNG를 누락/중복 없이 정확히 한 번씩 기입.
- 실제 해당 부위가 없는 캐릭터면 그 파츠 파일은 생략 가능. 입안·눈·목·팔 등 움직임에 필요한 핵심 부위는 빠뜨리지 않도록 한다.
- 이미지 작업 결과 ZIP **하나만** 납품. 원본 작업 지시서 ZIP이나 공식 그림의 무단 복사본을 내부에 다시 동봉할 필요 없음.
- `manifest.json`, `draw_order` 수치, 좌표 위치 JSON, PSD, .moc3, Cubism 로그, 자동 성공/실패 보고서, 품질 인증 파일은 **요구하지 않음**.

`layer_order.txt` 예시(정답 강제 아님 — 실제 캐릭터에 맞게 나열):

```text
isolated_parts/hair_back.png
isolated_parts/neck.png
isolated_parts/torso.png
isolated_parts/face_skin.png
isolated_parts/eye_L_white.png
isolated_parts/eye_L_iris.png
isolated_parts/eye_L_lash.png
isolated_parts/hair_front.png
```
