from ._worker import invoke
def segment_parts(image_path: str, boxes_json: str, person_alpha_png: str, output_dir: str) -> dict:
    return invoke("sam", {"image_path": image_path, "boxes_json": boxes_json,
                          "person_alpha_png": person_alpha_png, "output_dir": output_dir}, output_dir)
