"""VTuber pipeline. Heavy mode-specific dependencies load on demand."""
from importlib import import_module

__version__ = '0.1.0'
__all__ = ['avatar', 'accessory', 'core']


def __getattr__(name):
    if name in __all__:
        module = import_module(f'{__name__}.{name}')
        globals()[name] = module
        return module
    raise AttributeError(name)
