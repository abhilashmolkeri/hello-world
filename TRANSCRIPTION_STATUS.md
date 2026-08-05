# Photo transcription status

Scripts reconstructed from photographs of source listings held in Google Drive.
Line numbers visible in the photos were used to verify each file is complete and
continuous (consecutive photos overlap by roughly half a screen).

## Batch 1 — Drive folder `1uFlOIOYCX_pFs8lN9vSihCStHAQsCF5M` ("Model Manager")

Source on the original machine: `D:\work\scripts\DOE_generator\model_manager`

| File | Lines | Status |
|---|---|---|
| `model_manager/case_tools.py` | 59 | complete |
| `model_manager/data_tools.py` | 19 | complete |
| `model_manager/data_utils.py` | 34 | complete |
| `model_manager/file_tools.py` | 19 | complete |
| `model_manager/job_tools.py` | 44 | complete |
| `model_manager/os_tools.py` | 23 | complete |
| `model_manager/os_utils.py` | 56 | complete |
| `model_manager/submission_tools.py` | 49 | complete |

Two photos in that folder are mislabelled: the second `data_tools_1` is actually
`data_utils.py`, and `os_tools_2` is the continuation of `os_utils.py` (not of
`os_tools.py`, which is complete in a single photo).

## Batch 2 — Drive folder `1SyIhheEXHv8oXZqDYDYJiI-kQWIwB5Iz` (parent folder)

51 photos covering 9 files. Photo coverage was mapped by reading the line-number
gutter of every photo before transcribing.

### Done

| File | Lines | Photos | Source directory |
|---|---|---|---|
| `ansys_helper_functions/create_geo_groups_v1.py` | 92 | `create_geo_groups_1..2` | `D:\work\scripts\ansys_helper_functions` |
| `ansys_helper_functions/create_named_selections_v4.py` | 205 | `create_ns_1..5` | `D:\work\scripts\ansys_helper_functions` |
| `automation/generate_cases.py` | 194 | `generate_cases_1..4` | `...\scripts\automation` |
| `automation/clean_cases.py` | 149 | `clean_cases_0..2` | `...\scripts\automation` |
| `automation/launcher.py` | 256 | `launcher_1..6` | `...\scripts\automation` |
| `automation/README.md` | 191 | `readme`, `readme_2..4` | `...\scripts\automation` |
| `automation/setup_cases.py` | 535 | `setup_cases_1..11` | `...\scripts\automation` |
| `tools/split_mapdl_workbench.py` | 348 | `split_workbench_input_1..7` | `...\scripts\tools` |

The `clean_cases` gap is closed: the user supplied the missing photo of lines
1-50 (`clean_cases_0`), so that file is now complete.

### Not transcribed

| File | Lines | Photos | Reason |
|---|---|---|---|
| `combine.py` | 455 | `combine_1..7`, `combine_9..11` | Skipped at the user's request. Photo coverage is complete (photo 7 ends at line 336, photo 9 starts at 329, so the absent `combine_8` leaves no gap) - it can be transcribed later without new photos. |

## Method

The photos are HEIC and Google Drive's egress host is blocked from this
environment, so they were pulled through the Drive MCP tool, decoded from base64
locally, converted with `pillow-heif`, and split into overlapping top/bottom
halves to keep the code legible.
