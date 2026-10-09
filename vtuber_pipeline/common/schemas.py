"""Stable on-disk interchange contracts; no GPU tensor crosses a worker boundary."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal
import json

Mode = Literal["inochi2d", "live2d", "3d"]
Status = Literal["failed", "prepared", "needs_editor_export", "complete"]

@dataclass
class SourceSet:
    mode: Mode
    front_image: str
    face_image: str | None = None
    back_image: str | None = None
    left_image: str | None = None
    right_image: str | None = None
    user_layers_zip: str | None = None
    commercial_usage: str = "corporation"
    output_dir: str = "output"
    artwork_profile: str = "legacy"  # vts_auto accepts imported See-through layer schema

    def validate(self) -> None:
        if self.mode not in ("inochi2d", "live2d", "3d"):
            raise ValueError("unsupported mode")
        if self.artwork_profile not in ("legacy", "vts_auto"):
            raise ValueError("unsupported artwork profile")
        if self.commercial_usage not in ("personalNonProfit", "personalProfit", "corporation"):
            raise ValueError("unsupported commercial usage")
        if not Path(self.front_image).is_file():
            raise FileNotFoundError(self.front_image)
        for attr in ("face_image", "back_image", "left_image", "right_image", "user_layers_zip"):
            value = getattr(self, attr)
            if value and not Path(value).is_file():
                raise FileNotFoundError(value)

@dataclass
class Part:
    semantic_id: str
    rgba_png: str
    mask_png: str
    hidden_fill_mask_png: str | None
    bbox_xyxy: list[int]
    z_order: int
    landmarks_xy: list[list[float]]
    source_stage: str

@dataclass
class PartsDocument:
    width: int
    height: int
    parts: list[Part]
    psd_path: str | None
    ora_path: str

    def write(self, path: str) -> str:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def read(cls, path: str) -> "PartsDocument":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["parts"] = [Part(**item) for item in data["parts"]]
        return cls(**data)

@dataclass
class MeshSource:
    glb_path: str
    origin_model: str
    camera_json: str
    front_mask: str
    normal_path: str | None

@dataclass
class BuildResult:
    mode: Mode
    status: Status
    primary_file: str | None
    editable_file: str | None
    intermediate_dir: str
    error: str | None = None

    def write(self, output_dir: str) -> str:
        from .completion import validate_build_result
        validate_build_result(self)
        path = Path(output_dir) / "production_result.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)
