"""Probe a failing PSD runtime in fresh interpreters, without model inference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import sys


PROBES = ('numpy', 'pillow', 'psd_import', 'rle_roundtrip', 'raw_roundtrip',
          'bounded_writer', 'legacy_save')


def diagnose_psd_runtime(output, *, timeout_seconds=30):
    from tools.vts_handoff_process import _save
    from tools.vts_subprocess import run_logged
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {'state': 'running', 'python_executable': sys.executable, 'probes': []}
    for probe in PROBES:
        log = output / (probe + '.log')
        item = {'probe': probe, 'log_path': str(log), 'returncode': None, 'signal': None}
        try:
            code = run_logged(
                [sys.executable, '-X', 'faulthandler', '-u', '-m',
                 'tools.vts_psd_diagnose', '--probe', probe, '--output', str(output)],
                cwd=Path(__file__).resolve().parents[1], log_path=log,
                timeout_seconds=timeout_seconds)
            item['returncode'] = code
            item['signal'] = signal.Signals(-code).name if code < 0 else None
        except Exception as exc:
            item['error'] = str(exc)
            item['error_type'] = type(exc).__name__
        report['probes'].append(item)
        _save(output / 'psd_diagnosis.json', report)
        print('[VTS] PSD_DIAG_RESULT: ' + json.dumps(item), flush=True)
    report['state'] = ('probes_passed_cause_unresolved'
                       if all(p['returncode'] == 0 for p in report['probes'])
                       else 'probe_failed')
    _save(output / 'psd_diagnosis.json', report)
    return report


def _probe(probe, output):
    def step(operation, **details):
        print('[VTS] PSD_DIAG_STEP: ' + json.dumps(
            {'probe': probe, 'operation': operation, **details}), flush=True)

    step('start', python=sys.version, executable=sys.executable)
    # Metadata can be read without importing the possibly crashing module.
    from importlib.metadata import version, PackageNotFoundError
    installed = {}
    for package in ('numpy', 'Pillow', 'psd-tools', 'scipy', 'scikit-image'):
        try:
            installed[package] = version(package)
        except PackageNotFoundError:
            installed[package] = 'not_installed'
    step('installed_versions', packages=installed)
    if probe == 'numpy':
        step('import_numpy')
        import numpy as np
        pixels = np.arange(1024, dtype=np.uint8).reshape(4, 256)
        assert np.array_equal(pixels, pixels.copy())
        step('numpy_ok', version=np.__version__, path=np.__file__)
    elif probe == 'pillow':
        step('import_pillow')
        import PIL
        from PIL import Image, ImageCms
        image = Image.new('RGBA', (256, 4), (127, 90, 180, 2))
        image.save(output / 'pillow.png')
        with Image.open(output / 'pillow.png') as saved:
            assert saved.tobytes() == image.tobytes()
        step('create_srgb_profile')
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
        step('serialize_srgb_profile')
        assert profile.tobytes()
        step('apply_srgb_profile')
        assert ImageCms.profileToProfile(image, profile, profile, outputMode='RGBA').tobytes() == image.tobytes()
        step('pillow_ok', version=PIL.__version__, path=PIL.__file__)
    else:
        step('import_psd_tools')
        import psd_tools
        from psd_tools import PSDImage
        from psd_tools.api.layers import PixelLayer
        from psd_tools.constants import Compression
        import psd_tools.compression as codec
        step('psd_import_ok', version=psd_tools.__version__, path=psd_tools.__file__,
             rle_path=getattr(codec.rle_impl, '__file__', 'unknown'))
        if probe != 'psd_import':
            from PIL import Image
            data = bytes(v for _ in range(4) for a in range(256) for v in (127, 90, 180, a))
            image = Image.frombytes('RGBA', (256, 4), data)
            if probe in ('rle_roundtrip', 'raw_roundtrip'):
                compression = Compression.RLE if probe == 'rle_roundtrip' else Compression.RAW
                step('create_document', compression=compression.name)
                psd = PSDImage.new('RGBA', image.size, depth=8, compression=compression)
                step('create_group')
                group = psd.create_group(name='HAIR')
                step('encode_layer')
                layer = PixelLayer.frompil(image, group, name='alpha_probe', compression=compression)
                if layer.mask is not None:
                    layer.remove_mask()
                step('write_records')
                path = output / (probe + '.psd')
                with path.open('wb') as stream:
                    psd._record.write(stream)
            else:
                from tools.vts_psd_layer import new_import_psd, create_import_layer, save_import_psd
                step('create_document')
                psd = new_import_psd(image.size)
                step('create_group')
                group = psd.create_group(name='HAIR')
                step('encode_layer')
                create_import_layer(image, group, name='alpha_probe')
                path = output / (probe + '.psd')
                step('save', writer=probe)
                if probe == 'legacy_save':
                    psd.save(path)
                else:
                    save_import_psd(psd, path)
            step('open')
            saved = PSDImage.open(path)
            step('decode_layer')
            leaf = next(layer for layer in saved.descendants() if not layer.is_group())
            assert leaf.topil(apply_icc=False).convert('RGBA').tobytes() == data
            step('decode_layer_with_icc')
            assert leaf.topil().convert('RGBA').tobytes() == data
    print('[VTS] PSD_DIAG_PASS: ' + probe, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', required=True, choices=PROBES)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    _probe(args.probe, args.output)
