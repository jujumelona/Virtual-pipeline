# Canonical Template Asset Provenance

The production canonical topology is generated from the pinned MakeHuman base mesh
when no explicit `VTUBER_TEMPLATE_PATH` is supplied.

## Source

- Project: MakeHuman
- Upstream asset: `makehuman/data/3dobjs/base.obj`
- Pinned upstream commit: `a8bc2d54ff0ac92e78ff71431b1023eda42bf482`
- Asset license: CC0 1.0 / Public Domain Dedication

The MakeHuman application code itself is not embedded or imported into the runtime.
Only the CC0 graphical/base-mesh asset is used as the topology seed by the pipeline.

## Generated artifact

`vtuber_pipeline.avatar.template_mesh.get_template_path()` resolves an explicit
template when configured, otherwise it uses a repository template if present or
creates a cached `template.glb` from the pinned CC0 `base.obj`.

The old procedural sphere/cylinder/box template is test-only and is not selected by
the production resolver.

## Attribution note

CC0 does not require attribution, but source provenance is retained here for auditability.
