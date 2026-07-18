"""Smoke tests: verify the package and its core modules import cleanly.

These are intentionally lightweight — they give CI a non-empty test suite and
catch gross import/syntax regressions until a fuller suite is added.
"""


def test_package_imports() -> None:
    import trmnl_server

    assert trmnl_server is not None


def test_core_modules_import() -> None:
    from trmnl_server import config
    from trmnl_server.plugins import base
    from trmnl_server.plugins.munichglance import plugin, renderer

    assert config is not None
    assert base is not None
    assert plugin is not None
    assert renderer is not None
