# Live2D 이미지 AI 작업 지시서 ZIP

**이 ZIP 전체를 GPT·Gemini 등 이미지 생성 및 파일 작성이 가능한 대형 AI에게 첨부하십시오.** ZIP에 포함된 `START_HERE.md`를 첫 작업 지시로 사용합니다. 캐릭터 취향/설명은 같은 메시지에 적으면 됩니다.

## 대형 이미지 AI가 해야 할 일

1. 캐릭터의 **완성 기준 원화 1장** 제작
2. 그 원화를 계속 참조하면서 **움직임별 독립 파츠 원화** 제작 — 머리/눈/입/몸통/팔/필요한 장식
3. 머리카락·얼굴·목·팔이 움직일 때 드러날 **숨은 영역을 실제 그림으로 보강**
4. 작은 파츠를 한 시트에 모아 생성해도 최종적으로는 **파츠 하나당 PNG 파일**로 저장
5. 최종 이미지 파일들을 **ZIP으로 묶어 전달**

**이미지 AI에게 PSD 작성, PSD2Live 실행, .moc3 생성, 실제 회전 리깅, Cubism/VTube Studio 구동 검증을 요구하지 않습니다.** 그것은 이미지 작업 완료 후 별도 파이프라인이 담당합니다. 품질 PASS 문서·검수 인증서를 만들어 달라고도 하지 않습니다.

## 사용자가 할 일

1. [GitHub 제작 지시서 ZIP](https://github.com/jujumelona/Virtual-pipeline/raw/main/docs/live2d_image_ai_kit/Live2D_Image_AI_Instruction_Kit.zip)을 받습니다.
2. 이 ZIP **파일 자체**를 GPT/Gemini에 첨부하고 캐릭터 디자인, `상반신` 또는 `전신`을 말합니다.
3. AI가 납품한 **실제 PNG가 포함된 결과 ZIP**을 받습니다.
4. Colab v8에서 Live2D `ai_asset_zip`을 선택해 그 **결과 ZIP**을 업로드합니다. 첫 번째 **지시서 ZIP**과 결과 **원화 ZIP**은 다른 파일입니다.

대형 AI가 이미지 생성이나 ZIP 파일 작성 도구가 없으면 **제작하지 못한 파일을 만들어 냈다고 주장해서는 안 됩니다.** 실제 파일이 있어야 결과입니다.

- [공식 자료 링크·요약](OFFICIAL_LINKS.md)
- [부위별 원화 분리·회전용 숨은 영역](PARTS_ARTWORK.md)
- [최종 이미지 ZIP 폴더 구성](OUTPUT_FILES.md)
