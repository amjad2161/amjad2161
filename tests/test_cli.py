"""CLI smoke tests."""

from brainiac import cli


def test_cli_status_command(monkeypatch):
    monkeypatch.setattr("sys.argv", ["brainiac", "status"])
    assert cli.main() == 0


def test_cli_boot_command(monkeypatch):
    monkeypatch.setattr("sys.argv", ["brainiac", "boot"])
    assert cli.main() == 0
