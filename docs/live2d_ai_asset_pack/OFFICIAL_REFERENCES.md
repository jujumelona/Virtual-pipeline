# Live2D 공식 예제/매뉴얼 및 출처 (2026-10-11 확인)

**AI가 링크를 실제로 열어보는 기능이 없다면 읽었다고 주장하지 않는다.** 사용자가 직접 공식 예제 PSD/이미지를 첨부할 수 있다. 원본 그림은 무료 소재 라이선스를 확인하고 적법하게 사용한다. GitHub와 ZIP에 원본 공식 저작물의 무단 복제본을 넣지 않는다.

| 공식 페이지 | 링크 | 적용 |
|---|---|---|
| **일러스트 가공 + 모모세 히요리 예제 PSD 다운로드 링크** | https://docs.live2d.com/en/cubism-editor-tutorials/psd/ | 앞/옆/뒤 헤어, 얼굴·눈·입, 팔·몸통 실전 파츠, 가려진 부분 그리기 |
| **소재 분리 절차** | https://docs.live2d.com/en/cubism-editor-manual/divide-the-material/ | 원화에서 필요한 영역 추출하고 움직이며 노출되는 부분을 추가로 그림; 분리 PSD/가져오기 PSD 구분 |
| **PSD 작성 주의점** | https://docs.live2d.com/ko/cubism-editor-manual/precautions-for-psd-data/ | PSD RGB 8bit, sRGB, 파츠별 레이어 병합 |
| **Cubism 가져오기용 PSD 만들기** | https://docs.live2d.com/en/cubism-editor-manual/reimport-psd/ | 파츠별 래스터와 알파 먼지·불필요한 여백 정리 |
| **PSD 가져오기** | https://docs.live2d.com/en/cubism-editor-manual/psd-import/ | Cubism 레이어/폴더 구조 |
| **표준 파라미터 (한국어)** | https://docs.live2d.com/ko/cubism-editor-manual/standard-parameter-list/ | AngleX/Y/Z, 눈·입·팔 ID·범위 |
| **X/Y 키폼 (한국어)** | https://docs.live2d.com/ko/cubism-editor-manual/keyform-xydirection/ | 두 파라미터의 3×3 키폼 개념 |
| **회전 표현 제작** | https://docs.live2d.com/en/cubism-editor-manual/apply-3d-rotation-expression/ | Cubism 디포머를 이용한 회전 표현 |
| **회전 표현 설정** | https://docs.live2d.com/en/cubism-editor-manual/apply-3d-rotation-expression-settings/ | 회전 중심, 카메라, 각도 범위 |
| **가이드 이미지 배치** | https://docs.live2d.com/en/cubism-editor-manual/sketch/ | 추가 시점 이미지의 가이드 활용 |
| **FREE/PRO 비교** | https://www.live2d.com/en/cubism/comparison/ | 아틀라스 2048 한 장, ArtMesh 100, 파라미터 30, 디포머 50 등 |
| **공식 샘플 모델** | https://www.live2d.com/en/learn/sample/ | 실제 동작 모델 참조, 라이선스 확인 |
| **공식 무료 소재 라이선스** | https://www.live2d.com/eula/live2d-free-material-license-agreement_en.html | 공식 샘플 이미지/PSD 이용 조건 |

## 공식 문서에서 직접 확인된 분리 예시

- 머리의 큰 분류는 **앞머리·옆머리·뒷머리**. 좌우로 움직일 사이드 헤어와 독립 가닥은 따로 둔다.
- 눈은 **속눈썹·눈동자·흰자**, 눈썹과 코는 독립. 입은 **윗입술·아랫입술·입 안**으로 나눈다.
- 얼굴 윤곽은 머리카락 뒤 피부까지 그림. 귀는 독립 이동한다면 별도. 목은 고개가 움직일 때 끊기지 않게 윗부분을 연장한다.
- 몸은 목/몸통/팔/다리. 팔의 공식 예시는 **상완/전완/손**, 다리는 치마/좌우 다리. 옷깃과 리본은 움직임에 맞춰 구분한다.
- 분할 수는 **모델마다 다르며**, 공식 AI 이미지 생산 횟수나 8장 시트 권장값은 없다.
- **가이드 이미지**는 제작 중 참고용이며 자동으로 실제 Live2D 회전 키폼이 되지 않는다.

**시각 자료:** 이 문서들은 공식 예제 페이지의 링크를 제공한다. 사용자가 받는 별도 ZIP에는 프로젝트 자체 제작 도해 PNG 3개가 들어 있다. 공식 모델 이미지/PSD는 원본 라이선스 때문에 무단 동봉하지 않는다.
