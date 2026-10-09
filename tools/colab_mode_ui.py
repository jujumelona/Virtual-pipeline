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


def refresh_qwen(values: dict) -> None:
    q = values["LIVE2D_QWEN"]
    edition = values["LIVE2D_EDITION"]
    values["LIVE2D_USE_QWEN"] = q == "on" or (q == "auto" and edition == "pro")


def _browser_form_js(values: dict) -> str:
    """A JavaScript Promise resolved only by the user pressing submit."""
    import json

    fields = [
        {"id": "TASK", "title": "작업 종류", "options": {
            "캐릭터 생성": "캐릭터 생성 — Live2D / Inochi2D / 3D VRM",
            "액세서리 제작": "액세서리 제작 — 소품 / 교체 의상",
        }, "desc": "작업 종류에 따라 아래 설정이 자동으로 바뀝니다."},
        {"id": "MODE", "title": "캐릭터 제작 방식", "options": MODE_LABELS,
         "desc": "Live2D 아래에서 Cubism FREE/PRO를 선택합니다."},
        {"id": "LIVE2D_EDITION", "title": "Live2D 등급", "options": EDITION_LABELS,
         "desc": "FREE는 한 장의 완성 캐릭터, PRO는 기준 외형·헤어·의상 등 분리 이미지."},
        {"id": "LIVE2D_FRAMING", "title": "Live2D 제작 범위", "options": FRAMING_LABELS,
         "desc": "상반신 또는 전신을 선택하세요."},
        {"id": "LIVE2D_QWEN", "title": "Qwen 4bit + Stable-Layers", "options": QWEN_LABELS,
         "desc": "auto는 FREE 기본 분해, PRO는 Qwen 추가. T4 구동은 미검증입니다."},
        {"id": "TWO_D_INPUT", "title": "Inochi2D 입력 방식", "options": TWO_D_LABELS,
         "desc": "시트 ZIP, 분리 PNG 또는 자동 분리."},
        {"id": "MULTI_REFERENCE_3D", "title": "3D 다중 시점 이미지", "kind": "checkbox",
         "desc": "체크하면 다중 시점 ZIP, 해제하면 단일 이미지 입력."},
        {"id": "ACCESSORY_SUBTYPE", "title": "액세서리·의상 제작", "options": ACCESSORY_LABELS,
         "desc": "소품·2D 의상·3D XWear 중 하나를 선택합니다."},
        {"id": "ACCESSORY_ANCHOR", "title": "소품 부착 위치", "options": ANCHOR_LABELS,
         "desc": "AUTO는 파일명으로 판별, ALL은 모든 위치에 적용."},
        {"id": "OUTFIT_2D_TARGET", "title": "2D 교체 의상 대상", "options": {
            "live2d": "Live2D Cubism — 기존 교체형 의상 경로",
            "inochi2d": "Inochi2D — 기존 교체형 의상 경로",
        }, "desc": "교체 의상의 대상 2D 프로그램입니다."},
        {"id": "USAGE", "title": "사용 범위", "options": USAGE_LABELS,
         "desc": "개인 비영리, 개인 수익 또는 기업 사용을 선택하세요."},
        {"id": "EXISTING_IMAGE_PATH", "title": "기존 이미지 경로 (선택)", "kind": "text",
         "desc": "이미지가 있으면 /content 경로, 없으면 비워 두세요."},
        {"id": "ACCESSORY_BASE_VRM_PATH", "title": "소품·의상 기준 VRM 경로 (선택)", "kind": "text",
         "desc": "기존 VRM 경로. 비우면 이전 결과나 업로드를 이용합니다."},
        {"id": "WARDROBE_2D_BASE_ZIP_PATH", "title": "교체 의상 기준 2D ZIP (선택)", "kind": "text",
         "desc": "기존 2D 캐릭터 기준 ZIP 경로."},
        {"id": "WARDROBE_XWEAR_PATH", "title": "XWear 파일 경로 (선택)", "kind": "text",
         "desc": "기존 XWear 경로. 비우면 ④에서 업로드합니다."},
    ]
    initial = {field["id"]: values.get(field["id"], "") for field in fields}
    data = json.dumps({"fields": fields, "initial": initial}, ensure_ascii=False)
    # Colab output.eval_js awaits the Promise. No notebook polling, timers or
    # asynchronous ipywidgets callbacks are required.
    return """new Promise((resolve, reject) => {
  const data = """ + data + """;
  const panel = document.createElement('section');
  panel.style.cssText = 'box-sizing:border-box;width:100%;max-width:860px;padding:16px;border:1px solid #888;border-radius:10px;font:14px system-ui,sans-serif;line-height:1.5';
  const title = document.createElement('div');
  title.textContent = '② 제작 옵션 — 선택을 완료하고 아래 확정 버튼을 누르세요.';
  title.style.cssText = 'font-weight:700;font-size:16px;margin-bottom:10px';
  panel.append(title);
  const status = document.createElement('div');
  status.textContent = '선택이 끝나기 전에는 이 셀이 완료되지 않아 ③으로 넘어가지 않습니다.';
  status.style.cssText = 'margin:5px 0 12px';
  panel.append(status);
  const rows = {}, controls = {};
  for (const f of data.fields) {
    const row = document.createElement('div');
    row.style.cssText = 'margin-bottom:14px';
    const label = document.createElement('label');
    label.textContent = f.title;
    label.style.cssText = 'display:block;font-weight:650;margin-bottom:4px';
    let control;
    if (f.kind === 'text') {
      control = document.createElement('input');
      control.type = 'text';
      control.value = data.initial[f.id] || '';
      control.style.cssText = 'box-sizing:border-box;width:100%;padding:8px';
    } else if (f.kind === 'checkbox') {
      control = document.createElement('input');
      control.type = 'checkbox';
      control.checked = !!data.initial[f.id];
      control.style.cssText = 'width:18px;height:18px';
    } else {
      control = document.createElement('select');
      control.style.cssText = 'box-sizing:border-box;width:100%;padding:8px';
      for (const [key, caption] of Object.entries(f.options)) {
        const option = document.createElement('option');
        option.value = key;
        option.textContent = caption;
        control.append(option);
      }
      if (Object.prototype.hasOwnProperty.call(f.options, data.initial[f.id])) {
        control.value = data.initial[f.id];
      }
    }
    label.htmlFor = control.id = 'vp_choice_' + f.id;
    control.setAttribute('aria-label', f.title);
    control.addEventListener('change', update);
    const description = document.createElement('div');
    description.textContent = f.desc;
    description.style.cssText = 'font-size:12px;opacity:.75;margin-top:3px';
    row.append(label, control, description);
    panel.append(row);
    rows[f.id] = row;
    controls[f.id] = control;
  }
  function value(id) {return controls[id].value;}
  function visible(id, enabled) {rows[id].style.display = enabled ? 'block' : 'none';}
  function update() {
    const character = value('TASK') === '캐릭터 생성';
    const live2d = character && value('MODE') === 'live2d';
    const subtype = value('ACCESSORY_SUBTYPE');
    visible('MODE', character);
    visible('LIVE2D_EDITION', live2d);
    visible('LIVE2D_FRAMING', live2d);
    visible('LIVE2D_QWEN', live2d);
    visible('TWO_D_INPUT', character && value('MODE') === 'inochi2d');
    visible('MULTI_REFERENCE_3D', character && value('MODE') === '3d');
    visible('EXISTING_IMAGE_PATH', character);
    visible('ACCESSORY_SUBTYPE', !character);
    visible('ACCESSORY_ANCHOR', !character && subtype === '소품');
    visible('OUTFIT_2D_TARGET', !character && subtype === '2D 교체 의상');
    visible('ACCESSORY_BASE_VRM_PATH', !character && subtype !== '2D 교체 의상');
    visible('WARDROBE_2D_BASE_ZIP_PATH', !character && subtype === '2D 교체 의상');
    visible('WARDROBE_XWEAR_PATH', !character && subtype === '3D 교체 의상(XWear)');
    visible('USAGE', true);
  }
  update();
  const submit = document.createElement('button');
  submit.textContent = '② 설정 확정 및 ③ 진행';
  submit.style.cssText = 'padding:11px 18px;border-radius:7px;background:#1976d2;color:white;font-weight:700;border:0;cursor:pointer';
  panel.append(submit);
  submit.addEventListener('click', () => {
    const result = {};
    for (const f of data.fields) {
      const control = controls[f.id];
      result[f.id] = f.kind === 'checkbox' ? control.checked : control.value;
    }
    submit.disabled = true;
    status.textContent = '설정이 확정되었습니다. 다운로드 준비 단계로 진행합니다.';
    resolve(result);
  }, {once:true});
  (document.querySelector('#output-area') || document.body).append(panel);
  panel.scrollIntoView({block:'nearest'});
})"""


def choose_notebook_controls(values: dict, *, evaluate=None) -> tuple:
    """Pause the current Colab cell until the browser's submit Promise resolves.

    The evaluate dependency is injectable for deterministic CPU-only tests.
    """
    values["MODE_SELECTION_CONFIRMED"] = False
    values.pop("MODE_SELECTION_SNAPSHOT", None)
    if evaluate is None:
        try:
            from google.colab import output
        except ImportError as exc:
            raise RuntimeError("Colab의 ② 셀에서 옵션을 선택하세요.") from exc
        def evaluate(script):
            return output.eval_js(script, timeout_sec=None)
    selected = evaluate(_browser_form_js(values))
    if not isinstance(selected, dict):
        raise RuntimeError("② 선택 창이 완료되지 않았습니다. 다시 실행하세요.")
    allowed = {
        "TASK", "MODE", "LIVE2D_EDITION", "LIVE2D_FRAMING", "LIVE2D_QWEN",
        "TWO_D_INPUT", "MULTI_REFERENCE_3D", "ACCESSORY_SUBTYPE",
        "ACCESSORY_ANCHOR", "OUTFIT_2D_TARGET", "USAGE",
        "EXISTING_IMAGE_PATH", "ACCESSORY_BASE_VRM_PATH",
        "WARDROBE_2D_BASE_ZIP_PATH", "WARDROBE_XWEAR_PATH",
    }
    if set(selected) != allowed:
        raise RuntimeError("② 선택 결과의 필드가 올바르지 않습니다.")
    candidate = dict(values)
    candidate.update(selected)
    refresh_qwen(candidate)
    snapshot = selection_signature(candidate)
    values.update(selected)
    values["LIVE2D_USE_QWEN"] = candidate["LIVE2D_USE_QWEN"]
    values["MODE_SELECTION_SNAPSHOT"] = snapshot
    values["MODE_SELECTION_CONFIRMED"] = True
    return snapshot
