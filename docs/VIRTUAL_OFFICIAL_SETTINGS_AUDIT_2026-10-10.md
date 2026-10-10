# 이미지·모델·버추얼 프로그램 공식 설정 세부 점검

공식 **필수 규격**, **권장값**, **예제 기본값**, 프로젝트의 **자체 설정**을 구분한다. 자체 설정을 공식 최적값이라고 부르지 않는다. 입력별 최적 화질·물리·추적 민감도에 공통인 단일 숫자는 없다. 실제 제작은 Colab CUDA 경로이며 이번 작업 환경에는 GPU 장치가 없어 수치·파일 검증을 CPU에서 수행했다.

## 이미지 원화: 10개 모드

| 이미지 | 요청 구도 | 필수 관계 | 실제 모델 전처리 |
|---|---|---|---|
| free_upper_master.png | 2:3, 머리·양손 포함 상반신 | 완성 헤어·의상·액세서리 한 장 | See-through 정사각 패딩/1280 |
| free_full_master.png | 2:3, 머리·양손·양발 포함 전신 | 같은 완성 캐릭터 한 장 | 같은 처리 |
| pro_upper_base_master.png | 2:3, 신체·얼굴 상반신 | 탈착 자산 없는 불투명 베이스 | 같은 처리; 모델 분포 차이 시각 검수 |
| pro_full_base_master.png | 2:3, 신체·얼굴 전신 | 같은 베이스 원칙 | 같은 처리 |
| pro_upper_hair_variant.png | 베이스와 같은 크기·원점 | 얼굴/신체 없이 헤어만 | 원본 알파 또는 Qwen 전경 마스크 |
| pro_full_hair_variant.png | 전신 베이스와 같은 캔버스 | 긴 머리 끝 포함 | 같은 처리 |
| pro_upper_outfit_variant.png | 베이스와 같은 캔버스 | 피부/얼굴 없이 의상만 | 같은 처리 |
| pro_full_outfit_variant.png | 전신 베이스와 같은 캔버스 | 밑단·필요 신발 포함 | 같은 처리 |
| pro_upper_accessories_variant.png | 베이스와 같은 캔버스 | 장식과 실제 부착점만 | 같은 처리 |
| pro_full_accessories_variant.png | 전신 베이스와 같은 캔버스 | 전신 위치 유지 | 같은 처리 |

**2:3은 프로젝트 원화 구도이며 공식 See-through/Qwen 필수 비율이 아니다.** 외부 이미지 생성 모델은 지정되어 있지 않아 그 모델의 native 크기·steps·CFG를 공식값으로 확정할 수 없다. 생성기의 UI/API 크기 옵션을 실제로 선택해야 하며 프롬프트만으로 정확한 픽셀 크기를 강제할 수 없다. 2:3을 지원하지 않으면 가장 가까운 native 세로 크기를 쓰되 원화를 늘이거나 잘라 비율을 맞추지 않는다. PRO 자산은 실제 베이스 크기를 우선한다. 출력 후 실제 파일 크기와 구도는 확인해야 한다.

프롬프트에서 독립 자산에도 눈을 뜨고 입을 닫으며 의상을 입으라는 공통 지시가 들어가던 충돌을 제거했다. 실제 알파를 지원하면 독립 자산은 투명 배경을 요청하며 지원하지 않으면 단색 배경과 전경 분리 경로를 사용한다.

## Live2D 모델별 처리 숫자

| 항목 | 공식 기준 | 현재 코드 | 구분 |
|---|---|---|---|
| See-through 추론 캔버스 | 정사각 1280 | 1280×1280 | 공식 기본값 |
| 원본 비율 처리 | center-square pad/resize | 같은 고정 소스 함수, 최종 좌표 역변환 | 자르거나 가로세로 독립 늘이기 아님 |
| See-through steps | 30 | 30 | 공식 기본값 |
| seed | 42 | 고정 소스 기본 42 | 재현 기준, 최고 화질 의미 아님 |
| guidance | 1.0 | 공식 함수 값 유지 | 기본값 |
| depth 해상도 | 768 | 768 | 별도 추론 |
| 양자화 | NF4 선택 진입점 제공 | NF4 | 원본 고정밀과 다른 절충 |
| CPU offload | 선택 옵션, 기본 False | 강제하지 않음 | group offload와 다름 |
| group offload | 고정 소스 기본 True | 유지 | 실행 로그/VRAM 실측 필요 |
| native BF16 | 지원 장치에서 원본 정밀도 | Ampere 이상 BF16, T4 FP16 | T4 호환 변경, 화질 비교 필요 |
| 원본 Qwen Layered | 권장 bucket640, 50 steps, true_cfg4, cfg_normalize True | 단독 원본 경로는 실행하지 않음 | 아래 LoRA와 혼동 금지 |
| Stable-Layers 크기 | 긴 변 640, 각 변 16배수 반올림 | 같은 고정 소스 처리 | 입력 비율 대략 보존 |
| 2:3 입력의 LoRA 크기 | 해당 함수 결과 | 432×640 | 반올림으로 정확한 2:3은 아님 |
| LoRA 샘플러 | Heun | Heun | Euler로 대체하지 않음 |
| LoRA steps / CFG | 50 / 1.0 | 50 / 1.0 | 원본 Qwen CFG4를 적용하지 않음 |
| LoRA 기본 layer 수 | 4, background 포함 | 모든 부위 기본4; 사용자 지정2~10, FREE 남은 한도 고려 | 공식 기본값 반영; 사용자 변경은 별도 |
| 재귀 | 원본 모델 지원 | 최대3단계, 기본 최대8회 | 공식 최적 시도 수 아님 |
| LoRA prompt | 고정 소스 기본 문구 | 그대로 사용 | 외부 원화 프롬프트와 별개 |
| Qwen 메모리 | 원본 고정밀 모델 | transformer NF4, CPU text encoder | CPU 인코딩은 T4 VRAM 절약 절충; RAM/시간 미실측 |
| Qwen 최종 화소 | RGBA 모델 출력 | 알파 후보만 채택, 등록된 원화 RGB 유지 | hidden 영역 신규 복원 아님 |

## 업스케일링: 공식 애니 정지 이미지 모델 연결

기존 시트 확대 경로의 영상용 `realesr-animevideov3`를 정지 이미지용 `RealESRGAN_x4plus_anime_6B`로 교체했다. 새 가중치는 Colab 준비 셀에서 받고 실제 확대는 기존 독립 GPU 작업자에서 수행한다. inference 중 다운로드하지 않는다.

| 항목 | 공식 6B 실행 | 프로젝트 설정/검증 |
|---|---|---|
| 가중치 | 공식 v0.2.2.4 anime_6B | 실제 asset 17,938,799 bytes 확인 |
| 구조 | RRDBNet,6 blocks,64 features,32 growth,native×4 | 같은 key/shape와 forward, strict load |
| 확대 배율 | native×4; 다른 outscale은 후처리 리사이즈 | 1/2/4 선택, 실제 학습 모델은×4 |
| tile | 기본0(통짜), 메모리 부족 시 분할 | 128은 T4용 자체 타일 크기, 공식 화질 최적값 아님 |
| tile_pad / pre_pad | 10 / 0 | overlap10, 별도 prepad0 |
| 정밀도 | 공식 GPU CLI 기본 FP16 | GPU FP16; CPU 검증 FP32 |
| 얼굴 보정 | GFPGAN 선택 기능 | 사용하지 않음; 정체성 자동 변경 방지 |
| 알파 | 공식 neural/bicubic 선택 | 원래 알파 LANCZOS 크기 변경; geometry 보존 정책, neural alpha와 동일하지 않음 |
| 투명 경계 RGB | 공식 처리와 별도 | halo 방지를 위한 색 확장, 자체 처리 |
| 타일 축소 필터 | 공식 outscale LANCZOS4 | PIL LANCZOS, 타일 단위 처리 | 

공식 기본값과 다른 타일 크기·알파·축소 필터는 명시적인 프로젝트 절충이다. 원본 복원이나 최고 화질을 보장하지 않으며 전체 이미지와 경계 비교가 필요하다. 이번 실제 공식 체크포인트의 CPU 추론 및 17×23→34×46 출력·반투명 알파 유지 확인은 완료했다. 공식 BasicSR RRDBNet과 같은 가중치로 forward 최대 절대오차 0.0을 확인했다. 이는 GPU·타일 경계 화질 검증과 다르다.

See-through/Qwen 분해 직전에 원화를 강제로 키우지 않는다. 다음 단계가 이미 고정 크기로 처리하기 때문이다. 실제 PSD 선화 확대가 필요하면 등록된 모든 파츠와 신체 기준·좌표를 동일 배율로 처리하고 원본/확대본을 비교해야 한다. 현재 Live2D 단일 원화 경로에 그런 후처리 PSD 확대 기능을 추가했다고 주장하지 않는다. FREE 2048 아틀라스 제약도 함께 판단해야 한다.

## 기타 제작 프로그램 대조

| 프로그램 / 항목 | 공식 근거·규격 | 실제 설정 및 판정 |
|---|---|---|
| Florence-2 | task token+processor+post_process_generation, 예제 beams3/no sampling | 공식 API 사용, beams3/no sampling 유지. 토큰 상한256은 프로젝트 예산(공식 예제1024와 다름); 작은 부위 검출 정확성은 미검증 |
| SAM2.1 | image predictor의 set_image, box prompt, mask output | Inochi 경로는 tiny config/checkpoint, single mask(False). 공식지원 API지만 큰 모델의 최고 정확도와 동일하다고 못 함. 마스크/사각 경계 제한은 프로젝트 정책 |
| FLUX.2 klein4B distilled | 4 steps, CFG1.0 | 유지. 숨은 영역 편집에 사용, dtype은 native BF16 지원 여부로 선택. denoise PID 종료 후 VAE decode PID로 RAM/VRAM 피크 분리 |
| Depth Anything V2 Small HF | processor518×518 기준, aspect 유지,14배수, RGB /255, ImageNet mean/std | 고정 snapshot의 공식 processor를 pipeline이 사용. 원본 크기 numeric depth로 돌리고 relative로 표시. 미터 깊이 주장 없음 |
| TripoSR mesh | CLI 기본 MC256, chunk8192 | 미지정 값은 고정 upstream 기본값 사용. scikit-image MC backend는 구현 절충이며 원본 backend 동일성/최고 표면 품질 보장 아님 |
| TripoSR foreground | 기본0.85; no-remove-bg는 준비된 gray RGB 요구 | 이미 분리된 RGBA는 upstream resize_foreground(0.85)+neutral gray0.5 합성 후 전송하도록 수정. opaque 이미지는 이미 준비된 입력 계약 유지 |
| TripoSR texture | bake-texture 선택, texture2048은 bake 때만 적용 | 호출은 기본 vertex-color geometry; 후속 자체 투영 텍스처와 구분. 2048 옵션을 붙이는 것만으로 후속 텍스처가 개선되지 않음 |
| TripoSR 다중 관측 | 공식 단일 이미지 모델 | 각 관측별 독립 복원/정합은 프로젝트 기능. 공식 공동 다중 시점 모델이라고 부르지 않음 |
| Inochi SDK | stable0.8.7 실제 INP 직렬화/재로딩 | native mesh/UV/deform/physics binding 유지. SDK0.8.7 기본 pixelsPerMeter1000,gravity9.8,preservePixels=False. 문서 latest0.7과 고정 소스를 구분 |
| Inochi 파라미터 | SDK가 authored range 사용 | head X/Z±30,Y±20; body±15; eye open0/1/1. 프로젝트 선택이며 Cubism 표준 범위와 혼용하면 안 됨 |
| Inochi spring | 모델별 설정 필요 | hair3Hz,기타5Hz, angleDamping0.72,length80px,lengthDamping은 SDK 기본0.5. 기본 SDK는1Hz/angleDamping0.5/length100px. 모든 원화에 공식 최적값 아님; vertex 변형은 pivot을 사용하지만 native driver는 root에 붙고 serialized pivot을 사용하지 않음. 움직임/좌표축 실측 필요 |
| Blender | 실제 VRM importer/exporter, LTS 지원 환경 | 4.2.23 LTS와 VRM addon4.7.2 고정, hash검증·operator 검사. 임의 최신 버전 교체를 화질 개선이라 하지 않음 |
| VRM export | 호환성 위해 기본4 influences, advanced 기능 주의 | addon preferences 무시, advanced/all-influences/sparse/lights/glTF animation 비활성, armature 명시, 실제 RNA 옵션 타입 확인/보고. 투명 atlas는 GLB BLEND로 보존하도록 수정했다. shader·표정·spring은 실제 앱에서 확인 필요 |
| SkinTokens 선택 옵션 | 공식 skeleton/transfer demo 사용 | 고정소스+use_skeleton/use_transfer, skin-only graft. T4의 total memory 검사14GiB는 free VRAM 보장이 아님. 기본 필수 단계가 아님 |
| 3D spring/fit | 형식과 단위 규격, 모델별 예술적 조정 | hair stiffness0.50,gravity0.10,drag0.20 등 자체 preset. 공식 universal 최적값 없음 |

이 표는 해당 실행 경로의 확인된 설정과 차이를 기록한다. 표에 없는 모든 프로그램 설정, 아직 실행하지 않은 GPU/Editor 품질 검사를 자동으로 통과했다고 해석하지 않는다.

## Cubism Editor / VTube Studio

모든 Live2D 결과 ZIP과 프롬프트 ZIP에 `OFFICIAL_EDITOR_SETTINGS.md`를 제공한다. 표준 ID 전체 범위 참고, 눈 기본열림1·입 기본닫힘0, head±30/body±10, 대상불명 시 물리 계산60FPS, FREE 7제약, sRGB PSD와 공식 출력 절차를 포함한다. 실제 rig 생성은 하지 않는다. 물리 계산60FPS와 Viewer 표시FPS 및 모션FPS를 혼동하지 않는다. VTube Studio 입력추적→모델출력 연결은 사용자 실제 Editor 모델에 맞춰 검수한다. 물리/감도/스무딩의 공통 최적값을 임의로 강제하지 않는다.

## 병렬성과 GPU

현재 작업 환경에는 nvidia-smi나 /dev/nvidia 장치가 없다. 검증용 CPU 실행을 실제 제작 CPU 경로의 권장으로 제시하지 않는다. Colab 제작에서는 CUDA 요구 정책을 전파하며 GPU 모델 작업에 CUDA가 없으면 모델을 CPU에 로드하기 전에 실패한다. 공식 CPU text-encoder offload를 없애면 T4 VRAM 피크가 늘 수 있으므로 측정 없이 전체 모델을 동시에 GPU에 넣지 않는다.

독립 공식설정 검토·CPU검사와 다운로드(최대3개)는 병렬 진행한다. 실제 GPU 추론은 공유 GPU lock으로 직렬화하여 같은 T4에 큰 모델이 중복 상주하는 것을 막고, 작업자 종료로 메모리를 회수한다. 더 큰 GPU/여러 GPU에서는 장치별 VRAM 피크를 측정한 뒤 병렬 개수를 정해야 한다. 근거 없이 동시 추론이 항상 더 효율적이라고 표시하지 않는다.

## 검증과 출처

최종 전체 테스트: **663 passed, 2 skipped, 1 failed** (검증용 CPU torch를 별도 경로에 둔 실행).
유일한 실패는 기존 `test_preloaded_real_face_model_answers_first_request_then_unloads`다.
이 작업 환경은 AF_UNIX socket 생성을 `PermissionError [Errno 1]`로 거부한다.
TripoSR CLI 회귀 실패는 수정 후 전체 재검사에서 통과했다. GPU/Cubism/Blender 실측은 수행하지 않았다.

게시한 작업 단위:

- `73da7cec`: 이미지 비율 출처·native 크기와 독립 자산 프롬프트 충돌 수정.
- `460538c2`: 모든 Live2D 결과/프롬프트 ZIP에 공식 Editor 세부 안내 포함.
- `31d2dc80`: 실제 공식 정지 이미지 SR 체크포인트와 overlap10 연결.
- `904020f6`: TripoSR alpha 입력의 전경 정규화·회색 합성.
- `0019a81c`: CUDA 제작 정책, native BF16, 직접 추론의 공유 GPU 잠금 및 resident 모델 회수.
- `4c600733`: atlas alpha 보존과 명시적 VRM 호환 내보내기 옵션.

- 이미지 모드/프롬프트 충돌: 10개 모드 계약 테스트 추가.
- Cubism 안내: 실제 10개 결과 ZIP에 포함 확인.
- SR: 실제 공식 가중치 strict load, CPU inference, official RRDB forward 일치.
- TripoSR: alpha/neutral background와 CLI regression 테스트.
- GPU: native BF16/T4, required CUDA 사전 실패, worker 경계 테스트. 실제 GPU VRAM·시간 실측 없음.

공식 자료:

- [See-through](https://github.com/shitagaki-lab/see-through) — 프로젝트 고정소스 df019de5129d6c4b406587a14c3501669441a783
- [Stable-Layers](https://github.com/Stability-AI/Stable-Layers) — 고정소스 b826314b34b12d7c7cce9f0de7f49a330bd8e011
- [Qwen Layered](https://huggingface.co/Qwen/Qwen-Image-Layered)
- [Real-ESRGAN 모델 구분](https://github.com/xinntao/Real-ESRGAN/blob/master/README.md), [공식 CLI](https://github.com/xinntao/Real-ESRGAN/blob/master/inference_realesrgan.py), [RRDB source](https://github.com/XPixelGroup/BasicSR/blob/master/basicsr/archs/rrdbnet_arch.py)
- [Cubism 표준 파라미터](https://docs.live2d.com/en/cubism-editor-manual/standard-parameter-list/), [물리 FPS](https://docs.live2d.com/en/cubism-editor-manual/physics-operation/)
- [Florence](https://huggingface.co/microsoft/Florence-2-base), [SAM2 predictor](https://github.com/facebookresearch/sam2/blob/main/sam2/sam2_image_predictor.py), [FLUX distilled](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B)
- [Depth processor](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf/blob/main/preprocessor_config.json)
- [TripoSR CLI](https://github.com/VAST-AI-Research/TripoSR/blob/main/run.py) — 현재 upstream 문서 수치와 프로젝트 고정 실행 기본값을 구분한다.
- [고정 Inochi SDK defaults](https://raw.githubusercontent.com/Inochi2D/inochi2d/v0.8.7/source/inochi2d/core/puppet.d), [고정 physics source](https://raw.githubusercontent.com/Inochi2D/inochi2d/v0.8.7/source/inochi2d/core/nodes/drivers/simplephysics.d)
- [glTF 좌표·재질·알파 규격](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
- [고정 VRM Add-on operator](https://raw.githubusercontent.com/saturday06/VRM-Addon-for-Blender/v4.7.2/src/io_scene_vrm/exporter/export_scene.py)
- [Inochi puppet 문서](https://docs.inochi2d.com/en/latest/creator/nodes/puppet.html), [VRM export](https://vrm-addon-for-blender.info/en-us/ui/export_scene.vrm/)
