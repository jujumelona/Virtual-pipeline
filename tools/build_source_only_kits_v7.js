function generate(mode,asset){
  const M={
    face:["공통 FACE (제작 모드·프레이밍 독립)","얼굴·귀·턱·목까지만. 바스트업·상반신·전신·2D 엔진별 FACE 재생성 없음"],
    live2d_bust_up:["Live2D 방송 바스트업","머리부터 상복부까지, 양어깨·팔·양손 손가락 끝 포함. 골반·다리·발 제외"],
    live2d_upper:["Live2D 상반신","머리부터 허리 윗부분까지, 어깨·양팔·양손 포함. 다리·발 제외"],
    live2d_full:["Live2D 전신","머리부터 발끝까지, 6등신 애니풍 비율. 양팔·양손·다리·발 모두 포함"],
    inochi2d_upper:["Inochi2D 상반신","머리부터 허리 윗부분까지, 어깨·양팔·양손 포함. 다리·발 제외"],
    inochi2d_full:["Inochi2D 전신","머리부터 발끝까지, 6등신 애니풍 비율과 사지 관절 연결 유지"],
    "3d":["3D VRM 참조도","같은 캐릭터의 실제 앞·뒤·좌·우 및 대각 4방향 참조 그림"]
  };
  const A={
    character:["CHARACTER 완성 캐릭터 2D 원화","3D 형상 복원용으로 동일 캐릭터의 얼굴·헤어·옷을 입은 전신·팔·손·다리를 일체로 그린다. 별도 FACE·해부학적 BODY 자산을 생성하지 않는다.","모든 시점에 동일한 성인 애니 캐릭터 얼굴·헤어·의상·신발·소품을 완전 착의 상태로 포함한다.","정면·뒤·좌·우·대각의 완성 2D 캐릭터 원화를 실제 서로 다른 방향으로 그린다. 3D 메시/VRM 리깅은 후속 3D 작업이 담당한다"],
    face:["FACE 얼굴·목 전용","성인 애니 VTuber 얼굴(민머리·눈·코·입·귀·턱)과 목만 생성한다. 몸통·가슴·복부·어깨·팔·손·의상은 생성하지 않는다.","얼굴·귀·두피·목 피부톤 #F2D4BE 통일. 2~3단 셀 명암, 큰 주황 홍채, 자연스러운 U형 턱. 목은 후속 의상 목깃 속에 들어갈 부분만 남긴다.","실제 정면·좌우 45도·측면 90도·상하 고개 각도의 얼굴·귀·턱·목 투영을 그린다"],
    hair:["HAIR 헤어 원화","앞머리·양옆 머리·뒷머리·움직일 가닥만. 얼굴·눈·피부·몸통·의상·장신구를 결과 이미지에 그리지 않는다.","기존 FACE의 두상 원점과 크기에 맞춘다. FACE가 없다면 공통 캔버스와 두상 앵커를 정의하되 기존 캐릭터와 정합됐다고 주장하지 않는다.","모근, 앞·옆·뒷머리와 가려진 뒷머리 형상을 다각도 참고 원화에 표현한다. 끊어진 머리 부품 배치 시트 금지"],
    outfit:["OUTFIT 착의 몸통·팔·손 원화","선택된 의상을 입은 몸통·양어깨·상완·전완·양손을 제작한다. 전신 모드라면 옷을 입은 다리와 신발까지 포함한다. 얼굴·눈·귀·민머리 두상·헤어·독립 소품은 생성하지 않는다.","기준 FACE 목 끝에 옷깃을 정렬한다. 기본 의상은 불투명 무광 긴팔 작업복. 몸통·팔은 모두 옷감이 덮고, 손 피부만 FACE_SKIN_BASE=#F2D4BE 색상을 사용한다.","실제 옷깃·소매·손목·옷감 가림을 그린다. 몸통 정면 고정, 얼굴 고개만 45도 돌릴 때 목과 의상 연결이 끊기지 않도록 여유를 둔다. 의상을 벗은 신체 원화는 만들지 않는다"],
    accessory:["ACCESSORY 단일 소품 원화","사용자가 지정한 한 종류 소품만. 피부·얼굴·헤어·의복·요청하지 않은 다른 소품 제외.","FACE와 HAIR의 부착 앵커 위치를 참고한다. 기준 인물 이미지 픽셀은 결과 PNG에 포함하지 않는다.","요청 소품의 실제 옆 두께, 고정부, 가려진 후면, 이동하는 날개·가닥이 있다면 각도별 참조 원화에서 보여준다"]
  };
  if(!M[mode]||!A[asset] || (mode==="face")!==(asset==="face") || (mode==="3d"&&!["character","accessory"].includes(asset)) || (mode!=="3d"&&asset==="character"))throw Error("Invalid kit "+mode+"/"+asset);
  const [title,scope]=M[mode], [label,owned,palette,detail]=A[asset],is3d=mode==="3d";
  const v2={
    face:["face_front","head_three_quarter_L","head_three_quarter_R","head_profile_L","head_profile_R","head_pitch_up","head_pitch_down","neck_underpaint","face_neck_overlap"],
    hair:["hair_front","hair_three_quarter_L","hair_three_quarter_R","hair_profile_L","hair_profile_R","hair_back","hair_underlayers","hair_motion_clearance"],
    outfit:["outfit_front","outfit_three_quarter_L","outfit_three_quarter_R","outfit_profile_L","outfit_profile_R","outfit_back","outfit_inside_seams","outfit_joint_clearance"],
    accessory:["accessory_front","accessory_three_quarter_L","accessory_three_quarter_R","accessory_profile_L","accessory_profile_R","accessory_back","accessory_attachment_anchor","accessory_occlusion"]
  };
  const v3=["front","front_three_quarter_L","left","back_three_quarter_L","back","back_three_quarter_R","right","front_three_quarter_R","detail_occlusion"];
  const files=mode==="face"
    ? ["outputs/master.png",...v2.face.map(x=>"reference_views/"+x+".png"),
       "expression_refs/mouth_closed.png","expression_refs/mouth_open.png"]
    : is3d?v3.map(x=>"views/"+asset+"_"+x+".png")
    : ["outputs/master.png",...v2[asset].map(x=>"reference_views/"+x+".png")];
  const fl=files.map(s=>"- `"+s+"`").join("\n"),result=mode==="face"?"face__ARTWORK.zip":mode+"__"+asset+"__ARTWORK.zip";
  const context=`**선택:** ${title} / ${label}\n\n**구도:** ${asset==="face"?"두상에서 목 끝까지만. 몸통·어깨·팔·손 제외":scope}.\n\n**자산 경계:** ${owned}\n\n**색·위치:** ${palette}\n\n**원화 세부:** ${detail}`;
  const stage="**SOURCE_ART_ONLY_V7 — 이미지 생성 AI 전용.** 이 ZIP에서는 완성 원화와 여러 시점의 참고 원화 PNG만 제작한다. 잘라낸 파츠 PNG, 각 파츠별 재생성, 마스크, 레이어 PSD, 메시, 리깅, MOC3, VRM 완성을 이미지 생성 AI에 절대 요구하지 않는다. **실제 파츠 분리·PSD 생성·리깅은 후속 Colab 노트북의 책임**이며, 노트북의 미구현 기능을 성공으로 표시해서는 안 된다.";
  const composition=mode==="face"?"2D FACE는 얼굴·목만 제작한다. 3D 캐릭터는 3d__character.zip에서 완성된 의상 착용 캐릭터 전체의 2D 원화를 제작한다.":is3d?"각 참조 PNG는 실제 다른 방향에서 그린 그림이어야 하며 정면 복사·거울 반전으로 방향을 위조하지 않는다. 8방향 및 가려진 부분 참조 한 장을 각각 저장한다.":"한 파일에 한 방향의 원화만 담는다. 정면 마스터와 정면·3/4·측면·상하 고개 참고는 **동일 크기 캔버스·동일 머리 스케일·같은 중심 앵커**를 유지한다. `reference_views`는 움직임·가림의 참고 그림이며 파츠 이미지가 아니다.";
  const bg="실제 RGBA 투명 배경을 만들 수 있으면 사용한다. 불가능하면 균일한 흰색/단색 배경과 충분한 테두리 여백을 사용한다. 정면/참고 그림에 텍스트·워터마크·도형 표식·콜라주·빛 장식과 다른 자산 픽셀을 넣지 않는다.";
  const ref=mode==="face"?"Live2D https://docs.live2d.com/en/cubism-editor-tutorials/psd/ · Inochi2D https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html . 2D FACE는 3D VRM 복원과 분리되는 공통 얼굴/목 원화다.":is3d?"VRoid Studio https://vroid.com/en/studio : 형태·시점 참고만. VRM 생성은 이미지 AI의 산출 요구가 아니다.":mode.startsWith("inochi2d")?"Inochi2D 공식 문서 https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html 및 예제 https://github.com/Inochi2D/example-models : 시각 참고만.":"Live2D 공식 예제 https://www.live2d.com/en/learn/sample/haru-receptionist/ 와 원화 안내 https://docs.live2d.com/en/cubism-editor-tutorials/psd/ : 선화·구도·연결을 참고하고 기존 캐릭터를 복제하지 않는다.";
  const titles=["00_MASTER_FIRST.md","00_DELIVERY_AND_RECHECK.md","00_READ_FIRST.md","01_COMMON_RULES.md","02_ADVANCED_PARTS.md","03_MODE_RULES.md","04_OUTPUT_FILES.md","05_OFFICIAL_REFERENCES.md","06_ADVANCED_OFFICIAL_COMMUNITY.md","07_REVIEW_BEFORE_FINAL_ZIP.md","08_PRACTICAL_TIPS.md","09_VISUAL_ART_QUALITY.md","10_ANIME_STYLE.md","11_OFFICIAL_IMAGE_EXAMPLES.md"];
  const out=[
    `# 마스터 제작 계약\n\n${stage}\n\n${context}\n\n${composition}\n\n원화 결과 ZIP은 \`${result}\`.`,
    `# 납품과 재검사\n\n${stage}\n\n허용되는 실제 PNG 파일:\n\n${fl}\n\n동일 원화를 여러 각도로 이름만 바꿔 납품하지 않는다. 부족한 이미지만 다시 그린다. 최종 ZIP 이름은 \`${result}\`.`,
    `# 생성 시작 전 확인\n\n${stage}\n\n${context}\n\n사용자가 준 이미지가 있다면 그 캐릭터의 얼굴·눈·기본색·디자인을 우선 확인한다. 기존 FACE 기준이 없는 신규 자산은 새 디자인으로 생성 가능하지만 기존 몸체와 정확히 맞는다고 주장하지 않는다.`,
    `# 공통 원화 규칙\n\n${context}\n\n${composition}\n\n${bg}\n\n${stage}`,
    `# 원화 형태·정밀 표현 규칙\n\n${detail}\n\n${palette}\n\n${composition}\n\n한 장의 완성 그림에서 윤곽·색면·접합 관계가 자연스럽게 보이도록 그린다. 눈·소매·모발을 분리 PNG처럼 따로 나열하지 않는다.`,
    `# 구도 규칙\n\n${context}\n\n각 시점이 같은 캐릭터의 같은 자산을 보여야 한다. 몸은 정면이고 고개만 회전한 참고 그림을 요청한 경우 몸통까지 뒤집거나 회전하지 않는다. 배경·다른 자산은 제거한다.`,
    `# 출력 파일 계약\n\n${stage}\n\nZIP: \`${result}\`\n\n${fl}\n\nPNG 파일 이름·폴더 이름을 정확히 지킨다. 그 외의 파츠 파일, PSD·레イヤ 순서 파일, JSON·가짜 MOC3/VRM은 넣지 않는다.`,
    `# 공식 참고\n\n${ref}\n\n참고 링크를 실제로 열지 못했다면 봤다고 주장하지 않는다. 원화 제작은 사용자 기준 이미지와 SOURCE_ART_ONLY_V7 계약을 따라 진행한다.`,
    `# 다각도와 가려진 부분 원화\n\n${composition}\n\n${detail}\n\n${bg}\n\n이 그림들은 Colab 제작 과정에서 확인할 참고 시점이다. 여기에서 마스크/PSD/파츠 PNG를 납품하지 않는다.`,
    `# 원화 품질·납품 검수\n\n${context}\n\n원화 1장당 1시점, 정확한 자산 범위, 색상 통일, 눈과 얼굴 형태, 목·어깨 등 연결, 참조 시점의 방향과 동일성, 이미지 크기, 배경 조건을 육안으로 검사한다. 미완성 원화만 재생성한다. 노트북의 실제 분리 품질까지 이미지 AI가 검사했다고 주장하지 않는다.`,
    `# 실제 생성 팁\n\n${detail}\n\n${bg}\n\n선화와 색 경계를 깔끔하게 하되 그림을 여러 조각으로 떼어 놓지 않는다. 원화 생성 AI의 작업이 끝나면 그대로 \`${result}\`를 노트북에 업로드한다.`,
    `# 시각 품질\n\n${title}, ${label}. 과장된 실사 해부학 대신 크고 예쁜 애니 눈·짧고 둥근 얼굴·가느다란 선 끝과 정돈된 2~3톤 셀 셰이딩을 적용한다.\n\n${palette}\n\n${owned}`,
    `# 애니 스타일\n\n짧고 둥근 얼굴, 선명한 눈, 일본 애니 VTuber풍 일정한 선 굵기 변화, 2~3단계 셀 명암, 깨끗한 단색 표면, 정면·측면 시각 일관성. 실사 피부질감·인체 해부학 디테일·텍스트 표식 금지.\n\n${context}`,
    `# 참고 이미지 자료\n\n${ref}\n\n예제 캐릭터의 디자인 자체를 베끼지 않는다. ${title}에서 필요한 ${label}만 제작한다. 출력 경로는 04_OUTPUT_FILES.md의 실제 PNG 목록과 일치해야 한다.`
  ];
  if(out.length!==14)throw Error("14 docs expected");
  const extra = asset==="character" ? "\n\n## 3D_COMPLETE_CHARACTER_FROM_2D_V1\n한 인물의 얼굴·헤어·의상 입은 전신을 실제로 모두 그린 2D 다각도 원화만 생성. 후속 3D 모델링이 별도 진행된다.\n" : asset==="face"
    ? "\n\n## FACE_ONLY_V1\n얼굴·눈·귀·코·입·턱·목만 그린다. 몸통·가슴·어깨·팔·손·복부 및 의상은 어떤 참고 이미지에도 그리지 않는다.\n"
    : asset==="outfit"
    ? "\n\n## OUTFIT_CLOTHED_BODY_V1\n얼굴을 제외한 몸통·양팔·양손을 실제 의상을 착용한 모습으로 그린다. 의복은 불투명하고 목깃과 소매가 확실하다. 신체를 벗겨낸 원화는 만들지 않는다.\n"
    : "\n\n## ASSET_ONLY_V1\nFACE·OUTFIT을 복제하지 않고 선택한 자산만 그린다.\n";

  const facePrompt = [
    "【PRIMARY MASTER IMAGE PROMPT / 최우선】",
    "Professional original Japanese anime VTuber character concept art, premium 2D Live2D-ready adult anime face and neck ONLY, elegant youthful adult expression, clean bald scalp as a base for separate hair, beautifully drawn rounded short U-shaped face and natural chin, gorgeous large amber-orange anime eyes containing detailed sclera, eyelid shapes, refined upper and lower eyelashes, layered irises, pupils and reflective highlights, subtle natural eyebrows, delicate anime nose and soft expressive mouth, realistically structured-in-anime ears, well-proportioned jaw-to-neck connection, subtle peach blush, uniform soft-peach skin #F2D4BE on head, ears and neck, polished thin line art with graceful tapered stroke weights and carefully controlled two-to-three-tone cel shading. High-end streaming anime avatar illustration, NOT a diagram.",
    "Negative: kindergarten clipart, minimalist icon, flat oval head with sticker eyes, stick or cylindrical neck, primitive SVG circles, generic mannequin, plastic 3D render, photoreal skin, simple line smile, emoji, cartoon mascot, sloppy profiles, detached ears, hair, clothes, shoulders, torso, arms, multiple panels, labels or watermarks.",
    "정면 outputs/master.png를 **한 장의 고품질 애니 원화**로 먼저 그린다. 실제로 이 품질이 합격하기 전에는 나머지 11장의 제작을 시작하지 않는다."
  ].join("\n\n");
  const faceDesign = [
    "【VTUBER_FACE_ART_QUALITY_V2】 '버추얼'은 방송에서 얼굴·눈·입이 움직이는 아름다운 2D 일본 애니 캐릭터를 뜻한다. 동그라미·타원·직선 도형을 합성한 교육용 대머리 마네킹이 아니다.",
    "미형: 자연스러운 이마·두상·뒷통수, 짧고 부드러운 U형 턱, 균형 잡힌 눈의 크기와 간격, 작은 코·입, 실제 구조를 이해한 귀와 턱 아래로 유기적으로 이어지는 목. 성인 애니 VTuber 얼굴 원화의 유려한 곡선과 아름다운 비율을 유지.",
    "눈 필수: 양눈 각각 흰자·윗/아랫 눈꺼풀·속눈썹·다층 황금 주황색 홍채·동공·빛 반사 하이라이트. 주황 점 두 개나 정면 눈 스티커로 대체하지 않는다.",
    "선화: 가늘고 깨끗한 선 + 위치별 굵기 변화/끝의 테이퍼링, 볼의 은은한 홍조, 얼굴·두피·귀·목에 같은 피부색 #F2D4BE와 세련된 2~3단계 셀 쉐이딩. 실사·해부학적 목근육 디테일 금지.",
    "얼굴만 그리되 머리가 빠진 인형처럼 보여서는 안 된다. 후속 HAIR를 얹을 두상 볼륨은 자연스럽고, 목은 후속 OUTFIT 목깃으로 이어질 수 있게 그린다.",
    "출력은 image generation으로 실제 일러스트를 제작한다. Python/SVG/Cairo 원/타원/사각형/펜선 도형을 조립해 그럴듯한 아바타처럼 꾸미는 것은 **제작 실패**.",
    "FACE 원화에는 어깨·몸통·팔·손·옷·헤어·액세서리가 없어야 한다. 파츠 분리·PSD·마스크·리깅은 후속 Colab의 책임이다."
  ].join("\n- ");
  const faceAngles = [
    "master/front: 실제 같은 인물의 정면 애니 얼굴·목. master 합격 원화를 face_front 기준으로 재사용할 수 있지만 해상도/배치/캐릭터 정체성은 바꾸지 않는다.",
    "three_quarter_L/R: 두개골·코·턱·귀가 실제 약 45도 회전. 가까운 눈과 먼 눈의 크기/형태가 바뀐다. 정면 그림에서 눈/코 위치만 옮기거나 단순 거울반전하면 실패.",
    "profile_L/R: 약 90도 측면. 한쪽 눈만 측면 형태로 보이고 이마/코끝/입/턱/귀/뒤통수 실루엣이 실제 애니 측면으로 바뀐다. 눈이 두 개 보이거나 옆으로 움직인 정면 얼굴이면 실패.",
    "pitch_up: 턱밑 면과 코/눈 원근이 변하는 실제 상향 회전. pitch_down: 정수리와 이마 면적·눈·턱 원근이 변하는 실제 하향 회전. 이미지를 위아래 이동만 시킨 형태면 실패.",
    "neck_underpaint: 얼굴과 턱 뒤 목이 실제로 이어지는 완성 원화 참고. 단색 마스크 아님. face_neck_overlap: 3/4 턱과 목의 자연스러운 전후 가림 완성 원화. 원통형 목 금지.",
    "mouth_closed / mouth_open: 같은 정면 얼굴의 입만 자연스러운 다문/벌린 발화 형태로 다르고 얼굴형·눈매·눈동자·피부색은 일관. 벌린 입에는 자연스러운 입안·혀를 그린다."
  ].join("\n- ");
  const faceWorkflow = [
    "【작업 순서】 master.png 한 장 제작 → 시각적 미형/애니 품질 합격 → 동일 인물 시점별 한 장씩 독립 제작 → 모든 12장 확인 → ZIP 납품.",
    "12칸 컨택트시트를 만들어 잘라서 PNG 파일 수를 맞추거나 같은 그림을 이름만 바꾸는 것 금지. 한 파일=한 고해상도 시점. 권장 단일 캔버스 1200×1600 이상, 동일 두상 크기/중심 앵커, 머리와 목 전체가 크게 보이도록.",
    "원화 12장의 파일명·색상·해상도가 맞아도 화풍이 '단순 벡터 얼굴'이면 전체 제작 실패. 선화/눈/턱/목이 전문 VTuber 수준이 아니라면 다른 시점을 만들지 말고 마스터부터 다시 생성한다.",
    "PNG 배경은 실제 투명 RGBA를 우선. 투명 출력이 안 되면 균일 단색으로 두고 투명하다고 주장하지 않는다."
  ].join("\n- ");
  const faceQC = [
    "[ ] 마스터의 얼굴이 전문 VTuber 캐릭터로 보이고, 저품질 타원형 교육용 캐릭터·도형 클립아트가 아닌가?",
    "[ ] 양눈의 흰자·속눈썹·눈꺼풀·다층 주황 홍채·동공·하이라이트가 실제로 정교하게 보이는가?",
    "[ ] 귀·턱·목·뒤통수가 조형적으로 자연스럽고, 목이 잘린 직사각 기둥이 아닌가?",
    "[ ] 좌우 45°·90°와 상하 회전이 실제 두개골/안면 원근을 바꾸는가?",
    "[ ] 표정 2장도 같은 얼굴/눈매를 유지하는가? 모든 파일이 독립적인 고해상도 단일 원화인가?",
    "[ ] FACE 외 자산 픽셀 없음, 기준 피부색 통일, 생성 AI가 파츠 분리/PSD/리깅 완료했다고 주장하지 않음?",
    "하나라도 실패라면 최종 ZIP 완성 선언 금지. 컴퓨터로 파일 개수·CRC만 검사한 것은 화풍 검증이 아니다."
  ].join("\n- ");
  const focus = [
    [facePrompt,faceDesign,faceWorkflow,faceQC],
    [faceWorkflow,faceAngles,faceQC],
    [facePrompt,faceDesign],
    [faceDesign,faceWorkflow],
    [faceDesign,faceAngles],
    [faceAngles,faceDesign],
    [faceWorkflow,faceAngles],
    [facePrompt,faceDesign],
    [faceAngles,faceDesign],
    [faceQC,faceAngles],
    [facePrompt,faceWorkflow],
    [faceDesign,faceQC],
    [facePrompt,faceDesign],
    [faceDesign,faceQC]
  ];
  const docs=out.map((text,i)=>({
    name:titles[i],
    text:(asset==="face" ?
      "# 고품질 애니 VTuber FACE 원화 필수 — 원시 도형 얼굴 금지\n\n"+
      focus[i].join("\n\n---\n\n")+"\n\n---\n\n" : "")+text+extra+"\n"
  }));

  const enc=s=>{const a=unescape(encodeURIComponent(s)),b=new Uint8Array(a.length);for(let i=0;i<a.length;i++)b[i]=a.charCodeAt(i);return b};
  const table=new Uint32Array(256);for(let i=0;i<256;i++){let v=i;for(let j=0;j<8;j++)v=v&1?0xedb88320^(v>>>1):v>>>1;table[i]=v>>>0}
  const crc=a=>{let v=0xffffffff;for(let x of a)v=table[(v^x)&255]^(v>>>8);return (v^0xffffffff)>>>0};
  const l16=(arr,x)=>arr.push(x&255,x>>>8&255);
  const l32=(arr,x)=>arr.push(x&255,x>>>8&255,x>>>16&255,x>>>24&255);
  let bytes=[],central=[],offset=0;
  for(const doc of docs){const name=enc(doc.name),body=enc(doc.text),sum=crc(body),header=[];l32(header,0x04034b50);l16(header,20);for(let i=0;i<4;i++)l16(header,0);l32(header,sum);l32(header,body.length);l32(header,body.length);l16(header,name.length);l16(header,0);bytes.push(...header,...name,...body);
    const c=[];l32(c,0x02014b50);l16(c,20);l16(c,20);for(let i=0;i<4;i++)l16(c,0);l32(c,sum);l32(c,body.length);l32(c,body.length);l16(c,name.length);for(let i=0;i<4;i++)l16(c,0);l32(c,0);l32(c,offset);central.push(...c,...name);offset=bytes.length}
  const start=bytes.length;bytes.push(...central);const end=[];l32(end,0x06054b50);l16(end,0);l16(end,0);l16(end,14);l16(end,14);l32(end,central.length);l32(end,start);l16(end,0);bytes.push(...end);
  const abc="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",a=new Uint8Array(bytes),res=[];
  for(let i=0;i<a.length;i+=3){let x=a[i],y=a[i+1]||0,z=a[i+2]||0;res.push(abc[x>>2]+abc[(x&3)<<4|y>>4]+(i+1<a.length?abc[(y&15)<<2|z>>6]:"=")+(i+2<a.length?abc[z&63]:"="))}
  return {b64:res.join(""),size:a.length,doc_count:docs.length,files,mode,asset,zip:result};
}

// Canonical reproducible output for 18 instruction archives: 2D FACE 1, 2D scoped 15, 3D 2.
if (typeof require !== 'undefined' && require.main === module) {
  const fs = require('fs'), path = require('path');
  const root = path.join(__dirname, '..', 'docs', 'image_ai_kits_v2', 'zips');
  const modes = ['live2d_bust_up', 'live2d_upper', 'live2d_full', 'inochi2d_upper', 'inochi2d_full', '3d'];
  const assets = ['hair', 'outfit', 'accessory'];
  const targets = [['face','face'], ...modes.flatMap(mode=>(mode==='3d'?['character','accessory']:assets).map(asset=>[mode,asset]))];
  const check = process.argv.includes('--check');
  if (!check) fs.mkdirSync(root, {recursive: true});
  let validated = 0;
  for (const [mode,asset] of targets) {
    const art = generate(mode, asset);
    if (art.doc_count !== 14) throw Error('incorrect document count: ' + art.zip);
    const bytes = Buffer.from(art.b64, 'base64');
    const target = path.join(root, mode === 'face' ? 'face.zip' : mode + '__' + asset + '.zip');
    if (check) {
      if (!fs.existsSync(target) || !fs.readFileSync(target).equals(bytes)) throw Error('stale instruction ZIP: ' + target);
    } else fs.writeFileSync(target, bytes);
    validated += 1;
  }
  const published = fs.readdirSync(root).filter(name=>name.endsWith('.zip'));
  const required = new Set(targets.map(([mode,asset])=>mode==='face'?'face.zip':mode+'__'+asset+'.zip'));
  const stale = published.filter(name=>!required.has(name));
  if (check && (stale.length || published.length!==required.size)) throw Error('stale/duplicate kit ZIPs: '+stale.join(', '));
  if (!check) for (const name of stale) fs.unlinkSync(path.join(root,name));
  console.log((check ? 'PASS reproducible' : 'Generated') + ': ' + validated + ' source-only ZIPs / ' + validated * 14 + ' MDs');
}
