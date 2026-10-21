"""Closed-loop local VLM → PSD2Live MCP → native MOC3 → visual re-observation.

This is deliberately fail-closed: a native pose must pass all real geometry
gates AND the reference landmark residual must converge before acceptance.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from tools.vts_ai_landmark_pairs import create_vision_reference_manifest
from tools.vts_reference_keyform_author import apply_reference_keyforms


def _residual(plan: dict) -> float:
    """Root-mean-square reference pixel discrepancy, normalized by canvas."""
    manifest = plan.get("poses")
    canvas = plan.get("canvas")
    if not isinstance(canvas, list) or not isinstance(manifest, list):
        raise ValueError("Invalid feedback observation")
    error = []
    for pose in manifest:
        observed, desired = pose["observed"], pose["desired"]
        if set(observed) != set(desired):
            raise ValueError("Feedback landmarks are not paired")
        for key in observed:
            x, y = observed[key]
            tx, ty = desired[key]
            error.append(((x - tx) / canvas[0]) ** 2 +
                         ((y - ty) / canvas[1]) ** 2)
    if not error:
        raise ValueError("Missing landmark errors")
    return math.sqrt(sum(error) / len(error))


def run_ai_native_feedback_loop(*, reference_dir: Path, initial_native_dir: Path,
                                bindings: dict, model: str, endpoint: str,
                                psd2live_source: Path, output: Path,
                                max_rounds: int = 3,
                                target_residual: float = 0.018,
                                require_pixel_improvement: bool = False,
                                source_project: Path | None = None,
                                observer=None, author=None) -> dict:
    """Build and test real native keyforms, stopping on lack of convergence.

    observer/author injections are only for offline contract tests. Production
    defaults are the local image VLM and native PSD2Live MCP/Cubism renderer.
    """
    if not 1 <= max_rounds <= 4:
        raise ValueError("Feedback budget must be 1..4")
    if not 0.001 <= target_residual <= 0.08:
        raise ValueError("Invalid target landmark error")
    if author is None and source_project is None:
        raise ValueError("REAL_NATIVE_FEEDBACK_REQUIRES_EXPLICIT_EDITABLE_PROJECT")
    current_project = (Path(source_project).resolve(strict=True)
                       if source_project is not None else None)
    if current_project is not None and current_project.suffix != ".psd2live":
        raise ValueError("Expected actual generated .psd2live project")
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Feedback output must be a fresh directory")
    output.mkdir(parents=True)
    observe = observer or create_vision_reference_manifest
    apply = author or apply_reference_keyforms
    current_native = Path(initial_native_dir).resolve(strict=True)
    history = []
    accepted = None
    previous = None
    for iteration in range(max_rounds):
        round_dir = output / f"round_{iteration:02d}"
        plan, _ = observe(reference_dir, current_native, round_dir / "ai",
                          bindings=bindings, model=model, endpoint=endpoint)
        # A running PSD2Live project must have real, distinct warped objects.
        current_error = _residual(json.loads(
            (round_dir / "ai" / "vision_reference_manifest.json")
            .read_text(encoding="utf-8")))
        attempt = {"round": iteration, "before_error": current_error,
                   "accepted": False, "native_export_verified": False}
        history.append(attempt)
        if previous is not None and current_error >= previous - 0.001:
            attempt["reason"] = "NO_MEASURABLE_VISUAL_IMPROVEMENT"
            break
        if current_error <= target_residual:
            if accepted is None:
                attempt["reason"] = "BASELINE_WITHIN_THRESHOLD_NOT_REAUTHORED"
                # Native model may be acceptable, but this routine did not edit.
                break
            attempt["accepted"] = True
            accepted["accepted"] = True
            accepted["after_error"] = current_error
            break
        previous = current_error
        export_to = round_dir / "native_export"
        try:
            # Apply and export actual native keyforms, then render native QA.
            arguments = {"proxy_root": psd2live_source,
                         "work": round_dir / "mcp", "export_to": export_to}
            if current_project is not None:
                arguments["source_project"] = current_project
            result = apply(plan, **arguments)
            if not result.get("native_pose_qa", {}).get("pose_activity_passed"):
                raise RuntimeError("Native pose failed after authoring")
            if require_pixel_improvement:
                # Numeric facial landmarks alone can improve while the
                # silhouette/paint tears. Compare real native frames before
                # and after, with no resize or fabricated background masks.
                from tools.vts_native_visual_benchmark import evaluate_native_visual_change
                pixel = evaluate_native_visual_change(
                    reference_dir, round_dir / "mcp" / "native_validation",
                    round_dir / "pixel_quality",
                    previous_native_dir=current_native)
                if not pixel["pixel_improvement_verified"]:
                    raise RuntimeError("Native pixel correspondence did not improve")
                attempt["pixel_quality"] = {
                    "status": pixel["status"],
                    "relative_comparison": pixel["relative_comparison"],
                }
            attempt["native_export_verified"] = True
            attempt["exported_model3"] = result["exported_model3"]
            accepted = attempt
            if result.get("editable_project_copy"):
                current_project = Path(result["editable_project_copy"])
                if not current_project.is_file():
                    raise RuntimeError("Edited project was not actually saved")
            current_native = round_dir / "mcp" / "native_validation"
        except Exception as exc:
            attempt["reason"] = f"{type(exc).__name__}: {exc}"
            break
    else:
        # Re-observe the final pass; one successful pose-render is not enough.
        final_dir = output / "final_observation"
        plan, _ = observe(reference_dir, current_native, final_dir,
                          bindings=bindings, model=model, endpoint=endpoint)
        final_data = json.loads((final_dir / "vision_reference_manifest.json")
                                .read_text(encoding="utf-8"))
        error = _residual(final_data)
        if accepted and error <= target_residual and error < previous - 0.001:
            accepted["accepted"] = True
            accepted["after_error"] = error
        elif accepted:
            accepted["reason"] = "REMAINING_LANDMARK_ERROR_ABOVE_TARGET"
            accepted = None
    passed = bool(accepted and accepted.get("accepted"))
    verdict = {"schema": "vtuber/local-vlm-native-feedback-v1",
               "accepted": passed, "native_reference_keyforms_verified": passed,
               "actual_vtube_studio_tracking_verified": False,
               "full_90_degree_profile_verified": False,
               "native_pixel_comparison_required": require_pixel_improvement,
               "native_pixel_comparison_verified": bool(
                   passed and require_pixel_improvement and
                   accepted.get("pixel_quality")) if accepted else False,
               "target_error": target_residual,
               "rounds": history,
               "winning_export": accepted["exported_model3"] if passed else None}
    report = output / "feedback_verdict.json"
    report.write_text(json.dumps(verdict, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    if not passed:
        raise RuntimeError("NATIVE_AI_FEEDBACK_NOT_CONVERGED: " + str(report))
    return verdict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--native-dir", type=Path, required=True)
    parser.add_argument("--warp-bindings", type=Path, required=True)
    parser.add_argument("--psd2live-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000/v1/chat/completions")
    parser.add_argument("--source-project", type=Path, required=True,
                        help="Explicit generated .psd2live project; round N edits round N-1 saved copy")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--require-pixel-improvement", action="store_true",
                        help="Reject edits that fail genuine transparent native pose comparison")
    args = parser.parse_args()
    result = run_ai_native_feedback_loop(
        reference_dir=args.reference_dir, initial_native_dir=args.native_dir,
        bindings=json.loads(args.warp_bindings.read_text(encoding="utf-8")),
        model=args.model, endpoint=args.endpoint,
        psd2live_source=args.psd2live_source, output=args.output,
        max_rounds=args.rounds,
        require_pixel_improvement=args.require_pixel_improvement,
        source_project=args.source_project)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
