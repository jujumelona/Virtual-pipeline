(() => {
  const MARKER_A="## [BROADCAST_HANDS_BODY_COLOR_V1]";
  const MARKER_B="## [/BROADCAST_HANDS_BODY_COLOR_V1]";
  const DOCS=["00_MASTER_FIRST.md","00_DELIVERY_AND_RECHECK.md","00_READ_FIRST.md","01_COMMON_RULES.md","02_ADVANCED_PARTS.md","03_MODE_RULES.md","04_OUTPUT_FILES.md","07_REVIEW_BEFORE_FINAL_ZIP.md","08_PRACTICAL_TIPS.md","09_VISUAL_ART_QUALITY.md"];
  const pose="
- **양손 전체 필수:** 손목에서 멈추지 않고 왼손·오른손 각각 손바닥, 엄지, 검지·중지·약지·새끼손가락의 **끝까지 완전한 그림**을 만든다. 양쪽 상완·전완·손은 각각 독립 RGBA PNG다. 화면 뒤로 숨기는 것을 '손 생성 완료'라고 기록하지 않는다.
- **방송 기본 자세:** T/A자 팔벌림이 아니라 어깨 힘을 뺀 자연스러운 자세에서 팔꿈치를 편안하게 굽혀 양손을 윗배·몸통 옆쪽 가까이에 배치한다. 두 손을 몸 앞에 둬도 좋으나 얼굴을 가리지 않는다. 좌우 팔 길이·손목 방향·엄지 위치가 실제 같은 사람이어야 한다.";
  const bounds="
- **바스트업 BODY 원화 범위:** 최상단은 정수리 전체 위로 소량의 여백, 최하단은 **명치 아래~윗배까지 이어지는 몸통 베이스와 아래쪽에 놓인 손가락 끝보다 더 아래**다. 가슴이나 겨드랑이·손목에서 자르지 않는다. 두 조건 중 더 아래로 내려가는 쪽을 캔버스 하한으로 정한다. 정수리·좌우 어깨·양팔·양손과 열 손가락이 보이고 각 끝의 바깥쪽·아래쪽에 **캔버스 폭/높이의 약 3~5% 작업 여백**이 남게 한다. 손이 이 범위에 들어오지 않으면 기본 자세를 자연스럽게 조정하거나 캔버스를 확장한다. 허리 아래 골반·다리·발은 생성하지 않는다. 확대 방송 화면의 실제 크롭은 이 원본보다 좁혀도 되지만, 원본 PNG에서 손가락을 자르면 안 된다.";
  const bodyColor="
- **마스킹 색 구분:** 색으로 가려진 면을 메우는 BODY 보정용 원화/언더페인트의 **RGB는 주변의 실제 BODY에 보이는 픽셀과 동일하게** 한다. 목·얼굴 아래 피부는 해당 목/얼굴 피부색을, 어깨·몸통 찰흙형 외피의 뒤받침은 실제 외피 베이스색을, 팔꿈치·손목 안쪽은 각각 이어지는 팔/손의 지정색을 사용한다. 몸통과 피부가 원래 서로 다르면 억지로 하나의 색으로 통일하지 않는다. **임의의 회색·검정·흰색·반창고색으로 틈을 덮지 않는다.** 가장자리는 기존 원화의 셀 명암/선폭을 그대로 이어 그리되 가려지는 단면에 검은 절단선을 새로 긋지 않는다.
- **알파/클리핑 마스크는 다른 것:** 투명도·가림을 정의하는 알파/클리핑 마스크는 채색 피부가 아니다. 마스크 채널은 투명도 데이터로 유지한다. '몸색과 같게'라는 규칙을 알파 채널이나 별도의 회색조 클리핑 마스크에 적용해 불투명으로 덮으면 안 된다. 실제 같은 BODY 색상으로 칠하는 대상은 **보정용 RGB 그림**뿐이다.";
  const neck="
- **턱·목·어깨 OFF/ON:** face와 hair를 가린 뒤 part_art/neck.png를 열었을 때 목 위쪽은 턱 양옆 뒤·귀 아래 뒤까지 실제 피부색으로 채워져 있어야 한다. torso를 숨기면 목 아랫단이 가슴 윗면/어깨 아래로 이어져야 한다. 모두 켰을 때 목과 턱 및 어깨 접합에 투명 삼각형이나 검정 이중 테두리가 없고, 옆모습에서 귀 아래→턱 뒤→목 앞·뒷선→어깨로 실제 연속 연결되어야 한다. 3/4/측면 참고 그림만 예쁘게 있고 실제 neck.png가 잘려 있으면 불합격이다.";
  const joints="
- **팔 파츠 그림 경계:** 어깨 소켓 안쪽까지 arm.left/right.upper를 실제 외피/피부색으로 연장하고, 팔꿈치 뒤까지 arm.left/right.forearm 윗단을 연장하며, 손목의 숨은 시작부분을 hand.left/right에 실제 손색으로 채운다. 상완→전완→손을 한 번씩 켜고 끄며 색상·선화·가림 순서·자연스러운 길이를 확인한다. 손의 각 다섯 손가락은 만화풍 단순화는 허용하나 벙어리장갑 실루엣·추가 손가락·손가락 잘림은 금지한다.";
  const shot="
- **방송 화면 대조:** 원본 전체(양손·윗배 포함)와 방송용 확대 화면(얼굴·목·어깨 위주)을 **별도 미리보기**로 본다. 방송 확대 미리보기에 손이 일부 안 보이더라도 원본·파츠 폴더에서는 완전한 양손을 유지한다. 확대 화면은 컷/카메라 설정이며 손 삭제·프레임 수정 지시가 아니다.";
  function specs(mode,asset){
    const bust=mode==="live2d_bust_up";
    const is3d=mode==="3d";
    const body=asset==="body";
    const scope=(bust?"바스트업":is3d?"3D 8방향":mode.endsWith("_full")?"전신":"상반신");
    const type=is3d?"3D":"2D";
    let core;
    if(body&&!is3d){
      core="### "+scope+" BODY: 실제로 무엇을 완성하고 어떻게 합성할지
"+
        (bust?bounds:"
- **전체 범위:** "+(mode.endsWith("_full")?"정수리에서 양발 끝까지":"정수리부터 윗배/허리 위와 양손 끝까지")+"의 자연스러운 몸통·양어깨·양팔·양손을 전부 생성한다. 하단·좌우 캔버스 가장자리는 손가락을 자르지 않고 움직임을 위한 여백을 둔다.")+
        pose+bodyColor+neck+joints+shot;
    }else if(body&&is3d){
      core="### 3D BODY: 실제 8방향 원화에서 두 손과 같은 재질색
- 정면부터 좌·우측면, 등 뒤까지 8방향에 양손의 손바닥·엄지·손가락 끝을 모두 실제 해당 시점으로 그린다. 멀리 있는 손이 몸에 가려지는 시점은 그 사실을 가림으로 표현하되, 정면·측면의 손을 잘라 버리지 않는다. 9번째 가림 상세는 어깨·팔꿈치·손목의 실제 연결을 그린다. 기본 자세는 자연스러운 방송형 팔 자세이며 T포즈 강제 금지.
- 몸통은 기존 무광 불투명 BODY 지정색. 목/손 피부와 몸통의 지정 색이 다르면 그 차이를 유지한다. 임의 회색 덧칠 금지. 3D의 머티리얼 색과 2D의 알파 마스크는 다른 개념이다.";
    }else{
      core="### "+scope+" "+asset.toUpperCase()+": BODY 양손·목 보존과 자산별 정확한 정렬
"+
        (bust?bounds:"
- 기준 BODY는 해당 모드의 실제 프레임을 사용한다. BODY 양손은 손가락 끝까지 완성된 참조여야 하며, "+(mode.endsWith("_full")?"전신이라 양발까지 포함한다.":"상반신이라 손과 손목·어깨를 잘라서는 안 된다."))+
        "
- **현재 ZIP은 "+asset.toUpperCase()+"만 생성한다.** 기준 BODY의 양손·팔·목과 윗배는 위치 및 가림 참조로만 사용한다. BODY의 피부/클레이 RGB 픽셀을 현재 자산의 독립 산출물에 복사하거나, BODY 손이 잘린 상태로 둔 채 의상·머리카락·장식으로 숨기지 않는다. "+
        (asset==="outfit"?"소매 좌우의 윗단은 옷판 안쪽, 소매 끝은 손목 피부 바깥에 실제로 겹치게 한다. 커프를 그려 손가락 잘림을 감추지 않는다. 옷깃 안쪽과 겨드랑이/어깨의 숨은 천만 의상 재질색으로 채색한다.":asset==="hair"?"모근·귀 뒤·뒷머리·목 뒤에 실제 모발을 잇되 neck.png의 피부색을 헤어 원화에 그리지 않는다. 머리카락이 턱/목 연결 결함을 가리기 위한 가짜 검은 면이 되면 실패다.":"안경·귀걸이·목걸이·머리핀 등 요청한 한 종류의 부착점만 그린다. 목·귀·손 피부를 장식색으로 덮거나 BODY 색의 임시 도형으로 바꾸지 않는다.")+
        (is3d?" 3D는 8방향+가림 상세에서 실제 소품/헤어/의상의 두께·연결을 그리며 2D PNG·PSD를 요구하지 않는다.":" 2D는 실제 독립 자산 PNG만 납품하고, BODY 원화는 참고 합성으로만 사용한다.")+
        "
- **보정색:** 가림에 감춰지는 BODY 피부/무광 외피를 임의 회색 면으로 교체하지 않는다. 보이는 BODY RGB와 연속된 원래 색을 유지하도록 참고하되, 현재 자산의 숨은 픽셀은 현재 자산 고유의 재질색으로 그린다. 별도의 알파/클리핑 마스크를 몸색 RGB로 채워 버리지 않는다.";
    }
    return {bust,is3d,body,scope,core,asset,type};
  }
  function content(doc,mode,asset){
    const x=specs(mode,asset),intro="**범위 우선순위:** 이 지침은 같은 ZIP의 오래된 '가슴 위까지만', '손이 보일 때만 손' 같은 조건보다 우선한다. "+(x.bust?"바스트업의 원본에는 양손 끝까지 무조건 포함한다.":"BODY 원본의 양손 누락은 허용하지 않는다.")+" 작업 자산 소유권·2D/3D 형식 규칙은 유지한다.";
    if(doc==="00_MASTER_FIRST.md")return "### 최상위 방송 프레이밍·손·몸색 제작 명령
"+intro+"
"+x.core;
    if(doc==="00_READ_FIRST.md")return "### 이미지 생성 시작 전에 반드시 정할 원화 캔버스
"+intro+"
- 첫 생성 이전에 정수리·목·양어깨·두 손목·양손 열 손가락 끝과 아래/좌우 여백이 들어가는 캔버스를 확정한다. BODY 참조가 없으면 기준 디자인 마스터부터 완성한다. 눈으로 보지 않고 손을 추정했다는 완료 보고 금지.
"+x.core;
    if(doc==="02_ADVANCED_PARTS.md")return "### 파츠별 실제 제작법·숨겨진 연결과 보정색
"+intro+"
"+x.core+"
- 생성 순서: 기준 마스터 확인 → (BODY면) face/neck/torso→좌우 상완→좌우 전완→좌우 손을 각각 별도 생성 → 마스터의 색·선화·원본 픽셀과 대조 → 앞뒤 가림 순서로 합성 → 검정/흰 배경 알파 점검 → 정면·3/4·측면의 목/손목 접합 참고와 교차 대조. 해당 자산 아닌 파츠는 위치 참고만 한다.";
    if(doc==="03_MODE_RULES.md")return "### "+x.scope+" 방송 원본 범위와 화면 크롭의 차이
"+intro+"
"+x.core;
    if(doc==="04_OUTPUT_FILES.md")return "### 최종 파일에 반드시 실제로 존재해야 하는 그림
"+intro+"
"+x.core+(x.body&&!x.is3d?"
- 필수 독립 PNG: part_art/arm.left.upper.png, part_art/arm.left.forearm.png, part_art/hand.left.png, part_art/arm.right.upper.png, part_art/arm.right.forearm.png, part_art/hand.right.png, part_art/neck.png, part_art/torso.png. 파일 이름과 달리 실제 그림이 잘렸다면 불합격. part_art/_order.txt 및 outputs/master.png도 동일한 전체 캔버스 좌표로 제출한다. 열린 입·감긴 눈 등 대체 파츠는 중립 미리보기에 한꺼번에 켜지 않는다.":"
- 납품 경로는 해당 자산의 기존 2D/3D 출력 계약을 유지한다. BODY의 손 PNG를 "+asset.toUpperCase()+" ZIP에 복사하여 이중 납품하지 않는다.");
    if(doc==="07_REVIEW_BEFORE_FINAL_ZIP.md")return "### 실제 이미지 ON/OFF·방송 크롭·몸색 직접 검수
"+intro+"
"+x.core+"
- [ ] 기준 BODY 정수리·양손 손가락 끝의 바깥/아래 여백이 실제 원본에 있다. 특히 왼손·오른손 모두 끝까지 완성됐다.
- [ ] 상완→전완→손목→손가락이 서로 맞물려 보이며 손 개수/손가락 개수·방향이 정상이다.
- [ ] 얼굴 OFF에서 턱 아래 목 윗단이 채색돼 있고, torso OFF에서 목 아랫단이 이어진다.
- [ ] 가림 면의 보정 RGB는 해당 신체 부위 BODY 실색과 일치하며 알파/클리핑 마스크는 RGB 채색 그림과 혼동하지 않았다.
- [ ] 실제 정면·좌우 3/4·측면 참고에서 목 앞/뒤 선과 어깨 연결이 유지된다. 측면 참고가 리깅 키폼이 아님을 명시했다.
- [ ] 방송 확대 미리보기에 보이지 않는다고 원본 손·하부 몸통을 삭제하지 않았다.
- [ ] 해당 자산이 아닌 신체·헤어·의상·장식을 독립 출력물에 추가하지 않았다.";
    if(doc==="08_PRACTICAL_TIPS.md")return "### 방송용 손·목·소매 접합 실무 순서
"+intro+"
"+x.core+"
- 검수 때 첫 번째 화면은 모든 파츠의 정면 중립 합성, 두 번째는 얼굴·머리카락 OFF로 목을 보여주는 화면, 세 번째는 torso OFF로 목/팔 윗단, 네 번째는 forearm OFF/hand ON 상태의 손목 그림이다. 각 접합이 잘린 스티커처럼 보이면 실제 같은 색으로 원화를 고친 뒤 다시 합성한다.";
    if(doc==="09_VISUAL_ART_QUALITY.md")return "### 방송 화면 축소와 확대에서 그림 품질 평가
"+intro+"
"+x.core+"
- 손은 한 덩어리 장갑형·뒤집힌 엄지·손가락 끝 잘림이 없어야 한다. 좌우 손과 팔의 원근 비율·셀 명암·선굵기는 같은 캐릭터다. 목의 내부 보정 색이 원래 외피보다 회색/검정으로 다르면 불합격. 좁은 방송 크롭에서도 얼굴이 짧고 둥글며 큰 눈을 유지한다.";
    if(doc==="00_DELIVERY_AND_RECHECK.md")return "### 재압축 전 실제 납품 범위 재확인
"+intro+"
"+x.core+"
- 재검토에서는 납품 파일을 실제로 열어 양손 끝·턱/목·어깨·손목의 연결과 색을 보고, 한 곳이라도 잘렸다면 결과 완료를 선언하지 않는다.";
    if(doc==="01_COMMON_RULES.md")return "### 공통 몸색·손끝·프레임 계약
"+intro+"
"+x.core;
    throw Error("unexpected doc "+doc);
  }
  function patch(files,mode,asset){
    if(!["live2d_bust_up","live2d_upper","live2d_full","inochi2d_upper","inochi2d_full","3d"].includes(mode) || !["body","hair","outfit","accessory"].includes(asset))throw Error("unknown kit");
    for(const filename of DOCS){const old=files[filename];if(typeof old!=="string")throw Error("missing "+filename);
      const piece=MARKER_A+"
"+content(filename,mode,asset)+"
"+MARKER_B;
      const i=old.indexOf(MARKER_A),j=old.indexOf(MARKER_B);
      if((i>=0)!==(j>=0))throw Error("partial marker "+filename);
      files[filename]=i<0?old.trimEnd()+"

"+piece+"
":old.slice(0,i)+piece+old.slice(j+MARKER_B.length);
    }
    return files;
  }
  return {DOCS,MARKER_A,MARKER_B,patch,content,specs};
})()