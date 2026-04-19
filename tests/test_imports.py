import brainiac
from brainiac import *  # noqa: F403,F401


def test_star_import_exports_all_symbols():
    for symbol in brainiac.__all__:
        assert symbol in globals()
