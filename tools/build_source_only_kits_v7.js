function generate(mode,asset){
  const M={
    live2d_bust_up:["Live2D 방송 바스트업","머리부터 상복부까지, 양어깨·팔·양손 손가락 끝 포함. 골반·다리·발 제외"],
    live2d_upper:["Live2D 상반신","머리부터 허리 윗부분까지, 어깨·양팔·양손 포함. 다리·발 제외"],
    live2d_full:["Live2D 전신","머리부터 발끝까지, 6등신 애니풍 비율. 양팔·양손·다리·발 모두 포함"],
    inochi2d_upper:["Inochi2D 상반신","머리부터 허리 윗부분까지, 어깨·양팔·양손 포함. 다리·발 제외"],
    inochi2d_full:["Inochi2D 전신","머리부터 발끝까지, 6등신 애니풍 비율과 사지 관절 연결 유지"],
    "3d":["3D VRM 참조도","같은 캐릭터의 실제 앞·뒤·좌·우 및 대각 4방향 참조 그림"]
  };
  const A={
    body:["BODY 신체 기본 원화","성인(20세 이상) 애니 VTuber의 민머리 얼굴·눈·귀·코·입·목·손·몸통과 사지의 위치·관절을 제작한다. 몸통과 팔·다리는 비성적·완전 커버 작업용 보호 슈트 착용 상태로 묘사한다. 머리카락·패션 의상·장신구는 새로 디자인하지 않는다.","FACE_SKIN_BASE=#F2D4BE (사용자가 다른 피부색을 지정하면 전 뷰에서 함께 변경). 얼굴·귀·두피·목·양손 및 커버 아래의 BODY 기준 피부색은 모두 동일하다. 이미지에 보이는 가슴·등·배·어깨·팔·하체는 불투명 청회색(#526B83)의 중립적인 전신 작업용 슈트로 완전히 덮고, 목둘레·소맷단·발목에는 명확한 의복 경계선을 그린다. 몸통의 윤곽은 비해부학적 애니 스타일로 유지한다.","성인 VTuber 특유의 짧고 둥근 얼굴과 큰 애니 눈, 뚜렷한 주황 홍채·흰자·속눈썹, 간결한 코·입. 전문 일러스트 수준의 선화·2~3단계 셀 명암·목/어깨 연결과 자연스러운 뒤통수, 올바른 측면 투영. 단순 도형 프록시는 제작 실패로 판정"],
    hair:["HAIR 헤어 원화","앞머리·양옆 머리·뒷머리·움직일 가닥만. 얼굴·눈·피부·몸통·의상·장신구를 결과 이미지에 그리지 않는다.","기존 BODY의 두상 원점과 크기에 맞춘다. BODY가 없다면 공통 캔버스와 두상 앵커를 정의하되 기존 캐릭터와 정합됐다고 주장하지 않는다.","모근, 앞·옆·뒷머리와 가려진 뒷머리 형상을 다각도 참고 원화에 표현한다. 끊어진 머리 부품 배치 시트 금지"],
    outfit:["OUTFIT 의상 원화","지정한 의상 옷감·칼라·양 소매·밑단과 그 옷에 붙은 장식만. 신체 피부·눈·얼굴·헤어·다른 액세서리 제외.","BODY의 기존 캔버스·목둘레·어깨·허리 위치를 참조한다. 인체는 참조용일 뿐 결과 PNG에는 의상만 나타난다.","소매·목둘레·앞뒤 판·천의 안쪽·가림과 옷의 앞뒤 구조를 각도별로 자연스럽게 원화에 표현한다"],
    accessory:["ACCESSORY 단일 소품 원화","사용자가 지정한 한 종류 소품만. 피부·얼굴·헤어·의복·요청하지 않은 다른 소품 제외.","BODY와 HAIR의 부착 앵커 위치를 참고한다. 기준 인물 이미지 픽셀은 결과 PNG에 포함하지 않는다.","요청 소품의 실제 옆 두께, 고정부, 가려진 후면, 이동하는 날개·가닥이 있다면 각도별 참조 원화에서 보여준다"]
  };
  if(!M[mode]||!A[asset])throw Error("Invalid kit "+mode+"/"+asset);
  const [title,scope]=M[mode], [label,owned,palette,detail]=A[asset],is3d=mode==="3d";
  const v2={
    body:["body_front","head_three_quarter_L","head_three_quarter_R","head_profile_L","head_profile_R","head_pitch_up","head_pitch_down","neck_underpaint","body_joint_overlaps"],
    hair:["hair_front","hair_three_quarter_L","hair_three_quarter_R","hair_profile_L","hair_profile_R","hair_back","hair_underlayers","hair_motion_clearance"],
    outfit:["outfit_front","outfit_three_quarter_L","outfit_three_quarter_R","outfit_profile_L","outfit_profile_R","outfit_back","outfit_inside_seams","outfit_joint_clearance"],
    accessory:["accessory_front","accessory_three_quarter_L","accessory_three_quarter_R","accessory_profile_L","accessory_profile_R","accessory_back","accessory_attachment_anchor","accessory_occlusion"]
  };
  const v3=["front","front_three_quarter_L","left","back_three_quarter_L","back","back_three_quarter_R","right","front_three_quarter_R","detail_occlusion"];
  const files=is3d?v3.map(x=>"views/"+asset+"_"+x+".png"):["outputs/master.png",...v2[asset].map(x=>"reference_views/"+x+".png"),...(asset==="body"?["expression_refs/mouth_closed.png","expression_refs/mouth_open.png"]:[])];
  const fl=files.map(s=>"- `"+s+"`").join("\n"),result=mode+"__"+asset+"__ARTWORK.zip";
  const context=`**선택:** ${title} / ${label}\n\n**구도:** ${scope}.\n\n**자산 경계:** ${owned}\n\n**색·위치:** ${palette}\n\n**원화 세부:** ${detail}`;
  const stage="**SOURCE_ART_ONLY_V7 — 이미지 생성 AI 전용.** 이 ZIP에서는 완성 원화와 여러 시점의 참고 원화 PNG만 제작한다. 잘라낸 파츠 PNG, 각 파츠별 재생성, 마스크, 레이어 PSD, 메시, 리깅, MOC3, VRM 완성을 이미지 생성 AI에 절대 요구하지 않는다. **실제 파츠 분리·PSD 생성·리깅은 후속 Colab 노트북의 책임**이며, 노트북의 미구현 기능을 성공으로 표시해서는 안 된다.";
  const composition=is3d?"각 참조 PNG는 실제 다른 방향에서 그린 그림이어야 하며 정면 복사·거울 반전으로 방향을 위조하지 않는다. 8방향 및 가려진 부분 참조 한 장을 각각 저장한다.":"한 파일에 한 방향의 원화만 담는다. 정면 마스터와 정면·3/4·측면·상하 고개 참고는 **동일 크기 캔버스·동일 머리/몸 스케일·같은 중심 앵커**를 유지한다. `reference_views`는 움직임·가림의 참고 그림이며 파츠 이미지가 아니다.";
  const bg="실제 RGBA 투명 배경을 만들 수 있으면 사용한다. 불가능하면 균일한 흰색/단색 배경과 충분한 테두리 여백을 사용한다. 정면/참고 그림에 텍스트·워터마크·도형 표식·콜라주·빛 장식과 다른 자산 픽셀을 넣지 않는다.";
  const ref=is3d?"VRoid Studio https://vroid.com/en/studio : 형태·시점 참고만. VRM 생성은 이미지 AI의 산출 요구가 아니다.":mode.startsWith("inochi2d")?"Inochi2D 공식 문서 https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html 및 예제 https://github.com/Inochi2D/example-models : 시각 참고만.":"Live2D 공식 예제 https://www.live2d.com/en/learn/sample/haru-receptionist/ 와 원화 안내 https://docs.live2d.com/en/cubism-editor-tutorials/psd/ : 선화·구도·연결을 참고하고 기존 캐릭터를 복제하지 않는다.";
  const titles=["00_MASTER_FIRST.md","00_DELIVERY_AND_RECHECK.md","00_READ_FIRST.md","01_COMMON_RULES.md","02_ADVANCED_PARTS.md","03_MODE_RULES.md","04_OUTPUT_FILES.md","05_OFFICIAL_REFERENCES.md","06_ADVANCED_OFFICIAL_COMMUNITY.md","07_REVIEW_BEFORE_FINAL_ZIP.md","08_PRACTICAL_TIPS.md","09_VISUAL_ART_QUALITY.md","10_ANIME_STYLE.md","11_OFFICIAL_IMAGE_EXAMPLES.md"];
  const out=[
    `# 마스터 제작 계약\n\n${stage}\n\n${context}\n\n${composition}\n\n원화 결과 ZIP은 \`${result}\`.`,
    `# 납품과 재검사\n\n${stage}\n\n허용되는 실제 PNG 파일:\n\n${fl}\n\n동일 원화를 여러 각도로 이름만 바꿔 납품하지 않는다. 부족한 이미지만 다시 그린다. 최종 ZIP 이름은 \`${result}\`.`,
    `# 생성 시작 전 확인\n\n${stage}\n\n${context}\n\n사용자가 준 이미지가 있다면 그 캐릭터의 얼굴·눈·기본색·디자인을 우선 확인한다. 기존 BODY 참조가 없는 신규 자산은 새 디자인으로 생성 가능하지만 기존 몸체와 정확히 맞는다고 주장하지 않는다.`,
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
  const safety = asset==="body" ? "\n\n## SAFE_FULL_COVERAGE_BODY_V1\n성인(20세 이상) 방송용 애니 VTuber의 가족 친화적 제작 그림. 전체 캐릭터와 모든 참고 시점에서 상체·가슴·등·복부·골반·팔·다리에는 불투명 청회색(#526B83)의 비패션 작업용 보호 슈트를 그린다. 몸통의 목둘레와 팔 소맷단·발목단을 애니 스타일 선화로 분명하게 표현한다. 얼굴·목·손의 피부는 FACE_SKIN_BASE 색상으로 통일한다. 보호 슈트는 BODY 생성 시에만 쓰는 기본 보호 커버이며 별도 OUTFIT 디자인이나 파츠 원화 납품이 아니다. 후속 파이프라인에서 커버 안쪽 픽셀이 자동으로 생성된다고 가정하지 않는다. 정면 마스터·회전 시점·표정·관절 PNG 모두 동일한 커버를 적용한다. 예쁜 애니 전문 원화로 만들고 단순 도형 프록시는 불합격이다.\n" : "\n\n## SAFE_ASSET_ONLY_V1\n사람 캐릭터를 새로 그리지 않는다. 기존 BODY는 크기와 부착점만 참고하고 최종 그림에는 지정한 헤어·의상·소품 한 자산만 나타낸다. 투명 또는 균일한 단색 배경의 독립 자산 원화를 그린다.\n";
  const docs=out.map((text,i)=>({name:titles[i],text:text+safety+"\n"}));
  const enc=s=>{const a=unescape(encodeURIComponent(s)),b=new Uint8Array(a.length);for(let i=0;i<a.length;i++)b[i]=a.charCodeAt(i);return b};
  const table=new Uint32Array(256);for(let i=0;i<256;i++){let v=i;for(let j=0;j<8;j++)v=v&1?0xedb88320^(v>>>1):v>>>1;table[i]=v>>>0}
  const crc=a=>{let v=0xffffffff;for(let x of a)v=table[(v^x)&255]^(v>>>8);return (v^0xffffffff)>>>0};
  const l16=(arr,x)=>arr.push(x&255,x>>>8&255);
  const l32=(arr,x)=>arr.push(x&255,x>>>8&255,x>>>16&255,x>>>24&255);
  let bytes=[],central=[],offset=0;
  for(const doc of docs){const name=enc(doc.name),body=enc(doc.text),sum=crc(body),header=[];l32(header,0x04034b50);l16(header,20);for(let i=0;i<4;i++)l16(header,0);l32(header,sum);l32(header,body.length);l32(header,body.length);l16(header,name.length);l16(header,0);bytes.push(...header,...name,...body);
    const c=[];l32(c,0x02014b50);l16(c,20);l16(c,20);for(let i=0;i<4;i++)l16(c,0);l32(c,sum);l32(c,body.length);l32(c,body.length);l16(c,name.length);for(let i=0;i<5;i++)l16(c,0);l32(c,0);l32(c,offset);central.push(...c,...name);offset=bytes.length}
  const start=bytes.length;bytes.push(...central);const end=[];l32(end,0x06054b50);l16(end,0);l16(end,0);l16(end,14);l16(end,14);l32(end,central.length);l32(end,start);l16(end,0);bytes.push(...end);
  const abc="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",a=new Uint8Array(bytes),res=[];
  for(let i=0;i<a.length;i+=3){let x=a[i],y=a[i+1]||0,z=a[i+2]||0;res.push(abc[x>>2]+abc[(x&3)<<4|y>>4]+(i+1<a.length?abc[(y&15)<<2|z>>6]:"=")+(i+2<a.length?abc[z&63]:"="))}
  return {b64:res.join(""),size:a.length,doc_count:docs.length,files,mode,asset,zip:result};
}

// Canonical, reproducible output for all 24 instruction archives.
if (typeof require !== 'undefined' && require.main === module) {
  const fs = require('fs'), path = require('path');
  const root = path.join(__dirname, '..', 'docs', 'image_ai_kits_v2', 'zips');
  const modes = ['live2d_bust_up', 'live2d_upper', 'live2d_full', 'inochi2d_upper', 'inochi2d_full', '3d'];
  const assets = ['body', 'hair', 'outfit', 'accessory'];
  const check = process.argv.includes('--check');
  if (!check) fs.mkdirSync(root, {recursive: true});
  let validated = 0;
  for (const mode of modes) for (const asset of assets) {
    const art = generate(mode, asset);
    if (art.doc_count !== 14) throw Error('incorrect document count: ' + art.zip);
    const bytes = Buffer.from(art.b64, 'base64');
    const target = path.join(root, mode + '__' + asset + '.zip');
    if (check) {
      if (!fs.existsSync(target) || !fs.readFileSync(target).equals(bytes)) throw Error('stale instruction ZIP: ' + target);
    } else fs.writeFileSync(target, bytes);
    validated += 1;
  }
  console.log((check ? 'PASS reproducible' : 'Generated') + ': ' + validated + ' source-only ZIPs / ' + validated * 14 + ' MDs');
}
