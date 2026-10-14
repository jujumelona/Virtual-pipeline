"""Six fixed production modes and a shared independent-asset selector.

Phase 1 deliberately has NO model downloads, decomposition, artwork generation
or exporter action. Later pipeline stages consume this contract directly.
"""
from __future__ import annotations

from dataclasses import dataclass

TOP_MODE_CHOICES = {
    "live2d_bust_up": ("Live2D 바스트업", "live2d", "upper"),
    "live2d_upper": ("Live2D 상반신", "live2d", "upper"),
    "live2d_full": ("Live2D 전신", "live2d", "full"),
    "inochi2d_upper": ("Inochi2D 상반신", "inochi2d", "upper"),
    "inochi2d_full": ("Inochi2D 전신", "inochi2d", "full"),
    "3d": ("3D", "3d", "full"),
}
ASSET_KINDS = {
    "body": "신체만",
    "hair": "헤어만",
    "accessory": "액세서리만",
    "outfit": "의상만",
}

# The Colab dropdown displays Korean labels; machine keys remain stable.
DISPLAY_TO_MODE = {info[0]: key for key, info in TOP_MODE_CHOICES.items()}
DISPLAY_TO_ASSET = {label: key for key, label in ASSET_KINDS.items()}

@dataclass(frozen=True)
class AssetSelection:
    top_mode: str
    family: str
    framing: str
    asset_kind: str

    @property
    def mode_label(self) -> str:
        return TOP_MODE_CHOICES[self.top_mode][0]

    @property
    def asset_label(self) -> str:
        return ASSET_KINDS[self.asset_kind]

    def as_dict(self) -> dict:
        return {
            "schema": "vtuber/asset-selection-v1",
            "top_mode": self.top_mode,
            "family": self.family,
            "framing": self.framing,
            "asset_kind": self.asset_kind,
        }


def select_mode(top_mode: str, asset_kind: str) -> AssetSelection:
    """Validate UI state; no model or filesystem side effects."""
    if top_mode not in TOP_MODE_CHOICES:
        raise ValueError("상위 제작 모드는 Live2D 바스트업/상반신/전신, Inochi2D 상반신/전신, 3D 중 선택하세요.")
    if asset_kind not in ASSET_KINDS:
        raise ValueError("하위 자산은 신체/헤어/액세서리/의상 중 하나를 선택하세요.")
    _, family, framing = TOP_MODE_CHOICES[top_mode]
    return AssetSelection(top_mode=top_mode, family=family, framing=framing,
                          asset_kind=asset_kind)


def selection_signature(values: dict) -> tuple:
    selection = select_mode(values.get("TOP_MODE"), values.get("ASSET_KIND"))
    return (selection.top_mode, selection.asset_kind)


def begin_mode_selection(values: dict) -> None:
    """Discard all previous selections when a new parent mode is chosen."""
    top_mode = values.get("TOP_MODE")
    if top_mode not in TOP_MODE_CHOICES:
        raise ValueError("상위 제작 모드를 먼저 선택하세요.")
    values["ASSET_KIND"] = None
    values["MODE_CONFIG_APPLIED"] = None
    values["MODE_CONFIG_SIGNATURE"] = None


def apply_submode(values: dict, selected: str, updates: dict) -> bool:
    """One shared subtype UI for *all* six parent modes."""
    if values.get("TOP_MODE") != selected:
        return False
    values.update(updates)
    signature = selection_signature(values)
    values["MODE_CONFIG_APPLIED"] = selected
    values["MODE_CONFIG_SIGNATURE"] = signature
    return True


def require_submode_config(values: dict) -> AssetSelection:
    """Protect against stale notebook cells without inventing feature gates."""
    selection = select_mode(values.get("TOP_MODE"), values.get("ASSET_KIND"))
    if (values.get("MODE_CONFIG_APPLIED") != selection.top_mode
            or values.get("MODE_CONFIG_SIGNATURE") !=
            (selection.top_mode, selection.asset_kind)):
        raise RuntimeError("현재 상위·하위 선택에 맞게 공통 설정 셀을 다시 실행하세요.")
    return selection
