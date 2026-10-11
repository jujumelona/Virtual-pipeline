# 품질 검수 기록 템플릿

- 실제 master.png 파일/크기: (기록)
- 요구 움직임 파츠 ID / 실제 생성 파일 수: (기록)
- 진짜 RGBA 알파 확인: PASS / FAIL / UNKNOWN
- 동일 master 캔버스와 크롭 origin 확인: PASS / FAIL / UNKNOWN
- 시트에서 독립 PNG 추출 확인: PASS / FAIL / NOT_USED
- 시각적으로 캐릭터 디자인 일치: PASS / FAIL / UNKNOWN
- 실제 Cubism PSD import: NOT_TESTED (실행 전)
- 실제 Angle X/Y 회전과 가림 품질: NOT_TESTED (실행 전)
- FREE 아틀라스/ArtMesh/Deformer/Parameter 수: NOT_TESTED (모델 생성 전)
- 누락·실패·재생성 ID: (기록)

*실제 검증하지 않은 단계를 PASS로 표시하지 않는다.*

## V2 필수 검수

- 파츠별 creation_method 및 새로 그린 underpaint_regions: (실제 기록)
- 눈 속눈썹/흰자/홍채 혼합 없음: PASS/FAIL/UNKNOWN
- 머리 앞/옆/뒤 섞이지 않음: PASS/FAIL/UNKNOWN
- 목/이마/귀/관절 뒤쪽 숨은 그림 완성: PASS/FAIL/UNKNOWN
- 회전 참고화와 master 디자인 동일성: PASS/REJECTED/NOT_USED
- 실제 PSD_READY: PASS/NOT_DELIVERED
- 실제 RIGGED_EXPORT: PASS/NOT_TESTED
- 실제 MOTION_VERIFIED: PASS/NOT_TESTED

단순 RGBA/파일 개수 검사만으로 이 항목들을 PASS 하지 않는다.
