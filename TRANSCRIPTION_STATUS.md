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
| `automation/generate_cases.py` | 194 | `generate_cases_1..4` | `...\Skews_PMG_600um_GCW_Thk_500um\scripts\automation` |

### Not yet transcribed

| File | Lines | Photos | Coverage |
|---|---|---|---|
| `launcher.py` | 256 | `launcher_1..6` | continuous 1-256 |
| `README.md` | 191 | `readme`, `readme_2..4` | continuous 1-191 |
| `split_workbench_input.py` | 348 | `split_workbench_input_1..7` | continuous 1-348 |
| `combine.py` | 455 | `combine_1..7`, `combine_9..11` | continuous 1-455 |
| `setup_cases.py` | 535 | `setup_cases_1..11` | continuous 1-535 |
| `clean_cases.py` | 149 | `clean_cases_1..2` | **lines 51-149 only** |

Notes on the remaining set:

* `combine_8` is missing from the Drive folder, but it leaves no gap — photo 7
  ends at line 336 and photo 9 starts at line 329, so the two overlap.
* `clean_cases` is the only real gap: both photos start partway down the file
  (photo 1 begins at line 51). **Lines 1-50 were never photographed** — that
  covers the imports, module constants, and the head of `sim_dirs()`, which a
  sticky header in the photo shows is defined at line 32. A photo of the top of
  that file is needed before it can be reconstructed.

## Method

The photos are HEIC and Google Drive's egress host is blocked from this
environment, so they were pulled through the Drive MCP tool, decoded from base64
locally, converted with `pillow-heif`, and split into overlapping top/bottom
halves to keep the code legible.
