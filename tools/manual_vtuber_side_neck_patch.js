/* Manually authored side-profile/neck acceptance clauses, appended to existing
 * individually reviewed 14-MD records without touching other wording.
 * This is source text only; no CI publisher and no claims of native rig proof.
 */
(function(){
const MARK="[VTUBER_SIDE_NECK_RIG_ACCEPTANCE_V1]";
function patch(files,mode,asset){
    const is3d=mode==="3d",body=asset==="body";
    const native=is3d?
        "현재 자동 3D 제작기는 8방향 원화에서 전 방향 메시를 자동 구축하는 것으로 검증되지 않았다. 정면·후면·좌우 참고 이외 대각 시점의 메시·뼈·가림 반영은 추가 구현/검사가 필요하다.":
        mode.startsWith("inochi2d")?
        "Inochi2D는 Inochi Creator의 실제 Part Node·메시·변형·목뿌리 자식 계층을 제작해야 움직인다. 현재 2D PNG/PSD 참조를 Inochi 원생 프로젝트 및 90° 회전 키폼으로 자동 변환하지 못한다.":
        "PSD2Live 기본 머리 ParamAngleX 범위는 -45..+45°, ParamAngleY는 -30..+30°다. 실제 -90/+90° 옆모습 PNG는 자동으로 키폼이 되지 않는다. 실제 MOC3 극한 각도 렌더링과 턱·목·귀·헤어 가림을 확인할 때까지 90° 가능이라고 보고하지 않는다.";
    const side=is3d?
        (body?"8방향의 측면 그림에서 코→입→턱 윤곽, 귀 뒤→목→어깨 접합, 팔꿈치·손목을 실제로 보여 주고 관절 깊이/가림이 앞·뒤 그림과 맞는지 눈으로 대조한다. views/body_detail_occlusion.png는 메쉬나 본이 아니다.":
        "대각·측면 그림에서 해당 자산의 뒷면, BODY 부착점, 파츠의 실제 앞뒤 순서를 확인한다. 기준 몸체·얼굴 자체를 다시 제작하지 않는다."):
        body?
        "part_art/neck.png는 턱 아래 잘린 얇은 조각이 아니어야 한다. 정면에서 턱 뒤 피부를 입 높이 가까이까지 위쪽으로 실제 그려 두고, 아래는 part_art/torso.png의 상부와 실질적인 알파 교집합을 만들어 놓는다. 얼굴 아래·목·몸통이 알파로 단순히 접하는 선은 실패다. head_three_quarter_L/R는 약 45°, head_profile_L/R는 실제 90° 형태 참고다. 각각 코·입·턱·귀·목뿌리·양어깨가 한 그림 안에서 연결되고 좌우 반전 복제로 대체하지 않는다. head_pitch_up/down에서 턱 아래 목의 드러남/가림을 실제로 바꾼다. neck_underpaint와 body_joint_overlaps 참고 그림을 따로 그리는 것만으로는 실제 part_art/neck.png의 가려진 픽셀이 생기지 않는다.":
        asset==="hair"?
        "3/4·측면에는 앞/뒤/옆머리의 진짜 깊이, 귀 뒤 모근과 목 뒤 실제 가닥을 그린다. BODY의 귀·눈·목은 앵커 참고이며 헤어 파츠 PNG에 복사하지 않는다.":
        asset==="outfit"?
        "3/4·측면에는 목·어깨·겨드랑이·소매와 옷깃의 실제 가림·안감을 보여 준다. 기준 BODY 피부·목·얼굴은 의상 독립 파츠 PNG에 함께 그리지 않는다.":
        "3/4·측면에는 실제 액세서리 부착점(귀·머리·옷)과 숨은 뒷면의 위치·앞뒤 순서를 표현한다. 해당 소품 밖의 BODY·HAIR·OUTFIT PNG를 만들지 않는다.";
    const registered=is3d?
       "8방향은 각도별 완성 그림이지 움직이는 3D VRM·본·표정 계층 자체가 아니다.":
       "정면·좌우 3/4·양측면 및 상하 자세 비교 원화는 outputs/master.png와 동일한 전체 캔버스 치수·기준 크기로 그린다. 확대 클로즈업은 별도 보조 그림으로만 남긴다. 이미지 AI의 다각도 그림은 PSD2Live/Inochi 실제 키폼에 자동 등록되지 않는다.";
    let edited=0;
    for (const [name,original] of Object.entries(files)){
        if(original.includes(MARK))continue;
        if(!original.includes("## [/IMAGE_AI_SOURCE_ONLY_V2]"))throw Error("Missing 2D/3D contract "+mode+"/"+asset+"/"+name);
        const insert="\n- "+MARK+" [그림과 실제 리깅의 차이] "+side+"\n- [좌표/참조] "+registered+"\n- [엔진 확인] "+native+"\n";
        files[name]=original.replace("## [/IMAGE_AI_SOURCE_ONLY_V2]",insert+"## [/IMAGE_AI_SOURCE_ONLY_V2]");
        edited++;
    }
    if(edited!==14)throw Error("Expected 14 manuals per ZIP, got "+edited);
    return {files,edited};
}
return {patch};
})()