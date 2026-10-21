# 고품질 공개 Live2D 제작 경로 및 검증 현황

기준: 2026-10-22. 이 문서는 실제 커밋된 실행 경로를 설명하며 상업용 고급 모델 완성을 보증하지 않습니다.

## 1. 독립 원화 파츠 손실 방지 (구현됨)

기존 FACE / OUTFIT / HAIR / ACCESSORY의 완성 PNG를 한 장으로 합치고 See-through로 다시 분해하면 숨은 면과 실제 눈·입 파츠를 잃을 수 있습니다.

이제 각 원화 ZIP에 다음을 제공하면 원본 파츠를 그대로 PSD로 조립합니다.

- outputs/master.png: 해당 자산의 중립 완성 원화
- part_art/face.skin.png, part_art/eye.left.white.png 등: 전체 캔버스 크기의 실제 RGBA 파츠
- part_art/mouth.closed.png, part_art/mouth.open.png: 존재할 경우 입 열림·닫힘 원본
- part_art/_order.txt: 맨 위 레이어부터 ZIP 내부 PNG 경로를 한 줄씩 나열

모든 자산의 ZIP에 독립 파츠가 있으면 Colab에서 GPU See-through를 생략하고 원본 레이어를 보존합니다. 일부 자산만 보유한 경우에는 작업을 중단해 원래 그린 파츠를 버리지 않습니다.

원본 파츠로 각 자산의 마스터 이미지가 정확히 재구성되는지 흰색·검은색 배경에서 확인합니다. 좌표 보정은 공통 앵커에 대한 평행이동만 허용합니다. mouth.open 및 eye.closed 대체 원화는 중립 PSD에서 보이지 않는 숨김 레이어로 유지합니다. 이 파일들이 실제 애니메이션 키폼에 연결되는지는 네이티브 검증이 필요합니다.

## 2. PSD2Live v3.6.0 (새 선택형 백엔드)

Colab RIGGING 옵션:
- artwork_only: PSD까지만 생성
- auto: 고정 v3.3.1 공식/레거시 변환 경로
- auto_repair: v3.3.1 네이티브 포즈 기준 제한된 강도 조정
- modern: **별도 체크아웃한 PSD2Live v3.6.0 공식 Gradle CLI**로 원본 PSD 자동 리깅

modern은 v3.3.1 전용 vtsRig Gradle 초기화 어댑터를 사용하지 않고 상위 프로젝트의 공식 run --args 경로를 사용합니다. 저장소 버전 v3.6.0 태그, JDK 21 이상, 출력 MOC3/CMO3 참조, FREE 아틀라스 예산을 검사합니다. 기본 설정을 강제로 modern으로 바꾸지 않았으며, 실제 Colab GPU·편집기 통합 성능은 아직 인증되지 않았습니다.

환경변수 VTS_PSD2LIVE_MODERN_HOME으로 원본과 별도 위치의 정확한 v3.6.0 소스 체크아웃을 지정할 수 있습니다. 두 PSD2Live 백엔드는 GPL-3.0 외부 프로그램이고 이 저장소에 코드를 벤더링하지 않습니다.

## 3. 실제 텍스처 구조 기반 메쉬 편집

최신 PSD2Live의 layer_mesh_structure_preview 및 layer_mesh_structure MCP 작업을 연결했습니다. 이미지에 그려진 주름·명암선·패턴에 맞춰 메쉬를 재구성하고 기존 키폼·가중치·Glue를 보전하는 기능입니다.

실제 편집기에서 검사한 mesh:<ID> 핸들만 허용합니다. 편집할 프로젝트는 명시적으로 열고 별도 .psd2live 사본을 저장합니다. 텍스처 선이 검출되지 않으면 수정한 척하지 않고 중단합니다. 실제 편집 완료 후 내보낸 MOC3는 네이티브 포즈의 지오메트리·눈·입·움직임 검사를 통과해야 합니다.

실행 예시:

    python -m tools.vts_modern_mesh_refiner --psd2live-source /path/to/psd2live-v3.6.0 --source-project /path/to/model.psd2live --mesh-targets /path/to/mesh_ids.json --output /path/to/empty-output

mesh_ids.json은 실제 편집기에서 얻은 [ "mesh:actualId1", "mesh:actualId2" ] 형식입니다. 이름을 추측하면 안 됩니다.

별도로 tools.vts_reference_keyform_author는 실제 Warp ID와 ±45° 원화를 이용한 키폼 이동을 지원하며, --source-project로 편집 대상 문서를 지정합니다.

## 4. 비전·네이티브 렌더 기반 정량 평가

tools.vts_native_visual_benchmark는 좌우 45° 원화와 실제 Cubism MOC3의 동일 캔버스 PNG들을 비교합니다. 투명 알파 실루엣 IoU, 서로 겹치는 영역의 색상 오차, 불투명도 오차, 그림의 무게중심 차이를 측정합니다. 이전 모델을 제공하면 명백한 픽셀 퇴화를 거부합니다. 불투명 배경을 인위적으로 분리해 가짜 결과를 만들지는 않습니다.

    python -m tools.vts_native_visual_benchmark --reference-dir /path/to/reference_views --native-dir /path/to/new/native_poses --previous-native-dir /path/to/old/native_poses --output /path/to/review

tools.vts_ai_native_feedback_loop의 --require-pixel-improvement 선택 옵션을 사용하면 실제 수정 반복에서 해당 수치 검사를 의무화할 수 있습니다.

단, 픽셀 일치 개선은 그림의 미적 수준이나 캐릭터 동일성이 검증됐다는 뜻은 아닙니다. 최종 고품질 평가는 눈·입·목·머리카락·의상·감정 표정의 실제 움직임도 확인해야 합니다.

## 5. 재현 가능한 고품질 공개 자료

상위 저장소 https://github.com/tsunehimatoi/psd2live-examples 에는 실제 PSD, 편집 .psd2live 프로젝트, MOC3 및 제작 경험이 공개돼 있습니다. 개별 조건 확인 시 기본 CC0-1.0 예제를 사용할 수 있습니다.

SHA-256을 고정하고 검사하는 다운로드 도구:

    python -m tools.vts_open_quality_cases --case kirishima-mio --output /path/to/empty-dir

선택:
- ds: 약 9MB, 동작·물리 예시
- kirishima-mio: 약 86MB, 전신 원화/목·얼굴 정합 및 파츠 재작화 경험
- star_lan: 약 97MB, 관절·다중 텍스처
- hiakari-inori: 약 660MB, 복잡한 소매·치마·꼬리·장식 물리, AI 원화 제작

다운로드 SHA-256/용량과 ZIP 파일 안전성을 검증하며, 실제 네이티브 파일이 존재하는지 확인합니다. 이 사례를 로딩했다고 방송 품질 합격이라고 주장하지 않습니다.

Live2D 공식 Hiyori, Kei, Miara 등 샘플은 메쉬·표정·물리 구조 참고용으로 좋지만 CC0가 아닙니다. 공식 이용 조건을 준수해야 합니다.

## 6. 최신 PSD2Live 편집 프로젝트 자동 생성

PSD2Live v3.6 CLI는 네이티브 MOC3·CMO3를 내보내지만, 복잡한 MCP 메쉬 보정을 위해 별도의 **실제 편집 가능한 .psd2live 프로젝트**도 필요합니다. 다음 새 경로는 v3.6 headless MCP를 별도 격리 저장소에서 실행합니다.

    python -m tools.vts_modern_editable_project --psd /path/to/layered.psd --source /path/to/psd2live-v3.6.0 --output /path/to/fresh-editable-dir

실제 프로젝트를 가져온 뒤 rig_generate를 호출하고, 프로젝트를 디스크에 저장한 뒤 파일이 존재하는지 확인합니다. MCP 서버가 죽거나 실행이 중단되면 원본 프로젝트를 성공적으로 편집했다고 기록하지 않습니다. 이것을 다시 --source-project로 넘겨 Warp 또는 메쉬 MCP 편집을 이어갈 수 있습니다.

공개 CC0 ds PSD로 v3.6 CLI 실제 .moc3 + .cmo3가 성공한 증거: https://github.com/jujumelona/Virtual-pipeline/actions/runs/39651136521 . **이 실행은 headless 편집 프로젝트 생성 성공의 증거는 아닙니다.** 그 경로는 별도 통합 CI에서 검증합니다.

## 7. 로컬 비전 AI 품질 진단

아래 명령으로 실제 MOC3 native_pose_report.json + yaw_left_45.png / yaw_right_45.png와 원화 head_three_quarter_L.png / R.png를 로컬 이미지 인식 모델에 넣어 부위별 결함을 진단합니다.

    python -m tools.vts_local_visual_critique --reference-dir /path/to/reference_views --native-dir /path/to/native_poses --model your-local-vlm --output /path/to/visual-review

이미지는 127.0.0.1 또는 localhost OpenAI 호환 /v1/chat/completions 엔드포인트에만 전송합니다. 진단 범주는 눈·입·목·머리카락·의상·가림·선화·얼굴 정체성입니다. 유효한 JSON만 받아 수정 도구 후보를 만들며 모델 제안 코드를 실행하지 않습니다. 비전 모델의 진단만으로 미적 완성도를 인증하지 않습니다.

## 현재 미완료인 고급 제작 요건

1. 실제 복잡한 한 캐릭터에 대해 파츠 생성·가림면 재작화·독립 의상 결합까지 완전 자동으로 고품질 완료
2. v3.6.0 실제 모델 생성 → 실제 MCP 프로젝트 열기 → 메쉬 변경 → VTube Studio 실제 트래킹까지 한 번에 실행하는 실측
3. 완전한 90° 측면 파츠·텍스처·마스크 및 측면 고유 키폼 자동 제작
4. 공식 최고급 샘플과 동등한 표정과 물리의 지속적인 미적 품질 입증
5. 별도 3D 경로의 완전 자동 고품질 VRM 헤어·의상 장착 및 실시간 품질 인증

CI에서 100여 건의 단위·구조 테스트를 통과하더라도 이 다섯 가지가 자동 해결됐다는 뜻은 아닙니다.
