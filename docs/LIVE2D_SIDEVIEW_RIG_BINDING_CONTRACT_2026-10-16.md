# 2D 머리 회전·시선·측면 참고 원화·의상 결합 계약 (2026-10-16)

## 현재 실제 실행 경로와 미구현 경계

- BODY Colab 경로: `tools/vts_multiview_runtime.py:process_completed_ai_2d_zip` -> `tools/vts_production.py:make_cubism_handoff` -> `tools/vts_psd2live.py:run_psd2live` -> 외부 PSD2Live -> 실제 MOC3 렌더 검증.
- 2D `vtuber_pipeline/two_d/keyforms.py`는 별도의 analytic/interchange 경로이며, 그 JSON은 PSD2Live의 네이티브 MOC3로 자동 가져오지 않는다. 위 파일에서 고친 규칙만으로 현재 BODY MOC3의 시각적 문제가 직접 해결됐다고 주장하면 안 된다.
- `reference_views/head_three_quarter_L.png`, `head_profile_L.png` 등은 `_check_view_members`가 **이미지 유효성**만 검사한다. `reference_angles_used_as_rig_keyforms=False`가 사실이다. 현재 PSD2Live는 **정면 PSD를 입력받아** 자체 얼굴 변형을 작성하므로, 측면 원화와 변형 키폼은 아직 직접 연결되지 않았다.
- 머리 각도는 `ParamAngleX/Y/Z`, 시선은 `ParamEyeBallX/Y`로 독립. `ParamAngleX`만 조작한 네이티브 화면에서 머리 실루엣·코·귀·양 눈 전체가 움직여야 하고 **동공 이동만으로 대체하면 불합격**.
- 머리 회전 중 의상은 몸통 루트의 움직임을 따르며 의상 패널 자체의 임의 확대/수축 금지. 소매, 리본, 옷자락에는 부착점이 고정된 상태로 독립 물리/관절 움직임만 허용.

## 추가 구현: 제한된 네이티브 3/4 키폼 AI 보정 (2026-10-22)

기존 BODY Colab에서 측면 참고 PNG를 자동 키폼으로 사용하지 않는다는 사실은 그대로다. **추가한 독립 로컬 경로**에서는 `tools/vts_ai_landmark_pairs.py`가 이미지 입력 가능한 로컬 VLM으로 원화 3/4 시점과 실제 MOC3 -30/+30 렌더의 동일 얼굴 지점을 비교하고, `tools/vts_reference_keyform_author.py`가 관찰한 차이를 PSD2Live의 실제 `warp:...` 객체에 `ParamAngleX` 키폼으로 작성한다. 데스크톱 MCP가 적용/내보내기를 성공시키고 실제 MOC3 포즈 QA를 통과한 경우에만 `reference_angles_used_as_rig_keyforms=True`를 보고한다. `tools/vts_ai_native_feedback_loop.py`는 같은 관찰-편집-렌더 루프를 제한 횟수 반복하면서 실제 랜드마크 오차의 수렴도 요구한다. 상세 실행법: [LIVE2D_NATIVE_AI_AUTHORING.md](LIVE2D_NATIVE_AI_AUTHORING.md).

**지원 범위는 ±45°(기본) 또는 명시된 ±30° 기존 Warp의 국소 이동 보정이며, 네이티브 90° 옆얼굴 ArtMesh 교체·완전 재구성 또는 모든 각도의 시각 품질 인증이 아니다.** 원본 `.psd2live`는 보존하고 별도 사본에서 편집한다. 메쉬 형태·그리기 순서·목 깊이·마스크 등 복잡한 문제는 여전히 독립적인 리깅 검증을 요구한다.

## 제작 데이터 분리 (이미지 AI ZIP과 Colab 엔진의 책임 구분)

이미지 AI ZIP은 정면 최종 마스터, 3/4·측면·가림 참고 PNG만 제작한다. 후속 Colab에서 정면 마스터로부터 분리해야 하는 의미적 부위는 눈 흰자·홍채/동공·눈꺼풀·얼굴·머리카락·귀·목·몸통·팔·손 등이다. **실제 PSD/RGBA 파츠 분리, 마스크 생성, 메시·디포머·키폼·리깅은 Colab의 See-through/후속 엔진 책임**이며 이미지 AI에 수행하도록 지시하지 않는다. 모든 참고 원화는 동일 캐릭터 디자인과 시점별 가림 관계를 유지한다.

Colab은 원화의 위치와 의미적 ID를 확인한 뒤 **기하학적 접합, ArtMesh 키폼 생성, 파라미터 연결, 렌더 검사**를 담당한다. 단순히 측면 참고 그림을 PSD의 위쪽 레이어에 올리는 것은 `ParamAngleX` 리깅이 아니다. 눈 전체를 한 장으로 합치거나, 시선 이동 시 흰자·눈꺼풀을 통째로 이동시켜서도 안 된다.

## 구현해야 할 다각도-키폼 연결 알고리즘 (현재 미구현)

1. **좌표 통일**: 정면·좌 3/4·우 3/4·측면에서 동일한 캐릭터의 안쪽 눈꼬리, 바깥 눈꼬리, 홍채 중심, 콧끝, 입 양끝, 턱, 양 귀, 목 중심, 어깨 봉제선, 소매 부착점의 이름과 일치 검증. 각 이미지의 여백·크기·시점 정규화. 신뢰도 낮은 대응점에는 자동 성공 금지.
2. **동일 역할 ID 대응**: 앞면 PSD ArtMesh의 `face`, `eye.left.white`, `eye.left.iris`, `eye.left.lid`, `hair...`와 측면 목표 원화의 동일 부위를 연결. 화면상의 왼쪽/오른쪽과 캐릭터의 왼쪽/오른쪽을 혼동하지 않도록 고정. 보이지 않는 먼쪽 눈·귀는 가림/그리기 순서 변화로 제어.
3. **공통 변형 틀**: 얼굴 전체 `Head XY` 부모, 양 눈/눈썹/코/입의 위치 디포머 자식, 홍채·동공의 `EyeBall XY` 손자 관계. 머리 윤곽/코/눈·귀의 3/4 목표 위치와 면적·가림 관계를 목표 제약으로 해 `ParamAngleX=-30,0,+30` 등 키폼을 작성. 극단적인 옆모습에 원화 교체가 필요하면 별도 측면 ArtMesh를 만들어 파라미터별 불투명도와 Draw Order/가림을 키폼에 연결하고, 두 이미지를 단순 겹쳐 늘리지 않는다.
4. **연결 규칙**: 측면 텍스처가 나타나도 정면-측면 공유 앵커(머리 중심·목·눈 영역)가 같은 트랙을 따라야 한다. 0도와 정·측면 사이에서 얼굴 파츠가 튀거나 찢어지는 키폼을 자동 승인하지 않는다. 별도 색상·원화 간 명백한 불일치는 입력 재작화 요청.
5. **의상**: Body XY/Z 부모 -> 몸통에 맞춘 앞/뒤 천 -> 어깨/팔 회전 부모 -> 소매 자식 -> 자유로운 끝단 물리. 몸통과 의상을 각각 자기 중심에서 회전시키거나, 소매 길이·목둘레를 각도에 따라 균일 확장하지 않는다. 가려진 옷 안쪽/겨드랑이 원화를 확보하고 겹침/Glue/그리기 순서를 필요 부분에만 설정.
6. **검증**: 눈동자 전용 `ParamEyeBallX` 스윕에서 눈/의상 밖의 움직임을 금지. `ParamAngleX` 스윕에서는 머리 윤곽이 실제 변화하는지 확인. `ParamBodyAngleX/Y`에서는 옷 폭·면적·목둘레·소매 부착점 보존과 배경 구멍/찢어짐을 확인. 네이티브 MOC3 캡처와 3/4 참고 원화를 동일 기준으로 비교하고 각도별 키폼·픽셀 실측 결과를 기록.

**현재 구현한 검사**: `tools/vts_pose_parameter_isolation.py`의 네이티브 프레임 비교는 눈만 움직이는 가짜 회전과 시선 조작이 몸통/옷에 새는 현상을 탐지한다. 휴리스틱 검사이므로 사람이 보는 아트 품질이나 전체 의상 체적 보존을 증명하지 않는다.

**완료 조건**: `reference_angles_used_as_rig_keyforms=True`는 실제로 측면 의미 대응점과 키폼/메시·마스크가 네이티브 MOC3 생성에 반영되고 이를 원화·MOC3 포즈로 검증한 경우에만 허용. 지금은 FALSE. 다각도 입력이 있다는 이유만으로 전체 제작 성공 표시는 금지한다.

## 공식 근거

- Live2D Cubism 표준 파라미터: https://docs.live2d.com/ko/cubism-editor-manual/standard-parameter-list/
- 파츠 분리: https://docs.live2d.com/en/cubism-editor-manual/divide-the-material/
- 부모·자식 디포머: https://docs.live2d.com/en/cubism-editor-manual/system-of-parent-child-relation/
- 워프 디포머: https://docs.live2d.com/en/cubism-editor-manual/making-and-placement-of-warp-deformer/
- 얼굴 자동 움직임: https://docs.live2d.com/en/cubism-editor-manual/face-auto-edit/ (정면 얼굴에 한정)
- 드로우 오더: https://docs.live2d.com/en/cubism-editor-manual/draworder/
- Glue: https://docs.live2d.com/en/cubism-editor-manual/glue/
- 키폼: https://docs.live2d.com/en/cubism-editor-manual/keyform-xydirection/
- PSD 불러오기: https://docs.live2d.com/en/cubism-editor-manual/psd-import/
- 외부 PSD2Live 기능: https://github.com/tsunehimatoi/psd2live/blob/master/docs/en/README.md
