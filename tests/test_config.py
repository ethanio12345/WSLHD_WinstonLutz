"""Tests for ``core/config.py`` — configuration loading and template validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core.config import (
    CATPHAN_SUMMARY_NAMES,
    FP_SUMMARY_NAMES,
    REQUIRED_CATPHAN_TEMPLATE_NAMES,
    REQUIRED_FP_TEMPLATE_NAMES,
    ConfigError,
    WLDefaults,
    load_config,
    validate_catphan_template,
    validate_fp_template,
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

    Path(wl_root).mkdir(parents=True, exist_ok=True)
    Path(output_root).mkdir(parents=True, exist_ok=True)

    import yaml

    data = {
        "machines": {
            "LA2": {
                "display_name": "LA2 (TrueBeam)",
                "dicom_roots": {"winston_lutz": str(wl_root)},
                "output_root": str(output_root),
            }
        },
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
    assert config.machines["LA2"].output_root.startswith(str(tmp_path))
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
    with pytest.raises(ConfigError, match=r"output root .* does not exist"):
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

    # Ensure every configured dicom_root exists on disk; add output_root to each machine
    for _mkey, mconf in machines.items():
        for _mod, root in mconf.get("dicom_roots", {}).items():
            Path(root).mkdir(parents=True, exist_ok=True)
        mconf.setdefault("output_root", str(output_root))
        Path(mconf["output_root"]).mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {
        "machines": machines,
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
    """Machine with future module keys (trajectory_log, legacy field_profile) loads.

    Both ``trajectory_log`` (future) and ``field_profile`` (legacy — now
    decoupled from machines) are silently ignored as ``dicom_roots`` keys.
    """
    wl_root = tmp_path / "data" / "LA2" / "WinstonLutz"
    cp_root = tmp_path / "data" / "LA2" / "CatPhan"
    future_root = tmp_path / "data" / "LA2" / "Future"
    legacy_fp_root = tmp_path / "data" / "LA2" / "LegacyFieldProfile"
    config_path = _make_multi_module_yaml(
        tmp_path,
        machines={
            "LA2": {
                "display_name": "LA2",
                "dicom_roots": {
                    "winston_lutz": str(wl_root),
                    "catphan": str(cp_root),
                    "trajectory_log": str(future_root),
                    # Legacy key — silently ignored (decoupled)
                    "field_profile": str(legacy_fp_root),
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
    # The unknown keys pass through; the machine still has winston_lutz + catphan
    assert "trajectory_log" in config.machines["LA2"].dicom_roots
    assert "field_profile" in config.machines["LA2"].dicom_roots  # ignored, not rejected
    # has_field_profile() is always True now (page always available)
    assert config.has_field_profile()


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


# ---------------------------------------------------------------------------
# Field Profile config (decoupled from machines — generalize-field-profile-browser)
# ---------------------------------------------------------------------------

_FP_DEFAULTS: dict[str, Any] = {
    "protocol": "VARIAN",
}


def test_has_field_profile_always_true(tmp_path: Path) -> None:
    """has_field_profile() always returns True (page always available, decoupled)."""
    config_path = _make_machine_yaml(tmp_path)
    config = load_config(config_path)
    # No field_profile dicom_root anywhere, but page is still available
    assert config.has_field_profile() is True
    assert not any("field_profile" in m.dicom_roots for m in config.machines.values())


def test_fp_defaults_absent_loads_successfully(tmp_path: Path) -> None:
    """analysis_defaults.field_profile absent → config loads; page still works.

    The FP page falls back to protocol: VARIAN + pylinac defaults in this case.
    """
    config_path = _make_machine_yaml(tmp_path)
    config = load_config(config_path)
    # fp_defaults_or_none returns None when the section is absent
    assert config.fp_defaults_or_none is None
    # Page is still available
    assert config.has_field_profile()


def test_fp_defaults_present_loads(tmp_path: Path) -> None:
    """analysis_defaults.field_profile present → fp_defaults_or_none returns it."""
    config_path = _make_machine_yaml(
        tmp_path,
        analysis_defaults={
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            },
            "field_profile": {"protocol": "SIEMENS", "in_field_ratio": 0.7},
        },
    )
    config = load_config(config_path)
    fp = config.fp_defaults_or_none
    assert fp is not None
    assert fp.protocol == "SIEMENS"
    assert fp.in_field_ratio == 0.7


def test_fp_defaults_invalid_protocol_rejected(tmp_path: Path) -> None:
    """analysis_defaults.field_profile with invalid protocol → ConfigError.

    Even though the section is optional, IF present it must validate.
    """
    config_path = _make_machine_yaml(
        tmp_path,
        analysis_defaults={
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            },
            "field_profile": {"protocol": "INVALID"},
        },
    )
    with pytest.raises(ConfigError, match="validation failed"):
        load_config(config_path)


def test_legacy_fp_dicom_root_ignored(tmp_path: Path) -> None:
    """Legacy dicom_roots.field_profile is silently ignored (forward-compat).

    A machine may still have a `field_profile` entry under dicom_roots (legacy
    config); it loads fine and the (possibly missing) directory is NOT
    filesystem-validated, since field_profile is no longer a known module key.
    """
    wl_root = tmp_path / "data" / "LA2" / "WinstonLutz"
    # Note: legacy_fp_root intentionally does NOT exist on disk
    legacy_fp_root = tmp_path / "data" / "LA2" / "NonExistentLegacyFP"
    config_path = _make_multi_module_yaml(
        tmp_path,
        machines={
            "LA2": {
                "display_name": "LA2",
                "dicom_roots": {
                    "winston_lutz": str(wl_root),
                    "field_profile": str(legacy_fp_root),
                },
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
    # Loads successfully — the legacy field_profile root is not validated
    config = load_config(config_path)
    assert config.has_winston_lutz()
    assert config.has_field_profile()  # always True now


def test_fp_browse_root_default(tmp_path: Path) -> None:
    """fp_browse_root defaults to /data when field_profile section is absent."""
    config_path = _make_machine_yaml(tmp_path)
    config = load_config(config_path)
    assert config.fp_browse_root == "/data"


def test_fp_browse_root_override(tmp_path: Path) -> None:
    """field_profile.browse_root override is respected."""
    import yaml

    output_root = tmp_path / "out"
    output_root.mkdir(parents=True, exist_ok=True)
    wl_root = tmp_path / "dicom" / "LA2" / "WinstonLutz"
    wl_root.mkdir(parents=True, exist_ok=True)

    data = {
        "machines": {
            "LA2": {
                "display_name": "LA2 (TrueBeam)",
                "dicom_roots": {"winston_lutz": str(wl_root)},
                "output_root": str(output_root),
            }
        },
        "analysis_defaults": {
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            }
        },
        "assets": {"fry_meme_path": "/assets/fry.png", "logo_path": "/assets/logo.png"},
        "field_profile": {"browse_root": "/mnt/rt_images"},
    }
    config_path = tmp_path / "machines.yaml"
    config_path.write_text(yaml.dump(data), encoding="utf-8")
    config = load_config(config_path)
    assert config.fp_browse_root == "/mnt/rt_images"


def test_fp_defaults_optional_keys_use_defaults(tmp_path: Path) -> None:
    """Field Profile defaults with only protocol → optional keys fall back."""
    config_path = _make_machine_yaml(
        tmp_path,
        analysis_defaults={
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            },
            "field_profile": {"protocol": "VARIAN"},
        },
    )
    config = load_config(config_path)
    fp = config.fp_defaults_or_none
    assert fp is not None
    assert fp.protocol == "VARIAN"
    assert fp.centering == "BEAM_CENTER"
    assert fp.in_field_ratio == 0.8
    assert fp.penumbra == [20.0, 80.0]
    assert fp.is_fff is False
    assert fp.interpolation == "LINEAR"
    assert fp.edge_detection_method == "INFLECTION_DERIVATIVE"


def test_fp_defaults_rejects_extra_keys() -> None:
    """FieldProfileDefaults uses extra='forbid' — unknown keys raise."""
    from core.config import FieldProfileDefaults

    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        FieldProfileDefaults(protocol="VARIAN", bogus_key=True)


def test_fp_summary_names_count() -> None:
    """Sanity: exactly 29 metric named cells + 30th template_version."""
    assert len(FP_SUMMARY_NAMES) == 29
    assert len(REQUIRED_FP_TEMPLATE_NAMES) == 30
    assert "template_version" in REQUIRED_FP_TEMPLATE_NAMES
    assert "template_version" not in FP_SUMMARY_NAMES


def test_fp_template_validation_missing_names(tmp_path: Path) -> None:
    """Field Profile template missing defined names → ConfigError."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "incomplete field profile template"
    template_path = tmp_path / "bad_fp.xltx"
    wb.save(str(template_path))

    with pytest.raises(ConfigError, match="Field Profile template missing required defined names"):
        validate_fp_template(template_path)


def test_fp_template_file_not_found(tmp_path: Path) -> None:
    """Nonexistent Field Profile template → ConfigError."""
    with pytest.raises(ConfigError, match="Field Profile template not found"):
        validate_fp_template(tmp_path / "ghost_fp.xltx")
