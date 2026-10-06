# Implementation Plan: Fix Critical VTuber Pipeline Issues

**Goal**: Connect end-to-end pipeline from input image to valid VRM 1.0 file that works in VTuber software with blink/lip-sync/look-at.

**Current State Analysis** (after codebase exploration):
- Pipeline structure exists but stages are stubbed or disconnected
- `build.py` Stage 2 uses stub landmarks `[]`, Stage 3 uses canonical template instead of TripoSR
- `reconstruction.py` incorrectly checks `nvdiffrast` (blocked) when TripoSR is MIT-licensed
- `vrm_builder.py` uses `humanoidBones` (list) instead of `humanBones` (object) and `presets` instead of `preset`
- `template_fitting.py` returns hardcoded `objective_value=0.001`, no actual fitting
- `texture_transfer.py` generates 1x1 placeholder images
- `expressions.py` uses bounding-box heuristics, not actual eyelid/lip topology
- Commercial metadata hardcoded to `personalNonProfit` (opposite of goal)
- `template.glb` exists but is just sphere+cylinder+box (not VTuber-ready topology)
- `landmarks.json` has empty `landmark_to_vertex` mapping

---

## Phase 1: Critical Blockers (Must Fix First)

### 1. Fix Pipeline to Use Real TripoSR Reconstruction

**What**: Connect actual image-to-3D reconstruction instead of using canonical template directly.

**Files**:
- `vtuber_pipeline/avatar/build.py` - Stage 2 and Stage 3
- `vtuber_pipeline/avatar/reconstruction.py` - Remove incorrect nvdiffrast check
- `vtuber_pipeline/core/config.py` - Update blocked packages logic

**Changes**:
1. In `build.py` Stage 2: Replace stub `{"status": "stub", "landmarks": []}` with actual call:
   ```python
   from vtuber_pipeline.avatar.face_detector import AnimeFaceDetector
   detector = AnimeFaceDetector()
   landmarks_result = detector.detect(image_path)
   results["stages"]["face_landmarks"] = landmarks_result
   ```

2. In `build.py` Stage 3: Replace canonical template usage with TripoSR:
   ```python
   from vtuber_pipeline.avatar.reconstruction import reconstruct_avatar
   mesh_path = reconstruct_avatar(image_path, output_dir, profile='commercial')
   results["stages"]["reference_reconstruction"] = {
       "status": "complete",
       "mesh_path": mesh_path,
       "source": "triposr"
   }
   ```

3. In `reconstruction.py`: Remove `check_commercial_profile('nvdiffrast')` - TripoSR doesn't use nvdiffrast. TripoSR is MIT licensed.

**Dependencies**: TripoSR installed (git clone + pip install -e TripoSR)

**Verification**:
```bash
python -c "from vtuber_pipeline.avatar.build import build_avatar; r = build_avatar('tests/fixtures/test_char.png', 'test_out/'); print(r['stages']['face_landmarks'].get('landmarks', []))"
```

---

### 2. Fix VRM 1.0 Schema Compliance

**What**: Fix VRM extension JSON structure to match VRM 1.0 specification.

**Files**:
- `vtuber_pipeline/avatar/vrm_builder.py` - `create_vrm_extension()`
- `vtuber_pipeline/avatar/validator.py` - `validate_humanoid_bones()`, `validate_expressions()`

**Changes**:
1. In `vrm_builder.py` `create_vrm_extension()`:
   - Change `humanoidBones` from list to object:
     ```python
     # BEFORE (incorrect):
     "humanoid": {
         "humanoidBones": [{"node": 0, "name": "hips"}, ...]
     }
     
     # AFTER (correct VRM 1.0):
     "humanoid": {
         "humanBones": {
             "hips": {"node": 0},
             "spine": {"node": 1},
             "chest": {"node": 2},
             ...
         }
     }
     ```
   
   - Change `presets` to `preset`:
     ```python
     # BEFORE (incorrect):
     "expressions": {
         "presets": {"blink": {...}, "aa": {...}}
     }
     
     # AFTER (correct VRM 1.0):
     "expressions": {
         "preset": {
             "blink": {"morphTargetBinds": [...]},
             "aa": {"morphTargetBinds": [...]},
             ...
         }
     }
     ```

   - Fix `licenseUrl` to use VRM license document URL:
     ```python
     "licenseUrl": "https://vrm.dev/licenses/1.0/"
     ```

   - Fix save method to use explicit binary:
     ```python
     # Save as GLB first, then rename to .vrm
     temp_glb = output_path.with_suffix('.glb')
     gltf.save_binary(str(temp_glb))
     temp_glb.rename(output_path)
     ```

2. In `validator.py`:
   - Update `validate_humanoid_bones()` to check `humanBones` (object) not `humanoidBones` (list)
   - Update `validate_expressions()` to check `preset` not `presets`

**Verification**:
```bash
python -c "
from vtuber_pipeline.avatar.vrm_builder import export_vrm
from vtuber_pipeline.avatar.validator import validate_vrm
result = export_vrm('test.glb', 'test_out/')
v = validate_vrm(result['vrm_path'], 'test_out/')
print(f'Bones valid: {v[\"checks\"][\"humanoid_bones\"][\"valid\"]}')
"
```

---

### 3. Fix Commercial Metadata

**What**: Change VRM metadata to allow commercial use.

**Files**:
- `vtuber_pipeline/avatar/vrm_builder.py` - `create_vrm_extension()` meta section
- `vtuber_pipeline/cli.py` - Add `--commercial-usage` option

**Changes**:
1. In `vrm_builder.py`:
   ```python
   # Change from:
   "commercialUsage": "personalNonProfit"
   
   # To:
   "commercialUsage": "corporation"  # or "personalProfit"
   ```

2. Add CLI option for flexibility:
   ```python
   @click.option('--commercial-usage', type=click.Choice(['personalNonProfit', 'personalProfit', 'corporation']), default='corporation')
   ```

**Verification**:
```bash
python -c "
from pygltflib import GLTF2
gltf = GLTF2().load('test_out/avatar.vrm')
print(f'Commercial: {gltf.extensions[\"VRMC_vrm\"][\"meta\"][\"commercialUsage\"]}')
"
```

---

### 4. Generate Proper Canonical VTuber Template

**What**: Create a real anime head template with proper topology for VTuber expressions.

**Files**:
- `vtuber_pipeline/avatar/template_mesh.py` - Complete rewrite
- `assets/canonical_vtuber/template.glb` - Regenerate
- `assets/canonical_vtuber/landmarks.json` - Add vertex mappings
- `assets/canonical_vtuber/topology.json` - Update with new structure

**Changes**:
1. In `template_mesh.py`, create proper VTuber topology:
   - **Head**: Subdivided box with edge loops for eyes and mouth (not UV sphere)
   - **Eyes**: Two separate spheres with proper UV mapping
   - **Eyelids**: Define vertex groups (`upper_eyelid_L`, `upper_eyelid_R`, `lower_eyelid_L`, `lower_eyelid_R`)
   - **Mouth**: Edge loop around lips with cavity inside
   - **Nose**: Subtle protrusion
   - **Neck**: Cylinder connecting to body
   - **Shoulders**: Simple box extensions
   - **Arms**: Basic cylinders

2. Run `template_mesh.py` to regenerate `template.glb`.

3. Update `landmarks.json` with actual vertex index mappings for 28 anime-face-detector landmarks.

**Verification**:
```bash
python vtuber_pipeline/avatar/template_mesh.py
python -c "import trimesh; m = trimesh.load('assets/canonical_vtuber/template.glb'); print(f'Vertices: {len(m.vertices)}')"
```

---

## Phase 2: Quality Blockers

### 5. Implement Real Template Fitting

**What**: Replace stub fitting with actual non-rigid registration.

**Files**:
- `vtuber_pipeline/avatar/template_fitting.py`

**Changes**:
1. Implement actual fitting algorithm:
   ```python
   def fit_template(template_path, landmarks_2d, output_dir, config):
       # 1. Load template and reference meshes
       template = trimesh.load(template_path)
       reference = trimesh.load(reference_path)  # From TripoSR
       
       # 2. Coarse alignment - scale/translate to match bounding boxes
       scale, translation = compute_similarity_transform(template, reference)
       template.apply_scale(scale)
       template.apply_translation(translation)
       
       # 3. Landmark matching - 2D landmarks to 3D template vertices
       # Use scipy.optimize.minimize to solve for rotation + translation
       landmark_error = compute_landmark_error(landmarks_2d, template_vertices)
       
       # 4. Surface fitting - closest point ICP
       for iteration in range(max_iterations):
           correspondences = find_closest_points(template, reference)
           deformation = solve_for_deformation(correspondences)
           apply_deformation(template, deformation)
       
       # 5. Laplacian regularization - preserve smoothness
       laplacian_energy = compute_laplacian_energy(template)
       
       # 6. Save fit.npz with deformation field
       np.savez(output_dir / 'fit.npz', 
                vertices=template.vertices,
                deltas=deltas,
                weights=weights)
       
       return {"status": "complete", "metrics": actual_metrics}
   ```

2. Remove hardcoded `objective_value=0.001`, `iterations=100`, `converged=True`.

**Verification**:
```bash
python -c "
from vtuber_pipeline.avatar.template_fitting import fit_template
result = fit_template('assets/canonical_vtuber/template.glb', [[100, 200], ...], 'test_out/')
print(f'Converged: {result.get(\"converged\")}, Objective: {result.get(\"objective_value\")}')
"
```

---

### 6. Implement Real Texture Transfer

**What**: Project input image onto template UV and generate proper textures.

**Files**:
- `vtuber_pipeline/avatar/texture_transfer.py`

**Changes**:
1. Implement actual UV projection:
   ```python
   def transfer_texture(image_path, mesh_path, output_dir):
       # 1. Load input image
       source_img = Image.open(image_path)
       
       # 2. Load mesh with UV coordinates
       mesh = trimesh.load(mesh_path)
       
       # 3. Project face region onto template UV
       # Use landmarks to define face region
       face_texture = project_face_to_uv(source_img, landmarks, mesh)
       
       # 4. Use TripoSR texture for sides/back (fallback)
       body_texture = extract_body_texture(tripsr_texture_path)
       
       # 5. Generate 1024x1024 texture atlas
       texture_atlas = combine_textures(face_texture, body_texture)
       
       # 6. Save as face.png, body.png
       texture_atlas.save(output_dir / 'texture.png')
       
       return {"status": "complete", "face_png": ..., "body_png": ...}
   ```

2. Remove 1x1 placeholder image generation.

**Verification**:
```bash
python -c "
from vtuber_pipeline.avatar.texture_transfer import transfer_texture
result = transfer_texture('tests/fixtures/test_char.png', 'test.glb', 'test_out/')
print(f'Face texture: {result.get(\"face_png\")}')
"
```

---

### 7. Fix Expressions to Use Real Vertex Groups

**What**: Define expressions based on actual eyelid/lip topology, not bounding-box heuristics.

**Files**:
- `vtuber_pipeline/avatar/expressions.py`

**Changes**:
1. Load vertex groups from template metadata:
   ```python
   VERTEX_GROUPS = {
       "upper_eyelid_L": [...],  # Vertex indices from template
       "upper_eyelid_R": [...],
       "lower_eyelid_L": [...],
       "lower_eyelid_R": [...],
       "upper_lip": [...],
       "lower_lip": [...],
       "mouth_corners": [...],
   }
   ```

2. Update morph generation to use actual vertices:
   ```python
   def generate_blink_morph(vertices, bounds, side):
       # Get actual eyelid vertices from template
       eyelid_indices = VERTEX_GROUPS[f"upper_eyelid_{side}"]
       # Rotate these specific vertices down 45 degrees
       for idx in eyelid_indices:
           # Apply rotation around eye center
           morph_data.append((idx, [dx, dy, dz]))
       return morph_data
   ```

3. Update visemes to move actual lip vertices.

**Verification**:
```bash
python -c "
from vtuber_pipeline.avatar.expressions import generate_expressions
result = generate_expressions('assets/canonical_vtuber/template.glb')
blink = result['expressions']['blink']
print(f'Blink affects {blink[\"vertex_count\"]} vertices')
"
```

---

## Phase 3: Full Pipeline Integration

### 8. Fix Hair/Clothing Extraction

**What**: Extract hair and clothing from TripoSR reference mesh (not template).

**Files**:
- `vtuber_pipeline/avatar/hair.py`
- `vtuber_pipeline/avatar/clothing.py`
- `vtuber_pipeline/avatar/build.py` - Pass TripoSR mesh to extraction

**Changes**:
1. In `build.py`, pass TripoSR reference mesh:
   ```python
   ref_mesh = results["stages"]["reference_reconstruction"]["mesh_path"]
   results["stages"]["hair"] = hair.extract_hair(ref_mesh, output_dir)
   results["stages"]["clothing"] = clothing.extract_clothing(ref_mesh, ref_mesh, output_dir)
   ```

2. In `hair.py`, implement actual extraction:
   - Identify hair via surface normal + distance from head
   - Find connected components
   - Transfer to fitted template

3. In `clothing.py`, implement shell extraction:
   - Identify clothing vertices (non-skin areas)
   - Transfer skin weights from body

**Verification**:
```bash
python -c "
from vtuber_pipeline.avatar.hair import extract_hair
result = extract_hair('test_tripsr.glb', 'test_out/')
print(f'Hair ratio: {result.get(\"hair_ratio\")}')
"
```

---

### 9. Fix Accessory Bake

**What**: Implement actual VRM combination with accessories.

**Files**:
- `vtuber_pipeline/accessory/bake.py`

**Changes**:
1. Implement actual bake process:
   ```python
   def bake_accessories(base_vrm, accessory_paths, output_path):
       # 1. Load base VRM with pygltflib
       gltf = GLTF2().load(base_vrm)
       
       # 2. For each accessory:
       for acc_path in accessory_paths:
           # Load GLB
           acc_gltf = GLTF2().load(acc_path)
           # Apply transform from attachment.json
           # Add to scene, set parent bone
           merge_into_gltf(gltf, acc_gltf, attachment_config)
       
       # 3. Export combined VRM
       gltf.save_binary(output_path)
       
       # 4. Validate
       validate_vrm(output_path)
       
       return {"status": "complete", "output_path": output_path}
   ```

**Verification**:
```bash
python -c "
from vtuber_pipeline.accessory.bake import bake_accessories
result = bake_accessories('base.vrm', ['hat.glb'], 'combined.vrm')
print(f'Status: {result[\"status\"]}')
"
```

---

### 10. Add Real End-to-End Test

**What**: Create integration test that runs actual pipeline.

**Files**:
- `tests/integration/test_e2e_pipeline.py`
- `tests/fixtures/anime_face.png` - Create simple anime face image

**Changes**:
1. Create test that doesn't skip:
   ```python
   def test_e2e_pipeline():
       # Use actual anime face image fixture
       result = build_avatar('tests/fixtures/anime_face.png', 'test_output/')
       
       assert result['status'] == 'complete'
       assert Path(result['stages']['vrm_export']['vrm_path']).exists()
       
       # Verify VRM loads
       gltf = GLTF2().load(result['stages']['vrm_export']['vrm_path'])
       assert 'VRMC_vrm' in gltf.extensions
   ```

2. Create simple anime face test image (can be procedurally generated).

**Verification**:
```bash
pytest tests/integration/test_e2e_pipeline.py -v
```

---

### 11. Fix Third-Party Lock

**What**: Record actual commit SHAs and model hashes.

**Files**:
- `third_party.lock.json`

**Changes**:
```json
{
  "triposr": {
    "commit": "abc123def456...",  // Actual commit SHA
    "model_revision": "model.ckpt",
    "license": "MIT",
    "hash": "sha256:..."  // Hash of model weights
  },
  "anime_face_detector": {
    "commit": "def456...",  // Actual commit SHA
    "license": "MIT"
  }
}
```

**Verification**:
```bash
python -c "import json; d = json.load(open('third_party.lock.json')); print(d['tools']['triposr']['commit'])"
```

---

## Verification Commands Summary

### After Phase 1:
```bash
# Test TripoSR connection
python -c "from vtuber_pipeline.avatar.reconstruction import reconstruct_avatar; print(reconstruct_avatar)"

# Test VRM schema
python -c "from vtuber_pipeline.avatar.vrm_builder import create_vrm_extension; print(create_vrm_extension)"

# Test template exists
python -c "import trimesh; m = trimesh.load('assets/canonical_vtuber/template.glb'); print(len(m.vertices))"
```

### After Phase 2:
```bash
# Test fitting
python -c "from vtuber_pipeline.avatar.template_fitting import fit_template; print(fit_template)"

# Test textures
python -c "from vtuber_pipeline.avatar.texture_transfer import transfer_texture; print(transfer_texture)"
```

### After Phase 3 (Full E2E):
```bash
# Run full pipeline
vtuber-pipeline avatar --image tests/fixtures/anime_face.png --output output/ --profile commercial

# Verify VRM
python -c "
from pygltflib import GLTF2
gltf = GLTF2().load('output/avatar.vrm')
vrm = gltf.extensions['VRMC_vrm']
print(f'Bones: {list(vrm[\"humanoid\"][\"humanBones\"].keys())}')
print(f'Expressions: {list(vrm[\"expressions\"][\"preset\"].keys())}')
print(f'Commercial: {vrm[\"meta\"][\"commercialUsage\"]}')
"

# Run tests
pytest tests/ -v
```

---

## Files Summary

| File | Action | Phase |
|------|--------|-------|
| `vtuber_pipeline/avatar/build.py` | Modify | 1 |
| `vtuber_pipeline/avatar/reconstruction.py` | Modify | 1 |
| `vtuber_pipeline/core/config.py` | Modify | 1 |
| `vtuber_pipeline/avatar/vrm_builder.py` | Modify | 1, 2 |
| `vtuber_pipeline/avatar/validator.py` | Modify | 1 |
| `vtuber_pipeline/cli.py` | Modify | 1 |
| `vtuber_pipeline/avatar/template_mesh.py` | Modify | 1 |
| `assets/canonical_vtuber/template.glb` | Regenerate | 1 |
| `assets/canonical_vtuber/landmarks.json` | Modify | 1 |
| `assets/canonical_vtuber/topology.json` | Modify | 1 |
| `vtuber_pipeline/avatar/template_fitting.py` | Modify | 2 |
| `vtuber_pipeline/avatar/texture_transfer.py` | Modify | 2 |
| `vtuber_pipeline/avatar/expressions.py` | Modify | 2 |
| `vtuber_pipeline/avatar/hair.py` | Modify | 3 |
| `vtuber_pipeline/avatar/clothing.py` | Modify | 3 |
| `vtuber_pipeline/accessory/bake.py` | Modify | 3 |
| `tests/integration/test_e2e_pipeline.py` | Create | 3 |
| `tests/fixtures/anime_face.png` | Create | 3 |
| `third_party.lock.json` | Modify | 3 |

---

## Constraints

- Do NOT modify README.md
- Do NOT upload 1.txt to GitHub
- Korean comments OK in code
- Permissive licenses only (MIT, Apache-2.0, CC0)
- TripoSR is MIT licensed, safe for commercial use

---

## Verification

### Test Results (Iteration 2 - 2025-01-XX)

```
cd c:\Users\kkk\Desktop\Virtual-pipeline
pip install -e . --quiet
python -m pytest tests/ -x -q 2>&1
```

**Results:**
```
27 passed, 4 skipped, 16 warnings in 38.23s
```

**VRM Schema Verification:**
```python
from vtuber_pipeline.avatar.vrm_builder import create_vrm_extension
from pygltflib import GLTF2

gltf = GLTF2()
bone_mapping = {'hips': 0, 'spine': 1, 'chest': 2, 'neck': 3, 'head': 4}
vrm_ext = create_vrm_extension(gltf, bone_mapping=bone_mapping, commercial_usage='corporation')

# Results:
# SpecVersion: 1.0
# humanBones type: dict (correct VRM 1.0 format)
# humanBones keys: ['hips', 'spine', 'chest', 'neck', 'head']
# Commercial: corporation
# License URL: https://vrm.dev/licenses/1.0/
```

**Schema Compliance Checks:**
- ✅ `humanBones` is now an object (dict) with bone names as keys
- ✅ `preset` is now singular (not `presets`)
- ✅ `licenseUrl` uses VRM 1.0 license document URL
- ✅ `save_binary()` used before renaming to .vrm
- ✅ `commercialUsage` defaults to "corporation"
- ✅ `--commercial-usage` CLI option added

**Tests Passed:**
- ✅ test_vrm_schema_compliance
- ✅ test_commercial_usage_option
- ✅ All unit tests (24 passed)
- ✅ All integration tests (3 passed, 4 skipped)

**Commit:** 58ed9ca
