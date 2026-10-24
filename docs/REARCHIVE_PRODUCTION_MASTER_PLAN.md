# RE:ARCHIVE · 무료 고품질 Live2D 제작 실행 기준

**금액: 0원.** 유료 모델/파츠/Cubism PRO 구매를 전제로 하지 않는다. 이 저장소는 무료 CC0 편집 가능 모델 1개를 베이스로 하고, 다른 모델은 기술 참조로만 활용한다.

## 고정된 외형
- 약 7억 1,700만 년 전 선행 문명이 DNA 개조로 만든 인간형 생체 안드로이드.
- 큰 투명 민트·연두 눈, 미세 HUD 및 DNA 홍채 문양, 감정 표현이 풍부한 귀여운 얼굴.
- 흑백·실버 트윈테일, 작은 DNA 헤어핀과 귀 동기화 단자, 인체와 닮은 피부.
- 내부 생체 유지 슈트와 흰색·회색·검정 고급 보존 기록자 의상, 반투명 케이프/독립 소매.
- **가슴 위 투명 DNA 캡슐** 내부 독립 이중나선/발광/유리/금속 보호 링. 허리 예비 바이알, 의상 DNA 곡선, 개체 봉인 코드와 서리 문양.
- 동물 귀/꼬리, 역병의사 마스크, 과도한 메카·네온, 현대 교복/메이드복 금지.

## 파일 게이트와 책임
| Gate | 담당 | 필수 산출물 | 주의 |
|--|--|--|--|
| G0 | 이미지 기준 고정 | 이전 RE:ARCHIVE 원본 시트 | 시트는 PSD 아님 |
| G1 | 정면/좌우 45도 원화 제작 | `art/S01_front_neutral.png`, `references/S02_left_45.png`, `references/S03_right_45.png` | 전부 1536×2304 RGBA, 실제 별개 원화; 시각적 동일인 QA 별도 |
| G2 | 분리 원화 직접 제작 및 가려진 면 보강 | `parts/<group>/<id>.png` 92 슬롯(필수 79개) | 앞머리 아래 이마, 눈꺼풀 뒤 안구, 소매 안쪽 필수 |
| G3 | Colab See-through / SAM | 실제 독립 PSD 초안 | G1 통과 뒤 실행, G2 실제 원본 파츠 있으면 원본 보존 |
| G4 | Colab Real-ESRGAN anime 6B | 원본 보존 + 별도 2x/4x RGBA | 파츠 좌표 동시 확대; 업스케일로 숨은 면이 생기지는 않음 |
| G5 | 무료 편집 리그 PSD2Live | 새 편집 프로젝트, MOC3/물리 | Hiakari 기반. Mio/star_lan은 기술 참조. Stage9 DNA 물리 재사용 |
| G6 | 자동/수동 QA | pose renders, single 2048 atlas and full FREE limits report | 단순 MOC3 파일 존재=고품질 아님 |
| G7 | 실제 VTube Studio | 카메라 입·눈·물리 검수 | 앱 실측 전 BROADCAST_READY 금지 |

## 바로 여는 Colab
- [원화 ZIP 사전검사/See-through 인계](../notebooks/REARCHIVE_FREE_HANDOFF.ipynb)
- [이미지/파츠 Real-ESRGAN 업스케일](../notebooks/REARCHIVE_FREE_UPSCALE.ipynb)
- [기존 정면 See-through GPU 처리](../notebooks/FACE_SeeThrough_OfficialAligned_v3.ipynb)
- [기존 독립 파츠 조립·PSD2Live](../notebooks/VTuber_SeeThrough_Only_Source_ZIPs.ipynb)

**입력 계약:** [JSON](REARCHIVE_PRODUCTION_CONTRACT.json) · [파일 검증기](../tools/rearchive_production_preflight.py).
원본 분리 성공 전에 마스터 그림을 잘라 92개 리깅 파츠라고 위장하지 않는다.

## 무료 리그
- Hiakari Inori CC0: 눈/입/소매/물리 메인 편집 베이스. **동물 귀·꼬리는 제외**.
- Kirishima Mio CC0: 눈·입·목 연결 참고.
- star_lan CC0: 메시·아틀라스 참고.
- RE:ARCHIVE Stage9: 실제 구현한 가슴 DNA 코어 독립 물리.
- `.moc3` 파일들을 합쳐서 새 모델을 만들 수는 없다. 편집 프로젝트의 정확한 layer ID/실제 PNG를 통해 적합한 리깅을 이식한다.

**현재 상태:** 외형 기준·92 파츠 계약·노트북·검증기는 제작됨. 원화 S01/S02/S03의 독립 파츠, 새 고품질 캐릭터 적용 .psd2live, 방송 앱 검증은 **미완료**다.
