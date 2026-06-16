"""Configuration models and loader for the Winston-Lutz Streamlit app.

Loads ``machines.yaml``, validates it with pydantic, and performs filesystem
validation (DICOM roots exist, output root is writable). Also validates that
the xltx template defines all 25 required named cells.

Public API:
    - :class:`MachineConfig`
    - :class:`OutputConfig`
    - :class:`WLDefaults`
    - :class:`AssetsConfig`
    - :class:`AppConfig`
    - :func:`load_config`
    - :func:`validate_template`
    - :data:`REQUIRED_TEMPLATE_NAMES`
    - :data:`WL_METRIC_NAMES`
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — the 24 named cells (the app↔MyQA contract) + ``template_version``
# ---------------------------------------------------------------------------

# Session metadata (3)
_META_NAMES = ["machine_name", "session_date", "num_total_images"]
# Clinical metrics (9)
_CLINICAL_NAMES = [
    "max_2d_cax_to_bb",
    "median_2d_cax_to_bb",
    "mean_2d_cax_to_bb",
    "gantry_3d_iso",
    "coll_2d_iso",
    "couch_2d_iso",
    "bb_shift_x",
    "bb_shift_y",
    "bb_shift_z",
]
# Secondary metrics (12)
_SECONDARY_NAMES = [
    "max_2d_cax_to_epid",
    "median_2d_cax_to_epid",
    "mean_2d_cax_to_epid",
    "gantry_coll_3d_iso",
    "max_gantry_rms",
    "max_coll_rms",
    "max_couch_rms",
    "max_epid_rms",
    "num_gantry_images",
    "num_coll_images",
    "num_couch_images",
    "num_gantry_coll_images",
]

#: The 24 metric named cells written to the xltx summary sheet.
WL_METRIC_NAMES: tuple[str, ...] = (*_META_NAMES, *_CLINICAL_NAMES, *_SECONDARY_NAMES)

#: All 25 required defined names in the template (24 metrics + version stamp).
REQUIRED_TEMPLATE_NAMES: tuple[str, ...] = (*WL_METRIC_NAMES, "template_version")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class MachineScale(str):
    """Thin enum-like wrapper around pylinac's ``MachineScale``.

    We accept the scale as a plain string from YAML and convert it to the
    pylinac enum at the point of use (``core/wl_runner.py``).  Keeping it a
    string here avoids importing pylinac at config-load time (pylinac is
    heavy; config validation should be fast).
    """

    ALLOWED: tuple[str, ...] = ("VARIAN_IEC", "VARIAN_STANDARD", "IEC61217")


class MachineConfig(BaseModel):
    """Per-machine configuration."""

    model_config = ConfigDict(extra="allow")

    display_name: str
    dicom_roots: dict[str, str] = Field(
        ..., description="Keyed by module name; 'winston_lutz' required for v1."
    )

    @field_validator("dicom_roots")
    @classmethod
    def _validate_wl_root_present(cls, v: dict[str, str]) -> dict[str, str]:
        if "winston_lutz" not in v:
            raise ValueError(
                "dicom_roots must include 'winston_lutz' (the only supported module in v1)"
            )
        return v


class OutputConfig(BaseModel):
    """Output directory configuration."""

    root: str


class WLDefaults(BaseModel):
    """Centre-wide Winston-Lutz analysis defaults from ``machines.yaml``."""

    model_config = ConfigDict(extra="forbid")

    # Required
    bb_size_mm: float
    machine_scale: str
    tolerance_mm: float = Field(
        ..., description="UI-only pass/fail threshold; not passed to pylinac."
    )
    # Optional (fall back to pylinac defaults if absent)
    low_density_bb: bool = False
    open_field: bool = False
    apply_virtual_shift: bool = False
    snap_tolerance: float | None = None
    gantry_reference: float | None = None
    collimator_reference: float | None = None
    couch_reference: float | None = None

    @field_validator("machine_scale")
    @classmethod
    def _validate_scale(cls, v: str) -> str:
        if v not in MachineScale.ALLOWED:
            raise ValueError(f"machine_scale must be one of {MachineScale.ALLOWED}, got '{v}'")
        return v


class AssetsConfig(BaseModel):
    """Asset path configuration."""

    fry_meme_path: str
    logo_path: str


class AppConfig(BaseModel):
    """Top-level application configuration (the parsed ``machines.yaml``)."""

    model_config = ConfigDict(extra="forbid")

    machines: dict[str, MachineConfig]
    output: OutputConfig
    analysis_defaults: dict[str, Any] = Field(
        default_factory=dict,
        description="Keyed by module name; 'winston_lutz' processed in v1.",
    )
    assets: AssetsConfig

    @field_validator("analysis_defaults")
    @classmethod
    def _validate_wl_defaults_present(cls, v: dict[str, Any]) -> dict[str, Any]:
        if "winston_lutz" not in v:
            raise ValueError("analysis_defaults must include a 'winston_lutz' section")
        # Validate the WL defaults sub-section via WLDefaults model
        WLDefaults(**v["winston_lutz"])
        return v

    @property
    def wl_defaults(self) -> WLDefaults:
        """Convenience accessor for the centre-wide WL defaults."""
        return WLDefaults(**self.analysis_defaults["winston_lutz"])

    @property
    def sorted_machine_keys(self) -> list[str]:
        """Machine keys sorted alphabetically (for dropdown ordering)."""
        return sorted(self.machines.keys())


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """Raised when configuration is invalid or the filesystem is misconfigured."""


def load_config(path: Path) -> AppConfig:
    """Read ``machines.yaml``, validate with pydantic, and probe the filesystem.

    Performs filesystem validation:
    - Each machine's ``dicom_roots.winston_lutz`` path must exist.
    - ``output.root`` must exist and be writable (probe-write).

    Args:
        path: Path to ``machines.yaml``.

    Returns:
        Validated :class:`AppConfig`.

    Raises:
        ConfigError: If the file cannot be read, fails pydantic validation,
            or a filesystem check fails.
    """
    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")

    try:
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"Top-level of {path} must be a mapping, got {type(raw).__name__}")

    # Pydantic validation
    try:
        config = AppConfig(**raw)
    except Exception as exc:
        raise ConfigError(f"Configuration validation failed:\n{exc}") from exc

    # Filesystem validation — DICOM roots
    for machine_key, machine in config.machines.items():
        wl_root = Path(machine.dicom_roots["winston_lutz"])
        if not wl_root.exists():
            raise ConfigError(f"Machine {machine_key}: DICOM root {wl_root} does not exist")

    # Filesystem validation — output root writability
    output_root = Path(config.output.root)
    if not output_root.exists():
        raise ConfigError(
            f"Output root {output_root} does not exist — check the docker-compose volume mount"
        )
    if not _is_writable(output_root):
        raise ConfigError(
            f"Output root {output_root} is not writable — check mount options and disk space"
        )

    return config


def _is_writable(path: Path) -> bool:
    """Probe-write a small temp file to confirm ``path`` is writable."""
    probe = path / ".wl_probe_write"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Template validation
# ---------------------------------------------------------------------------


def validate_template(template_path: Path) -> None:
    """Verify the xltx template defines all 25 required named cells.

    Args:
        template_path: Path to ``templates/winston_lutz.xltx``.

    Raises:
        ConfigError: If the template cannot be loaded or is missing names.
    """
    # Imported lazily so config validation works without openpyxl installed
    # (e.g. in minimal CI environments that only check the YAML schema).
    from openpyxl import load_workbook

    if not template_path.exists():
        raise ConfigError(f"WL template not found: {template_path}")

    try:
        wb = load_workbook(str(template_path))
    except Exception as exc:
        raise ConfigError(f"Cannot load template {template_path}: {exc}") from exc

    defined = set(wb.defined_names)
    missing = [n for n in REQUIRED_TEMPLATE_NAMES if n not in defined]
    if missing:
        raise ConfigError(
            "WL template missing required defined names: " + ", ".join(sorted(missing))
        )


def configure_logging() -> None:
    """Configure stdout logging (Docker convention — captured by ``docker logs``)."""
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


__all__ = [
    "REQUIRED_TEMPLATE_NAMES",
    "WL_METRIC_NAMES",
    "AppConfig",
    "AssetsConfig",
    "ConfigError",
    "MachineConfig",
    "MachineScale",
    "OutputConfig",
    "WLDefaults",
    "configure_logging",
    "load_config",
    "validate_template",
]
