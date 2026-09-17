"""Unit tests for desktop entry, systemd user service, install script, and packaging."""

import configparser
import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).parent.parent.resolve()


def test_desktop_file_syntax_and_contents(repo_root: Path) -> None:
    desktop_paths = [
        repo_root / "data" / "gtk-emoji-picker.desktop",
        repo_root / "gtk-emoji-picker.desktop",
    ]

    for path in desktop_paths:
        assert path.exists(), f"Desktop entry file missing at {path}"

        config = configparser.ConfigParser(interpolation=None)
        config.read(path, encoding="utf-8")

        assert "Desktop Entry" in config.sections()
        entry = config["Desktop Entry"]

        assert entry.get("Type") == "Application"
        assert entry.get("Name") == "GTK Emoji Picker"
        assert entry.get("Exec") == "gtk-emoji-picker"
        assert "Utility" in entry.get("Categories", "")
        assert entry.get("Terminal") == "false"
        assert entry.get("StartupWMClass") == "gtk-emoji-picker"


def test_systemd_service_file_syntax_and_contents(repo_root: Path) -> None:
    service_paths = [
        repo_root / "data" / "gtk-emoji-picker-daemon.service",
        repo_root / "gtk-emoji-picker-daemon.service",
    ]

    for path in service_paths:
        assert path.exists(), f"Systemd service file missing at {path}"

        config = configparser.ConfigParser(interpolation=None)
        config.read(path, encoding="utf-8")

        assert "Unit" in config.sections()
        assert "Service" in config.sections()
        assert "Install" in config.sections()

        unit = config["Unit"]
        service = config["Service"]
        install = config["Install"]

        assert "GTK Emoji Picker" in unit.get("Description", "")
        assert "gtk-emoji-picker-daemon" in service.get("ExecStart", "")
        assert service.get("Type") == "simple"
        assert service.get("Restart") == "on-failure"
        assert install.get("WantedBy") == "graphical-session.target"


def test_install_script_help_and_dry_run(repo_root: Path) -> None:
    install_script = repo_root / "install.sh"
    assert install_script.exists()
    assert os.access(install_script, os.X_OK)

    # Test --help flag
    res_help = subprocess.run(
        [str(install_script), "--help"],
        capture_output=True,
        text=True,
    )
    assert res_help.returncode == 0
    assert "Usage:" in res_help.stdout
    assert "--user" in res_help.stdout
    assert "--system" in res_help.stdout
    assert "--enable-service" in res_help.stdout

    # Test --dry-run flag
    res_dry = subprocess.run(
        [str(install_script), "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert res_dry.returncode == 0
    assert "[Dry Run]" in res_dry.stdout
    assert "Target Prefix" in res_dry.stdout
    assert "gtk-emoji-picker-daemon.service" in res_dry.stdout

    # Test --uninstall --dry-run
    res_uninst_dry = subprocess.run(
        [str(install_script), "--uninstall", "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert res_uninst_dry.returncode == 0
    assert "Uninstalling" in res_uninst_dry.stdout
    assert "[Dry Run]" in res_uninst_dry.stdout


def test_install_script_system_mode_requires_root(repo_root: Path) -> None:
    install_script = repo_root / "install.sh"

    res = subprocess.run(
        [str(install_script), "--system", "--dry-run"],
        capture_output=True,
        text=True,
    )

    if os.geteuid() == 0:
        assert res.returncode == 0
    else:
        assert res.returncode != 0
        assert "requires root privileges" in res.stderr


def test_uninstall_wrapper_script(repo_root: Path) -> None:
    uninstall_script = repo_root / "uninstall.sh"
    assert uninstall_script.exists()
    assert os.access(uninstall_script, os.X_OK)

    res_dry = subprocess.run(
        [str(uninstall_script), "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert res_dry.returncode == 0
    assert "Uninstalling GTK Emoji Picker" in res_dry.stdout


def test_pyproject_scripts_entry_points(repo_root: Path) -> None:
    pyproject_file = repo_root / "pyproject.toml"
    assert pyproject_file.exists()

    content = pyproject_file.read_text(encoding="utf-8")
    assert 'gtk-emoji-picker = "gtk_emoji_picker.__main__:main"' in content
    assert (
        'gtk-emoji-picker-daemon = "gtk_emoji_picker.infrastructure.shortcut_daemon:main"'
        in content
    )
