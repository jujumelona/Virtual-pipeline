"""Detachable hair parts, never mandatory for the neutral avatar."""
from __future__ import annotations
from vtuber_pipeline.sheet_contract import Sheet,Tile,FULL

HAIR_SHEET=Sheet("hair_variant.png",(4096,6144),2,2,(
    Tile("hair_front",0,0,FULL),
    Tile("hair_back",0,1,FULL),
    Tile("hair_left",1,0,FULL),
    Tile("hair_right",1,1,FULL),
))
HAIR_PARTS=frozenset(t.name for t in HAIR_SHEET.tiles)
assert HAIR_PARTS=={"hair_front","hair_back","hair_left","hair_right"}
