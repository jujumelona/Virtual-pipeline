# 24개 이미지 생성 ZIP · 336개 MD 개별 의미 충돌 검사

**검사 날짜:** 2026-10-16 (KST)  
**실제 검사:** 게시된 ZIP 바이너리를 GitHub Actions Linux에서 모두 열어 각 14개 MD의 UTF-8 텍스트, 파일 구조, CRC, 역할·모드·표준 출력·버전 마커를 점검.

## 확정 결과

- **24 ZIP / 336 MD 모두 실제 파싱 완료**, ZIP에 14개 MD가 중복 없이 존재하고 ZIP CRC 통과.
- 2D **20개 ZIP에 180회 존재하던 `IMAGE_ART_MULTIVIEW_SOURCE_ONLY_V1` 옛 계약 블록 제거**.
- 2D `IMAGE_AI_SOURCE_ONLY_V2` 블록은 모든 MD에 정확히 한 쌍. 그 내용은 템플릿 실제 열람→마스터 확정→**한 번에 파츠 하나씩 원화 생성**→독립 RGBA `part_art/*.png`→다각도→Colab PSD 조립 역할 분담.
- 3D 4개 ZIP은 8방향 턴어라운드+가림 참조(총 9장). 2D PSD/파츠/리깅을 요구하지 않는다.
- **자동 의미 충돌 규칙 확정 0건**, 추가 분류된 금지·제외 문구 58회는 사용 단계에서 잘못 요청하지 않도록 하는 정상 안내로 판정.
- 실제 이미지 생성기가 공식 템플릿의 시각 자료를 정말 보았는지, 이미지 간 일관성과 실제 3D/2D 리깅 품질까지 검증하는 기능은 이 문서 검사 범위가 아니다.

## ZIP 하나하나 결과

| ZIP | MD 확인 | 확정 충돌 | 정상적인 금지 문장(검토) | 구분 |
|---|---:|---:|---:|---|
| `live2d_bust_up__body.zip` | 14 | 0 | 0 | 정리 완료 |
| `live2d_bust_up__hair.zip` | 14 | 0 | 0 | 정리 완료 |
| `live2d_bust_up__outfit.zip` | 14 | 0 | 0 | 정리 완료 |
| `live2d_bust_up__accessory.zip` | 14 | 0 | 0 | 정리 완료 |
| `live2d_upper__body.zip` | 14 | 0 | 0 | 정리 완료 |
| `live2d_upper__hair.zip` | 14 | 0 | 0 | 정리 완료 |
| `live2d_upper__outfit.zip` | 14 | 0 | 0 | 정리 완료 |
| `live2d_upper__accessory.zip` | 14 | 0 | 0 | 정리 완료 |
| `live2d_full__body.zip` | 14 | 0 | 0 | 정리 완료 |
| `live2d_full__hair.zip` | 14 | 0 | 0 | 정리 완료 |
| `live2d_full__outfit.zip` | 14 | 0 | 0 | 정리 완료 |
| `live2d_full__accessory.zip` | 14 | 0 | 0 | 정리 완료 |
| `inochi2d_upper__body.zip` | 14 | 0 | 0 | 정리 완료 |
| `inochi2d_upper__hair.zip` | 14 | 0 | 0 | 정리 완료 |
| `inochi2d_upper__outfit.zip` | 14 | 0 | 0 | 정리 완료 |
| `inochi2d_upper__accessory.zip` | 14 | 0 | 1 | 신체 생성 제외 안내 |
| `inochi2d_full__body.zip` | 14 | 0 | 0 | 정리 완료 |
| `inochi2d_full__hair.zip` | 14 | 0 | 0 | 정리 완료 |
| `inochi2d_full__outfit.zip` | 14 | 0 | 0 | 정리 완료 |
| `inochi2d_full__accessory.zip` | 14 | 0 | 1 | 신체 생성 제외 안내 |
| `3d__body.zip` | 14 | 0 | 14 | 2D 제작 제외 안내 |
| `3d__hair.zip` | 14 | 0 | 14 | 2D 제작 제외 안내 |
| `3d__outfit.zip` | 14 | 0 | 14 | 2D 제작 제외 안내 |
| `3d__accessory.zip` | 14 | 0 | 14 | 2D 제작 제외 안내 |

**금지 문구의 실물 내용 분류:** Inochi2D `accessory` 2개 ZIP 각 1회: 신체·눈·목 그림을 액세서리 납품물에 섞어 만들지 말라는 지침. 3D 4개 ZIP 각 14회: 3D 참조 원화 ZIP에 2D PSD·리깅용 PNG·키폼을 요구하지 않는다는 지침. 서로 반대되는 수행 지시는 아니다.

## 재발 방지

- `tools/audit_24_image_kits.py --strict`: **24개 바이너리/336개 MD 모든 행**을 점검하여 구 계약 재등장 또는 실제 잘못된 단계 산출물 요구 발견 시 실패.
- `tools/update_source_only_body_kits.py --check`: 20개 2D ZIP의 원화 제작 계약이 소스와 동일한지 비교, 일치하지 않으면 실패.
- 구형 `tools/apply_image_ai_multiview_briefs.py`는 2D에 더 이상 과거 PSD·마스크 납품 블록을 새로 작성하지 않게 수정.
- 과거 템플릿 발행 워크플로는 **쓰기/자동 덮어쓰기에서 읽기 전용 검증**으로 변경. 2D 발행의 정상 경로는 최신 파츠 생성 계약과 동기화 도구.
- 새 ZIP으로 실제 생성하여 템플릿 관찰 및 파츠 그래픽 품질을 확인하는 E2E 테스트는 별도 수행해야 한다.

## 검증 기록

- [실제 24개 ZIP 전수 검사 / Actions 실행](https://github.com/jujumelona/Virtual-pipeline/actions/runs/38787020452) — strict PASS
- [템플릿 발행 회귀 차단 검증](https://github.com/jujumelona/Virtual-pipeline/actions/runs/38787231870) — PASS

이 기록은 **문서 간 충돌 검사**의 범위에서만 작성했으며, 생성 이미지 품질·외부 참조 열람/라이선스·PSD2Live/native 모델 성능에 대한 성공 보증으로 사용할 수 없다.
