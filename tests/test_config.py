"""Tests for ``core/config.py`` — configuration loading and template validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core.config import (
    CATPHAN_SUMMARY_NAMES,
    REQUIRED_CATPHAN_TEMPLATE_NAMES,
    ConfigError,
    WLDefaults,
    load_config,
    validate_catphan_template,
    validate_template,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_machine_yaml(
    tmp_path: Path,
    *,
    wl_root: Path | None = None,
    output_root: Path | None = None,
    analysis_defaults: dict[str, Any] | None = None,
    assets: dict[str, str] | None = None,
    extra: str = "",
) -> Path:
    """Write a minimal valid ``machines.yaml`` to ``tmp_path`` and return its path."""
    if wl_root is None:
        wl_root = tmp_path / "dicom" / "LA2" / "WinstonLutz"
        wl_root.mkdir(parents=True, exist_ok=True)
    if output_root is None:
        output_root = tmp_path / "out"
        output_root.mkdir(parents=True, exist_ok=True)
    if analysis_defaults is None:
        analysis_defaults = {
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            }
        }
    if assets is None:
        assets = {"fry_meme_path": "/assets/fry.png", "logo_path": "/assets/logo.png"}

    # Ensure the wl_root exists (filesystem validation requires it)
    Path(wl_root).mkdir(parents=True, exist_ok=True)
    Path(output_root).mkdir(parents=True, exist_ok=True)

    import yaml

    data = {
        "machines": {
            "LA2": {
                "display_name": "LA2 (TrueBeam)",
                "dicom_roots": {"winston_lutz": str(wl_root)},
            }
        },
        "output": {"root": str(output_root)},
        "analysis_defaults": analysis_defaults,
        "assets": assets,
    }
    config_path = tmp_path / "machines.yaml"
    config_path.write_text(yaml.dump(data) + extra, encoding="utf-8")
    return config_path


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_load_config_happy_path(tmp_path: Path) -> None:
    """Valid config + valid template loads successfully."""
    config_path = _make_machine_yaml(tmp_path)
    config = load_config(config_path)

    assert "LA2" in config.machines
    assert config.machines["LA2"].display_name == "LA2 (TrueBeam)"
    assert config.output.root.startswith(str(tmp_path))
    assert config.wl_defaults.bb_size_mm == 5.0
    assert config.wl_defaults.tolerance_mm == 1.0
    assert config.sorted_machine_keys == ["LA2"]


def test_validate_template_real_template() -> None:
    """The committed template should pass validation."""
    template_path = Path(__file__).resolve().parent.parent / "templates" / "winston_lutz.xltx"
    validate_template(template_path)  # should not raise


# ---------------------------------------------------------------------------
# Pydantic validation
# ---------------------------------------------------------------------------


def test_missing_required_key_bb_size(tmp_path: Path) -> None:
    """Missing required ``bb_size_mm`` → ConfigError."""
    config_path = _make_machine_yaml(
        tmp_path,
        analysis_defaults={
            "winston_lutz": {
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            }
        },
    )
    with pytest.raises(ConfigError, match="validation failed"):
        load_config(config_path)


def test_invalid_machine_scale(tmp_path: Path) -> None:
    """Invalid ``machine_scale`` value → ConfigError."""
    config_path = _make_machine_yaml(
        tmp_path,
        analysis_defaults={
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "BOGUS_SCALE",
                "tolerance_mm": 1.0,
            }
        },
    )
    with pytest.raises(ConfigError, match="validation failed"):
        load_config(config_path)


def test_optional_pylinac_param_absent(tmp_path: Path) -> None:
    """Optional params absent → config still loads, defaults applied."""
    config_path = _make_machine_yaml(tmp_path)
    config = load_config(config_path)
    # apply_virtual_shift defaults to False
    assert config.wl_defaults.apply_virtual_shift is False
    assert config.wl_defaults.low_density_bb is False


def test_optional_pylinac_param_present(tmp_path: Path) -> None:
    """Optional params present → config reflects them."""
    config_path = _make_machine_yaml(
        tmp_path,
        analysis_defaults={
            "winston_lutz": {
                "bb_size_mm": 3.0,
                "machine_scale": "IEC61217",
                "tolerance_mm": 0.5,
                "apply_virtual_shift": True,
                "snap_tolerance": 3,
            }
        },
    )
    config = load_config(config_path)
    assert config.wl_defaults.bb_size_mm == 3.0
    assert config.wl_defaults.machine_scale == "IEC61217"
    assert config.wl_defaults.apply_virtual_shift is True
    assert config.wl_defaults.snap_tolerance == 3


def test_wl_defaults_model_rejects_extra_keys() -> None:
    """WLDefaults uses extra='forbid' — unknown keys raise."""
    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        WLDefaults(
            bb_size_mm=5.0,
            machine_scale="VARIAN_IEC",
            tolerance_mm=1.0,
            bogus_key=True,
        )


# ---------------------------------------------------------------------------
# Filesystem validation
# ---------------------------------------------------------------------------


def test_nonexistent_dicom_root(tmp_path: Path) -> None:
    """DICOM root that doesn't exist → ConfigError."""
    bogus_root = tmp_path / "does" / "not" / "exist"
    config_path = _make_machine_yaml(tmp_path, wl_root=bogus_root)
    # _make_machine_yaml creates the dir, so remove it to simulate missing
    bogus_root.rmdir()
    with pytest.raises(ConfigError, match=r"DICOM root .* does not exist"):
        load_config(config_path)


def test_read_only_output_root(tmp_path: Path) -> None:
    """Read-only output root → ConfigError."""
    output_root = tmp_path / "readonly_out"
    output_root.mkdir()
    config_path = _make_machine_yaml(tmp_path, output_root=output_root)
    # Remove write permission
    output_root.chmod(0o555)
    try:
        with pytest.raises(ConfigError, match="not writable"):
            load_config(config_path)
    finally:
        # Restore so tmp_path cleanup works
        output_root.chmod(0o755)


def test_missing_output_root(tmp_path: Path) -> None:
    """Output root that doesn't exist → ConfigError."""
    output_root = tmp_path / "nope"
    config_path = _make_machine_yaml(tmp_path, output_root=output_root)
    output_root.rmdir()
    with pytest.raises(ConfigError, match=r"Output root .* does not exist"):
        load_config(config_path)


# ---------------------------------------------------------------------------
# Template validation
# ---------------------------------------------------------------------------


def test_template_missing_names(tmp_path: Path) -> None:
    """Template missing defined names → ConfigError from validate_template."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "incomplete template"
    template_path = tmp_path / "bad.xltx"
    wb.save(str(template_path))

    with pytest.raises(ConfigError, match="missing required defined names"):
        validate_template(template_path)


def test_template_file_not_found(tmp_path: Path) -> None:
    """Nonexistent template file → ConfigError."""
    with pytest.raises(ConfigError, match="WL template not found"):
        validate_template(tmp_path / "ghost.xltx")


def test_config_file_not_found(tmp_path: Path) -> None:
    """Missing machines.yaml → ConfigError."""
    with pytest.raises(ConfigError, match="Configuration file not found"):
        load_config(tmp_path / "ghost.yaml")


# ---------------------------------------------------------------------------
# Multi-module config (machine-config MODIFIED spec — tasks 2.6)
# ---------------------------------------------------------------------------

_CP_DEFAULTS: dict[str, Any] = {
    "hu_tolerance": 40,
    "scaling_tolerance": 0.5,
    "slice_thickness_tolerance": 0.5,
}


def _make_multi_module_yaml(
    tmp_path: Path,
    *,
    machines: dict[str, dict[str, Any]],
    analysis_defaults: dict[str, Any] | None = None,
    output_root: Path | None = None,
) -> Path:
    """Write a ``machines.yaml`` with arbitrary machine/module configuration."""
    import yaml

    if output_root is None:
        output_root = tmp_path / "out"
        output_root.mkdir(parents=True, exist_ok=True)

    # Ensure every configured dicom_root exists on disk
    for _mkey, mconf in machines.items():
        for _mod, root in mconf.get("dicom_roots", {}).items():
            Path(root).mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {
        "machines": machines,
        "output": {"root": str(output_root)},
        "analysis_defaults": analysis_defaults or {},
        "assets": {"fry_meme_path": "/assets/fry.png", "logo_path": "/assets/logo.png"},
    }
    config_path = tmp_path / "machines.yaml"
    config_path.write_text(yaml.dump(data), encoding="utf-8")
    return config_path


def test_valid_config_with_both_modules(tmp_path: Path) -> None:
    """Both winston_lutz and catphan configured → loads with both defaults."""
    wl_root = tmp_path / "data" / "LA2" / "WinstonLutz"
    cp_root = tmp_path / "data" / "LA2" / "CatPhan"
    config_path = _make_multi_module_yaml(
        tmp_path,
        machines={
            "LA2": {
                "display_name": "LA2 (TrueBeam)",
                "dicom_roots": {
                    "winston_lutz": str(wl_root),
                    "catphan": str(cp_root),
                },
            }
        },
        analysis_defaults={
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            },
            "catphan": _CP_DEFAULTS,
        },
    )
    config = load_config(config_path)
    assert config.has_winston_lutz()
    assert config.has_catphan()
    assert config.wl_defaults.bb_size_mm == 5.0
    assert config.cp_defaults.hu_tolerance == 40


def test_valid_config_wl_only(tmp_path: Path) -> None:
    """WL-only machine → loads; has_catphan() is False."""
    wl_root = tmp_path / "data" / "LA3" / "WinstonLutz"
    config_path = _make_multi_module_yaml(
        tmp_path,
        machines={
            "LA3": {
                "display_name": "LA3",
                "dicom_roots": {"winston_lutz": str(wl_root)},
            }
        },
        analysis_defaults={
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            }
        },
    )
    config = load_config(config_path)
    assert config.has_winston_lutz()
    assert not config.has_catphan()


def test_valid_config_catphan_only(tmp_path: Path) -> None:
    """CatPhan-only machine (no WL) → loads; has_winston_lutz() is False."""
    cp_root = tmp_path / "data" / "LA4" / "CatPhan"
    config_path = _make_multi_module_yaml(
        tmp_path,
        machines={
            "LA4": {
                "display_name": "LA4",
                "dicom_roots": {"catphan": str(cp_root)},
            }
        },
        analysis_defaults={"catphan": _CP_DEFAULTS},
    )
    config = load_config(config_path)
    assert config.has_catphan()
    assert not config.has_winston_lutz()


def test_empty_dicom_roots_rejected(tmp_path: Path) -> None:
    """Machine with empty dicom_roots → ConfigError."""
    config_path = _make_multi_module_yaml(
        tmp_path,
        machines={
            "LA5": {
                "display_name": "LA5",
                "dicom_roots": {},
            }
        },
        analysis_defaults={},
    )
    with pytest.raises(ConfigError, match="validation failed"):
        load_config(config_path)


def test_catphan_without_defaults_rejected(tmp_path: Path) -> None:
    """Machine with catphan but analysis_defaults.catphan missing → ConfigError."""
    cp_root = tmp_path / "data" / "LA2" / "CatPhan"
    config_path = _make_multi_module_yaml(
        tmp_path,
        machines={
            "LA2": {
                "display_name": "LA2",
                "dicom_roots": {"catphan": str(cp_root)},
            }
        },
        analysis_defaults={},
    )
    with pytest.raises(ConfigError, match="catphan module configured"):
        load_config(config_path)


def test_nonexistent_catphan_dicom_root(tmp_path: Path) -> None:
    """CatPhan root that doesn't exist → ConfigError."""
    cp_root = tmp_path / "data" / "LA2" / "CatPhan"
    config_path = _make_multi_module_yaml(
        tmp_path,
        machines={
            "LA2": {
                "display_name": "LA2",
                "dicom_roots": {"catphan": str(cp_root)},
            }
        },
        analysis_defaults={"catphan": _CP_DEFAULTS},
    )
    # _make_multi_module_yaml creates the dir, so remove it
    cp_root.rmdir()
    with pytest.raises(ConfigError, match=r"DICOM root .* does not exist"):
        load_config(config_path)


def test_forward_compat_unknown_module_key(tmp_path: Path) -> None:
    """Machine with a future module key (field_profile) loads successfully."""
    wl_root = tmp_path / "data" / "LA2" / "WinstonLutz"
    cp_root = tmp_path / "data" / "LA2" / "CatPhan"
    fp_root = tmp_path / "data" / "LA2" / "FieldProfile"
    config_path = _make_multi_module_yaml(
        tmp_path,
        machines={
            "LA2": {
                "display_name": "LA2",
                "dicom_roots": {
                    "winston_lutz": str(wl_root),
                    "catphan": str(cp_root),
                    "field_profile": str(fp_root),
                },
            }
        },
        analysis_defaults={
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            },
            "catphan": _CP_DEFAULTS,
        },
    )
    config = load_config(config_path)
    # The unknown key passes through; the machine still has winston_lutz + catphan
    assert "field_profile" in config.machines["LA2"].dicom_roots


def test_catphan_template_validation_missing_names(tmp_path: Path) -> None:
    """CatPhan template missing defined names → ConfigError."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "incomplete catphan template"
    template_path = tmp_path / "bad_catphan.xltx"
    wb.save(str(template_path))

    with pytest.raises(ConfigError, match="CatPhan template missing required defined names"):
        validate_catphan_template(template_path)


def test_catphan_template_file_not_found(tmp_path: Path) -> None:
    """Nonexistent CatPhan template → ConfigError."""
    with pytest.raises(ConfigError, match="CatPhan template not found"):
        validate_catphan_template(tmp_path / "ghost_catphan.xltx")


def test_catphan_summary_names_count() -> None:
    """Sanity: exactly 18 metric named cells + 19th template_version."""
    assert len(CATPHAN_SUMMARY_NAMES) == 18
    assert len(REQUIRED_CATPHAN_TEMPLATE_NAMES) == 19
    assert "template_version" in REQUIRED_CATPHAN_TEMPLATE_NAMES
    assert "template_version" not in CATPHAN_SUMMARY_NAMES
