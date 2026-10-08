import json
from pathlib import Path
import numpy as np
from PIL import Image


def test_eye_open_min_closes_eye_and_default_remains_open(tmp_path):
    from vtuber_pipeline.two_d.keyforms import build_keyforms
    mesh=tmp_path/'mesh.json'
    v=[[10,10],[20,10],[20,20],[10,20]]
    mesh.write_text(json.dumps({'width':32,'height':32,'meshes':[{'semantic_id':'eye.left.iris','vertices_xy':v}]}))
    p=build_keyforms(str(mesh),'unused','unused',str(tmp_path))
    result=json.loads(Path(p['keyforms_json']).read_text())['keyforms'][0]['deltas']['eye.left.open']
    minimum=np.asarray(v)+np.asarray(result['min'])
    assert np.ptp(minimum[:,1])<1, 'closed-eye keyform must collapse visible iris height'
    assert np.allclose(result['default'],0)
    assert np.allclose(result['max'],0)


def test_psd_composite_has_same_top_layer_as_ora(tmp_path):
    from vtuber_pipeline.common.schemas import Part,PartsDocument
    from vtuber_pipeline.two_d.layer_export import write_psd_and_ora
    from psd_tools import PSDImage
    parts=[]
    for name,z,color in [('back',0,(255,0,0,255)),('front',50,(0,255,0,255))]:
        p=tmp_path/(name+'.png');Image.new('RGBA',(32,32),color).save(p)
        parts.append(Part(name,str(p),str(p),None,[0,0,32,32],z,[],'user'))
    doc=PartsDocument(32,32,parts,None,'')
    result=write_psd_and_ora(doc,str(tmp_path))
    pixel=PSDImage.open(result['psd']).composite().convert('RGB').getpixel((16,16))
    assert pixel==(0,255,0), pixel
