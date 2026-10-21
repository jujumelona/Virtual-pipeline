"""Deterministic failure triage for small local agent + real authoring tools.

This is routing, not a replacement for actual PSD2Live/native geometry changes.
Every action names the required evidence and executable operation; no blind
strength retry is called a repair of broken source art or keyforms.
"""
from __future__ import annotations


def quality_repair_plan(native: dict | None, *,
                        source_art: dict | None = None,
                        pixel_quality: dict | None = None) -> dict:
    source_art = source_art or {}
    native = native or {}
    pixel_quality = pixel_quality or {}
    actions = []
    seen = set()

    def add(tool, reason, evidence, prerequisites):
        if tool in seen:
            return
        seen.add(tool)
        actions.append({
            "tool": tool, "reason": reason, "evidence": evidence,
            "requires": prerequisites, "executed": False,
            "quality_fix_verified": False,
        })

    if source_art.get("master_reconstruction_difference_bounds") or \
            source_art.get("neutral_exact_same_as_master") is False:
        add("source_art_regenerate", "Original RGBA layers do not rebuild source master",
            "neutral_composite", ["original independent RGBA layers", "image generator"])

    if not native.get("native_pose_rendered"):
        add("native_runtime_debug", "Real Cubism Core MOC3 frames missing",
            "native_pose_report", ["working Cubism Core/OpenGL runner", "real MOC3"])
    else:
        if native.get("native_pose_geometry_passed") is False:
            add("vts_modern_mesh_refiner", "Native pose has disconnected/collapsed geometry",
                "native_pose_geometry_passed", [
                    "PSD2Live v3.6 editor", "inspected mesh:<id> handles",
                    "original underpaint/mask evaluation"])
        if (native.get("parameter_isolation") or {}).get("passed") is False:
            add("vts_reference_keyform_author", "Yaw/gaze/control independence failure",
                "parameter_isolation", [
                    "PSD2Live v3.6 project", "real Warp IDs",
                    "matching reference and native renders"])
        if native.get("native_mouth_interpolation_passed") is False:
            add("mouth_art_and_keyforms", "Native mouth interpolation is not continuous",
                "native_mouth_interpolation_passed", [
                    "separate painted mouth closed/open", "lip and inner mouth mesh",
                    "real mouth keyform edit"])
        if native.get("pose_activity_passed") is False and not any(
                entry["tool"] in ("vts_modern_mesh_refiner",
                                  "vts_reference_keyform_author",
                                  "mouth_art_and_keyforms") for entry in actions):
            add("native_parameter_diagnosis", "Native model has inactive poses",
                "pose_activity_passed", ["real parameter IDs", "pose-by-pose captures"])

    if pixel_quality and pixel_quality.get("pixel_improvement_verified") is False:
        add("native_visual_benchmark", "Native visual fidelity has not improved",
            "pixel_improvement_verified", [
                "registered 3/4 source drawings", "real before/after native frames"])

    if not actions:
        add("human_visual_and_vts_tracking", "Technical gates alone do not certify art",
            "unverified_artistic_and_application_quality", [
                "expression and physics visual review", "VTube Studio tracking capture"])
    return {
        "schema": "vtuber/native-repair-action-plan-v1",
        "actions": actions,
        "agent_role": "choose diagnosed tool; never hallucinate source pixels or mesh IDs",
        "all_actions_executed": False,
        "artistic_quality_verified": False,
        "actual_vtube_studio_tracking_verified": False,
    }
