"""E2E: Field Profile page — scaffold tests (page not yet implemented).

The Field Profile module does not have a page yet (``pages/3_Field_Profile.py``
does not exist). These tests document the expected behavior and will activate
once the page is built.

When the Field Profile page is implemented:
1. Remove the ``pytest.skip`` calls
2. Add a ``field_profile`` fixture in conftest.py (navigate to the page)
3. Add Field Profile DICOM test data generation
4. Add Field Profile config section to the test machines.yaml
5. Add a Field Profile xltx template + builder script
6. Add ``core/fp_runner.py`` and ``core/fp_excel_writer.py``
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

_SKIP_REASON = (
    "Field Profile page not yet implemented. "
    "These tests will activate once pages/3_Field_Profile.py exists. "
    "See the module docstring for the implementation checklist."
)


@pytest.mark.skip(reason=_SKIP_REASON)
def test_fp_machine_dropdown_shows_machine(page) -> None:  # type: ignore[no-untyped-def]
    """The Field Profile page machine dropdown shows test machines with FP configured."""
    pytest.fail("Not implemented — Field Profile page does not exist")


@pytest.mark.skip(reason=_SKIP_REASON)
def test_fp_simple_mode_runfolder_preview(page) -> None:  # type: ignore[no-untyped-def]
    """The runfolder preview shows the DICOM count for the selected machine."""
    pytest.fail("Not implemented — Field Profile page does not exist")


@pytest.mark.skip(reason=_SKIP_REASON)
def test_fp_simple_mode_analysis_button(page) -> None:  # type: ignore[no-untyped-def]
    """The analysis button exists and is labeled for field profile analysis."""
    pytest.fail("Not implemented — Field Profile page does not exist")


@pytest.mark.skip(reason=_SKIP_REASON)
def test_fp_simple_mode_full_pipeline(page) -> None:  # type: ignore[no-untyped-def]
    """Full Simple mode: click button -> success card with profile metrics.

    Expected metrics on the success card:
    - Flatness (%)
    - Symmetry (%)
    - Field size (mm)
    - Penumbra L/R (mm)
    - CAX position
    """
    pytest.fail("Not implemented — Field Profile page does not exist")


@pytest.mark.skip(reason=_SKIP_REASON)
def test_fp_simple_mode_handoff_to_advanced(page) -> None:  # type: ignore[no-untyped-def]
    """The hand-off button switches to Field Profile Advanced mode."""
    pytest.fail("Not implemented — Field Profile page does not exist")


@pytest.mark.skip(reason=_SKIP_REASON)
def test_fp_advanced_tabs_render(page) -> None:  # type: ignore[no-untyped-def]
    """Advanced mode tabs render (Profile Plot, Flatness, Symmetry, Penumbra)."""
    pytest.fail("Not implemented — Field Profile page does not exist")


@pytest.mark.skip(reason=_SKIP_REASON)
def test_fp_advanced_rerun_button(page) -> None:  # type: ignore[no-untyped-def]
    """The Re-run analysis button works with changed parameters."""
    pytest.fail("Not implemented — Field Profile page does not exist")


@pytest.mark.skip(reason=_SKIP_REASON)
def test_fp_advanced_download_button(page) -> None:  # type: ignore[no-untyped-def]
    """The Download xlsx button produces a valid xlsx file."""
    pytest.fail("Not implemented — Field Profile page does not exist")
