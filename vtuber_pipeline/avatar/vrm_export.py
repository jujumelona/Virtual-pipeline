"""VRM export module for VTuber Pipeline."""


def export_vrm(rigged_mesh_path: str, output_path: str) -> str:
    """
    리깅된 메시를 VRM 형식으로 내보냅니다.

    VRM 사양:
        - 휴머노이드 골격: Hips, Spine, Chest, Neck, Head,
          Shoulder(L/R), UpperArm(L/R), LowerArm(L/R), Hand(L/R),
          UpperLeg(L/R), LowerLeg(L/R), Foot(L/R)
        - 블렌드셰이프 프리셋: Blink, BlinkLeft, BlinkRight,
          A(aa), I(ih), U(ou), E(ee), O(oh),
          Happy, Sad, Angry, Surprised, Relaxed
        - SpringBone: 머리카락, 귀, 가슴, 꼬리 등의 물리 설정

    TODO: pygltflib + VRM 확장을 사용한 구현
    """
    raise NotImplementedError(
        "VRM 내보내기는 아직 구현되지 않았습니다. "
        "pygltflib 및 VRM 1.0 사양을 참조하세요: https://github.com/vrm-c/vrm-specification"
    )
