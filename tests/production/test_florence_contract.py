import importlib.util
from pathlib import Path
import sys
import pytest


def worker():
    root=Path(__file__).resolve().parents[2]/'tools/model_workers'
    sys.path.insert(0,str(root))
    spec=importlib.util.spec_from_file_location('florence_worker',root/'florence_worker.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_open_vocabulary_uses_official_bbox_label_key():
    result=worker().parse_boxes({'bboxes':[[1,2,8,9]],'bboxes_labels':['head'],'polygons':[]},'head',(20,20))
    assert result==[{'semantic_id':'head','bbox_xyxy':[1,2,8,9], 'source':'Florence-2-base','score':None,'detected_label':'head'}]


def test_every_detection_can_be_sorted_for_layering():
    from vtuber_pipeline.common.part_taxonomy import SEMANTIC_PROMPTS,z_order
    for part in SEMANTIC_PROMPTS:
        assert isinstance(z_order(part),int)
