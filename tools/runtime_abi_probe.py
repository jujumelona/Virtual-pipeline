"""Fail before UI startup if NumPy/SciPy native extensions are inconsistent.

Executed only in a fresh Python process, never in the running Colab kernel.
"""
from __future__ import annotations

import sys


def main() -> None:
    import numpy as np
    import numpy.testing as npt
    import scipy
    from scipy.spatial import cKDTree
    from scipy.sparse import csr_matrix
    import trimesh
    import gradio
    # The production gate must be importable before Gradio starts accepting
    # images. This imports the real vendor module and its transitive modules.
    from anime_face_detector import create_detector
    import anime_face_detector.detector as detector_module
    assert callable(create_detector)
    assert callable(detector_module.get_checkpoint_path)

    # Exercise both NumPy's testing C-extension and SciPy's compiled modules.
    npt.assert_allclose(np.array([1.0, 2.0]) + 1, [2.0, 3.0])
    tree = cKDTree(np.array([[0.0, 0.0], [1.0, 1.0]]))
    distance, index = tree.query([0.0, 0.0])
    assert float(distance) == 0.0 and int(index) == 0
    assert int(csr_matrix(np.eye(2)).nnz) == 2
    assert len(trimesh.creation.box().vertices) == 8
    print(
        "[ABI PASS] "
        f"Python={sys.version.split()[0]} NumPy={np.__version__} "
        f"SciPy={scipy.__version__} trimesh={trimesh.__version__} "
        f"Gradio={gradio.__version__}",
        flush=True,
    )


if __name__ == "__main__":
    main()
