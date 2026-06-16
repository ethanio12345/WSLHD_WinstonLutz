"""Tests for the WL machine dropdown filtering (task 1.8b).

Covers the 4 MODIFIED wl-simple-mode scenarios:
- WL-only machine appears in WL dropdown
- CatPhan-only machine does NOT appear in WL dropdown
- Both-modules machine appears in WL dropdown
- Neither-module machine (would be rejected by config validation, so only 3 real cases)

Tests ``AppConfig.machine_keys_for_module("winston_lutz")`` which powers the
dropdown filter in ``pages/1_Winston_Lutz.py``.
"""

from __future__ import annotations

from core.config import MachineConfig


def _machine(display_name: str, roots: dict[str, str]) -> MachineConfig:
    """Build a MachineConfig with the given dicom_roots."""
    return MachineConfig(display_name=display_name, dicom_roots=roots)


def test_wl_dropdown_filters_to_wl_configured_machines() -> None:
    """The WL dropdown lists only machines with winston_lutz configured."""
    from core.config import AppConfig, AssetsConfig, OutputConfig

    config = AppConfig(
        machines={
            "LA2": _machine("LA2 (TrueBeam)", {"winston_lutz": "/data/LA2/WL"}),
            "LA3": _machine("LA3 (Edge)", {"catphan": "/data/LA3/CP"}),
            "LA4": _machine(
                "LA4 (TrueBeam)",
                {"winston_lutz": "/data/LA4/WL", "catphan": "/data/LA4/CP"},
            ),
        },
        output=OutputConfig(root="/out"),
        analysis_defaults={
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            },
            "catphan": {
                "hu_tolerance": 40,
                "scaling_tolerance": 0.5,
                "slice_thickness_tolerance": 0.5,
            },
        },
        assets=AssetsConfig(fry_meme_path="/assets/fry.png", logo_path="/assets/logo.png"),
    )

    wl_keys = config.machine_keys_for_module("winston_lutz")
    # LA2 (WL only) and LA4 (both) appear; LA3 (CP only) does not
    assert wl_keys == ["LA2", "LA4"]
    assert "LA3" not in wl_keys


def test_catphan_dropdown_filters_to_cp_configured_machines() -> None:
    """The CatPhan dropdown lists only machines with catphan configured."""
    from core.config import AppConfig, AssetsConfig, OutputConfig

    config = AppConfig(
        machines={
            "LA2": _machine("LA2 (TrueBeam)", {"winston_lutz": "/data/LA2/WL"}),
            "LA3": _machine("LA3 (Edge)", {"catphan": "/data/LA3/CP"}),
            "LA4": _machine(
                "LA4 (TrueBeam)",
                {"winston_lutz": "/data/LA4/WL", "catphan": "/data/LA4/CP"},
            ),
        },
        output=OutputConfig(root="/out"),
        analysis_defaults={
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            },
            "catphan": {
                "hu_tolerance": 40,
                "scaling_tolerance": 0.5,
                "slice_thickness_tolerance": 0.5,
            },
        },
        assets=AssetsConfig(fry_meme_path="/assets/fry.png", logo_path="/assets/logo.png"),
    )

    cp_keys = config.machine_keys_for_module("catphan")
    # LA3 (CP only) and LA4 (both) appear; LA2 (WL only) does not
    assert cp_keys == ["LA3", "LA4"]
    assert "LA2" not in cp_keys


def test_wl_dropdown_empty_when_no_wl_machines() -> None:
    """WL dropdown is empty when no machine has winston_lutz configured."""
    from core.config import AppConfig, AssetsConfig, OutputConfig

    config = AppConfig(
        machines={
            "LA4": _machine("LA4", {"catphan": "/data/LA4/CP"}),
        },
        output=OutputConfig(root="/out"),
        analysis_defaults={
            "catphan": {
                "hu_tolerance": 40,
                "scaling_tolerance": 0.5,
                "slice_thickness_tolerance": 0.5,
            },
        },
        assets=AssetsConfig(fry_meme_path="/assets/fry.png", logo_path="/assets/logo.png"),
    )

    assert config.machine_keys_for_module("winston_lutz") == []


def test_dropdown_keys_sorted_alphabetically() -> None:
    """Machine keys returned by machine_keys_for_module are sorted alphabetically."""
    from core.config import AppConfig, AssetsConfig, OutputConfig

    config = AppConfig(
        machines={
            "LA10": _machine("LA10", {"winston_lutz": "/data/LA10/WL"}),
            "LA2": _machine("LA2", {"winston_lutz": "/data/LA2/WL"}),
            "LA1": _machine("LA1", {"winston_lutz": "/data/LA1/WL"}),
        },
        output=OutputConfig(root="/out"),
        analysis_defaults={
            "winston_lutz": {
                "bb_size_mm": 5.0,
                "machine_scale": "VARIAN_IEC",
                "tolerance_mm": 1.0,
            },
        },
        assets=AssetsConfig(fry_meme_path="/assets/fry.png", logo_path="/assets/logo.png"),
    )

    assert config.machine_keys_for_module("winston_lutz") == ["LA1", "LA10", "LA2"]
