"""Semantic parts are character-left/right, not viewer-left/right."""
PART_DEPTH = {
    "hair.back": 10, "body": 20, "leg": 22, "shoe": 24, "arm": 26,
    "neck": 30, "cloth": 35, "face": 40, "eye": 50, "eyebrow": 54,
    "mouth": 55, "hair.side": 65, "hair.front": 70,
    "ornament": 80, "hat": 85,
}
SEMANTIC_PROMPTS = {
    "head": "head", "face": "face", "hair.front": "front hair",
    "hair.back": "back hair", "eye.left": "left eye", "eye.right": "right eye",
    "eyebrow": "eyebrow", "mouth": "mouth", "neck": "neck",
    "body": "torso", "arm.upper": "upper arm", "arm.forearm": "forearm",
    "hand": "hand", "cloth.skirt": "skirt", "cloth.coat": "coat",
    "leg": "leg", "shoe": "shoe", "hat": "hat", "ornament": "ornament",
}
def z_order(semantic_id: str) -> int:
    for stem in sorted(PART_DEPTH, key=len, reverse=True):
        if semantic_id == stem or semantic_id.startswith(stem + "."):
            return PART_DEPTH[stem]
    raise ValueError("Unknown semantic part: " + semantic_id)
