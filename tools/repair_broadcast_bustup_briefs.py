"""Regenerate README-linked Live2D bust-up artwork instruction ZIPs.

This is an explicit migration, not an image quality certificate. Run from a
checkout: python tools/repair_broadcast_bustup_briefs.py --write
No GitHub upload, Cubism processing, or GPU rendering is performed here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import tempfile
import os
from zipfile import ZipFile

KITS = Path(__file__).resolve().parents[1] / 'docs' / 'image_ai_kits_v2'
ASSETS = ('body', 'hair', 'outfit', 'accessory')
FRAME = ('방송용 Live2D 바스트업은 머리부터 배 바로 위 또는 배까지 이어지는 상체를 완성 원화로 제작한다. '
         '턱 아래 목, 양어깨, 상완, 상복부가 자연스럽게 연결되어야 한다. 얼굴 화면 점유율을 고정하지 않는다. '
         '전신 6등신 디자인을 참고하더라도 하체를 그리지는 않는다.')
BODY_FACE = ('얼굴형을 하나의 U형으로 고정하지 않는다. 둥근형·타원형·하트형·부드러운 각형 중 '
             '사용자 캐릭터에 맞는 애니풍 얼굴형을 선택한다. 양 눈은 자연스럽게 뜨고 홍채·동공·하이라이트의 '
             '시선이 같아야 한다. 단순화된 귀와 작은 코·입, 턱 뒤 목 언더페인트와 양어깨·상복부를 '
             '일관된 선화와 셀셰이딩으로 표현한다. 눈 크기 추천치는 선택적 출발점이지 필수 규격이 아니다.')
BODY_QA = ('회색 단색 BODY_flat_proxy.png, 코드 생성 사각형·다각형, 얼굴형 반복, 졸린 비대칭 눈, '
           '홍채 시선 불일치, 실사 귀·입술·긴 턱, 잘린 목·어깨 또는 쇄골 아래 몸통 절단은 최종 원화 불합격이다. '
           '배 바로 위까지 상체가 연결됐는지 원본/합성/축소 프리뷰로 실제 확인하고, 실제 PSD, RGBA, 마스크, '
           '좌표·검증 JSON·입력·시각검수 안내를 검사한다. GPU/Editor 실물 검증 없이 PASS 판정 금지.')
BODY_PROMPT = ('High-end hand-drawn Japanese anime VTuber BODY master illustration, broadcast waist-up '
               'composition from head to upper abdomen or navel, naturally connected anime neck shoulders and arms, '
               'complete shaded opaque neutral inner base, individualized rounded oval or heart-shaped face, '
               'naturally open coherent eyes with matching iris gaze pupils and highlights, stylized tiny nose and mouth, '
               'jaw-hidden neck underpaint, crisp tapered linework and refined cel shading, PSD-ready transparent layers. '
               'No flat gray polygon torso, realistic ears or chin, half-closed cross-eyed irises, detached neck, '
               'clipped torso, duplicated features, detachable hair clothing accessories in BODY-only asset.')
SCOPES = {
    'body': FRAME + ' ' + BODY_FACE + ' 신체만 제작하며 교체 헤어·의상·소품은 따로 만든다. 안전하게 가린 불투명 중립 베이스도 완성 그림 수준이어야 한다.',
    'hair': '배까지 보이는 기준 BODY 캔버스와 두상 위치를 참조하여 요청받은 헤어만 작업한다. 얼굴·눈·목·신체를 다시 그리지 않는다.',
    'outfit': '배까지 보이는 기준 BODY 캔버스와 목·어깨·상복부 위치를 참조하여 요청받은 의상 한 벌만 작업한다. 몸통·얼굴은 다시 그리지 않는다.',
    'accessory': '배까지 보이는 기준 BODY 캔버스의 위치·좌우·고정부만 참조하여 요청받은 소품 한 종류만 작업한다. 인물 원화를 다시 그리지 않는다.',
}
ASSET_QA = {
    'hair': '요청한 헤어의 모근·앞옆뒤 가닥·뒷면 숨은 픽셀과 기준 두상 정합을 검수한다. 신체 피부·눈·귀는 새로 그리지 않는다.',
    'outfit': '요청한 의상 한 벌의 옷깃·소매·상복부 옷감·안감과 기준 몸체 정합을 검수한다. 얼굴·눈·목 피부를 새로 그리지 않는다.',
    'accessory': '요청 소품 하나의 부착점·좌우/전후 의미·알파와 기준 신체 캔버스 정합을 검수한다. 피부·머리카락·의상을 새로 만들지 않는다.',
}
PROMPTS = {
    'hair': 'HAIR ONLY, align requested layered hairstyle to the unchanged waist-up reference canvas, no face or skin repaint.',
    'outfit': 'OUTFIT ONLY, align requested garment collar shoulders sleeves and upper abdomen to reference body, no skin or face.',
    'accessory': 'ACCESSORY ONLY, one requested item aligned to reference body anchors, no face body hair or outfit regeneration.',
}
REFERENCES = (
    ('Live2D 공식 파츠 분리', 'https://docs.live2d.com/en/cubism-editor-tutorials/psd/'),
    ('Live2D 공식 샘플 갤러리', 'https://www.live2d.com/en/learn/sample/'),
    ('NaNo 작가 버튜버 원화', 'https://xfolio.jp/portfolio/k_NaNo_nano/works/3633411'),
    ('SkylaVT 모델 원화', 'https://vgen.co/SkylaVT/service/fullbody-vtuber-model-art-ready-to-rig-/8b93c4ce-4b80-4a03-9f90-28420c37a948'),
    ('Rei VTuber 모델 원화', 'https://vgen.co/Reinamegumi/service/live2d-vtuber-model-art-rigging/cbe66dec-5efd-4908-8c13-8acff8a21024'),
)
BAD_LINE = re.compile(r'52~61%|52-61 percent|1\.65~1\.95H|1\.65–1\.95H|'
                      r'코드로 만든.*프록시|단색.*도형 프록시|프록시 CPU 예시|'
                      r'도형 코드를 실행|상체 윗부분만 짧게|FACE-DOMINANT CLOSE BUST-UP|'
                      r'no waist and no elbows|긴 몸통·팔꿈치·손은 그리지')
MARKER = '## [2026-10-13 방송용 상복부 완성 원화 교정 | {}]'
GUIDED = {
    '00_MASTER_FIRST.md', '00_READ_FIRST.md', '03_MODE_RULES.md',
    '07_REVIEW_BEFORE_FINAL_ZIP.md', '09_VISUAL_ART_QUALITY.md',
    '10_ANIME_STYLE.md', '11_OFFICIAL_IMAGE_EXAMPLES.md'
}


def updated_spec(spec: dict) -> dict:
    spec = json.loads(json.dumps(spec, ensure_ascii=False))
    spec['contract_id'] = 'broadcast_waist_up_body_v3'
    spec['design_basis'] = 'Complete, individual anime waist-up VTuber, not cropped close face or flat gray torso'
    spec['body_defaults']['frame_height_over_H'] = 'Character dependent: complete upper abdomen frame'
    spec['body_defaults']['head_silhouette_in_frame'] = 'No fixed head screen ratio'
    spec['body_defaults']['body_cutoff'] = 'upper abdomen or navel, as requested'
    spec['body_defaults']['look'] = 'individualized cute anime face and naturally connected shoulders torso'
    spec['body_defaults']['exclusions'] = 'flat gray polygon, realistic chin/ears, crooked half-open eyes, clipped chest'
    spec['short_scope'] = SCOPES.copy()
    spec['body_face'], spec['body_visual_qa'] = BODY_FACE, BODY_QA
    spec['image_prompt_body'], spec['image_prompt_other'] = BODY_PROMPT, PROMPTS.copy()
    return spec


def updated_geometry(spec: dict) -> dict:
    result = json.loads(json.dumps(spec, ensure_ascii=False))
    result['modes']['live2d_bust_up'] = FRAME
    result['bust_up_body_eye_start'] = BODY_FACE
    return result


def refresh_doc(value: str, *, asset: str, name: str, replacements: list[tuple[str, str]]) -> str:
    for before, after in replacements:
        if before:
            value = value.replace(before, after)
    # Remove the misleading concrete Pillow example, including its code fence.
    if asset == 'body' and name == '02_ADVANCED_PARTS.md':
        value = re.sub(r'### 중립 몸체 프록시 실행 예시.*?(?=\n(?:##|###) |\Z)', '', value, flags=re.S)
    value = '\n'.join(line for line in value.splitlines()
                      if line.startswith('## [') or not BAD_LINE.search(line))
    if name in GUIDED:
        marker = MARKER.format(asset)
        if marker in value:
            raise ValueError(f'duplicate broadcast upgrade marker: {asset}/{name}')
        links = '\n'.join(f'- [{title}]({url})' for title, url in REFERENCES)
        intro = (f'{marker}\n\n{SCOPES[asset]}\n\n'
                 '먼저 공식/작가 사례의 실제 이미지를 최소 3종 열어서 얼굴형·눈·목·어깨·구도를 비교한다. '
                 '링크만 읽었을 경우 이미지 열람 PASS로 기록하지 않는다. 타인의 캐릭터 고유 외형 복제 금지. '
                 '고품질 완성 원화 한 장을 먼저 만든 뒤 눈·목·어깨·상복부의 시각 QA에 통과하면 '
                 'RGBA 파츠 분리·가림 보완·PSD·마스크·미리보기·JSON으로 진행한다. '
                 '미완성 원화·회색 프록시는 납품하지 않으며 Cubism 네이티브 리깅 수행을 가장하지 않는다.\n'
                 f'{links}\n')
        value = intro + '\n' + value
    if name == '02_ADVANCED_PARTS.md' and asset == 'body':
        value += '\n' + BODY_FACE + '\nBODY_flat_proxy.png는 최종 불합격이다.\n'
    if name in ('07_REVIEW_BEFORE_FINAL_ZIP.md', '09_VISUAL_ART_QUALITY.md'):
        value += '\n' + (BODY_QA if asset == 'body' else ASSET_QA[asset]) + '\n'
    if name == '09_VISUAL_ART_QUALITY.md':
        value += '\nPillow 도형의 무결성은 고급 애니 원화 품질 증거가 아니다.\n'
    if name == '10_ANIME_STYLE.md':
        prompt = BODY_PROMPT if asset == 'body' else PROMPTS[asset]
        if prompt not in value:
            value += '\n' + prompt + '\n'
    if name == '04_OUTPUT_FILES.md':
        value += ('\n최종 ZIP 필수: 실제 PSD, 분리된 투명 PNG, 알파 마스크, '
                  '원본 PSD와 입력 이미지, 원본 대 결과/PRO 정합 미리보기, '
                  '레이어 좌표·검증·분할 이력 JSON, 제작·시각검수·Cubism 사용자 안내 MD.\n')
    return value.rstrip() + '\n'


def rewrite_zip(src: Path, dst: Path, *, asset: str, replacements: list[tuple[str, str]]) -> None:
    with ZipFile(src) as z:
        infos = z.infolist()
        if len(infos) != 14 or len({i.filename for i in infos}) != 14 or z.testzip():
            raise ValueError(f'Not a valid 14-MD ZIP: {src}')
        originals = {i.filename: z.read(i.filename).decode('utf-8') for i in infos}
    edited = {name: refresh_doc(text, asset=asset, name=name, replacements=replacements)
              for name, text in originals.items()}
    with ZipFile(dst, 'w') as z:
        for info in infos:
            z.writestr(info, edited[info.filename].encode('utf-8'))
    with ZipFile(dst) as z:
        if z.testzip() or set(z.namelist()) != set(originals):
            raise ValueError('Rewritten ZIP corrupt')
        if '배' not in z.read('03_MODE_RULES.md').decode('utf-8'):
            raise ValueError('Broadcast frame absent in output')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Apply migration to canonical 4 ZIPs and source')
    args = parser.parse_args()
    bs = KITS / 'source/BUST_UP_FACE_FIRST_CONTRACT.json'
    gp = KITS / 'source/FACE_NECK_GEOMETRY_GUIDANCE.json'
    original = json.loads(bs.read_text(encoding='utf-8'))
    geometry = json.loads(gp.read_text(encoding='utf-8'))
    target = updated_spec(original)
    geo = updated_geometry(geometry)
    with tempfile.TemporaryDirectory(prefix='broadcast-art-fix-') as temp:
        pending = []
        for asset in ASSETS:
            before = KITS / 'zips' / f'live2d_bust_up__{asset}.zip'
            after = Path(temp) / before.name
            replace = [(geometry['modes']['live2d_bust_up'], FRAME),
                       (original['short_scope'][asset], SCOPES[asset]),
                       (original['image_prompt_other'].get(asset, ''), PROMPTS.get(asset, ''))]
            if asset == 'body':
                replace += [(original['body_face'], BODY_FACE),
                            (original['body_visual_qa'], BODY_QA),
                            (original['image_prompt_body'], BODY_PROMPT)]
            rewrite_zip(before, after, asset=asset, replacements=replace)
            pending.append((before, after))
        print('PASS: 4 canonical ZIPs reconstructed and checked in a temporary directory')
        if args.write:
            # Perform all checks above before touching the checked-out release files.
            for before, after in pending:
                os.replace(after, before)
            bs.write_text(json.dumps(target, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            gp.write_text(json.dumps(geo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print('UPDATED: 4 ZIPs and source contracts; run relevant pytest and commit on main')
        else:
            print('DRY RUN ONLY: no repository changes (use --write after review)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())