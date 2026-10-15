# 24개 VTuber 이미지 생성 ZIP: MD 원문 직접 검토 및 수정 기록

- 날짜: **2026-10-16 (KST)**
- 대상: `docs/image_ai_kits_v2/zips/`의 **24개 ZIP, 총 336개 MD**
- 방식: **GitHub에 게시된 ZIP 바이너리를 직접 읽고** 각 파일의 본문과 다른 문서의 산출물·작업 범위·품질 검수 지시를 대조한 뒤 문장 원문을 수정함. CI가 ZIP을 재생성하거나 자동 수정한 결과가 아님.
- 결과: **21개 ZIP 직접 수정(2D 20개 + 3D BODY 1개)**. 3D HAIR/OUTFIT/ACCESSORY 3개는 검토 뒤 변경하지 않음. 수정된 문장 위치 **총 1,624개**(반복 삽입된 같은 계약 문장도 파일별 1회씩 포함).
- 원본 ZIP의 14개 MD 이름을 유지. 새 ZIP 바이너리 재구성 직후 각 MD의 본문이 의도한 수정값과 같은지 직접 재압축/재해제하여 대조하고, GitHub 반영 후 다시 ZIP 원문을 열어 24개 파일을 확인함.

## 발견하고 수정한 의미 충돌

### 1. 구형 Python 검증 코드 요구

**증거:** `00_DELIVERY_AND_RECHECK.md`와 `07_REVIEW_BEFORE_FINAL_ZIP.md`는 `04_OUTPUT_FILES.md`의 Python 검증 코드를 실행하고 PASS를 기록하라고 했음. 그러나 `04_OUTPUT_FILES.md`에는 그런 코드 자체가 없고, 필수 PNG 제작·납품 계약이 들어 있음.

**실제 수정:** 2D 20개 ZIP에서 두 MD의 지시를 **실제 파일 목록, RGBA 투명도, 각 파츠의 순서, 중립 합성, 각도별 PNG를 원본과 직접 대조**하도록 교체. 실행하지 않은 테스트를 PASS로 기록하지 않게 명시.

### 2. BODY 전용 입·눈 지시가 HAIR·OUTFIT·ACCESSORY에 복제됨

**증거:** 2D 비신체 ZIP의 `00_MASTER_FIRST.md`, `00_READ_FIRST.md`, `07_REVIEW_BEFORE_FINAL_ZIP.md` 등 첫 페이지와 공통 계약에서 홍채·흰자·윗속눈썹·입안·치아·혀를 작업하라고 되어 있었음. 별도 `- 7) 필수 납품`은 BODY가 아닌 자산에도 BODY 전용 입 벌림 참고 원화를 붙이라고 했음.

**실제 수정:** 2D의 각 MD에 **BODY/HAIR/OUTFIT/ACCESSORY 별도 제작 대상**을 반영. 본래 신체·눈·입은 HAIR/OUTFIT/ACCESSORY에서 **위치·색상 참고에만 사용**하고 새 산출물로 만들지 않음. 대체 입안·치아·혀 PNG와 닫힌/열린 입 참고 원화는 BODY에만 요구.

### 3. 전신 BODY의 하체 필수 원화 목록 누락

**증거:** 2D 전신 BODY의 `- 4) 권장 파츠 역할`은 상완·전완·손에서 목록을 끝내지만 다른 문서는 전신 6등신과 양발까지 요구했음.

**실제 수정:** `live2d_full__body.zip`, `inochi2d_full__body.zip` 모든 해당 문서에 `pelvis`, `thigh.left/right`, `shin.left/right`, `foot.left/right`를 명시. 표준 파츠 수를 강제로 24개 등 고정하지 않음.

### 4. 템플릿을 열라는 지시와 무관한 범용 제작 지시

**증거:** 모든 자산이 동일한 눈·입·관절 검수 순서를 복제하며, Inochi2D까지 Live2D 샘플 PSD 계층을 자기 플랫폼 유일한 기준처럼 설명하는 문장이 있었음.

**실제 수정:** 각 자산의 템플릿 슬롯에 맞춰 **원화 하나당 PNG 하나를 생성**하고 해당 자산의 원화·가림·부착점을 검사하도록 교체. 다른 플랫폼의 템플릿은 구조 참고로만 사용; 실제 사용자 캐릭터와 자산 구도가 우선.

### 5. 3D BODY의 2D 파일명 혼입

**증거:** 3D BODY `IMAGE_AI_SOURCE_ONLY_V2` 블록은 3D 8방향+가림 상세 1장을 요구하면서 별도로 `neck_underpaint`, `body_joint_overlaps` 같은 2D 참고 파일명을 지시했음.

**실제 수정:** 3D BODY의 14개 MD에서는 **8방향 턴어라운드 + `views/body_detail_occlusion.png`** 한 장으로 목·턱·어깨·팔 관절과 가림을 명확히 묘사하도록 정정. 2D 참조명을 별도 3D 산출물로 요구하지 않음.

## 24개 ZIP별 확인 결과

| ZIP 원본명 | MD 확인 | 수정 위치 | 검토 결과 |
|---|---:|---:|---|
| `live2d_bust_up__body.zip` | 14/14 | 91 | BODY 분리·입 표정·허위 코드 정정 |
| `live2d_bust_up__hair.zip` | 14/14 | 77 | HAIR 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `live2d_bust_up__outfit.zip` | 14/14 | 77 | OUTFIT 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `live2d_bust_up__accessory.zip` | 14/14 | 77 | ACCESSORY 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `live2d_upper__body.zip` | 14/14 | 91 | BODY 분리·입 표정·허위 코드 정정 |
| `live2d_upper__hair.zip` | 14/14 | 77 | HAIR 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `live2d_upper__outfit.zip` | 14/14 | 77 | OUTFIT 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `live2d_upper__accessory.zip` | 14/14 | 77 | ACCESSORY 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `live2d_full__body.zip` | 14/14 | 91 | BODY 분리·입 표정·전신 하체 목록·허위 코드 정정 |
| `live2d_full__hair.zip` | 14/14 | 77 | HAIR 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `live2d_full__outfit.zip` | 14/14 | 77 | OUTFIT 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `live2d_full__accessory.zip` | 14/14 | 77 | ACCESSORY 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `inochi2d_upper__body.zip` | 14/14 | 91 | BODY 분리·입 표정·허위 코드 정정 |
| `inochi2d_upper__hair.zip` | 14/14 | 77 | HAIR 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `inochi2d_upper__outfit.zip` | 14/14 | 77 | OUTFIT 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `inochi2d_upper__accessory.zip` | 14/14 | 77 | ACCESSORY 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `inochi2d_full__body.zip` | 14/14 | 91 | BODY 분리·입 표정·전신 하체 목록·허위 코드 정정 |
| `inochi2d_full__hair.zip` | 14/14 | 77 | HAIR 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `inochi2d_full__outfit.zip` | 14/14 | 77 | OUTFIT 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `inochi2d_full__accessory.zip` | 14/14 | 77 | ACCESSORY 전용 범위 확정·눈/입 혼입 제거·허위 코드 정정 |
| `3d__body.zip` | 14/14 | 14 | 3D 전용 가림 참조명 정정 |
| `3d__hair.zip` | 14/14 | 0 | 실문서 확인, 변경 불필요 |
| `3d__outfit.zip` | 14/14 | 0 | 실문서 확인, 변경 불필요 |
| `3d__accessory.zip` | 14/14 | 0 | 실문서 확인, 변경 불필요 |

## 14개 MD별로 검토한 책임

| MD | 비교한 내용 |
|---|---|
| `00_MASTER_FIRST.md` | 최초 제작 대상·BODY 비율·작업 단계·하나씩 파츠 생성과 공식 참고 |
| `00_DELIVERY_AND_RECHECK.md` | 실제 존재하는 납품 파일·검사 방법·없는 Python 실행 지시 |
| `00_READ_FIRST.md` | 이미지 AI 생성 전 템플릿 확인·자산별 분리 원칙 |
| `01_COMMON_RULES.md` | 실제 자산 소유·BODY와의 좌표·의상/헤어 분리 |
| `02_ADVANCED_PARTS.md` | 독립 파츠·관절·앞뒤 가림·전신과 상반신 차이 |
| `03_MODE_RULES.md` | 해당 방송 프레임·상반신/전신·3D 모드별 경계 |
| `04_OUTPUT_FILES.md` | 실재 필수 경로·단일 파츠 PNG·입 대체 그림 |
| `05_OFFICIAL_REFERENCES.md` | 공식 참조와 실제 렌더된 산출물의 구별 |
| `06_ADVANCED_OFFICIAL_COMMUNITY.md` | 예시 디자인 복사와 실제 자산 범위 혼동 방지 |
| `07_REVIEW_BEFORE_FINAL_ZIP.md` | 존재하지 않는 테스트 PASS 주장 및 품질 검수 |
| `08_PRACTICAL_TIPS.md` | 자산별 실무 제작과 겹침·재질·부착점 |
| `09_VISUAL_ART_QUALITY.md` | 실제 그림 품질과 기하/파일 구조 검사 구별 |
| `10_ANIME_STYLE.md` | 머리·눈·얼굴 등 고유 스타일과 BODY 자산 지침 |
| `11_OFFICIAL_IMAGE_EXAMPLES.md` | 공개 템플릿 캐릭터를 복제하거나 다른 자산까지 그리는 지시가 없는지 |

## 직접 반영·재열람 기록

- **직접 수정 커밋:** [024120c47aeb854a6dc5d4e1c5bda023ef7b3ace](https://github.com/jujumelona/Virtual-pipeline/commit/024120c47aeb854a6dc5d4e1c5bda023ef7b3ace)
- GitHub 게시 바이너리 재열람에서 24 ZIP 전부 14 MD 확인.
- 수정 후 재열람 기준: 존재하지 않는 `04_OUTPUT_FILES.md` Python 코드 실행 지시 **0**, 비BODY ZIP의 BODY 입 참고 의무 **0**, 전신 BODY 다리 역할 누락 **0**, 구형 첫 페이지 눈·입 일괄 제작 지시 **0**.
- 구형 ZIP을 자동으로 재발행하던 GitHub 워크플로의 `push` 트리거는 제거하여, 이 직접 수정 ZIP을 자동 생성기로 덮어쓰지 않도록 함.

### 평가 범위 및 남은 한계

이번에 확인한 것은 **실제 게시된 MD 텍스트와 명세 사이의 충돌**이다. 이후 다른 문서나 생성기 버전이 바뀌었을 때 동기화 여부는 다시 검사해야 한다. 실제 이미지 생성 AI가 외부 템플릿을 눈으로 보았다는 사실, 파츠 그림의 애니풍 품질, 입 원화의 결합, MOC3/Inochi2D의 실제 모션 결과까지 인증한 것은 아니다.
