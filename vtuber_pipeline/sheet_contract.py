"""Fixed sheet geometry / registrations shared by README, ZIP gate and exporters.

A sprite tile is NOT independently centred: it represents a known ROI of the
2048x3072 front-master. Every pixel of that tile maps to that master ROI.
This is a deterministic coordinate transform, not invented image registration.
"""
from __future__ import annotations
from dataclasses import dataclass

MASTER = (2048, 3072)
FACE = (2048, 2048)

@dataclass(frozen=True)
class Tile:
    name: str
    row: int
    col: int
    roi: tuple[int, int, int, int]

@dataclass(frozen=True)
class Sheet:
    filename: str
    size: tuple[int, int]
    columns: int
    rows: int
    tiles: tuple[Tile, ...]

    @property
    def cell_size(self) -> tuple[int, int]:
        w, h = self.size
        assert w % self.columns == 0 and h % self.rows == 0
        return w // self.columns, h // self.rows

    def box(self, tile: Tile) -> tuple[int, int, int, int]:
        w, h = self.cell_size
        return (tile.col*w, tile.row*h, (tile.col+1)*w, (tile.row+1)*h)


def _t(name, r, c, box):
    return Tile(name, r, c, box)

# Character-left is on the image right in a frontal, non-mirrored master.
L_EYE = (1024, 650, 2048, 1674)
R_EYE = (0, 650, 1024, 1674)
CENTER_FACE = (512, 512, 1536, 1536)
CENTER_MOUTH = (512, 900, 1536, 1924)
CENTER_NECK = (512, 1420, 1536, 2444)
SHEETS_2D = (
    Sheet("sheet_face.png", (4096, 4096), 4, 4, (
        _t("ear_left",0,0,L_EYE), _t("ear_right",0,1,R_EYE),
        _t("neck",0,2,CENTER_NECK), _t("face",0,3,CENTER_FACE),
        _t("eye_left_white",1,0,L_EYE), _t("eye_left_iris",1,1,L_EYE),
        _t("eye_left_lid",1,2,L_EYE), _t("brow_left",1,3,L_EYE),
        _t("eye_right_white",2,0,R_EYE), _t("eye_right_iris",2,1,R_EYE),
        _t("eye_right_lid",2,2,R_EYE), _t("brow_right",2,3,R_EYE),
        _t("nose",3,0,CENTER_MOUTH), _t("mouth_closed",3,1,CENTER_MOUTH),
        _t("mouth_open",3,2,CENTER_MOUTH),
    )),
    Sheet("sheet_hair.png", (4096, 6144), 2, 2, (
        _t("hair_front",0,0,(0,0,2048,3072)),
        _t("hair_back",0,1,(0,0,2048,3072)),
        _t("hair_left",1,0,(0,0,2048,3072)),
        _t("hair_right",1,1,(0,0,2048,3072)),
    )),
    Sheet("sheet_body_outfit.png", (4096, 6144), 2, 4, (
        _t("body",0,0,(0,1300,2048,2836)),
        _t("outfit_front",0,1,(0,1300,2048,2836)),
        _t("outfit_back",1,0,(0,1300,2048,2836)),
        _t("arm_left",1,1,(0,1100,2048,2636)),
        _t("arm_right",2,0,(0,1100,2048,2636)),
        _t("hand_left",2,1,(0,1400,2048,2936)),
        _t("hand_right",3,0,(0,1400,2048,2936)),
    )),
)
VIEWS_3D = Sheet("sheet_body_views.png", (4096, 6144), 2, 2, (
    _t("front",0,0,(0,0,2048,3072)),
    _t("back",0,1,(0,0,2048,3072)),
    _t("left",1,0,(0,0,2048,3072)),
    _t("right",1,1,(0,0,2048,3072)),
))

def sheet_names(mode: str) -> frozenset[str]:
    if mode in ("live2d", "inochi2d", "2d"):
        return frozenset({"front_master.png"} | {s.filename for s in SHEETS_2D})
    if mode == "3d":
        return frozenset({"face.png", VIEWS_3D.filename})
    raise ValueError("Unknown image sheet mode: " + str(mode))

def assert_contract() -> None:
    from vtuber_pipeline.prompt_contract import LAYER_PARTS
    expected = {name for name, _ in LAYER_PARTS}
    found = [t.name for sheet in SHEETS_2D for t in sheet.tiles]
    assert len(found) == len(expected) == 26 and set(found) == expected
    for sheet in (*SHEETS_2D, VIEWS_3D):
        assert sheet.columns * sheet.rows >= len(sheet.tiles)
        slots = [(t.row, t.col) for t in sheet.tiles]
        assert len(set(slots)) == len(slots)
        for t in sheet.tiles:
            x0, y0, x1, y1 = t.roi
            assert 0 <= t.row < sheet.rows and 0 <= t.col < sheet.columns
            assert 0 <= x0 < x1 <= MASTER[0] and 0 <= y0 < y1 <= MASTER[1]
            assert (x1-x0, y1-y0) == sheet.cell_size

assert_contract()
