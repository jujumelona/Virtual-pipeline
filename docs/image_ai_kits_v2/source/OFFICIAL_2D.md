# 공식 Live2D / Inochi2D 일러스트 예제 및 분리 기준

## Live2D의 실제 공식 자료

- 일러스트 가공 튜토리얼 / 공식 샘플 PSD: https://docs.live2d.com/en/cubism-editor-tutorials/psd/
- 소재 나누기 매뉴얼: https://docs.live2d.com/en/cubism-editor-manual/divide-the-material/
- PSD 작업 주의사항: https://docs.live2d.com/en/cubism-editor-manual/precautions-for-psd-data/
- Parts 레이어 구조: https://docs.live2d.com/en/cubism-editor-manual/edit-parts/
- 공식 예제 모델: https://www.live2d.com/en/learn/sample/
- 공식 무상 소재 이용 조건: https://www.live2d.com/eula/live2d-free-material-license-agreement_en.html

**공식 튜토리얼의 핵심 내용:** 머리카락은 앞/옆/뒤, 얼굴은 눈·눈썹·속눈썹·흰자·홍채·코·입·귀·윤곽, 입은 윗입술/아랫입술/입안, 몸은 목·몸통·상완·전완·손·하체 등 움직임에 맞춰 분리. 눈꼬리 속눈썹의 추가 분리, 숨겨진 이마·흰자·입안·목을 충분히 그리는 방법도 설명한다. **완성 일러스트를 나누는 것 외에 그림 제작 시점부터 움직일 부분을 별도 레이어로 그리는 방법도 공식적으로 언급한다.**

## Inochi2D 공식 자료

- Inochi2D 공식 문서: https://docs.inochi2d.com/en/latest/index.html
- Inochi Creator 첫 PSD 불러오기 튜토리얼(공식 Aka 예제): https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html
- 공식 FAQ(PSD 호환성, Live2D 리깅 비호환): https://docs.inochi2d.com/en/latest/inochi2d/faq.html

Inochi Creator는 PSD 가져오기를 지원하며 가져온 노드의 일부 블렌드/표시 상태는 조정이 필요할 수 있다. 원화 준비는 비슷하지만 Live2D에서 리깅한 데이터를 Inochi2D에 그대로 가져올 수 없다.

## 이 ZIP과 공식 규정의 차이

각 파츠의 정확한 파일명, 결과 ZIP 폴더 구조와 이미지 시트 개수는 이 프로젝트가 이미지 AI의 작업을 명확히 하기 위해 정한 **제작 계약**이다. Live2D 공식에 없는 8장·24개·60개 고정 수량을 강제하지 않는다. 공식 문서의 그림/PSD는 링크만 제공하며 라이선스 확인 없이 재배포하지 않는다.

### 공인 자료와 개인 작화 조언의 구별
- **Live2D 공식:** https://docs.live2d.com/en/cubism-editor-tutorials/psd/ — 눈·입·목·헤어/옷의 실제 분할과 가려진 영역을 보완하는 기법을 설명. 완성 원화에서 분리하거나 작화 단계에 미리 분리할 두 방식이 가능하지만, 이 제작 ZIP에서는 **완성 원화 먼저**를 우선한다.
- **Cubism 공식 PSD:** https://docs.live2d.com/en/cubism-editor-manual/precautions-for-psd-data/ — PSD RGB·8비트/채널·sRGB 권장 등의 내용은 후속 PSD/Editor 안내용이다.
- **Inochi2D 공식:** https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html — PSD 가져오기에서 그림자 레이어가 겹쳐 보일 수 있다. https://docs.inochi2d.com/en/latest/creator/nodes/node.html — 자식 노드의 상대 좌표와 Sorting은 후속 Creator 작업이다.
- **CLIP STUDIO TIPS 개인 작가:** https://tips.clip-studio.com/en-us/articles/7379 , https://tips.clip-studio.com/en-us/articles/6615 , https://tips.clip-studio.com/en-us/articles/5958 — 애니풍 얼굴 비율·각도별 눈·머리 모근과 가닥 설계 참고. 에디터 공식 규격이나 고정 픽셀 수가 아니다.
