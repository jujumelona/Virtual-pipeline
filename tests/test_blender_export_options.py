from types import SimpleNamespace

import pytest

from tools.blender_jobs import avatar_rig_export


OPTION_NAMES = (
    "use_addon_preferences", "export_invisibles", "export_only_selections",
    "enable_advanced_preferences", "export_all_influences", "export_lights",
    "export_gltf_animations", "export_try_sparse_sk", "ignore_warning",
)


def operator(properties):
    return SimpleNamespace(get_rna_type=lambda: SimpleNamespace(properties=properties))


def test_compatibility_options_override_addon_preferences_and_record_rna():
    properties = {name: SimpleNamespace(type="BOOLEAN", default=True)
                  for name in OPTION_NAMES}
    properties["armature_object_name"] = SimpleNamespace(type="STRING", default="")
    options, observed = avatar_rig_export.compatibility_export_options(operator(properties), "Avatar")
    assert options == {**dict.fromkeys(OPTION_NAMES, False), "armature_object_name": "Avatar"}
    assert observed["export_all_influences"] == {"type": "BOOLEAN", "default": True}


def test_missing_compatibility_option_fails_before_export():
    properties = {name: SimpleNamespace(type="BOOLEAN", default=False)
                  for name in OPTION_NAMES if name != "export_try_sparse_sk"}
    properties["armature_object_name"] = SimpleNamespace(type="STRING", default="")
    with pytest.raises(RuntimeError, match="export_try_sparse_sk"):
        avatar_rig_export.compatibility_export_options(operator(properties), "Avatar")


def test_changed_property_type_fails_before_export():
    properties = {name: SimpleNamespace(type="BOOLEAN", default=False)
                  for name in OPTION_NAMES}
    properties["armature_object_name"] = SimpleNamespace(type="STRING", default="")
    properties["export_all_influences"].type = "STRING"
    with pytest.raises(RuntimeError, match="export_all_influences"):
        avatar_rig_export.compatibility_export_options(operator(properties), "Avatar")
