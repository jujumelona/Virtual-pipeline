# Live2D 모델별·모드별 공식 방식 및 품질 점검

대상: 사용자가 제공한 `live2d_free_pro_chat_reference_updated.md`의 FREE/PRO 레이어 PSD 제작. 3D와 Inochi2D는 이 점검 대상이 아니다. 상반신/전신 × FREE 및 PRO 네 자산 = 총 10개 모드다.

**판정: 공식 추론 설정을 따르는 부분과 T4를 위한 변경 부분이 함께 있다. 실행 연결 오류는 아래처럼 수정했지만, 모든 모드에서 최고 품질이 보장되는 방식이라고 판정할 근거는 아직 없다. 실제 GPU 이미지와 Cubism Editor 가져오기를 검증해야 한다.** 공식 기본값은 재현 기준이며 입력별 최적 품질의 증명이 아니다.

## 1. 모델별 점검

| 모델/단계 | 공식 기준과 현재 실행 | 판정 및 이번 조치 |
|---|---|---|
| See-through LayerDiff NF4 | 공식 양자화 PSD 진입점, 신체→머리 2단계. 분해 1280px, 30 steps, guidance 1.0 | 전체 애니 캐릭터용으로 FREE 및 PRO 신체에 유지. 얼굴 없는 독립 헤어·의상·액세서리는 이 경로에서 제외. NF4는 원본 고정밀과 동일한 화질이라고 보장하지 않음 |
| See-through Marigold NF4 | 공식 애니 깊이 모델, 768px. 실제 깊이/좌우 분리 경로 유지 | Serialized Linear4bit의 BF16 계산을 T4용 FP16로 명시 변경. 실제 T4 깊이 품질과 좌우 가림 순서는 미검증 |
| Qwen-Image-Layered | 원본의 레이어 생성 모델 사용. 현재 독립 원본 실행이 아니라 Stable-Layers LoRA를 붙인 실행 | 원본 Qwen의 CFG 설정을 LoRA 실행에 섞지 않음. Qwen 출력의 RGB를 최종 원화에 덮어쓰지 않고 알파 후보만 사용. 자동 해부학 의미 판정은 없음 |
| Stable-Layers LoRA | 고정 소스의 Heun, 50 steps, CFG 1.0, 최대 변 640px, 투명 출력. 공식 기본 레이어 수 4 | 샘플러·steps·CFG·크기 유지. 부위별 후보 수 2~10 및 재귀는 프로젝트 자체 정책이며 공식 최적화 결과가 아님. 더 많은 분할/시도가 항상 더 좋다는 근거 없음 |
| Qwen transformer NF4 (OzzyGT) | 별도 배포자의 양자화 체크포인트. 공식 Qwen/Stable-Layers의 원본 고정밀과 다른 실행 | 체크포인트의 `bnb_4bit_compute_dtype=bfloat16`은 `torch_dtype`만 바꿔도 남음. 실제 Linear4bit 모듈의 계산 dtype을 변경하도록 수정. 고정밀 대비 화질 비교 미검증 |
| dtype/메모리 | T4는 FP16, native BF16 가능한 Ampere 이상은 BF16 | Qwen이 고성능 GPU에서도 FP16으로 강제되던 부분 수정. transformer만 NF4; 텍스트 인코더는 CPU의 비양자화 모델이며 VAE도 별도 필요. 표준 Colab RAM/VRAM 적합성은 실측하지 않음 |
| anime parser / SAM2.1 | 공식 코드의 선택적 별도 기능. 현재 선택된 양자화 PSD 진입점에서 호출하지 않음 | 사용하지 않는 두 체크포인트 다운로드 제거. 계획 메타데이터에 미실행 상태 명시. 정밀 마스크를 SAM2가 실제로 보정했다고 주장할 수 없음 |
| Cubism PSD | 공식 RGB, 8-bit, sRGB, 마스크/효과 적용 지침 | 최종 PSD에 sRGB ICC를 기록하고 알파를 별도 사용자 마스크 대신 레이어의 투명도 채널에 저장. 픽셀·알파 직렬화 검사 통과. 실제 Editor 가져오기는 별도 확인 필요 |

See-through 원본은 head bounding box를 추출해 머리 분해를 수행한다. 독립 헤어·옷만 넣는 것은 같은 입력 계약이 아니다. 이번 변경은 그러한 자산에서 관련 없는 얼굴/신체를 생성하거나 head crop에서 실패할 수 있는 경로를 제거했다.

`torch_dtype`는 비양자화 모듈의 dtype을 제어한다. 현재 Diffusers 0.37.0은 체크포인트에 양자화 설정이 있으면 그것을 사용하므로 serialized NF4의 계산 dtype은 따로 설정해야 한다. 이 수정은 T4 호환성 수정이며, FP16 수치 품질 및 OOM 해결의 실측 증명이 아니다.

## 2. 10개 모드 각각의 판정

공통 출력: 입력 캔버스에 등록된 PSD, RGBA PNG, 알파 마스크, 실제 합성 비교, 레이어 목록, 검수 MD, 로그. 선택한 PRO 자산만 독립 출력하며 MOC3/리깅 완료를 만들지 않는다.

| 모드 | 현재 적합한 실행 경로 | 해당 모드에서 남은 품질 확인 |
|---|---|---|
| FREE 상반신 | 완성 이미지 → See-through → 선택 Qwen → avatar.psd | 눈·입 미세 분리, 얼굴 정체성, 양손, 옷·머리 가림 복원. 100 후보/텍스처 필요조건 후 Editor 최종 제한 확인 |
| FREE 전신 | 전신 완성 이미지 → See-through → 선택 Qwen → avatar.psd | 상반신 항목과 발·신발·다리. 정사각형 1280 추론에서 세로 원본의 선화가 축소되는 영향, 2048 한 장에 얼굴 디테일 유지 |
| PRO 신체 상반신 | 신체/얼굴 이미지 → See-through → 선택 Qwen → body.psd | 헤어/의상 없는 신체는 전체 캐릭터 모델의 분포와 다를 수 있음. 불필요한 생성 파츠, 눈·입·손, 기존 기준과 정체성 확인 |
| PRO 신체 전신 | 전신 신체/얼굴 → See-through → 선택 Qwen → body.psd | 신체 상반신 항목과 발·다리·몸통. 숨은 관절/피부가 실제 움직임에 충분한지 검수 |
| PRO 헤어 상반신 | 원본 투명 알파 또는 Qwen 전경 알파 → 선택 Qwen → hair.psd | 앞/뒤·좌/우·뿌리·잔머리·가림. 투명 원본 경로는 원본 픽셀을 보존하지만 가려진 뿌리는 새로 그리지 않음 |
| PRO 헤어 전신 | 같은 독립 자산 경로 → hair.psd | 긴 머리의 끝·몸/의상과 가림·전신 위치. Qwen 640 후보를 확대해도 새로운 고해상도 선화는 생기지 않음 |
| PRO 의상 상반신 | 원본 투명 알파 또는 Qwen 전경 알파 → 선택 Qwen → outfit.psd | 소매·깃·단추·몸통·주름과 피부의 가림, 몸 기준에 맞는 실제 착용 위치 |
| PRO 의상 전신 | 같은 독립 자산 경로 → outfit.psd | 상반신 항목과 치마/바지·밑단·신발·뒤쪽. 숨은 뒷면은 원화 보완 필요 |
| PRO 액세서리 상반신 | 원본 투명 알파 또는 Qwen 전경 알파 → 선택 Qwen → accessory.psd | 작은 장식의 알파 가장자리·부착점·독립 움직임. 하나의 유효 레이어가 자연스러운 자산은 강제로 쪼개지 않음 |
| PRO 액세서리 전신 | 같은 독립 자산 경로 → accessory.psd | 상반신 항목과 전신상의 위치·몸/옷과 가림. 캔버스 크기 일치만으로 정합 성공을 주장하지 않음 |

독립 자산의 불투명 원본은 Qwen이 켜져 있고 최소 1회 예산이 있어야 한다. 첫 전경 분리도 총 예산에 포함한다. 배경 layer_0를 제외한 전경 알파를 합치고 원본 RGB에 적용한다. 마스크의 시각 정확성은 검수 대상이다. 투명 원본은 기존 알파를 보존한다. 외부 PSD를 제공하면 모델 분해를 우회하며 캔버스와 프로필을 검증한다.

FREE의 Colab Qwen `auto`는 현재 꺼짐, PRO `auto`는 켜짐이다. FREE 품질이 부족하면 Qwen을 자동으로 켜는 시각 품질 판별기는 구현되어 있지 않다. FREE의 추가 세분화가 필요하면 옵션을 켜서 결과를 비교해야 한다. 강제 분할이나 자동 품질 판정을 이미 구현된 것으로 해석하면 안 된다.

## 3. 커밋·푸시한 수정

| 원인 | 수정 | main의 게시 커밋 |
|---|---|---|
| NF4 체크포인트 계산 BF16이 T4용 로딩 설정 이후에도 남음 | 실제 See-through/Qwen Linear4bit 계산 dtype을 첫 forward 전에 변경 | `382c54d1353a40059db6016121a769b2f5d3de65` |
| 독립 PRO 자산이 전체 캐릭터 body→head 모델에 연결됨 | 투명 원본 보존 및 불투명 원본의 일반 전경 마스크 경로로 분리 | `0ffcd4462e4a570536024a13762a1703ec9fdbd6` |
| 호출하지 않는 parser/SAM2 가중치 준비 | 실제 사용 모델만 다운로드, 미연결 상태 명시 | `bea37273fb609441909365b014b8cb374e40eb91` |
| BF16 지원 GPU에서도 Qwen을 FP16로 강제 | native BF16 지원 GPU는 원래 BF16 실행 유지 | `9034364867a8fcd3aff23d55481071da64d3a0a7` |
| RGB PSD의 알파가 별도 사용자 마스크로 저장됨 | 최종 PSD 알파를 레이어 투명도 채널로 적용 | `a6703160e9ef36f7bfada3fd927233f77482ad9c` |
| 출력 sRGB 프로필 누락 및 다른 프로필의 RGB 재해석 | 출력 ICC 기록, 입력/외부 PSD의 비-sRGB 프로필은 변환 요청 후 중단 | `a37194f5cf0e3d9ca6aeffb2bc23c660da595715` |

FREE 파라미터 제한 안내도 명확히 했다: 총 30개에 블렌드셰이프가 포함되며 그중 블렌드셰이프는 최대 3개다. 30+3이 아니다. 실제 리깅 객체는 Editor에서 검증한다.

## 4. 최고 품질이라고 확정하기 전에 필요한 검증

- 같은 입력·seed로 원본 고정밀과 NF4 결과를 비교하고 얼굴/선화/가림/알파를 검수한다. 현재 NF4 모델은 메모리 절약을 위한 선택이며 최고 화질의 증거가 아니다.
- 실제 T4에서 10개 입력 유형의 모델 실행, RAM/VRAM 피크, 작업 종료/재실행을 확인한다. CPU 텍스트 인코더의 메모리 점유와 추론 시간도 측정한다.
- Qwen 재귀는 공식 권장 기본 4 후보를 모든 부위에 사용하도록 변경했다. 8회·3단계는 프로젝트 재귀 한도이며 공식 단일 4레이어 결과와 비교한다. `.qN`은 마스크 분할 ID이며 동공/하이라이트/치아/혀의 생성 증명이 아니다.
- See-through의 원본 캔버스 복원은 좌표 복원이다. 분해 과정에서 재생성·축소된 원본 RGB를 되살리는 것은 아니다. PRO 직접 원본 경로와 Qwen 마스크 분할은 원래 픽셀을 보존하지만 숨은 영역을 복원하지 않는다.
- PSD를 실제 Cubism Editor에서 열어 RGB/알파/순서를 확인하고 메시·디포머·키폼·물리를 제작해 움직임을 검수한다. psd-tools에서 열린다는 사실만으로 Editor 지원을 확정하지 않는다.
- 외부 PSD의 효과, 혼합 모드, 그룹 불투명도는 이미지 편집기에서 미리 적용한다. 이 importer는 모든 Photoshop 효과를 동일하게 렌더링하는 엔진이 아니다.
- FREE는 ArtMesh 100, 폴더 30, warp+rotation 디포머 합계 50, 파라미터 총 30(블렌드셰이프 최대 3), ArtPath 3, 2048px 텍스처 한 장을 Editor에서 확인한다. 면적 검사는 실제 패킹 성공의 증명이 아니다.

## 5. 검증 기록

집중 CPU 테스트: 162 passed. 실제 PSD·ZIP·ICC·반투명 알파 round-trip, 독립 자산 6개 조합과 FREE/PRO 신체, Qwen 프로세스 계약, 모드/준비/예산 검증을 포함한다. GPU 호출은 테스트에서 추론 경계만 대체했다. 고정 Stable-Layers 원본에 런타임 패치를 적용한 Python 구문 컴파일도 확인했다.

저장소 전체 테스트: **624 passed, 2 skipped, 1 failed**. 실패는 `tests/test_colab_gpu_prewarm.py::test_preloaded_real_face_model_answers_first_request_then_unloads`의 워커 가용성 검사다. 이 환경에서 별도 최소 프로그램으로 AF_UNIX 소켓 생성을 시도해도 `PermissionError [Errno 1] Operation not permitted`가 발생한다. 소켓 테스트나 제작 검사를 비활성화하지 않았다. 실제 GPU 추론 및 Cubism Editor 실행은 이 환경에서 수행하지 않았다.

## 6. 공식 근거 및 재현 소스

- [See-through 공식 저장소](https://github.com/shitagaki-lab/see-through), 고정 revision `df019de5129d6c4b406587a14c3501669441a783`: `inference/scripts/inference_psd_quantized.py`, `common/utils/cv.py`, `common/utils/inference_utils.py`. 현재 프로젝트의 실제 경로와 고정 소스를 대조했다.
- [Stable-Layers 공식 저장소](https://github.com/Stability-AI/Stable-Layers), 고정 revision `b826314b34b12d7c7cce9f0de7f49a330bd8e011`: `decompose.py`와 README. Heun/50/CFG1/640은 이 LoRA 실행의 기준이다.
- [Qwen-Image 공식 저장소](https://github.com/QwenLM/Qwen-Image) 및 [Layered 모델](https://huggingface.co/Qwen/Qwen-Image-Layered). 원본 권장 CFG와 LoRA 실행의 CFG를 혼동하지 않았다.
- [실제 NF4 체크포인트 설정](https://huggingface.co/OzzyGT/qwen-image-layered-bnb-4bit-transformer/blob/main/config.json): 별도 공급자의 NF4 계산 BF16 설정 확인.
- [Diffusers 0.37.0 bitsandbytes 문서](https://huggingface.co/docs/diffusers/v0.37.0/en/quantization/bitsandbytes) 및 동일 버전 wheel의 `quantizers/auto.py`: serialized quantization config 우선 처리 확인.
- [Cubism PSD 작성 주의사항](https://docs.live2d.com/en/cubism-editor-manual/precautions-for-psd-data/) 및 [PSD 준비](https://docs.live2d.com/en/cubism-editor-manual/reimport-psd/): RGB·8-bit·sRGB 및 마스크/효과 적용 지침.
- [Cubism FREE/PRO 공식 비교](https://www.live2d.com/en/cubism/comparison/): 7개 제한과 블렌드셰이프를 포함한 파라미터 총수 확인.

기존 MD 요구의 연결 점검과 이전 수정은 [connection audit](LIVE2D_CONNECTION_AUDIT_2026-10-10.md)에 남아 있다. 이 문서의 독립 PRO 경로가 그 문서의 이전 공통 See-through 설명을 갱신한다.
