"""Official Editor guidance; reference only, never synthesized native rig objects."""


def editor_settings_md():
    return """# Cubism 공식 설정 참고 — Editor에서 적용

이 문서는 PSD와 함께 제공하는 작업 참고이며 실제 파라미터·키폼·물리를 생성하지 않습니다.
FREE는 필요한 항목만 선택하세요. 파라미터 총 30개에 블렌드셰이프가 포함됩니다.

## 표준 ID와 범위

| ID | 최소 | 기본 | 최대 |
|---|---:|---:|---:|
| ParamAngleX / ParamAngleY / ParamAngleZ | -30 | 0 | 30 |
| ParamEyeLOpen / ParamEyeROpen | 0 | 1 | 1 |
| ParamEyeLSmile / ParamEyeRSmile | 0 | 0 | 1 |
| ParamEyeBallX / ParamEyeBallY / ParamEyeBallForm | -1 | 0 | 1 |
| ParamBrowLY / ParamBrowRY / ParamBrowLX / ParamBrowRX | -1 | 0 | 1 |
| ParamBrowLAngle / ParamBrowRAngle / ParamBrowLForm / ParamBrowRForm | -1 | 0 | 1 |
| ParamMouthForm | -1 | 0 | 1 |
| ParamMouthOpenY | 0 | 0 | 1 |
| ParamCheek | 0 | 캐릭터에 맞게 | 1 |
| ParamBodyAngleX / ParamBodyAngleY / ParamBodyAngleZ | -10 | 0 | 10 |
| ParamBreath | 0 | 0 | 1 |
| ParamArmLA / ParamArmRA / ParamArmLB / ParamArmRB | -30 | 0 | 30 |
| ParamHandL / ParamHandR | -10 | 0 | 10 |
| ParamHairFront / ParamHairSide / ParamHairBack / ParamHairFluffy | -1 | 0 | 1 |
| ParamShoulderY | -10 | 0 | 10 |
| ParamBustX / ParamBustY | -1 | 0 | 1 |
| ParamBaseX / ParamBaseY | -10 | 0 | 10 |

표준 범위는 시작점입니다. 필요한 표현은 공식 지침에 따라 범위를 확장하고 실제 키폼을 검수하세요.
캐릭터 왼쪽·오른쪽 기준과 화면 좌표를 혼동하지 마세요.

공식 +방향: AngleX/AngleZ·시선X·BodyAngleX/BodyAngleZ는 화면 오른쪽,
AngleY·시선Y·BodyAngleY·BaseY·BustY는 위쪽입니다. 눈썹X의 음수는
양쪽 눈썹을 모으므로 좌우 부위에 같은 화면 이동값을 넣지 마세요.
눈·입을 더 크게 열거나 강하게 닫을 때 범위를 0.1 단위로 확장할 수 있습니다.
아래 그룹 ID는 필요한 것만 생성하며 추가 파라미터를 뜻하지 않습니다.

| 부위 | 공식 파라미터 그룹 ID |
|---|---|
| 얼굴 / 머리 | ParamGroupFace / ParamGroupHead |
| 눈 / 안구 / 눈썹 | ParamGroupEyes / ParamGroupEyeballs / ParamGroupBrows |
| 입 / 신체 | ParamGroupMouth / ParamGroupBody |
| 손 / 왼손 / 오른손 | ParamGroupHands / ParamGroupHandL / ParamGroupHandR |
| 팔 / 왼팔 / 오른팔 | ParamGroupArms / ParamGroupArmL / ParamGroupArmR |
| 다리 / 왼다리 / 오른다리 | ParamGroupLegs / ParamGroupLegL / ParamGroupLegR |
| 흔들림 / 표정 / 머리카락 / 전체 | ParamGroupSway / ParamGroupExpression / ParamGroupHair / ParamGroupOverall |

## 물리·텍스처·파일

물리 계산 FPS는 사용 환경에 맞추세요. 대상이 불명확하면 공식 권장은 60 FPS입니다.
진자 길이·이동성·지연·가속도·출력 배율에는 모든 캐릭터에 공통인 최적 숫자가 없습니다.
Editor에서 프리셋을 시작점으로 사용하고 눈·머리·옷의 흔들림과 가림을 검수하세요.
물리 계산 FPS와 Viewer 표시 FPS, 모션 FPS는 서로 다른 설정입니다.

PSD는 RGB·8-bit·sRGB이며 마스크와 효과를 픽셀에 적용해야 합니다.
FREE는 2048px 텍스처 한 장, ArtMesh 100, 폴더 30, 디포머 합계 50,
파라미터 총 30(블렌드셰이프 최대 3), ArtPath 3을 Editor에서 확인하세요.
실제 텍스처 패킹은 얼굴·눈·선화의 배율과 경계 여백을 보며 검수하세요.
.cmo3 저장 후 공식 Editor에서 .moc3와 .model3.json 및 필요한 텍스처/물리 데이터를 출력하세요.
VTube Studio에서 추적 입력과 모델 출력 파라미터를 실제로 연결하고 움직임을 확인하세요.

## 원화·좌표·텍스처 품질

원화 캔버스와 텍스처 아틀라스는 별개입니다. FREE의 2048px 한 장 제한을
원화 캔버스 제한으로 적용하지 마세요. 2:3은 프로젝트 구도이며 공식 필수 비율이 아닙니다.
파츠 위치는 원화 캔버스에서 유지하고, 움직일 때 드러나는 가려진 영역을 보완하세요.
가져오기용 PSD는 파츠마다 선화·채색·클리핑을 합치고 레이어 마스크를 적용하세요.
중복 레이어 이름을 피하고 실제 Editor 가져오기 결과를 확인하세요.

PSD 가져오기의 ArtMesh 생성 여백 기본값은 1px입니다. Environment settings의
Modeling에서 바꿀 수 있으며 아틀라스 배치 여백과 별개입니다.
큰 원화의 화면 미리보기는 1/2 표시가 공식 권장입니다. 원화 화소를 줄이는 설정이 아닙니다.
대상 버전이5.2 이하이면 PSD 가져오기에 해당 버전의 blend mode를 선택하세요.
기본 합성은 Normal 색상/Over 알파입니다. 5.3의 고급 합성은 대상 SDK 지원을 확인하세요.
이 파이프라인의 등록 PNG 변환은 특수 PSD 합성 속성을 보존하지 못하면 오류를 반환합니다.
원본 PSD를 직접 가져오는 Editor의 지원 기능과 구분하세요.

아틀라스는 대상 SDK 호환성을 위해 가로·세로가 같은 크기를 권장합니다.
공식 Editor 텍스처 생성 방식은 High Quality를 권장합니다.
자동 배치 여백의 허용 범위는 0~50px이며 이것이 단일 권장 여백값은 아닙니다.
100% 미만 배치는 출력 해상도를 낮춥니다. 겹침·캔버스 이탈·미배치 파츠를 검사하세요.
PRO에서는 모든 파츠를 억지로 한 장에 축소하기보다 필요한 텍스처 크기·수를 검토하세요.
큰 텍스처는 VTube Studio 모바일에서 성능 문제를 일으킬 수 있습니다.

VTube Studio 모델 아이콘은 PNG/JPG, 512×512px 권장입니다. 원화 크기와 다릅니다.
물리는 .moc3 출력 시 함께 내보내 .model3.json에 physics3.json을 등록하세요.
VTube Studio는 표준 파라미터 ID·범위를 권장하며 앱의 Auto-Setup 후 보정하세요.
공식 안내의 SDK 출력 버전을 사용하고 beta SDK 지원은 별도로 확인하세요.

## 공식 출처

- https://docs.live2d.com/en/cubism-editor-manual/standard-parameter-list/
- https://docs.live2d.com/en/cubism-editor-manual/physics-operation/
- https://docs.live2d.com/en/cubism-editor-manual/precautions-for-psd-data/
- https://docs.live2d.com/en/cubism-editor-manual/psd-import/
- https://docs.live2d.com/en/cubism-editor-manual/blend-mode/
- https://www.live2d.com/en/cubism/comparison/
- https://docs.live2d.com/en/cubism-editor-manual/texture-atlas-edit/
- https://docs.live2d.com/en/cubism-editor-manual/divide-the-material/
- https://github.com/DenchiSoft/VTubeStudio/wiki/Loading-your-own-Models
"""
