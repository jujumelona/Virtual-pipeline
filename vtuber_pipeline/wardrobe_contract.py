"""Explicit garment-only assets, separate from permanent 2D character parts."""
from __future__ import annotations
from vtuber_pipeline.sheet_contract import Sheet,Tile, BODY, ARMS

# 2D clothing uses a distinct 4:3, 2x2 RGBA atlas. Each cell is one
# deformable garment component; a costume must never alter base anatomy.
GARMENT_SHEET=Sheet("outfit_variant.png",(4096,3072),2,2,(
    Tile("outfit_front",0,0,BODY),
    Tile("outfit_back",0,1,BODY),
    Tile("outfit_sleeve_left",1,0,ARMS),
    Tile("outfit_sleeve_right",1,1,ARMS),
))
GARMENT_PARTS=frozenset(t.name for t in GARMENT_SHEET.tiles)
assert len(GARMENT_PARTS)==4
assert all(GARMENT_SHEET.cell_size==(t.roi[2]-t.roi[0],t.roi[3]-t.roi[1])
           for t in GARMENT_SHEET.tiles)
