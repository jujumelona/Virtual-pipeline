"""Image-space coordinate transforms; source origin is top left."""
from dataclasses import dataclass
from PIL import Image

@dataclass(frozen=True)
class CropTransform:
    x0: int
    y0: int
    crop_width: int
    crop_height: int
    infer_width: int
    infer_height: int

    def box_to_original(self, box):
        x0, y0, x1, y1 = box
        sx = self.crop_width / self.infer_width
        sy = self.crop_height / self.infer_height
        return [round(self.x0 + x0*sx), round(self.y0 + y0*sy),
                round(self.x0 + x1*sx), round(self.y0 + y1*sy)]

    def point_to_original(self, x, y):
        return [self.x0 + x*self.crop_width/self.infer_width,
                self.y0 + y*self.crop_height/self.infer_height]

def restore_mask(mask: Image.Image, transform: CropTransform, source_size: tuple[int, int]):
    if min(transform.crop_width, transform.crop_height) <= 0:
        raise ValueError("empty crop")
    result = Image.new("L", source_size, 0)
    region = mask.convert("L").resize((transform.crop_width, transform.crop_height), Image.Resampling.NEAREST)
    result.paste(region, (transform.x0, transform.y0))
    return result
