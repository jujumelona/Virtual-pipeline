"""Template fitting module for VTuber Pipeline."""


def fit_template(mesh_path: str, landmarks: dict, output_path: str) -> str:
    """
    미리 정의된 VTuber 템플릿 메시를 입력 메시에 피팅합니다.

    입력:
        mesh_path: TripoSR로 생성된 .obj/.glb 메시 경로
        landmarks: AnimeFaceDetector.detect()의 출력 {"bbox": ..., "landmarks": [[x,y]*28]}
        output_path: 피팅된 메시를 저장할 .glb 경로

    출력:
        피팅된 메시 파일 경로 (output_path)

    TODO: 구현 예정
        - 랜드마크를 3D 메시 공간으로 투영
        - 비선형 변형(NICP 또는 유사 알고리즘) 적용
        - 표정 블렌드셰이프 바인딩
    """
    raise NotImplementedError(
        "template_fitting은 아직 구현되지 않았습니다. "
        "Colab 노트북의 scaffold 섹션을 참조하세요."
    )
