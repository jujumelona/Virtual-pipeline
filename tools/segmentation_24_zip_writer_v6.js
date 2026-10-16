(() => {
  const assetV3 = {
    body: ["face","irides","eyebrow","eyewhite","eyelash","ears","nose","mouth","neck"],
    hair: ["front hair","back hair"],
    outfit: ["topwear","neckwear","handwear","bottomwear","legwear","footwear"],
    accessory: ["headwear","earwear","eyewear","neckwear","tail","wings","objects"]
  };
  const expected = {
    body: "양쪽 흰자·홍채·속눈썹 각각 실제 독립 RGBA, 양 눈썹, 얼굴바탕·코·중립 입/열린 입안, 두피·목·몸통·양 상완·전완·손·숨은 관절면",
    hair: "앞머리, 옆머리 좌/우, 뒷머리, 머리카락 뿌리의 숨은 면과 움직임 단위",
    outfit: "의상 앞·뒤, 각 소매 좌/우, 안감·주름·겹침·관절 경계 (실제 해당 의상에 존재하는 부위만)",
    accessory: "사용자가 요청한 한 종류 소품의 독립 본체, 부착점, 다른 파츠 뒤 가려지는 뒷면, 실제 움직임이 필요한 세부"
  };
  const missingV3 = {
    body: "See-through V3에는 bare hand, forearm, upper arm, fingers, individual eyelids, inner mouth, torso/neck underpaint가 없다. 'handwear'는 손 자체가 아니라 장갑/손 착용품이다. 몸통 무광 베이스가 topwear로 오인되어도 의상으로 단정하지 않는다.",
    hair: "앞/뒤 머리카락은 V3 태그가 있지만 옆머리 좌/우·개별 술·뿌리 숨은 면의 전용 태그는 없다.",
    outfit: "topwear 등은 의복 의미 영역이며 소매 좌/우·안감·허리 접합·주름 단위가 아니다. handwear=장갑, legwear=다리 의복, footwear=신발이다.",
    accessory: "headwear/earwear/eyewear/neckwear/tail/wings/objects 중 실제 요청 품목에 해당하는 것만 유효하다. 클래스만으로 정확한 장식 본체·고정점·내부 움직임 파츠를 인증할 수 없다."
  };
  const modes = {
    live2d_bust_up: "Live2D 방송용 바스트업: 큰 두상, 머리~상복부, 양팔과 양손가락 끝. 다리·발·골반 파츠 금지.",
    live2d_upper: "Live2D 상반신: 머리~허리, 양어깨·팔·손. 다리·발 파츠 금지.",
    live2d_full: "Live2D 전신: 머리~양발까지. BODY에서 좌우 다리·무릎·발/신발 경계를 추가 검사.",
    inochi2d_upper: "Inochi2D 상반신: 머리~허리, 팔·손 포함. Cubism 파라미터/ArtMesh로 납품하는 것이 아니라 Inochi용 PSD/노드 후처리.",
    inochi2d_full: "Inochi2D 전신: 머리~양발까지. 하체·관절 세분화 필요, Inochi 네이티브 리깅은 별도.",
    "3d": "3D 캐릭터용 전후좌우/다각도 참고 그림. See-through 2D PSD 분리로 VRM 메시를 만들 수 없다."
  };
  function contract(mode,asset) {
    if(!(mode in modes)||!(asset in expected))throw Error("invalid");
    const is3d = mode==="3d",full=mode.endsWith("full");
    const notes=is3d
      ? asset==="body" ? "실제 3D 메시·UV·본·검증된 VRM은 3D 재구성/Blender 후처리에서만 산출. 원화 AI는 다각도 참조로 제한."
      : asset==="accessory" ? "기존 VRM과 명시된 부착 위치가 있을 때만 액세서리 메시 생성 경로를 실행한다. 2D 장식 PSD를 VRM 액세서리로 위장하지 않는다."
      : "현행 3D 독립 HAIR/OUTFIT의 기존 VRM 자동 결합 엔진은 미지원. 다각도 참조 그림만 제작하고 3D 완성 성공을 선언하지 않는다."
      : asset==="body" ? "원본 BODY는 민머리이며 의상·장식·머리카락 픽셀이 없어야 한다. 얼굴·목·몸통·팔·손 피부 기본색은 동일하게 유지한다."
      : asset==="hair" ? "외부 기준 BODY는 위치 참조 전용. 원화에는 머리카락만 두고 얼굴/눈/몸통 픽셀을 섞지 않는다."
      : asset==="outfit" ? "기준 BODY는 정렬 참조로만 이용. 실제 옷과 필요한 안감/소매만, 피부/눈/머리카락 픽셀 금지."
      : "사용자가 요청한 장식 단 한 종류만. 소품 유형을 모르거나 여러 후보가 섞이면 임의로 headwear 등으로 결정하지 않고 품목 확인/수정 필요.";
    let stage;
    if(is3d){
      stage="See-through V3 = 사용 금지 (3D VRM 경로가 아님). 3D 참고도 입력 검사와 3D 전용 모델링 경로만 사용.";
    }else if(asset==="body"){
      stage="실행 경로: 원화 ZIP 형식/시점 검사 → See-through V3의 body/head 2단계 NF4 추론 → 실제 PSD·관측된 태그 검사 → 필요하면 공식 left/right 및 depth 분할 → 전용 눈·관절 정밀 마스크/가림 면 보정 → 개별 RGBA·PSD·합성 검수. V3에서 얻은 눈 의미 영역은 좌우 각각 재검증한다.";
    }else{
      stage="실행 경로: 독립 자산 PNG의 진짜 알파가 있으면 보존; 아니면 단색 배경에서 실물 전경 마스크를 검사해 추출 → 독립 자산 PSD 1개 후보 → 별도 세부 분리·가림 면 보정 필요. **이 자산만 있는 PNG에는 See-through V3 전체 캐릭터용 head crop을 실행하지 않는다.** V3의 의미 태그는 캐릭터 전체 PSD가 별도로 제공된 경우의 참고 카테고리일 뿐이다.";
    }
    const suffix=(asset==="body"&&full)? " Live2D/Inochi2D 전신에만 좌우 골반·허벅지·정강이·발 파츠도 추가한다.":"";
    return `## [MODE_ASSET_SEETHROUGH_V3_ROUTING_V6]
### ${mode} / ${asset} — 24개 자산별 실제 분리 경로
**${is3d ? "3D 다각도 원화와 후속 3D 모델링을 구분한다." : "V5의 GPT 원화 역할을 유지하며 후속 2D 분리 단계의 자산별 기준을 지정한다."}** 모드·자산을 서로 바꿔 처리하면 실패다.
- 작업 범위: ${modes[mode]}
- 대상 경계: ${notes}
- **See-through V3의 실제 기본 태그 중 이 자산 관련 항목:** ${is3d ? "사용하지 않음" : assetV3[asset].join(", ")}. 23개 태그 이외의 파츠 명칭을 모델이 직접 출력한다고 간주하지 않는다.
- **실제 후속 세부 분리·검수 대상:** ${is3d?"2D RGBA 분리 대상 없음; 3D 전용 다각도·모델링 검수":expected[asset]+suffix}
- **V3만으로 불가능/불충분:** ${is3d?"2D PSD는 3D 메시·스키닝·텍스처·VRM을 대체할 수 없다.":missingV3[asset]}
- **어떤 엔진이 실제 수행:** ${stage}
- **완성 조건:** 이미지 생성 GPT가 한 장짜리 가짜 파츠 시트를 만들면 실패. See-through 결과 PSD만 생성되거나 레이어 이름/개수만 맞으면 **분리 성공 아님**. 실제 움직일 파츠의 서로 다른 원본 RGB/알파/레이어/가려진 면이 검증돼야 한다. 실패 항목은 해당 파츠만 정밀 분리·인페인팅하여 재검사하고, 전체 원화를 매번 재생성하지 않는다.
- 3D HAIR/OUTFIT처럼 제작 엔진이 없는 경우 또는 독립 2D 자산의 세부 분리가 남아 있으면 \`NOT_YET_RIG_READY\`로 명시한다. 중간 PSD를 완성된 방송 모델로 제출 금지.
- 경로 규정의 코드 기준: \`tools/vts_segmentation_profiles.py\`. Live2D/Inochi2D 실행은 \`notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb\`의 모드/자산 선택을 따른다.
## [/MODE_ASSET_SEETHROUGH_V3_ROUTING_V6]`;
  }
  return {contract};
})()