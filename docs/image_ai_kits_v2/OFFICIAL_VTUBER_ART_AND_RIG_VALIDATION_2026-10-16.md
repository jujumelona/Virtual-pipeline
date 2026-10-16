# 공식 Live2D / PSD2Live / Inochi2D 기준 대조 검증 — 2026-10-16

## 검증 범위

**검사 자료:** 24개 게시 ZIP에 각각 14 MD 존재하는 실제 GitHub 바이너리, 각 ZIP의 `02_ADVANCED_PARTS.md` 상세 제작 지침, `07_REVIEW_BEFORE_FINAL_ZIP.md` 실제 시각 검수 지침, 관련 Colab 런타임 및 PSD2Live 소스. **CI 수행 결과로 판정하지 않음.** 캐릭터의 실제 생성 PNG나 실제 작동하는 네이티브 모델 파일은 이 검증에 제공되지 않았음.

**결론: 원화 제작 명세의 공식 적합성과 네이티브 모델 구현 완료는 다르다.** 현재 2D ZIP의 제작 지침은 정면 원본 보존 및 가림 복원 원칙에 맞췄지만, 파츠 원화만으로 실제 90° 측면·목의 변형·Inochi2D Puppet이 자동 완성되는 것은 아니다.

## 공식 문서 기준

1. Live2D Cubism 공식 'Illustration Processing': **보이는 원화의 소재를 복사해 분리하고 이동할 때 드러나는 숨은 면을 덧그린다**. 앞·옆·뒷머리, 눈 흰자·홍채·속눈썹, 윗입술/아랫입술·입안, 목·몸통·상완·전완·손, 다리 구분. 목을 얼굴 아래에서 넉넉히 키워 **입 부근까지** 늘리는 예시. <https://docs.live2d.com/en/cubism-editor-tutorials/psd/>
2. Live2D 'Keyforms': 파츠를 분리한 다음 Angle X/Y 디포머와 매개변수별 키폼을 별도로 저작하고 대각 자세도 확인. <https://docs.live2d.com/en/cubism-editor-manual/keyform-xydirection/>
3. Live2D Standard Parameters: ParamAngleX/Y 기본 **-30~+30**, 필요시 -45~+45 등 확장 가능. 참조측면 PNG를 냈다는 이유로 90° 모델이 되지 않음. <https://docs.live2d.com/en/cubism-editor-manual/standard-parameter-list/>
4. PSD2Live PSD_LAYER_SPEC: RGB 8-bit 레이어 PSD, 진짜 분리된 눈 흰자·홍채·윗속눈썹, 완전 열린 입 또는 입안+치아+혀, 앞·뒷머리, 캐릭터 기준 좌우, 중립/극단 자세·마스크·가림 점검. <https://github.com/tsunehimatoi/psd2live/blob/master/docs/en/spec/PSD_LAYER_SPEC.md>
5. Inochi2D 공식: Inochi Creator에 PSD 입력 가능하지만 **Neck Root 등 노드·부모자식 구조 및 파라미터/디포머 리깅 작업**이 필요하다. Inochi Puppet과 Live2D MOC3는 동종 출력물이 아님. <https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html> · <https://docs.inochi2d.com/en/latest/creator/first-model/tutorial02.html>

## 실제 GitHub 원문과 코드 판정

| 기능/작업 | 현 상태 | 검증 근거와 한계 |
|---|---|---|
| 24개 ZIP 직접 삽입 | **확인** | 각 ZIP 14 MD / 02 실제 파츠 작화 섹션 한 쌍 / 07 실제 그림 검수 섹션 한 쌍 / 00 서두의 참조 지시 확인 |
| 얼굴·목 숨은 면 독립 작화 지시 | **공식 방향 적합** | face/neck/torso 각각 보여주기·끄기, 턱 뒤와 몸통 안쪽까지 채색, 측면 귀·턱 연결. 단순 설명서이지 실제 완성 이미지가 아님 |
| 마스터 실제 픽셀 보존 | **지침 보강** | 마스터에서 보이는 픽셀은 마스킹·복사로 유지; AI는 가려진 곳만 추가. 정확히 보존할 도구가 없으면 SOURCE_PIXEL_TRANSFER_REQUIRED로 이관. 원래 가시 픽셀을 재생성하면 하드 픽셀 동등성에서 실패할 가능성이 큼 |
| 독립 눈 흰자/홍채/윗속눈썹 | **공식 입력 계약 적합** | PSD2Live 이름변환 `vts_psd2live_names.py`; 확인해야 할 사항: 각 PNG의 진짜 RGBA와 눈동자만 이동하는 화면 |
| 입 닫힘/열림/윗니/혀 | **입력 요구 충족, 동작 미검증** | upstream PSD2Live `RigBuilder.kt`의 MOUTH_CLOSE/MOUTH_OPEN/TOOTH/TONGUE 관련 ParamMouthOpenY 불투명도; 중립 PSD와 리깅 후 실제 조합은 다른 검증 |
| 목 상하/좌우 분리·실제 부착 | **원화 지침 적합, 리깅 미검증** | `vts_authored_part_art.py`는 jaw/neck 및 neck/torso 알파 겹침을 최소 픽셀 수로 검토하지만 실제 끊김·두께·선화 연속성을 보증하지 못함 |
| 실제 3/4·정면 회전 | **키폼 바인딩 미확인** | `vts_multiview_runtime.py`은 `reference_angles_used_as_rig_keyforms=False`; 참고 이미지는 해당 PSD에 자동 구동점으로 반영되지 않음 |
| 실제 ±30·±45 머리 회전 | **실제 모델 필요** | `vts_native_moc_pose_worker.py`가 `ParamAngleX` ±30/±45, `ParamAngleY`, 입·눈·시선 프레임을 네이티브 모델에서 렌더해야 판정 가능 |
| 실제 90° 측면 회전 | **현재 자동 경로 미지원** | `head_profile_L/R` PNG는 90° 측면 아트 참조일 뿐. 별도 회전 메시/키폼 또는 얼굴 아트 교체 모델이 없으면 지원 선언 불가 |
| HAIR/OUTFIT/ACCESSORY를 BODY 네이티브 모델에 합치기 | **미완료** | 현재 `process_completed_ai_2d_zip()`의 비BODY 분기는 PSD attachment 패키징에 머물고 BODY의 native MOC3에 자동적으로 합쳐 리깅하지 않는다 |
| Inochi2D 네이티브 Puppet | **미구현/미검증** | 현 `process_completed_ai_2d_zip()`는 `target_mode`가 없고 BODY는 `psd2live=True`를 호출함. Inochi2D PSD 원화는 활용 가능하나 .inp Puppet 자동 결과가 아님 |
| 3D 8방향 + detail 9장 | **참조 명세 적합, 메시/VRM 미검증** | `prepare_3d_turnaround_input()`이 참조자료를 수집하나 전체 3D 메시·UV·본·스키닝 및 HAIR/OUTFIT native 제작 완료 증명은 아님 |

## 반드시 불합격으로 처리할 예시

- 얼굴·목 파츠의 이름만 맞고, 얼굴 OFF에서 턱 뒤 숨은 목 픽셀이 없음
- BODY 마스터를 AI가 부위별로 다시 생성하여 정면 파츠 합성으로 원본을 재현하지 못함
- 측면 참조는 정상이나 실제 MOC3 ±45°에서 눈이 2개 그대로 보이고 턱/목이 끊김
- 열린 입안 PNG와 윗니/혀가 존재해도 실제 ParamMouthOpenY로 전환되지 않음
- 뒷머리 PNG는 있으나 귀/목 뒤에 다른 자산 피부를 대신해서 칠함
- OUTFIT의 목깃/겨드랑이 안감을 실제로 그리지 않고 BODY의 빈 부분을 덮어만 둠
- Inochi2D ZIP을 Live2D PSD2Live로 변환한 .moc3를 Inochi2D 최종 Puppet이라고 표시함
- 3D 아홉 장의 그림만 있고 모델 메시/UV/뼈/표정이 없는데 완성 VRM이라고 표시함

## 실물 품질을 판정할 입력

실제 생성한 `outputs/master.png`, `part_art/_order.txt`, 모든 `part_art/*.png`, `reference_views/*.png`, BODY의 닫힌/열린 입 `expression_refs`, Colab 조립 PSD 및 리깅 결과(`.model3.json`+`.moc3`, Inochi Puppet이라면 실제 `.inp`와 파라미터 상태)가 있어야 한다. 각 레이어 끔/켬, ±30·±45·상하, 입/눈, 목 가림을 직접 시각 확인한 뒤에만 최종 작품을 인정한다.

**이번의 PASS는 공식 원화 제작 지시와 ZIP 실물 일치까지**이며, 네이티브 리깅·90° 측면·트래킹·3D VRM은 미확인/미구현으로 별도 표기한다.
