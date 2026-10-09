"""Colab v8 selection UI: options are shown only for the chosen task/mode.

Mode names describe real output formats. FREE/PRO are Cubism Editor tiers
INSIDE Live2D, not separate VTube Studio/Live2D top-level modes.
This module never downloads models or creates prompts.
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
            expected = qwen == "on" or (qwen == "auto" and edition == "pro")
            if values.get("LIVE2D_USE_QWEN") != expected:
                raise ValueError("Qwen 옵션이 변경되었습니다.")
            return (task, mode, usage, edition, framing, qwen,
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


def require_confirmed_selection(values: dict) -> tuple:
    """Prevent Run All from downloading default models before widget selection."""
    if not values.get("MODE_SELECTION_CONFIRMED"):
        raise RuntimeError(
            "② 설정 미확정: ② 셀에서 작업·모드를 선택하고 '② 설정 확정' 버튼을 "
            "누른 다음 이 셀을 다시 실행하세요. 선택 전 다운로드·업로드·제작은 금지됩니다."
        )
    current = selection_signature(values)
    if values.get("MODE_SELECTION_SNAPSHOT") != current:
        values["MODE_SELECTION_CONFIRMED"] = False
        raise RuntimeError("② 확정 후 옵션이 바뀌었습니다. '② 설정 확정'을 다시 누르세요.")
    return current


def render_notebook_controls(values: dict) -> bool:
    """Render dynamically scoped widgets, update notebook globals on change.

    TASK and every subordinate option are task-scoped widgets.
    Confirming is mandatory before any later download, upload or build.
    """
    try:
        import ipywidgets as w
        from IPython.display import display
    except ImportError:
        # Plain-Python CI can execute the selection cell without Colab.
        # On Colab, missing widgets must be fixed instead of silently using
        # defaults. Cell ③ performs an explicit runtime check.
        return False

    values["MODE_SELECTION_CONFIRMED"] = False
    values.pop("MODE_SELECTION_SNAPSHOT", None)
    status = w.HTML(value="<b>미확정:</b> 모드를 고르고 아래 '② 설정 확정'을 누르세요.")

    def dirty():
        values["MODE_SELECTION_CONFIRMED"] = False
        values.pop("MODE_SELECTION_SNAPSHOT", None)
        status.value = "<b>미확정:</b> 옵션이 변경됐습니다. '② 설정 확정'을 다시 누르세요."

    def select(key, choices: dict, *, name: str, description: str):
        options = [(label, value) for value, label in choices.items()]
        current = values[key]
        control = w.Dropdown(
            options=options, value=current, description=name,
            style={"description_width": "initial"},
            layout=w.Layout(width="min(100%, 860px)"),
        )
        def update(change):
            if change["name"] == "value":
                values[key] = change["new"]
                if key in ("LIVE2D_EDITION", "LIVE2D_QWEN"):
                    refresh_qwen(values)
                dirty()
        control.observe(update, names="value")
        return w.VBox([control, w.HTML(value=description)])

    def text_input(key: str, *, name: str, description: str):
        control = w.Text(
            value=values[key], description=name,
            style={"description_width": "initial"},
            layout=w.Layout(width="min(100%, 860px)"),
        )
        def on_text(change):
            values[key] = change["new"]
            dirty()
        control.observe(on_text, names="value")
        return w.VBox([control, w.HTML(value=description)])

    def bool_input(key: str, *, name: str, description: str):
        control = w.Checkbox(value=values[key], description=name,
                             indent=False, layout=w.Layout(width="min(100%, 860px)"))
        def on_check(change):
            values[key] = change["new"]
            dirty()
        control.observe(on_check, names="value")
        return w.VBox([control, w.HTML(value=description)])

    def paragraph(body: str):
        return w.HTML(value="<div style='padding:6px 0;opacity:.85'>" + body + "</div>")

    def common():
        return [
            select("USAGE", USAGE_LABELS, name="사용 범위",
                   description="선택한 결과의 이용 목적입니다. 무료 배포/개인용이어도 외부 모델의 실제 라이선스를 따릅니다."),
        ]

    def mode_options(mode: str):
        if mode == "live2d":
            return [
                paragraph("<b>Live2D → Cubism FREE / PRO</b>. 둘 다 VTube Studio 호환 Live2D용입니다. "
                          "FREE/PRO는 VTube Studio 버전이 아닌 Cubism Editor의 제작 등급입니다."),
                select("LIVE2D_EDITION", EDITION_LABELS, name="Cubism 등급",
                       description="FREE: 헤어·의상·장식까지 착용한 완성 이미지 1장, ArtMesh 최대 100개. "
                                   "PRO: 기준 외형 + 몸체·헤어·의상·선택 액세서리를 별도 이미지로 준비합니다."),
                select("LIVE2D_FRAMING", FRAMING_LABELS, name="제작 범위",
                       description="상반신과 전신 모두 정면 기준입니다. 두 범위를 동시에 생성할 필요는 없습니다."),
                select("LIVE2D_QWEN", QWEN_LABELS, name="Qwen 세부 분해",
                       description="auto는 FREE에서 Qwen을 설치하지 않고 PRO에서 추가 설치합니다. "
                                   "on은 둘 다 설치·실행, off는 모두 제외. "
                                   "Qwen 4비트+Stable-Layers는 Colab T4 실기 성공 미확인입니다."),
                text_input("EXISTING_IMAGE_PATH", name="기존 원본 경로 (선택)",
                           description="FREE 완성 원본 이미지가 이미 /content에 있으면 경로를 입력합니다. "
                                       "비워 두면 ④ 셀에서 업로드합니다. PRO는 ④에서 독립 PNG를 업로드합니다."),
                paragraph("외부 대형 이미지 AI 생성 프롬프트는 <b>README</b>에만 있습니다. "
                          "여기서는 그림을 생성하거나 프롬프트를 출력하지 않습니다."),
            ]
        if mode == "inochi2d":
            return [
                select("TWO_D_INPUT", TWO_D_LABELS, name="Inochi2D 입력",
                       description="sheets: README 시트 ZIP. provided_layers: 20개 분리 레이어. "
                                   "automatic: 그림 1장에서 AI 분리."),
                text_input("EXISTING_IMAGE_PATH", name="기존 원본 경로 (선택)",
                           description="automatic 입력에서 사용할 수 있습니다. 비우면 ④에서 업로드합니다."),
            ]
        return [
            bool_input("MULTI_REFERENCE_3D", name="3D 다중 시점 시트 사용",
                       description="켜짐: 정면·후면·좌우·얼굴 참조가 포함된 시트 ZIP 입력. "
                                   "꺼짐: 캐릭터 원본 1장 입력."),
            text_input("EXISTING_IMAGE_PATH", name="기존 원본 경로 (선택)",
                       description="단일 이미지 입력일 때 사용. 비우면 ④에서 업로드합니다."),
        ]

    def accessory_options(subtype: str):
        if subtype == "소품":
            return [
                select("ACCESSORY_ANCHOR", ANCHOR_LABELS, name="소품 부착 위치",
                       description="AUTO는 이미지 파일명으로 위치를 판단합니다. "
                                   "ALL은 모든 위치에 중복 적용되므로 필요한 경우에만 선택하세요."),
                text_input("ACCESSORY_BASE_VRM_PATH", name="기존 VRM 경로 (선택)",
                           description="입력하면 해당 VRM을 기준으로 사용합니다. 비우면 최근 결과나 ④ 업로드를 이용합니다."),
            ]
        if subtype == "2D 교체 의상":
            return [
                select("OUTFIT_2D_TARGET", {
                    "live2d": "Live2D Cubism — 기존 분리형 의상 경로",
                    "inochi2d": "Inochi2D — 기존 분리형 의상 경로",
                }, name="의상 제작 대상",
                       description="이 옵션은 기존 교체형 의상 제작 경로입니다. "
                                   "Live2D FREE 완성 캐릭터 1장 제작과 혼동하지 마세요."),
                text_input("WARDROBE_2D_BASE_ZIP_PATH", name="기존 2D 기준 ZIP (선택)",
                           description="기준 중립 캐릭터 시트 ZIP이 있으면 경로 지정. 없으면 ④에서 업로드합니다."),
            ]
        return [
            text_input("ACCESSORY_BASE_VRM_PATH", name="기존 VRM 경로 (선택)",
                       description="의상을 적용할 VRM 경로. 비우면 최근 VRM이나 ④ 업로드를 사용합니다."),
            text_input("WARDROBE_XWEAR_PATH", name="XWear 원본 경로 (선택)",
                       description="VRoid Studio 의상 파일 경로. 비우면 ④에서 costume.xwear를 업로드합니다."),
        ]

    pane = w.VBox()
    shared = common()
    task_picker = select("TASK", {
        "캐릭터 생성": "캐릭터 생성 — Live2D / Inochi2D / 3D VRM",
        "액세서리 제작": "액세서리 제작 — 소품 / 교체 의상",
    }, name="① 작업 종류",
       description="작업을 바꾸면 아래 옵션이 즉시 전환됩니다. 셀을 다시 실행할 필요는 없습니다.")

    def redraw_task(change=None):
        if values["TASK"] == "캐릭터 생성":
            detail = w.VBox()
            mode_picker = select("MODE", MODE_LABELS, name="② 캐릭터 제작 모드",
                                 description="Live2D를 고른 뒤 FREE / PRO를 선택합니다.")
            def redraw_mode(change=None):
                detail.children = tuple(mode_options(values["MODE"]))
            mode_picker.children[0].observe(redraw_mode, names="value")
            redraw_mode()
            pane.children = (paragraph("<b>캐릭터 생성 설정</b>"), mode_picker, detail)
        else:
            detail = w.VBox()
            subtype_picker = select("ACCESSORY_SUBTYPE", ACCESSORY_LABELS,
                                    name="② 액세서리·의상 작업",
                                    description="선택한 소품·의상 작업의 옵션만 표시합니다.")
            def redraw_subtype(change=None):
                detail.children = tuple(accessory_options(values["ACCESSORY_SUBTYPE"]))
            subtype_picker.children[0].observe(redraw_subtype, names="value")
            redraw_subtype()
            pane.children = (paragraph("<b>액세서리·의상 제작 설정</b>"), subtype_picker, detail)

    task_picker.children[0].observe(redraw_task, names="value")
    redraw_task()
    confirm = w.Button(description="② 설정 확정 — ③ 진행 허용",
                       button_style="success", icon="check",
                       layout=w.Layout(width="330px"))
    def on_confirm(_):
        try:
            refresh_qwen(values)
            snapshot = selection_signature(values)
        except ValueError as exc:
            dirty()
            status.value = "<b>설정 오류:</b> " + str(exc)
            return
        values["MODE_SELECTION_SNAPSHOT"] = snapshot
        values["MODE_SELECTION_CONFIRMED"] = True
        status.value = ("<b>설정 확정 완료.</b> ③ 모델 다운로드 셀을 실행하세요. "
                        "선택값을 바꾸면 다시 확정해야 합니다.")
        print("[② 설정 확정]", " / ".join(map(str, snapshot[:4])), flush=True)
    confirm.on_click(on_confirm)
    display(w.VBox([task_picker, *shared, pane, confirm, status]))
    return True


def refresh_qwen(values: dict) -> None:
    q = values["LIVE2D_QWEN"]
    edition = values["LIVE2D_EDITION"]
    values["LIVE2D_USE_QWEN"] = q == "on" or (q == "auto" and edition == "pro")
