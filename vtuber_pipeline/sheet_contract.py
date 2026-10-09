"""Deterministic high-resolution sprite atlas geometry shared by all boundaries.

Small facial parts are rendered at 2x spatial sampling: 2048px cells
represent 1024px-wide ROIs of the master. Do not recenter parts within a cell.
3D views each retain a full 2048x3072 orthographic tile. All ROI transforms
are uniform; cropped artwork never changes aspect ratio.
"""
from __future__ import annotations
from dataclasses import dataclass

MASTER = (2048,3072)
FACE = (2048,2048)

@dataclass(frozen=True)
class Tile:
    name: str
    row: int
    col: int
    roi: tuple[int,int,int,int]

@dataclass(frozen=True)
class Sheet:
    filename: str
    size: tuple[int,int]
    columns: int
    rows: int
    tiles: tuple[Tile,...]

    @property
    def cell_size(self) -> tuple[int,int]:
        w,h=self.size
        assert w%self.columns==0 and h%self.rows==0
        return w//self.columns,h//self.rows

    def box(self,tile:Tile)->tuple[int,int,int,int]:
        w,h=self.cell_size
        return tile.col*w,tile.row*h,(tile.col+1)*w,(tile.row+1)*h


def _t(name,r,c,roi):
    return Tile(name,r,c,roi)

# LEFT/RIGHT refer to CHARACTER sides (left appears on viewer-right).
L_EYE=(1024,650,2048,1674)
R_EYE=(0,650,1024,1674)
CENTER_FACE=(512,512,1536,1536)
CENTER_MOUTH=(512,900,1536,1924)
CENTER_NECK=(512,1420,1536,2444)
BODY=(0,1300,2048,2836)
ARMS=(0,1100,2048,2636)
HANDS=(0,1400,2048,2936)
FULL=(0,0,2048,3072)

# A full sheet is never crowded with tiny eyes and unrelated torso layers.
# Facial 2x atlas pixels are retained without destructive x0.5 reduction.
SHEETS_2D=(
    Sheet("sheet_face_base.png",(4096,4096),2,2,(
        _t("ear_left",0,0,L_EYE),
        _t("ear_right",0,1,R_EYE),
        _t("neck",1,0,CENTER_NECK),
        _t("face",1,1,CENTER_FACE),
    )),
    Sheet("sheet_eye_left.png",(4096,4096),2,2,(
        _t("eye_left_white",0,0,L_EYE),
        _t("eye_left_iris",0,1,L_EYE),
        _t("eye_left_lid",1,0,L_EYE),
        _t("brow_left",1,1,L_EYE),
    )),
    Sheet("sheet_eye_right.png",(4096,4096),2,2,(
        _t("eye_right_white",0,0,R_EYE),
        _t("eye_right_iris",0,1,R_EYE),
        _t("eye_right_lid",1,0,R_EYE),
        _t("brow_right",1,1,R_EYE),
    )),
    Sheet("sheet_mouth.png",(4096,4096),2,2,(
        _t("nose",0,0,CENTER_MOUTH),
        _t("mouth_closed",0,1,CENTER_MOUTH),
        _t("mouth_open",1,0,CENTER_MOUTH),
    )),
    Sheet("sheet_hair.png",(4096,6144),2,2,(
        _t("hair_front",0,0,FULL),
        _t("hair_back",0,1,FULL),
        _t("hair_left",1,0,FULL),
        _t("hair_right",1,1,FULL),
    )),
    Sheet("sheet_body_outfit.png",(4096,3072),2,2,(
        _t("body",0,0,BODY),
        _t("outfit_front",0,1,BODY),
        _t("outfit_back",1,0,BODY),
    )),
    Sheet("sheet_arms_hands.png",(4096,3072),2,2,(
        _t("arm_left",0,0,ARMS),
        _t("arm_right",0,1,ARMS),
        _t("hand_left",1,0,HANDS),
        _t("hand_right",1,1,HANDS),
    )),
)

VIEWS_3D=(
    Sheet("sheet_front_back.png",(4096,3072),2,1,(
        _t("front",0,0,FULL), _t("back",0,1,FULL),
    )),
    Sheet("sheet_side_views.png",(4096,3072),2,1,(
        _t("left",0,0,FULL), _t("right",0,1,FULL),
    )),
)

def sheet_names(mode:str)->frozenset[str]:
    if mode in ("live2d","inochi2d","2d"):
        return frozenset({"front_master.png"}|{s.filename for s in SHEETS_2D})
    if mode=="3d":
        return frozenset({"face.png"}|{s.filename for s in VIEWS_3D})
    raise ValueError("Unknown image sheet mode: "+str(mode))

def assert_contract()->None:
    from vtuber_pipeline.prompt_contract import LAYER_PARTS
    expected={name for name,_ in LAYER_PARTS}
    found=[t.name for s in SHEETS_2D for t in s.tiles]
    assert len(found)==len(expected)==26 and set(found)==expected
    found_views=[t.name for s in VIEWS_3D for t in s.tiles]
    assert len(found_views)==4 and set(found_views)=={"front","back","left","right"}
    for sheet in (*SHEETS_2D,*VIEWS_3D):
        assert sheet.columns*sheet.rows>=len(sheet.tiles)
        slots=[(t.row,t.col) for t in sheet.tiles]
        assert len(set(slots))==len(slots)
        cw,ch=sheet.cell_size
        for t in sheet.tiles:
            x0,y0,x1,y1=t.roi
            assert 0<=t.row<sheet.rows and 0<=t.col<sheet.columns
            assert 0<=x0<x1<=MASTER[0] and 0<=y0<y1<=MASTER[1]
            assert cw*(y1-y0)==ch*(x1-x0), "nonuniform aspect ratio in "+t.name
            assert cw%(x1-x0)==0, "nonintegral scale for "+t.name
            assert (cw//(x1-x0)) in (1,2)
assert_contract()
