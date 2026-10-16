(() => {
  const VIEWS = {
    body: ["body_front","head_three_quarter_L","head_three_quarter_R","head_profile_L","head_profile_R","head_pitch_up","head_pitch_down","neck_underpaint","body_joint_overlaps"],
    hair: ["hair_front","hair_three_quarter_L","hair_three_quarter_R","hair_profile_L","hair_profile_R","hair_back","hair_underlayers","hair_motion_clearance"],
    outfit: ["outfit_front","outfit_three_quarter_L","outfit_three_quarter_R","outfit_profile_L","outfit_profile_R","outfit_back","outfit_inside_seams","outfit_joint_clearance"],
    accessory: ["accessory_front","accessory_three_quarter_L","accessory_three_quarter_R","accessory_profile_L","accessory_profile_R","accessory_back","accessory_attachment_anchor","accessory_occlusion"]
  };
  const FRAMES = {
    live2d_bust_up:"머리와 눈이 큰 방송용 바스트업. 상복부·양팔·양손가락 끝까지 포함. 골반·다리·발 없음.",
    live2d_upper:"머리~허리 부근, 양어깨·양팔·양손 포함. 다리·발 없음.",
    live2d_full:"정수리~발끝 전신, 양손가락·발끝 잘림 없음.",
    inochi2d_upper:"Inochi2D 상반신, 머리~허리, 양팔·손 포함. 다리·발 없음.",
    inochi2d_full:"Inochi2D 전신, 정수리~발끝, 양손·발 포함."
  };
  const ASSETS = {
    body:"민머리 두상, 크고 선명한 눈, 짧고 넓은 얼굴, 코·입·귀, 목·어깨, 비해부학적 불투명 무광 베이스 몸통, 양팔·양손만. 헤어·별도 의상·장신구 픽셀 0개. 얼굴·목·몸통·팔·손의 기본색 통일.",
    hair:"기존 BODY 참조에 위치를 맞추는 앞·옆·뒤 머리카락만. 기준 몸체·얼굴·눈·옷·별개 장신구 픽셀 제외.",
    outfit:"기준 BODY 위에 교체해 입힐 요청 의상·안감·소매만. 몸체·얼굴·눈·머리카락·별개 장신구 제외.",
    accessory:"사용자가 요청한 한 종류 소품만. 기준 몸체의 부착 위치에 정렬하되 신체/얼굴/머리/의상을 복제하지 않는다."
  };
  function contract(mode, asset) {
    if (!(mode in FRAMES) || !(asset in ASSETS)) throw Error("Invalid 2D mode / asset");
    const refs = VIEWS[asset].map(v=>"  - `reference_views/"+v+".png`").join("\n");
    const expression = asset === "body"
      ? "  - `expression_refs/mouth_closed.png`, `expression_refs/mouth_open.png`: 서로 다른 실제 표정 참고 원화; 중립 마스터와 같은 크기/얼굴 위치.\n"
      : "";
    const body = asset === "body"
      ? "- 눈 흰자·홍채·속눈썹은 고품질 애니 원화에서 식별되게 그리지만, 그들을 개별 PNG로 만들어야 할 책임은 후속 분리 단계에 있다. 각 눈의 세 개 층이 실제 서로 다른 RGB·알파 픽셀인지 검증하고 불완전하면 해당 영역만 정밀 분리/가림 복원한다.\n- 턱과 목·어깨의 자연스러운 정면 연결은 원화에서 보존한다. 턱/목/팔꿈치/손목의 숨겨진 이어지는 영역은 분리 단계에서 실제 인페인팅하고 위치·색을 검사한다.\n"
      : "- 현재 자산 외의 BODY/얼굴/눈/의상/장신구 픽셀을 결과 이미지에 합치지 않는다. 원래 캐릭터는 위치·색·디자인 참조로만 사용한다.\n";
    return `## [GPT_ARTWORK_SEGMENTER_HANDOFF_V5]
### ${mode} / ${asset} — GPT 마스터 원화에서 실제 분리 AI까지
**최상위 역할 계약. 이 ZIP은 GPT의 원화 생성 지시서이지 GPT에게 PSD·파츠 분리를 시키는 지시서가 아니다.** 모든 14개 MD의 기존 \`part_art/\`, \`_order.txt\`, \`isolated_parts/\`, PSD, 알파, 개별 눈·목 세분화, 합성 검수 지시는 **별도 후속 분리 엔진의 출력/검사 명세**로 해석한다. 이미지 생성 AI가 그 파일을 생성했다고 주장해서는 안 된다.
1. GPT는 \`outputs/master.png\` **실제 정면 원화 PNG 1장**(RGB 또는 진짜 RGBA)을 생성한다. 콜라주, 부품을 떨어뜨려 배치한 시트, 가짜 투명 PNG, 기존 이미지와 다른 인물로 그린 설정화는 불합격이다.
2. 다음은 투명 파츠가 아닌, 같은 캐릭터의 다른 시점/숨은 부분 참고 원화이다. **각각 별도의 실제 PNG**로 그린다.
${refs}
${expression}3. 마스터와 front/three_quarter/profile/pitch 참고는 **동일한 원본 캔버스 가로·세로 픽셀 크기, 인물 스케일·중심좌표**를 유지한다. 뷰 이름을 바꾸거나 정면을 복제해 다른 시점으로 위장하지 않는다.
4. **모드 구도:** ${FRAMES[mode]}
5. **자산 경계:** ${ASSETS[asset]}
6. **See-through 분리를 고려한 원화:** 한 이미지에 한 시점·한 캐릭터, 흰색/단순 단색 배경, 선명한 애니 셀 셰이딩/파츠 윤곽·깔끔한 경계; 글자·워터마크·장식 배경·눈 위의 불필요한 손/머리카락 겹침·과도한 발광 금지. 구분을 위해 머리·팔을 물리적으로 잘라 떼어 놓거나 전체 원화 품질을 저하시키지 않는다.
${body}7. **GPT 결과물:** \`${mode}__${asset}__ARTWORK.zip\`에 \`outputs/master.png\`, 위 \`reference_views/*.png\` 및 BODY에서 \`expression_refs/*.png\`만 저장한다. \`manifest.json\`, \`layer_order.txt\`, \`part_art/_order.txt\`, \`part_art/*.png\`, \`isolated_parts/\`, PSD, MOC3 등 분리/리깅 파일은 생성하지 않는다. 원화 ZIP 납품과 Live2D 완료를 혼동하지 않는다.
8. **후속 파이프라인:** \`tools/vts_source_only_pack.py\`가 실물 마스터·뷰의 PNG 형식/중복/크기 등을 확인한다. 이후 See-through V3/NF4로 분리 PSD 후보를 만들고, 관찰된 파츠를 공식 좌우/깊이 세분화 또는 SAM 정밀 마스크로 필요 시 개선한다. Qwen-Image-Layered는 기존 런타임에서 해당 자산에 **실제로 연결된 경우에만** 추가 RGBA 분해에 사용한다. Qwen은 텍스트만으로 L/R 홍채·흰자·속눈썹 레이어를 정확히 지정하는 기능을 보장하지 않는다.
9. **후속 검수:** 원본 보이는 RGB 보존, 실제 알파, 가려진 부분 복원, PSD 순서/캔버스 좌표, 좌우 눈 흰자·홍채·속눈썹, 턱-목-몸통·팔-손 접합, 마스터 중립 합성 일치와 변형을 검사한다. 불합격 부위는 분리 작업에서만 재시도/인페인팅하고 GPT가 파츠 시트를 대신 그리게 하지 않는다. 결과 PSD는 Cubism/Inochi2D 모델 리깅/방송 동작 성공을 뜻하지 않는다.
10. 위에 적힌 PNG를 실제 제작할 수 없으면 그 누락을 명확히 보고한다. 분리 엔진 오류는 GPT 원화 생성 완료와 별도로 보고한다.
## [/GPT_ARTWORK_SEGMENTER_HANDOFF_V5]
`;
  }
  return {contract,views:VIEWS};
})()