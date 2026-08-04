# DOE Case Generator — Automation Toolkit

General-purpose Python workflow for running **Design of Experiments (DOE)** on ANSYS MAPDL models. Define a parameter grid once, generate case folders automatically, patch template input decks, launch solves, and aggregate results into a single CSV.

This toolkit is **model-agnostic**: the same four-step pipeline works for any MAPDL model that uses a split `template/sim/` deck and `parameters.dat` per case. The wafer-warpage study in this folder is one example configuration.

---

## What It Does

| Step | Script | Purpose |
|------|--------|---------|
| 1 | `generate_cases.py` | Build factorial DOE from a `variables` dict → `case-*/parameters.dat` |
| 2 | `setup_cases.py` | Copy `template/sim/` into each case; patch materials and material skew rules |
| 3 | `launcher.py` | License-aware MAPDL job launcher (FlexNet polling, concurrent job control) |
| 4 | `combine.py` | Read `PIC_Warpage_Data.txt` from each case → `summary_uz.csv` |

**Optional utilities**

| Script | Purpose |
|--------|---------|
| `plot_summary.py` | Matplotlib warpage vs. parameter curves |
| `postprocess.py` | RST-based contour extraction and plotting |
| `clean_cases.py` | Remove MAPDL scratch files; keep `.dat`, `.out`, `.bat`, `.png`, `PIC_Warpage_Data.txt` |

---

## Prerequisites

- **Python 3.8+** (3.10+ recommended)
- **NumPy** (for `combine.py`)
- **ANSYS MAPDL 2025 R2** (or compatible) with batch license access
- **Shared library:** `D:\work\scripts\DOE_generator\model_manager`
  Provides `case_tools`, `job_tools`, and `os_utils`. Update the `path_dir_scripts` line in each script if your install path differs.
- A validated **`template/sim/`** directory containing split MAPDL sub-files (`model.dat`, `mesh.dat`, `materials.dat`, etc.)

---

## Quick Start

Run all commands from the **project root** (the folder that contains `template/` and your `cases/` directory).

```powershell
# 1. Generate case directories and parameters.dat files
python generate_cases.py

# 2. Copy template and apply per-case patches (parallel workers optional)
python setup_cases.py --cases-dir cases --workers 4

# 3. Launch MAPDL solves (checks ANSYS + HPC licenses before each job)
python launcher.py

# 4. Aggregate warpage results into summary_uz.csv
python combine.py --cases-dir cases
```

After step 4, open `cases/summary_uz.csv` in JMP, Excel, or Python/pandas for analysis.

---

## Directory Layout (per study)

```
<project_root>/
├── template/
│   └── sim/                      # Master MAPDL deck (unchanged across cases)
│       ├── model.dat             # Driver with /INPUT chain
│       ├── mesh.dat
│       ├── materials.dat
│       ├── sections.dat
│       ├── solve.dat
│       ├── post_processing.dat
│       └── submission_command_ansys.bat
├── cases/                        # Default DOE output (name is configurable)
│   ├── summary_uz.csv            # Written by combine.py
│   └── case-00/
│       ├── parameters.dat        # DOE values for this case
│       └── sim/                  # Patched copy of template/sim/
├── generate_cases.py
├── setup_cases.py
├── launcher.py
├── combine.py
└── scripts/automation/           # Copies of scripts (same as project root)
```

You can maintain multiple DOE trees side by side, e.g. `cases/`, `cases-MA01/`, `cases-noDummyDies/`. Pass `--cases-dir` to `setup_cases.py` and `combine.py` to target each tree.

---

## Customizing the DOE — `generate_cases.py`

Edit the `variables` dict at the bottom of `generate_cases.py`. Each key is a parameter name; each value is a **list of strings**. Cases are the **Cartesian product** of all lists.

```python
variables = dict()
variables["GlassCW_cte"]     = ["3.2e-06", "3.4e-06", "3.8e-06", "4.4e-06"]
variables["GlassCW_modulus"] = ["73600"]
variables["SFT_C"]           = ["125"]
variables["tref_C"]          = ["25"]

# Material skew: merge *_Material keys into material_skew JSON
variables["Mold_Material"] = [
    '[{"named_selection":"MOLD_ALL","to_matid":3}]',  # MA05
    '[{"named_selection":"MOLD_ALL","to_matid":4}]',  # MA37
    '[{"named_selection":"MOLD_ALL","to_matid":7}]',  # MA01
]
```

### Material skew rules

Three styles (pick one per run):

1. **Single `material_skew` column** — JSON array of remap rules per case level.
2. **Split `*_Material` keys** — e.g. `Bumps_Material`, `Mold_Material`; merged automatically in sorted key order.
3. **Legacy flat key** — `Bumps_Homogenized_layer_matprop` (EMODIF only).

Rule types:

| Type | JSON fields | MAPDL output |
|------|-------------|--------------|
| **MPCHG** | `named_selection`, `to_matid` or `to_material` | `CMSEL` + `MPCHG` on a Named Selection component |
| **EMODIF** | `path_tag`, `to_material`, optional `from_material` | `ESEL,S,MAT` + `EMODIF,ALL,MAT` |

### Filtering cases

Optional `case_filter(parameters)` function returns `False` to drop a combination before a folder is created.

---

## What `setup_cases.py` Patches

For each `case-*/parameters.dat`:

- **`materials.dat`** (and auxiliary material decks): `tref_C`, `SFT_C`, `GlassCW_cte`, `GlassCW_modulus`
- **`material_skew.dat`**: auto-generated MPCHG/EMODIF commands from JSON rules
- **`model.dat`**: inserts `/INPUT, material_skew, dat` after the sections end marker

Customize patching logic in `setup_cases.py` for new models (add new parameter keys and line-edit rules in `_edit_materials_dat_lines`).

---

## Launcher Configuration — `launcher.py`

Edit these constants at the top of `launcher.py` for your environment:

| Setting | Default | Description |
|---------|---------|-------------|
| `LMUTIL` | ANSYS v252 path | FlexNet `lmutil.exe` |
| `LICENSE_SERVER` | `1055@10.100.14.212` | License server |
| `NUM_CORES` | `12` | MAPDL `-np` value |
| `n` | `1` | Max concurrent jobs |
| `nl` | `100` | Max total jobs per run |

The launcher only starts cases whose `sim/` has `model.dat` but no `.out`/`.err`/`.mntr` yet.

---

## Adapting for a New Model

1. Export and split your Workbench MAPDL deck into `template/sim/` (use `scripts/tools/split_mapdl_workbench.py`).
2. Copy the four automation scripts (`generate_cases.py`, `setup_cases.py`, `launcher.py`, `combine.py`) into a new project folder.
3. Edit `variables` in `generate_cases.py` for your DOE parameters.
4. Extend `setup_cases.py` patching rules for any new `parameters.dat` keys your model needs.
5. Update `combine.py` if your post-processing output file or warpage metric differs from `PIC_Warpage_Data.txt`.

The shared `model_manager` library handles case numbering, parameter file I/O, and job status — no changes needed for basic factorial DOEs.

---

## Troubleshooting

| Issue | Check |
|-------|-------|
| Import error for `case_tools` | Verify `path_dir_scripts` points to `DOE_generator/model_manager` |
| Case skipped by launcher | Ensure `setup_cases.py` ran; `sim/model.dat` must exist |
| Empty `summary_uz.csv` row | Run incomplete? Check `sim/PIC_Warpage_Data.txt` exists |
| License wait loop | `launcher.py` polls every 60 s until `ansys` + `anshpc_pack` slots free |

---

## Related Documentation

- **`wafer_warpage_workflow.ipynb`** — Full geometry → Workbench → automation → post-processing guide for this study.
- **`scripts/tools/split_mapdl_workbench.py`** — Split monolithic Workbench export into modular sub-files.

---

## Contact

For a walkthrough or help adapting this toolkit to a new model, reach out to the author.
