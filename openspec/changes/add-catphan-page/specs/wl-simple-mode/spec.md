## MODIFIED Requirements

### Requirement: Machine selection via dropdown

The WL Simple mode UI SHALL present a dropdown of only those machines where `dicom_roots.winston_lutz` is present and exists on the filesystem, displaying each machine's `display_name` and using the machine key (e.g. `LA2`) as the internal identifier. Machines without WL configured SHALL NOT appear in this dropdown (but remain available on the CatPhan page if `catphan` is configured).

#### Scenario: Single machine configured with WL

- **WHEN** `machines.yaml` defines one machine (`LA2`) with `dicom_roots.winston_lutz`
- **THEN** the Simple mode dropdown contains exactly one entry: `LA2 (TrueBeam)` (or whatever `display_name` is configured)

#### Scenario: Multiple machines configured with WL

- **WHEN** `machines.yaml` defines `LA2`, `LA3`, `LA4` and all three have `dicom_roots.winston_lutz`
- **THEN** the dropdown lists all three entries, ordered by machine key alphabetically

#### Scenario: Mixed WL/CatPhan configuration

- **WHEN** `LA2` has `winston_lutz` configured, `LA3` has only `catphan` (no WL), `LA4` has both
- **THEN** the WL dropdown lists `LA2` and `LA4` only; `LA3` is absent from the WL dropdown (it appears on the CatPhan page instead)

#### Scenario: No machines with WL configured

- **WHEN** no machine in `machines.yaml` has `winston_lutz` configured
- **THEN** the dropdown is empty and a banner reads "No machines have Winston-Lutz configured. Edit machines.yaml and reload."
