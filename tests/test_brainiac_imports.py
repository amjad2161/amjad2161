"""Top-level package import smoke tests."""

import brainiac


def test_brainiac_all_symbols_resolve():
    assert hasattr(brainiac, "__all__")
    for symbol in brainiac.__all__:
        assert hasattr(brainiac, symbol)
