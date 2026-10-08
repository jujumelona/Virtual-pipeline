from ._worker import invoke
def create_person_alpha(image_path: str, output_dir: str) -> dict:
    return invoke("anime_alpha", {"image_path": image_path, "output_dir": output_dir}, output_dir)
