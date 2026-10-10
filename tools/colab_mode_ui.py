"""Static Colab mode validation and routing.

Colab's native #@param form is the sole UI. No browser JavaScript,
ipywidgets, callbacks, confirmation buttons or blocking mode dialogs.
"""
from __future__ import annotations

MODE_LABELS = {
    "3d": "3D VRM — 전신 3D 캐릭터",
    "inochi2d": "Inochi2D — Inochi Creator/Session용 2D",
    "live2d": "Live2D — Cubism / VTube Studio 호환 2D",
}
EDITION_LABELS = {
    "free": "FREE — 완성 스타일 1장 · Cubism FREE 제한",
    "pro": "PRO — 헤어·의상·액세서리 분리 자산",
}
PRO_ASSET_LABELS = {"body": "신체·얼굴만 제작", "hair": "헤어만 제작",
                    "outfit": "의상만 제작", "accessory": "액세서리만 제작"}
FRAMING_LABELS = {
    "upper": "상반신 — 머리부터 허리/골반 위, 양팔·양손 포함",
    "full": "전신 — 머리부터 양발·신발까지 전부 포함",
}
QWEN_LABELS = {
    "auto": "자동 — FREE는 기본 분해, PRO는 Qwen 4비트 + Stable-Layers",
    "on": "사용 — Qwen 4비트 + Stable-Layers 추가 실행 (T4 미검증)",
    "off": "미사용 — See-through NF4 중심 분해",
}
USAGE_LABELS = {
    "personalNonProfit": "개인 비영리 — 개인용·비수익 사용",
    "personalProfit": "개인 수익 — 개인 창작·수익 활동",
    "corporation": "기업 — 조직·법인 사용",
}
TWO_D_LABELS = {
    "sheets": "시트 ZIP — 기준 이미지 + 6개 분할 시트",
    "provided_layers": "분리 PNG — 기준 1장 + 리깅 파츠 20장",
    "automatic": "자동 분리 — 원본 캐릭터 이미지 1장",
}
ACCESSORY_LABELS = {
    "소품": "소품 — 기존 VRM에 액세서리 이미지 부착",
    "2D 교체 의상": "2D 교체 의상 — 기존 중립 베이스에 새 의상·헤어 추가",
    "3D 교체 의상(XWear)": "3D 교체 의상 — 기존 VRM과 XWear를 VRoid Editor에 전달",
}
ANCHOR_LABELS = {
    "AUTO": "AUTO — 소품 파일명으로 부착 위치 자동 판단",
    "ALL": "ALL — 모든 지원 부착 위치에 각각 적용",
    "HEAD_TOP": "HEAD_TOP — 머리 위",
    "FACE": "FACE — 얼굴",
    "LEFT_EAR": "LEFT_EAR — 왼쪽 귀",
    "RIGHT_EAR": "RIGHT_EAR — 오른쪽 귀",
    "NECK": "NECK — 목",
    "CHEST": "CHEST — 가슴",
    "BACK": "BACK — 등",
    "LEFT_SHOULDER": "LEFT_SHOULDER — 왼쪽 어깨",
    "RIGHT_SHOULDER": "RIGHT_SHOULDER — 오른쪽 어깨",
    "LEFT_HAND": "LEFT_HAND — 왼손",
    "RIGHT_HAND": "RIGHT_HAND — 오른손",
    "LEFT_FOOT": "LEFT_FOOT — 왼발",
    "RIGHT_FOOT": "RIGHT_FOOT — 오른발",
    "HIPS": "HIPS — 골반/엉덩이",
}


def internal_scope(task: str, mode: str, edition: str,
                   accessory_subtype: str, outfit_target: str) -> str:
    """One place for notebook download/build routing; no VTS top-level mode."""
    if task == "액세서리 제작":
        if accessory_subtype == "3D 교체 의상(XWear)":
            return "wardrobe_handoff"
        if accessory_subtype == "2D 교체 의상":
            return outfit_target
        return "3d"
    if task != "캐릭터 생성" or mode not in MODE_LABELS:
        raise ValueError("Unknown production task/mode")
    if mode == "live2d":
        if edition not in EDITION_LABELS:
            raise ValueError("Unknown Cubism FREE/PRO edition")
        return "live2d_" + edition
    return mode


def input_profile(task: str, mode: str, subtype: str, two_d_input: str,
                  multi_reference_3d: bool) -> str:
    if task == "액세서리 제작":
        if subtype == "3D 교체 의상(XWear)":
            return "wardrobe_3d"
        if subtype == "2D 교체 의상":
            return "wardrobe_2d"
        return "standard"
    if mode == "live2d":
        return "live2d_artwork"
    if mode == "inochi2d":
        return two_d_input
    if mode == "3d" and multi_reference_3d:
        return "sheets"
    return "standard"


def selection_signature(values: dict) -> tuple:
    """Only the active task's settings determine the current selection."""
    task, usage = values.get("TASK"), values.get("USAGE")
    if usage not in USAGE_LABELS:
        raise ValueError("사용 범위를 확인하세요.")
    if task == "캐릭터 생성":
        mode = values.get("MODE")
        if mode not in MODE_LABELS:
            raise ValueError("캐릭터 모드를 확인하세요.")
        if mode == "live2d":
            edition, framing, qwen = (values.get("LIVE2D_EDITION"), values.get("LIVE2D_FRAMING"),
                                      values.get("LIVE2D_QWEN"))
            if edition not in EDITION_LABELS or framing not in FRAMING_LABELS or qwen not in QWEN_LABELS:
                raise ValueError("Live2D 등급·제작 범위·Qwen 옵션을 확인하세요.")
            asset_kind = values.get("LIVE2D_PRO_ASSET", "body")
            if edition == "pro" and asset_kind not in PRO_ASSET_LABELS:
                raise ValueError("PRO 독립 제작 종류를 확인하세요.")
            passes = values.get("LIVE2D_QWEN_PASSES", 8)
            layers = values.get("LIVE2D_QWEN_LAYERS", 4)
            if not isinstance(passes, int) or not 0 <= passes <= 12:
                raise ValueError("Qwen 반복 횟수 0..12 범위를 확인하세요.")
            if not isinstance(layers, int) or not 2 <= layers <= 10:
                raise ValueError("Qwen 회당 분리 레이어 2..10 범위를 확인하세요.")
            expected = qwen == "on" or (qwen == "auto" and edition == "pro")
            if values.get("LIVE2D_USE_QWEN") != expected:
                raise ValueError("Qwen 옵션이 변경되었습니다.")
            return (task, mode, usage, edition, framing, qwen,
                    layers, passes, asset_kind if edition == "pro" else None,
                    values.get("EXISTING_IMAGE_PATH", ""))
        if mode == "inochi2d":
            setting = values.get("TWO_D_INPUT")
            if setting not in TWO_D_LABELS:
                raise ValueError("Inochi2D 입력 방식을 확인하세요.")
            return (task, mode, usage, setting, values.get("EXISTING_IMAGE_PATH", ""))
        return (task, mode, usage, bool(values.get("MULTI_REFERENCE_3D")),
                values.get("EXISTING_IMAGE_PATH", ""))
    if task == "액세서리 제작":
        subtype = values.get("ACCESSORY_SUBTYPE")
        if subtype not in ACCESSORY_LABELS:
            raise ValueError("액세서리 작업 종류를 확인하세요.")
        if subtype == "소품":
            anchor = values.get("ACCESSORY_ANCHOR")
            if anchor not in ANCHOR_LABELS:
                raise ValueError("소품 부착 위치를 확인하세요.")
            return (task, subtype, usage, anchor, values.get("ACCESSORY_BASE_VRM_PATH", ""))
        if subtype == "2D 교체 의상":
            target = values.get("OUTFIT_2D_TARGET")
            if target not in ("live2d", "inochi2d"):
                raise ValueError("교체 의상 대상을 확인하세요.")
            return (task, subtype, usage, target, values.get("WARDROBE_2D_BASE_ZIP_PATH", ""))
        return (task, subtype, usage, values.get("ACCESSORY_BASE_VRM_PATH", ""),
                values.get("WARDROBE_XWEAR_PATH", ""))
    raise ValueError("작업 종류를 선택하세요.")


def refresh_qwen(values: dict) -> None:
    """Derive Qwen execution from static Colab #@param settings."""
    q = values["LIVE2D_QWEN"]
    edition = values["LIVE2D_EDITION"]
    if q not in QWEN_LABELS or edition not in EDITION_LABELS:
        raise ValueError("Live2D FREE/PRO 또는 Qwen 옵션이 올바르지 않습니다.")
    values["LIVE2D_USE_QWEN"] = q == "on" or (q == "auto" and edition == "pro")


# Native Colab form routing. Only the selected category's settings cell updates
# the active configuration. No callbacks, confirmation buttons or JS polling.
TOP_LEVEL_CHOICES = {
    "Live2D": ("캐릭터 생성", "live2d"),
    "Inochi2D": ("캐릭터 생성", "inochi2d"),
    "3D VRM": ("캐릭터 생성", "3d"),
    "액세서리 제작": ("액세서리 제작", "3d"),
}


def begin_mode_selection(values: dict) -> None:
    top = values.get("TOP_LEVEL_MODE")
    if top not in TOP_LEVEL_CHOICES:
        raise ValueError("상위 제작 모드가 올바르지 않습니다.")
    values["TASK"], values["MODE"] = TOP_LEVEL_CHOICES[top]
    values["MODE_CONFIG_APPLIED"] = None
    values.pop("MODE_CONFIG_SIGNATURE", None)
    # Defaults are internal fallbacks for inactive settings, NOT choices
    # applied on behalf of the user for the active mode.
    defaults = {
        "LIVE2D_EDITION": "free",
        "LIVE2D_PRO_ASSET": "body",
        "LIVE2D_FRAMING": "upper",
        "LIVE2D_QWEN": "auto",
        "LIVE2D_QWEN_LAYERS": 4,
        "LIVE2D_QWEN_PASSES": 8,
        "LIVE2D_USE_QWEN": False,
        "TWO_D_INPUT": "sheets",
        "MULTI_REFERENCE_3D": True,
        "ACCESSORY_SUBTYPE": "소품",
        "OUTFIT_2D_TARGET": "live2d",
        "ACCESSORY_ANCHOR": "AUTO",
        "ACCESSORY_BASE_VRM_PATH": "",
        "WARDROBE_2D_BASE_ZIP_PATH": "",
        "WARDROBE_XWEAR_PATH": "",
        "EXISTING_IMAGE_PATH": "",
    }
    for key, val in defaults.items():
        values[key] = val


def apply_submode(values: dict, selected: str, updates: dict) -> bool:
    """Return False for unselected cells without applying their options."""
    if values.get("TOP_LEVEL_MODE") != selected:
        return False
    if selected not in TOP_LEVEL_CHOICES:
        raise ValueError("알 수 없는 상위 모드")
    expected_task, expected_mode = TOP_LEVEL_CHOICES[selected]
    if (values.get("TASK"), values.get("MODE")) != (expected_task, expected_mode):
        raise RuntimeError("② 상위 모드 셀을 다시 실행하세요.")
    values.update(updates)
    if selected == "Live2D":
        refresh_qwen(values)
    signature = selection_signature(values)
    values["MODE_CONFIG_APPLIED"] = selected
    values["MODE_CONFIG_SIGNATURE"] = signature
    return True


def require_submode_config(values: dict) -> tuple:
    """Reject ③/④/⑤ until the matching submode cell has actually run."""
    top = values.get("TOP_LEVEL_MODE")
    if top not in TOP_LEVEL_CHOICES:
        raise RuntimeError("② 상위 모드를 먼저 선택하세요.")
    if values.get("MODE_CONFIG_APPLIED") != top:
        raise RuntimeError(
            "② 선택된 상위 모드의 전용 설정 셀을 실행한 다음 ③으로 진행하세요."
        )
    signature = selection_signature(values)
    if values.get("MODE_CONFIG_SIGNATURE") != signature:
        raise RuntimeError("② 하위 옵션이 변경되었습니다. 해당 모드의 설정 셀부터 다시 실행하세요.")
    return signature
