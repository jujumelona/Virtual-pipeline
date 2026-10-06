# VTuber Commercial Pipeline

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jujumelona/Virtual-pipeline/blob/main/notebooks/VTuber_Commercial_Pipeline_Colab.ipynb)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)

이미지에서 상업용 VTuber 아바타와 액세서리를 생성하는 오픈소스 파이프라인입니다.

## Overview

이 파이프라인은 두 가지 모드를 제공합니다:

**Avatar Mode**: 단일 이미지를 입력으로 받아 3D 메시를 재구성하고, 템플릿 피팅, 리깅을 거쳐 VRM 파일로 내보냅니다.
- 입력: 캐릭터 이미지 (PNG/JPG)
- 출력: VRM 아바타 파일

**Accessory Mode**: 여러 이미지를 배치로 처리하여 3D 액세서리를 재구성하고 `attachment.json` 설정 파일을 생성합니다.
- 입력: 액세서리 이미지들 (모자, 귀걸이 등)
- 출력: GLB 메시 파일들 + attachment.json

## Open-Source Tools Used

| Tool | License | Purpose | Link |
|------|---------|---------|------|
| anime-face-detector | MIT | 애니메이션 얼굴 감지 및 28개 랜드마크 | https://github.com/hysts/anime-face-detector |
| TripoSR | MIT | 단일 이미지 → 3D 메시 재구성 | https://github.com/VAST-AI-Research/TripoSR |
| trimesh | MIT | 3D 메시 처리 및 변환 | https://github.com/mikedh/trimesh |
| Pillow | HPND (허용적) | 이미지 처리 | https://github.com/python-pillow/Pillow |
| pydantic | MIT | 데이터 검증 | https://github.com/pydantic/pydantic |
| Click | BSD-3 | CLI 인터페이스 | https://github.com/pallets/click |

## Commercial Profile Safety Policy

이 파이프라인은 상업적 사용 시 라이선스 제한이 있는 패키지를 차단하는 안전 검사를 수행합니다.

**차단된 패키지:**
- `instantmesh`: 런타임 경로가 nvdiffrast 사용
- `nvdiffrast`: 퍼블릭 라이선스가 NVIDIA 외 사용을 제한
- `stable-fast-3d`: 커뮤니티 라이선스에 상업적 조건 존재

**안전한 패키지:**
- TripoSR: MIT 라이선스로 상업적 프로필에서 안전하게 사용 가능

## Installation

```bash
# 저장소 클론
git clone https://github.com/jujumelona/Virtual-pipeline.git
cd Virtual-pipeline

# TripoSR 설치 (별도 클론 필요)
git clone https://github.com/VAST-AI-Research/TripoSR
pip install -e TripoSR

# 파이프라인 패키지 설치
pip install -e .
```

## Quick Start

### Google Colab

위의 "Open In Colab" 배지를 클릭하면 로컬 설정 없이 브라우저에서 전체 파이프라인을 실행할 수 있습니다.

### Avatar Mode (CLI)

```bash
vtuber-pipeline avatar --image my_character.png --output output/ --profile commercial
```

### Accessory Mode (CLI)

```bash
vtuber-pipeline accessory --images hat.png earrings.png --output output/
```

### Python API

```python
from vtuber_pipeline.avatar.reconstruction import reconstruct_avatar
from vtuber_pipeline.accessory.attachment import generate_attachment_config, AnchorType

# 아바타 3D 재구성
mesh_path = reconstruct_avatar('character.png', 'output/', profile='commercial')

# 액세서리 attachment 설정 생성
generate_attachment_config(['hat.glb', 'earrings.glb'], 'output/attachment.json', AnchorType.HEAD_TOP)
```

## Pipeline Flow

```
Avatar Mode:
Image → [AnimeFaceDetector] → landmarks.json
      → [TripoSR] → mesh.obj
      → [TemplateFitting*] → fitted_mesh.glb
      → [Rigging*] → rigged_mesh.glb
      → [VRM Export*] → avatar.vrm

Accessory Mode:
Images → [TripoSR × N] → meshes[]
       → [AttachmentConfig] → attachment.json

* = 향후 구현 예정 (placeholder with clear interface)
```

## Project Structure

```
Virtual-pipeline/
├── .agents/
│   └── tasks/
│       ├── implementations.json
│       ├── notebook.json
│       ├── project-files.json
│       └── scaffold.json
├── examples/
│   ├── .gitkeep
│   └── attachment_example.json
├── notebooks/
│   └── VTuber_Commercial_Pipeline_Colab.ipynb
├── tests/
│   └── __init__.py
├── vtuber_pipeline/
│   ├── __init__.py
│   ├── cli.py
│   ├── accessory/
│   │   ├── __init__.py
│   │   ├── attachment.py
│   │   └── reconstruction.py
│   ├── avatar/
│   │   ├── __init__.py
│   │   ├── face_detector.py
│   │   ├── reconstruction.py
│   │   ├── rigging.py
│   │   ├── template_fitting.py
│   │   └── vrm_export.py
│   └── core/
│       ├── __init__.py
│       ├── cache.py
│       ├── config.py
│       └── utils.py
├── .gitignore
├── LICENSE
├── pyproject.toml
├── requirements.txt
└── README.md
```

## License

MIT — LICENSE 파일을 참조하세요. 모든 의존성은 상업적 사용과 호환되는 허용적 라이선스를 사용합니다.
