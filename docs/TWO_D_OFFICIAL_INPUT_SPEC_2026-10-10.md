# 2D 프로그램별 공식 원화·좌표·출력 규격

조사일: 2026-10-10. 대상은 저장소에서 실행하는 Live2D Cubism FREE/PRO,
VTube Studio, Inochi2D SDK 0.8.7 및 앞단 See-through/Stable-Layers다.
사용자가 언급한 `sdlive`는 정확한 제품을 식별하지 못했다. Live2D를 뜻한다고
확정하지 않는다. 저장소에는 해당 이름의 프로그램 연결이 없다.

필수 규격·권장값·예제 기본값·자체 설정을 구분한다. 아래 문서에서 확인하지 못한
고정 비율·픽셀·그림체는 공식값으로 만들어 넣지 않는다.

## 모드와 대상

| 모드 | 제작 프로그램 | 방송용 산출물 | 입력의 적용 기준 |
|---|---|---|---|
| Live2D FREE 상반신/전신 | Cubism FREE | Editor에서 내보낸 MOC3 세트 | 같은 PSD 규격, FREE 모델 제한 적용 |
| Live2D PRO 상반신/전신 신체 | Cubism PRO | 같은 공식 런타임 세트 | 같은 PSD 규격, PRO 기능 범위 |
| PRO 헤어/의상/액세서리 | Cubism PRO의 교체 파츠 | 기존 모델에 리깅·등록된 파츠 | 기준 신체와 실제 캔버스·위치 정합은 프로젝트 교체 계약 |
| Inochi2D 캐릭터/교체 의상 | Inochi SDK/Creator | 실제 SDK로 저장한 INP | RGBA 텍스처·정점·UV·파라미터 바인딩 |
| VTube Studio | Cubism 모델의 로드/추적 | MOC3+model3.json+텍스처+필요 물리 | PSD 제작기가 아님; INP/VRM 호환으로 표시하지 않음 |

## Cubism: 원화와 아틀라스의 다른 규격

| 항목 | 공식 근거 | 코드/작업 판정 |
|---|---|---|
| 원화 비율 | 아래 공식 가져오기 문서에 모든 모델 공통 2:3 지정 없음 | 2:3은 프로젝트 구도 |
| 원화 픽셀 | FREE 텍스처 제한을 PSD 캔버스 제한으로 설명하지 않음 | 원본 캔버스와 아틀라스를 따로 취급 |
| 가져오기 파일 | PSD, RGB, 8비트/채널 필수 | 실제 생성 PSD 구조와 Editor 열기는 별도 검증 |
| 프로파일 | sRGB 권장; 다른 프로파일은 변환 | RGB 표지만으로 sRGB 프로파일 보장을 주장하지 않음 |
| 레이어 | 가져오기용은 파츠별 선화·채색·클리핑 합침; 레이어 마스크 사용하지 않음 | 최종 알파에 효과 적용, 중복 이름 점검 |
| 그림체 | 이 제작 문서에는 필수 애니 그림체 지정 없음 | 분해 AI의 지원 그림체와 혼동하지 않음 |
| 가려진 영역 | 움직이며 드러나는 부분의 선·색을 보완 | RGB 보존/마스크만으로 숨은 영역 복원 완료 주장 금지 |
| PSD 좌표 | 레이어를 캔버스에 배치, import 기본 ArtMesh 여백1px | 파츠의 관측 위치 보존; 눈·손의 고정 픽셀값은 확인되지 않음 |
| 아틀라스 형태 | SDK 호환성 고려, 일반적으로 폭=높이 권장 | 세로 원화를 정사각형으로 찌그러뜨리라는 의미 아님 |
| 생성 품질 | High Quality 권장 | Editor 안내에 반영; 실제 Editor 옵션 자동 적용 아님 |
| 자동 배치 여백 | 허용0~50px | 단일 공식 최적 여백값으로 표시하지 않음 |
| 배율 | 지정1~100%; 100% 미만이면 출력 해상도 감소 | 얼굴·눈·선화의 실제 배율 확인 필요 |
| 배치 검증 | 겹침·프레임 이탈·미배치 확인 | PSD의 정상 생성만으로 아틀라스 정상 판정 금지 |

FREE 제한: 텍스처 한 장 최대2048px, ArtMesh100, 파라미터30(블렌드셰이프 포함),
블렌드셰이프3, 디포머 합계50, 폴더30, ArtPath3, Warp 분할9×9,
Draw Order 그룹2. PRO의 비교표상 개수 제한 해제는 GPU 무제한을 뜻하지 않는다.

## VTube Studio: 실제 공식 권장

| 항목 | 공식 설명 | 적용 위치 |
|---|---|---|
| 표준 파라미터 | 표준 ID·최소/최대 권장, ID가 중요 | Cubism 모델 설정; 앱 Auto-Setup 후 조정 |
| 파일 | model3.json이 다른 모델 파일 참조 | 실제 Editor 내보낸 폴더 검사 |
| 물리 | MOC3와 함께 physics3.json 출력·등록 권장 | model3.json 참조까지 확인 |
| SDK 버전 | 공식 로드 문서의 지원 export version; beta 주의 | 최신 beta를 임의 강제하지 않음 |
| 텍스처 | 여러 장·큰 텍스처 지원, 모바일에서는 지연/충돌 가능 | PRO도 무조건 최대 텍스처 사용하지 않음 |
| 모델 아이콘 | PNG/JPG, 512×512px 권장 | 캐릭터 원화 해상도와 구분 |
| 모델 제작 | 내장 모델 제작기 없음, Live2D 모델만 지원 | PSD/INP/VRM을 방송용 VTS 완성 모델로 표시하지 않음 |

## Inochi2D: 문서와 고정 SDK 소스

공개 `latest` 문서는 0.7로 표시된다. 실행하는 SDK 0.8.7의 파일·좌표·기본값은
해당 태그 소스도 함께 대조했다. 개발판 코드를 0.8.7 공식 규격으로 간주하지 않는다.

| 항목 | 실제 공식 근거 | 현재 상태 |
|---|---|---|
| 텍스처 데이터 | SDK Texture unsigned 8-bit RGBA | PNG를 4채널로 로드 |
| 스타일 | 공식 Puppet 문서에 픽셀아트용 Point Filtering 안내 | 일반 그림은 Linear 기본; 스타일별 구분 |
| 필터 | SDK 기본 Linear, Clamp; Point는 NEAREST | 픽셀아트에 애니 SR/Linear가 필수라고 주장하지 않음 |
| 좌표축 | 0.8.7 카메라의 위/아래 역전 orthographic, Quad의 Y/UV 함께 증가 | 원화 Y 방향을 유지해야 함; 기존 Y 반전 오류 수정 |
| 원점 | 카메라 중앙 이동; Creator PSD importer도 문서 중심을 뺌 | (x-W/2,y-H/2), 변형 delta는 (dx,dy) |
| UV | Quad는 텍스처 공간 좌표를 별도로 생성 | 위치·UV 동시 수직 반전은 하지 않음 |
| 물리 단위 | SDK pixelsPerMeter1000, gravity9.8 | 작품 크기에 맞춰 조정 가능한 기본값 |
| 물리 기본 | SimplePhysics1Hz, angle/length damping0.5, length100 | hair3Hz/기타5Hz,0.72,80px는 자체 preset |
| 입력 크기 제한 | 공통 권장2:3/4K값은 조사 문서에서 확인되지 않음 | 출력기8192 캔버스 상한은 프로젝트 방어값, 공식 상한 아님 |
| INP | 텍스처·리깅 포함 공식 컨테이너 | 실제 SDK 쓰기/재로딩; 헤더만 검사하지 않음 |

좌표 수정은 소스 대조로 확인했다. 네이티브 E2E에 실제 INP JSON의 정점·UV를
검사하는 회귀 검증을 추가했다. 이 환경에는 D 컴파일러가 없어 새 네이티브 실행은
수행하지 않았다. 실제 Viewer 화면 검증 완료로 표시하지 않는다.

알파는 고정 SDK의 Texture 로더·Part blend·fragment shader·INP serializer를
대조했다. renderer는 premultiplied RGB를 요구하지만 파일 로더는 자동 변환하지
않아 출력 경계에 공식 `inTexPremultiply`를 한 번 적용하도록 수정했다.
중간 PNG/PSD는 straight alpha를 유지한다. 실제 INP 내부 TGA의0/64/128/255 알파
픽셀을 검사하는 native CI를 추가했다. 로컬에서 네이티브 CI는 실행하지 않았다.
native physics driver 부착 위치/피벗은 여전히 검수 대상이다.

## 앞단 AI의 공식 설정과 스타일

| 모델 | 공식 기준 | 프로그램 규격과 구분 |
|---|---|---|
| See-through V3 | 단일 애니 캐릭터, 의미 레이어 최대23; 기본 고해상도 경로1280 | Cubism ArtMesh23 제한이 아님; 리깅 완료 모델 아님 |
| See-through 정밀도 | 기본BF16; NF4/group-offload는 공식 저VRAM 선택 경로 | 프로젝트 T4 FP16/NF4 비교 품질은 별도 |
| See-through NF4 깊이 | 현재 README720, 프로젝트 고정소스 실행값768 | upstream 현재값과 고정 revision 값을 섞지 않음 |
| Stable-Layers | Heun/50steps/CFG1/긴변640/4레이어 권장 | 더 높은 입력크기로 무조건 품질 향상하지 않음 |
| Stable-Layers 비율 | 긴변 조정 후 각 변16배수 반올림 | 정확한2:3 보장은 아님 |
| Stable-Layers 알파 | editor/compositing용 `--transparent` | RGBA 출력과 숨은 영역 품질은 별도 |
| Stable-Layers prompt | 기본 `a clean, well composed image`; source image가 분해 주도 | 외부 원화 생성 프롬프트와 다름 |

Florence/SAM2/FLUX/Depth/TripoSR/SR/Blender/VRM 및 3D 모드의 수치·차이는
[기존 전체 프로그램 감사표](VIRTUAL_OFFICIAL_SETTINGS_AUDIT_2026-10-10.md)에 있다.
외부 원화 생성 모델이 지정되지 않아 그 생성기의 공식 픽셀·프롬프트·steps·CFG를
확정하지 않는다. 공식 지원 형식과 방송 품질 실측을 같은 것으로 판정하지 않는다.

## 분할 결과에 반영한 설정

- Colab 초기값·모드 UI·CLI·제작 함수의 Qwen 레이어 기본값을 공식4개로 통일했다.
  눈썹3개/헤어8개 등 자동 부위별 휴리스틱을 제거했다. 사용자가2~10개를 명시하거나
  FREE 잔여 ArtMesh 예산으로 제한하는 경우는 공식 기본값과 다른 설정이다.
- Live2D 파츠 PNG와 비교 프리뷰에 sRGB ICC를 넣는다. 원본 캔버스 좌표·RGBA 화소와
  알파 마스크를 보존하며 모델 내부640px 출력을 최종 원화 해상도로 잘못 표시하지 않는다.
- 일반2D PSD/ORA에도 sRGB ICC를 넣고 RGB8비트 PSD의 알파를 실제 투명 채널에 적용한다.
  중복 파츠 이름은 거부한다. 입력의 다른 ICC 프로파일을 sRGB로 임의 재해석하지 않는다.
  프로파일 없는 입력은 기존 sRGB 입력 계약에 따른다.
- 실제 PNG·PSD 저장/재열기 검증과 관련 모드·제작 테스트163개가 통과했다.
  이는 GPU 분할 품질이나 Editor/Viewer 화면 실측 통과를 의미하지 않는다.
- Inochi 관련 setup/transport/completion 및 PSD 검사21개가 통과했다.
  실제 GPU와 SDK renderer의 반투명 화면 실측을 대체하지 않는다.
- Qwen 작업자의 실제 RGBA PNG 크기를 고정 공식 `compute_aspect_resize` 결과와
  대조한다. 잘못된 크기의 결과는 성공 처리하거나 늘이지 않고 거부한다.
  qwen_stage.json에 실제 원본/후보 캔버스·Heun/50/CFG1/640/16배수/알파 설정을
  기록한다. 최종 파츠 PNG·PSD는 별도로 원화 캔버스 좌표와 화소를 유지한다.
- 크기 검사를 결과에만 적용하지 않는다. 모델 로딩 전에 공식 계산에 따른
  RGB/LANCZOS 입력 PNG를 준비하여 추론에 전달한다. 고정 upstream의 resize도
  이미 준비된 같은 크기를 사용하며 잠재공간·decode가 해당 폭/높이를 사용한다.
  생성된 잘못된 크기를 사후 확대해서 정상으로 위장하지 않는다. 원본 입력은 유지한다.

## 공식 출처

- Cubism [PSD 조건](https://docs.live2d.com/en/cubism-editor-manual/precautions-for-psd-data/), [소재 분리](https://docs.live2d.com/en/cubism-editor-manual/divide-the-material/), [PSD 가져오기](https://docs.live2d.com/en/cubism-editor-manual/psd-import/)
- Cubism [아틀라스](https://docs.live2d.com/en/cubism-editor-manual/texture-atlas-edit/), [FREE/PRO 비교](https://www.live2d.com/en/cubism/comparison/)
- VTube Studio [모델 로드](https://github.com/DenchiSoft/VTubeStudio/wiki/Loading-your-own-Models), [지원 모델](https://github.com/DenchiSoft/VTubeStudio/wiki/Models)
- Inochi [Puppet](https://docs.inochi2d.com/en/latest/creator/nodes/puppet.html), [INP 규격](https://docs.inochi2d.com/en/latest/spec/inp/index.html)
- Inochi SDK0.8.7 [Camera](https://github.com/Inochi2D/inochi2d/blob/v0.8.7/source/inochi2d/math/camera.d), [MeshData](https://github.com/Inochi2D/inochi2d/blob/v0.8.7/source/inochi2d/core/meshdata.d), [Texture](https://github.com/Inochi2D/inochi2d/blob/v0.8.7/source/inochi2d/core/texture.d)
- Inochi SDK0.8.7 [vertex shader](https://github.com/Inochi2D/inochi2d/blob/v0.8.7/shaders/basic/basic.vert), [Puppet defaults](https://github.com/Inochi2D/inochi2d/blob/v0.8.7/source/inochi2d/core/puppet.d), [physics defaults](https://github.com/Inochi2D/inochi2d/blob/v0.8.7/source/inochi2d/core/nodes/drivers/simplephysics.d)
- Creator [PSD importer (main, 보조 자료)](https://github.com/Inochi2D/inochi-creator/blob/main/source/creator/io/psd.d): SDK0.8.7 규격의 단독 근거로 삼지 않음
- [See-through](https://github.com/shitagaki-lab/see-through), [Stable-Layers](https://github.com/Stability-AI/Stable-Layers)
