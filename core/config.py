"""Configuration models and loader for the Winston-Lutz / CatPhan Streamlit app.

Loads ``machines.yaml``, validates it with pydantic, and performs filesystem
validation (DICOM roots exist, output root is writable). Also validates that
the xltx templates define all required named cells.

Public API:
    - :class:`MachineConfig`
    - :class:`OutputConfig`
    - :class:`WLDefaults`
    - :class:`CatPhanDefaults`
    - :class:`AssetsConfig`
    - :class:`AppConfig`
    - :func:`load_config`
    - :func:`validate_template`
    - :func:`validate_catphan_template`
    - :data:`REQUIRED_TEMPLATE_NAMES`
    - :data:`REQUIRED_CATPHAN_TEMPLATE_NAMES`
    - :data:`WL_METRIC_NAMES`
    - :data:`CATPHAN_SUMMARY_NAMES`
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

#: The 24 metric named cells written to the WL xltx summary sheet.
WL_METRIC_NAMES: tuple[str, ...] = (*_META_NAMES, *_CLINICAL_NAMES, *_SECONDARY_NAMES)

#: All 25 required defined names in the WL template (24 metrics + version stamp).
REQUIRED_TEMPLATE_NAMES: tuple[str, ...] = (*WL_METRIC_NAMES, "template_version")

# ---------------------------------------------------------------------------
# Constants — the 19 named cells for the CatPhan xlsx (the app↔MyQA contract)
# ---------------------------------------------------------------------------

# Session metadata (3)
_CP_META_NAMES = ["machine_name", "session_date", "num_images"]
# Pass/fail flags (4)
_CP_FLAG_NAMES = [
    "hu_linearity_passed",
    "geometry_passed",
    "uniformity_passed",
    "thickness_passed",
]
# Geometry (2)
_CP_GEOMETRY_NAMES = ["measured_slice_thickness_mm", "avg_line_distance_mm"]
# Uniformity (2)
_CP_UNIFORMITY_NAMES = ["uniformity_index", "integral_non_uniformity"]
# Contrast (2)
_CP_CONTRAST_NAMES = ["low_contrast_visibility", "num_rois_seen"]
# Resolution (2)
_CP_RESOLUTION_NAMES = ["mtf_50_lp_mm", "mtf_90_lp_mm"]
# NPS (2)
_CP_NPS_NAMES = ["nps_avg_power", "nps_max_freq"]
# Orientation (1)
_CP_ORIENTATION_NAMES = ["catphan_roll_deg"]

#: The 18 metric named cells written to the CatPhan xltx summary sheet
#: (excludes ``template_version`` which is the 19th).
CATPHAN_SUMMARY_NAMES: tuple[str, ...] = (
    *_CP_META_NAMES,
    *_CP_FLAG_NAMES,
    *_CP_GEOMETRY_NAMES,
    *_CP_UNIFORMITY_NAMES,
    *_CP_CONTRAST_NAMES,
    *_CP_RESOLUTION_NAMES,
    *_CP_NPS_NAMES,
    *_CP_ORIENTATION_NAMES,
)

#: All 19 required defined names in the CatPhan template (18 metrics + version stamp).
REQUIRED_CATPHAN_TEMPLATE_NAMES: tuple[str, ...] = (*CATPHAN_SUMMARY_NAMES, "template_version")

#: Module keys the app currently knows about (for validation).
#: Unknown keys (e.g. ``field_profile``) pass through silently for forward compat.
_KNOWN_MODULE_KEYS: set[str] = {"winston_lutz", "catphan"}


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
    """Per-machine configuration.

    ``dicom_roots`` is a multi-module dict where ``winston_lutz`` and
    ``catphan`` are each independently optional. At least one module root must
    be present per machine. Unknown keys (e.g. ``field_profile``) pass through
    silently for forward compatibility.
    """

    model_config = ConfigDict(extra="allow")

    display_name: str
    dicom_roots: dict[str, str] = Field(
        ..., description="Keyed by module name; at least one module root required per machine."
    )

    @model_validator(mode="after")
    def _validate_at_least_one_module(self) -> MachineConfig:
        if not self.dicom_roots:
            raise ValueError("dicom_roots must contain at least one module root")
        return self


class OutputConfig(BaseModel):
    """Output directory configuration."""

    root: str
    category: str = "Clinical QA"
    pylinac_subfolder: str = "Pylinac"


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


class CatPhanDefaults(BaseModel):
    """Centre-wide CatPhan 504 analysis defaults from ``machines.yaml``.

    Required keys: ``hu_tolerance``, ``scaling_tolerance``,
    ``slice_thickness_tolerance``. All other pylinac CatPhan ``analyze()``
    parameters are optional and fall back to pylinac defaults if absent.
    No ``tolerance_mm`` UI-only field (CatPhan's pass/fail comes from
    pylinac's per-test tolerances, not a separate UI widget).
    """

    model_config = ConfigDict(extra="forbid")

    # Required
    hu_tolerance: float
    scaling_tolerance: float
    slice_thickness_tolerance: float
    # Optional (fall back to pylinac defaults if absent)
    thickness_slice_straddle: str | int = "auto"
    expected_hu_values: dict[str, float] | None = None
    x_adjustment: float = 0.0
    y_adjustment: float = 0.0
    angle_adjustment: float = 0.0
    roi_size_factor: float = 1.0
    scaling_factor: float = 1.0
    minimum_rois_seen: int = 3


class AppConfig(BaseModel):
    """Top-level application configuration (the parsed ``machines.yaml``)."""

    model_config = ConfigDict(extra="forbid")

    machines: dict[str, MachineConfig]
    output: OutputConfig
    analysis_defaults: dict[str, Any] = Field(
        default_factory=dict,
        description="Keyed by module name; validated conditionally against configured modules.",
    )
    assets: AssetsConfig

    @model_validator(mode="after")
    def _validate_module_defaults(self) -> AppConfig:
        """Cross-validate: each configured module needs its analysis_defaults section.

        - If any machine has ``winston_lutz``, ``analysis_defaults.winston_lutz`` must be present.
        - If any machine has ``catphan``, ``analysis_defaults.catphan`` must be present.
        """
        configured_modules: set[str] = set()
        for machine in self.machines.values():
            configured_modules.update(machine.dicom_roots.keys())

        if "winston_lutz" in configured_modules:
            wl_section = self.analysis_defaults.get("winston_lutz")
            if wl_section is None:
                raise ValueError(
                    "winston_lutz module configured for machine(s) but "
                    "analysis_defaults.winston_lutz is missing"
                )
            WLDefaults(**wl_section)  # validate the sub-section

        if "catphan" in configured_modules:
            cp_section = self.analysis_defaults.get("catphan")
            if cp_section is None:
                raise ValueError(
                    "catphan module configured for machine(s) but "
                    "analysis_defaults.catphan is missing"
                )
            CatPhanDefaults(**cp_section)  # validate the sub-section

        return self

    @property
    def wl_defaults(self) -> WLDefaults:
        """Convenience accessor for the centre-wide WL defaults."""
        return WLDefaults(**self.analysis_defaults["winston_lutz"])

    @property
    def cp_defaults(self) -> CatPhanDefaults:
        """Convenience accessor for the centre-wide CatPhan defaults."""
        return CatPhanDefaults(**self.analysis_defaults["catphan"])

    def has_catphan(self) -> bool:
        """Return True if any machine has ``catphan`` configured."""
        return any("catphan" in m.dicom_roots for m in self.machines.values())

    def has_winston_lutz(self) -> bool:
        """Return True if any machine has ``winston_lutz`` configured."""
        return any("winston_lutz" in m.dicom_roots for m in self.machines.values())

    def machine_keys_for_module(self, module_key: str) -> list[str]:
        """Return sorted machine keys that have ``module_key`` configured.

        Used by page dropdowns to filter to the relevant machines only.
        """
        return sorted(k for k, m in self.machines.items() if module_key in m.dicom_roots)

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
    if path.is_dir():
        raise ConfigError(
            f"Configuration path is a directory, not a file: {path}. "
            "This can happen if Docker Compose bind-mounted a non-existent file "
            "(Docker auto-creates it as a directory). Run: "
            "cp machines.yaml.example machines.yaml"
        )

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

    # Filesystem validation — DICOM roots (all configured modules per machine)
    for machine_key, machine in config.machines.items():
        for _module_key, root_str in machine.dicom_roots.items():
            root_path = Path(root_str)
            if not root_path.exists():
                raise ConfigError(f"Machine {machine_key}: DICOM root {root_path} does not exist")

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
    """Verify the WL xltx template defines all 25 required named cells.

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


def validate_catphan_template(template_path: Path) -> None:
    """Verify the CatPhan xltx template defines all 19 required named cells.

    Args:
        template_path: Path to ``templates/catphan_504.xltx``.

    Raises:
        ConfigError: If the template cannot be loaded or is missing names.
    """
    from openpyxl import load_workbook

    if not template_path.exists():
        raise ConfigError(f"CatPhan template not found: {template_path}")

    try:
        wb = load_workbook(str(template_path))
    except Exception as exc:
        raise ConfigError(f"Cannot load CatPhan template {template_path}: {exc}") from exc

    defined = set(wb.defined_names)
    missing = [n for n in REQUIRED_CATPHAN_TEMPLATE_NAMES if n not in defined]
    if missing:
        raise ConfigError(
            "CatPhan template missing required defined names: " + ", ".join(sorted(missing))
        )


def configure_logging() -> None:
    """Configure stdout logging (Docker convention — captured by ``docker logs``)."""
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


__all__ = [
    "CATPHAN_SUMMARY_NAMES",
    "REQUIRED_CATPHAN_TEMPLATE_NAMES",
    "REQUIRED_TEMPLATE_NAMES",
    "WL_METRIC_NAMES",
    "AppConfig",
    "AssetsConfig",
    "CatPhanDefaults",
    "ConfigError",
    "MachineConfig",
    "MachineScale",
    "OutputConfig",
    "WLDefaults",
    "configure_logging",
    "load_config",
    "validate_catphan_template",
    "validate_template",
]
