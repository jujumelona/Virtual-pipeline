import io,json,tempfile,unittest
from pathlib import Path
from zipfile import ZipFile
from PIL import Image,ImageDraw
from tools.rearchive_production_preflight import audit,load_bundle,prepare_seethrough
ROOT=Path(__file__).resolve().parents[1]
C=json.loads((ROOT/"docs/REARCHIVE_PRODUCTION_CONTRACT.json").read_text())
def png():
    im=Image.new("RGBA",(1536,2304),(0,0,0,0))
    ImageDraw.Draw(im).ellipse((400,140,1080,2160),fill=(120,215,200,255))
    f=io.BytesIO();im.save(f,"PNG");return f.getvalue()
class TestRearchiveProduction(unittest.TestCase):
    def test_92_parts_79_required(self):
        self.assertEqual(len(C["parts"]),92)
        self.assertEqual(sum(p["required"] for p in C["parts"]),79)
        self.assertEqual(len(set(p["path"] for p in C["parts"])),92)
    def test_missing_front(self):
        self.assertIn("art/S01_front_neutral.png",audit({},C)["missing"])
    def test_valid_and_pack(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"input.zip"
            with ZipFile(p,"w") as z:z.writestr("art/S01_front_neutral.png",png())
            b=load_bundle(p);r=audit(b,C)
            self.assertEqual(r["status"],"FILES_VALID_ART_REVIEW_REQUIRED")
            o=Path(d)/"output.zip";prepare_seethrough(b,r,o)
            with ZipFile(o) as z:self.assertEqual(z.read("outputs/master.png"),png())
    def test_do_not_accept_rgb(self):
        im=Image.new("RGB",(1536,2304),"white");f=io.BytesIO();im.save(f,"PNG")
        self.assertTrue(audit({"art/S01_front_neutral.png":f.getvalue()},C)["invalid"])
    def test_do_not_claim_angles(self):
        self.assertEqual(len(audit({"art/S01_front_neutral.png":png()},C,"sheets")["missing"]),2)
    def test_identical_views_rejected(self):
        b={"art/S01_front_neutral.png":png(),"references/S02_left_45.png":png(),"references/S03_right_45.png":png()}
        self.assertIn("DUPLICATE_VIEW_PIXELS",[x["error"] for x in audit(b,C,"sheets")["invalid"]])
    def test_79_parts_not_invented(self):
        self.assertGreaterEqual(len(audit({"art/S01_front_neutral.png":png()},C,"parts")["missing"]),79)
if __name__=="__main__":unittest.main()
