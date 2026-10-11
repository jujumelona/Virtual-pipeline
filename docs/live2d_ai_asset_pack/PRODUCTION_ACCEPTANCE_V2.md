# 대형 이미지 AI Live2D 재제작·승인 계약 v2

작성일: 2026-10-11. 이 문서는 사용자가 제출한 **Live2D_AI_DEMO_Asset_Pack**에서 실제로 드러난 실패를 해결하기 위한 **납품 지시서**다. 원화 제작에 GPT/Gemini 등 이미지·파일 생성이 가능한 대형 AI를 사용한다. 공식 Live2D가 AI 이미지 8장이나 파츠 총수 24/60개를 지정했다는 주장은 하지 않는다.

## 1. 완성했다고 주장하면 안 되는 출력

- 마스터에서 마스크로 잘라 `isolated_parts/*.png` 29개를 만들었을 뿐인데 **독립 파츠 원화를 제작했다**고 보고한 것.
- 눈 속눈썹 파일에 홍채/눈 주변 그림이 붙고, 뒷머리 파일에 앞머리/얼굴이 섞였는데 **올바른 파츠 분리 PASS** 처리한 것.
- 얼굴·머리카락·목·소매·팔꿈치 뒤에 실제 원화가 없는데 **움직임용 뒷부분 완성**이라고 한 것.
- 마스터와 얼굴/헤어/의상 디테일이 다른 좌우 3/4 시점 이미지를 **동일 캐릭터 회전 참고화**로 승인한 것.
- 이미지 PNG만 만들었는데 **PSD 제작, MOC3/모델 리깅, 회전 품질 검수**를 완료했다고 표시한 것.

## 2. 큰 AI에게 실제로 시킬 순서

1. `outputs/master.png`를 기준 이미지로 **실제 생성하거나 사용자 제공 이미지를 확정**한다. 이후 매 파츠 생성 요청에 이 **실제 이미지 파일**을 첨부한다. 참고자료: `OFFICIAL_REFERENCES.md` 및 사용자가 제공한 합법적인 공식 샘플 그림/PSD.
2. `PARTS_AND_ROTATION_SPEC.md`의 **움직임별 part_id**에 따라 별도 그림을 생성한다. 작업 요청은 헤어/얼굴·목/눈·눈썹/입/몸통·의상/좌우 팔/필요 시 하체·장식 단위로 묶어도 된다. 한 시트에 여러 작은 파츠를 넣어도 된다. **최종 산출은 각 ID별 실질적인 독립 RGBA PNG**다.
3. 원본에서 보이는 픽셀은 디자인 보존을 위해 활용할 수 있지만 **마스크 추출만으로는 완료가 아니다**. 앞머리 밑 이마, 옆머리 밑 귀·얼굴, 뒷머리 뿌리, 고개 밑 목, 눈동자 밑 흰자, 입안, 팔 밑 의상, 어깨·팔꿈치·손목을 새 그림/원화 보정으로 **실제로 채워 넣는다**.
4. 각 파츠의 `creation_method` 값을 `generated` / `redrawn` / `edited_with_underpaint` / `extracted_only`로 기록하고, `underpaint_regions`에 새로 그린 위치를 기록한다. **필수 움직임 파츠가 단순 extracted_only인 상태는 원화 완성 불합격**. 이 기록은 생성자의 자기 신고이며, 품질에 대한 독립적 증명은 아님.
5. 단독 PNG를 master의 실제 좌표계로 되돌리기 위한 `placement={left,top,width,height}`를 기록한다. 시트를 사용했다면 파츠별 `rect_on_sheet=[x,y,w,h]`도 별도 기록한다. 시트 안의 부위는 서로 겹치지 않아야 하며, **독립 PNG 추출본과 시트를 함께 납품**한다.
6. `previews/neutral_composite.png`와 `previews/parts_contact_sheet.png`를 실제 제작해 원화/파츠 디자인을 **사람이 직접 비교할 수 있게** 만든다.

## 3. 파츠별 시각 합격 기준

| 파츠 | 반드시 보여야 하는 것 | 실패 |
|---|---|---|
| 앞·옆·뒤 머리 | hair_front / hair_side_L/R / hair_back 각각 다른 움직임 부분, 머리카락 뿌리·가림 뒤 연장 | hair_back에 앞머리 또는 얼굴 픽셀 혼입 |
| 얼굴·귀·목 | 눈·입이 합쳐지지 않은 얼굴 피부, 가려진 이마/귀/볼, 길게 그린 목 | 얼굴 레이어에 눈 통째 혼합, 머리 움직이면 목 빈 공간 |
| 좌우 눈 | 각 눈의 속눈썹·흰자·홍채·눈썹이 **각각 독립**, 홍채 아래까지 완성된 흰자 | lash PNG에 iris가 붙어 있음 |
| 입 | 윗입술·아랫입술·**실제로 채색된 입안** 독립, 닫을 때 입안 가림 가능 | 빈 이미지, 자투리 픽셀만 있는 입안 |
| 몸통·팔 | 팔이 움직여도 가려진 몸통/옷이 존재. 상완·전완·손이 어깨/팔꿈치/손목에서 서로 겹칠 원화가 존재 | 관절이 잘려 움직일 때 틈/구멍 |
| 하체/액세서리(해당 경우) | 실제 의상·장식 디자인에 부합하는 독립 움직임 파츠 | 원본에 없는 구성 창작, 붙어야 할 위치 오류 |

**스크립트가 픽셀 개수·파일명·알파만 확인하는 것은 시각적 파츠 합격 검사가 아니다.** 사람이 직접 시각 점검하거나 해당 시각 검수 능력이 있는 AI가 실제 이미지를 보고 판정해야 하며, 자동 판정의 오류 가능성도 기록한다.

## 4. 회전 대비와 참고화

- 공식 `ParamAngleX / ParamAngleY / ParamAngleZ`의 일반 표준 범위는 **-30/0/+30**. 3×3 XY 키폼은 **그림 9장**이 아니라 모델의 9가지 **변형 상태**다.
- 회전을 위해 움직임 중 노출될 원화(얼굴·귀·목·머리뿌리·의상)를 독립 파츠에 준비한다. **원화가 있어도 실제 XY 키폼·디포머가 자동 생성됐다고 주장하지 않는다**.
- 좌우 3/4 또는 측면 가이드 이미지를 요청/생성한 경우 `reference_views/`에 넣고, 마스터와 **눈매, 얼굴 윤곽, 헤어 길이, 의상 색/패턴, 좌우 장식, 몸 비율**을 나란히 비교하는 `previews/reference_identity_comparison.png`를 제출한다.
- **디자인이 달라진 참고화는 REJECTED, 재생성 대상**이며 최종 회전 가이드로 쓰지 않는다. 공식 요구 이미지 수는 없으며, ±90도 전체 측면 자동 완성도 보장하지 않는다.

## 5. 서로 다른 네 가지 완료 등급

| 등급 | 반드시 실제로 존재해야 하는 것 | 완료 불가 사례 |
|---|---|---|
| **A / ARTWORK_READY** | master, 유효한 독립 RGBA 파츠들, manifest(새 그림 방식·좌표), 합성/컨택트 시트, 시각 검수, 가림 추가 그림 | 단순 마스크 분리·누락·부위 혼합 |
| **B / PSD_READY** | A + **실제 PSD**, 정확한 레이어/순서/원점, PSD RGB 8bit, 재열어 합성 결과 확인 | PSD 파일 없음, PNG 이름만 psd로 바꿈 |
| **C / RIGGED_EXPORT** | B + 실제 **PSD2Live 또는 Cubism 실행** 로그와 model3.json, moc3, 텍스처, 필요하면 physics3.json, 모델 파일 참조 검증 | 원화/PSD만 있고 실행 안 됨 |
| **D / MOTION_VERIFIED** | C + 실제 Cubism/런타임의 Angle X/Y 이동, 눈 깜빡임·시선·입·팔 변형을 렌더링하고 틈·깨짐을 검수 | 파일 검증만 실시 |

외부 이미지 생성 AI가 PSD 작성 도구 또는 리깅 실행 환경에 접근하지 못하면 **B/C/D를 NOT_DELIVERED 또는 NOT_TESTED로 보고**하고 완료라고 말하면 안 된다. 이미지만 생성하는 일과 PSD2Live 실제 리깅은 다른 작업이다.

## 6. 최종 ZIP 구성

```text
Live2D_Character_Assets/
  README.md
  OFFICIAL_REFERENCES.md
  PARTS_AND_ROTATION_SPEC.md
  PRODUCTION_ACCEPTANCE_V2.md
  outputs/master.png
  isolated_parts/<part_id>.png
  sheets/*.png                                # 사용한 경우만, 독립 PNG를 대신하지 않음
  reference_views/*.png                       # 사용한 경우만
  previews/neutral_composite.png
  previews/parts_contact_sheet.png
  previews/reference_identity_comparison.png  # 회전 참고화 납품 시
  manifest.json                                # creation_method/underpaint_regions/placement/상태
  quality_review.md                            # 무엇이 검증됐고 무엇이 미완료인지
  cubism/avatar.psd                            # B 승인 시
  rigged/avatar.model3.json + ...              # C 승인 시
```

**ZIP 내부 이미지·PSD·모델의 실제 존재와 내용으로만 승인한다.** 이미지가 생성됐다는 사실만으로 정상 동작 Live2D를 만들었다고 결론내지 않는다.

## 7. 공식 참고자료

- [공식 일러스트 가공·예제 PSD](https://docs.live2d.com/en/cubism-editor-tutorials/psd/)
- [공식 소재 분리](https://docs.live2d.com/en/cubism-editor-manual/divide-the-material/)
- [PSD 요구사항](https://docs.live2d.com/en/cubism-editor-manual/precautions-for-psd-data/)
- [표준 파라미터](https://docs.live2d.com/en/cubism-editor-manual/standard-parameter-list/)
- [FREE/PRO 비교](https://www.live2d.com/en/cubism/comparison/)

**공식:** 움직임에 따라 파츠를 나누고 숨은 곳을 보완하며 PSD를 준비하는 원칙. **프로젝트 자체 요구:** 위 A/B/C/D 검수 등급, AI provenance 메타데이터와 ZIP 구조. 혼동하지 않는다.
