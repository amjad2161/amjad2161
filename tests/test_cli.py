"""Tests for the G.A.N.E CLI entry points."""
import sys
import pytest
from unittest.mock import patch

from brainiac.cli import (
    _parse_coord_pair, _cmd_nav_route, _cmd_nav_position, main,
)


def test_parse_coord_pair_valid():
    assert _parse_coord_pair("32.0,34.0") == (32.0, 34.0)
    assert _parse_coord_pair("-90.5,180.0") == (-90.5, 180.0)


def test_parse_coord_pair_invalid():
    with pytest.raises(ValueError):
        _parse_coord_pair("not-a-coord")
    with pytest.raises(ValueError):
        _parse_coord_pair("32.0")


@pytest.mark.asyncio
async def test_nav_route_runs(capsys):
    rc = await _cmd_nav_route(32.0, 34.0, 32.1, 34.1, mode="drone", lang="en")
    captured = capsys.readouterr()
    assert rc == 0
    assert "Distance" in captured.out
    assert "Turn-by-turn" in captured.out


@pytest.mark.asyncio
async def test_nav_route_hebrew(capsys):
    rc = await _cmd_nav_route(32.0, 34.0, 32.1, 34.1, mode="drone", lang="he")
    captured = capsys.readouterr()
    assert rc == 0
    # At least one Hebrew character in the output
    assert any("\u05D0" <= c <= "\u05EA" for c in captured.out)


@pytest.mark.asyncio
async def test_nav_position_runs(capsys):
    rc = await _cmd_nav_position()
    captured = capsys.readouterr()
    assert rc == 0
    assert "Position" in captured.out
    assert "Satellites" in captured.out


def test_main_help_returns_zero(capsys):
    with patch.object(sys, "argv", ["brainiac", "help"]):
        rc = main()
    captured = capsys.readouterr()
    assert rc == 0
    assert "nav route" in captured.out
    assert "nav position" in captured.out


def test_main_unknown_command():
    with patch.object(sys, "argv", ["brainiac", "xyzzy"]):
        rc = main()
    assert rc == 1


def test_main_nav_unknown_subcommand():
    with patch.object(sys, "argv", ["brainiac", "nav", "bogus"]):
        rc = main()
    assert rc == 1


def test_main_nav_route_missing_args(capsys):
    with patch.object(sys, "argv", ["brainiac", "nav", "route"]):
        rc = main()
    captured = capsys.readouterr()
    assert rc == 1
    assert "Usage" in captured.out
