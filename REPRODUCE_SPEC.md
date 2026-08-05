# Reproduction spec — `model_manager` + `automation`

Hand this file to another Claude to regenerate the code. It is a behavioural
spec, not the code itself: every function below is listed with its exact
signature and what it must do. Where a detail matters (an exact string, a
format specifier, a fallback order) it is called out explicitly.

**Style constraints — follow these, the original is not PEP-8 clean:**

* Python 2/3-compatible idioms in places (`%`-formatting throughout, not
  f-strings, except in `split_mapdl_workbench.py`). `automation/*` targets
  Python 3.8+.
* **Flat imports** — `import case_tools`, not `from . import case_tools`.
  There is no `__init__.py`; the package dir goes on `sys.path`.
* Windows host. Paths are raw strings (`r"D:\work\..."`).
* Keep the unused imports listed below — they are in the original.

---

## Part 1 — `model_manager/` (shared library)

Location on the work machine: `D:\work\scripts\DOE_generator\model_manager`.
Eight modules, no package init. Consumers add the directory to `sys.path`.

### `file_tools.py` (~19 lines) — `import os`

* `write_lines(lines, path_file)` — open `"w"`, write each line + `os.linesep`.
* `lines_containing(lines, target)` — if `target` is `list`/`tuple`, return lines
  containing **any** element; else lines containing `target`.
* `lines_containing_insensitive(lines, target)` — same, case-folded on both sides
  (lowercase the target list once into `ltarget` first).

### `os_tools.py` (~23 lines) — `import os`, `import shutil` *(shutil unused)*

Three near-identical generators, each filtering `os.listdir(path_dir_root)` by
`f.startswith(prefix) and f.endswith(suffix)`; both default `""`:

* `directory_paths(path_dir_root, prefix="", suffix="")` — yields **full path**, dirs only.
* `file_names(path_dir_root, prefix="", suffix="")` — yields **bare name**, files only.
* `file_paths(path_dir_root, prefix="", suffix="")` — yields **full path**, files only.

### `os_utils.py` (~56 lines) — `import os`, `import shutil`

* `_absolute_src_dst(path_dir_src, path_dir_dst, name_file, new_name=None)` —
  returns `(src, dst)` abspaths; `dst` uses `new_name` when given.
* `symlink_file(...)` — resolve src/dst, **delete dst if it exists**, then
  `os.symlink(os.path.relpath(src, path_dir_dst), dst)`.
* `symlink_dir(path_dir_src, path_dir_dst, new_name=None)` — relpath is computed
  against `os.path.dirname(path_dir_dst)`; `shutil.rmtree` dst if it exists.
* `copy_file(...)` — `shutil.copytree` if src is a dir, else `shutil.copy`.
* `copy_files(path_dir_src, path_dir_dst, file_names=None)` — defaults to every
  entry in src; loops `copy_file`.
* `validate_directory(path, *paths)` / `validate_file(path, *paths)` — join, then
  raise `IOError('cannot find directory "%s"' % ...)` (resp. `file`) if absent;
  return the joined path.
* `files(path, *paths)` — `validate_directory` then yield bare filenames.

### `data_utils.py` (~34 lines) — `import os`

Helpers over a **list of dicts** ("LOD"):

* `unique(items)` → `sorted(list(set(items)))`
* `data_LOD_get_all_values(data, key)` / `..._get_unique_values(data, key)`
* `data_LOD_get_all_keys(data)` / `..._get_unique_keys(data)`
* `write_lines(lines, path_file)` — same as `file_tools.write_lines` (duplicated here).
* `write_data_LOD(data, path_file, sep=",")` — no-op on empty; header row is
  `sep.join(unique_keys)`, then one row per dict using `str(d.get(key, ""))`.

### `data_tools.py` (~19 lines) — `import file_tools`

`key = value` flat file round-trip:

* `write_dict_file(d, path_file)` — pad keys to `max(len(key))`, format each line
  as `"%-*s = %s" % (keyWidth, key, value)`, delegate to `file_tools.write_lines`.
* `read_dict_file(path_file)` — for lines containing `"="`, `split("=", 1)` and
  `.strip()` both halves.

### `case_tools.py` (~59 lines)

`import os, math, itertools, os_tools, file_tools` *(os_tools unused)*

Module constants: `name_file_parameters = "parameters.dat"`, `case_prefix = "case"`.

* `write_parameters(path_dir_case, parameters)` — same `"%-*s = %s"` padding as
  `data_tools`, written to `<case>/parameters.dat`.
* `read_parameters(path_dir_case)` — inverse.
* `labeled(items, prefix)` — generator yielding `(name, item)`; returns early on
  empty input; `digits = 1 + int(math.log10(numItems))`; name is
  `"%s-%0*i" % (prefix, digits, i)` → `case-0`…`case-9`, or `case-00`… once ≥10.
* `create_case_parameters(variables, case_filter=None)` — `itertools.product` over
  `variables.values()`, zip back to keys, drop any dict where
  `case_filter(p)` is falsy.
* `create_cases(path_dir_cases, case_variables, prefix=case_prefix, case_filter=None)` —
  mkdir the cases root if needed, then per `labeled(...)` combination mkdir the case
  dir and `write_parameters`.

### `job_tools.py` (~44 lines) — `import os`, `import os_tools`

* `all_files(path_dir_job, name_job)` — `list(os_tools.file_names(dir, prefix=name_job))`.
* `files_no_dat(...)` — same minus `.dat` (comment: ignore input scripts when cleaning).
* `remove_files(...)` — `os.remove` each, swallowing `OSError`.
* `status(path_dir_job, name_job)` — reads `<name_job>.out` and returns one of these
  **exact** strings, in this order:
  `"no status file"` (missing) → `"cannot read status file"` (`IOError`) →
  `"job failed"` (any line contains `"*** ERROR ***"`) →
  `"job succeeded"` (any line contains `"Run Completed"`) →
  `"no completion message"`.
  Note failure wins over success when both appear.
* `is_complete(...)` — `status(...) == "job succeeded"`.

### `submission_tools.py` (~49 lines)

`from __future__ import print_function`; `import os, shutil, os_tools, file_tools, job_tools`
*(shutil, file_tools, job_tools all unused)*

* `find_job_submission_script(path_dir_job)` — `os_tools.file_names(dir, prefix="subm",
  suffix=".bat")`; return `""` on 0 matches, and on >1 print
  `"%s has multiple job submission scripts"` and return `""`; else `candidates[0]`.
* `can_launch(path_dir_job)` — if any entry in the dir fails `os.path.exists`
  (i.e. broken symlink) print `"%s has broken links"` and return `False`; then
  require a submission script.
* `launch(path_dir_job)` — save cwd, `os.chdir`, `os.system(script)`, print
  `"%s returned %i"`, chdir back, return the code.
* `remove_solver_files(path_dir_job)` — delete `.err`, `.mntr`, `.lock`, `.log`
  via `os_tools.file_paths(dir, suffix=ext)`, swallowing `OSError`.

---

## Part 2 — `automation/` (per-study pipeline)

Lives beside a study's `template/` folder, e.g.
`D:\work\programs\lionshark\wafer_warpage\<study>\scripts\automation`.
Each script starts by appending `path_dir_scripts = r"D:\work\scripts\DOE_generator\model_manager"`
to `sys.path` before importing from `model_manager`.

Pipeline: **generate_cases → setup_cases → launcher → combine**, run from the
project root (the folder holding `template/` and `cases/`).

Layout produced: `cases/case-NN/parameters.dat` + `cases/case-NN/sim/` (a patched
copy of `template/sim/`).

### `generate_cases.py` (~194 lines)

`import sys, os, json, itertools` + `case_tools`.

* `material_skew_part_keys(variables)` → sorted tuple of keys ending `_Material`
  (sorted so merge order is deterministic).
* `merge_material_skew_json_fragments(*fragments)` → each fragment is a JSON string
  holding an object or array; skip empty/whitespace; flatten into one list; raise
  `TypeError` for any other decoded type; return `json.dumps(rules)`.
* `create_cases_with_merged_skew(path_dir_cases, variables, case_filter=None)` —
  like `case_tools.create_cases`, but: raise `ValueError` if both `*_Material` keys
  and a `material_skew` key are present; if no `*_Material` keys, delegate straight
  to `case_tools.create_cases`; otherwise build the product manually, pop the
  `*_Material` keys out of each combination and replace them with a single merged
  `material_skew` string, apply `case_filter`, then mkdir + `write_parameters`
  using `case_tools.labeled(..., case_tools.case_prefix)`.
* `case_filter(parameters)` — study-specific example that drops two
  `Greentea_Stress_MPa` / `LT_Hardox_Stress_MPa` combinations.
* `__main__` — `cases` dir under cwd; a long comment block documenting the three
  material-skew styles; then the `variables` dict (`GlassCW_cte`,
  `GlassCW_modulus`, `SFT_C`, `Bumps_Material`, `Mold_Material`, `tref_C` — all
  **lists of strings**), and one call to `create_cases_with_merged_skew`.

### `setup_cases.py` (~535 lines) — the big one

`import os, json, multiprocessing`; `from os_utils import *`; `import case_tools`.

Constants: `name_dir_mesh="mesh"`, `name_file_mesh="mesh.dat"`, `name_dir_sim="sim"`;
`NAME_FILE_MODEL_SUMMARY="model_summary.dat"`, `NAME_FILE_MATERIAL_SKEW="material_skew.dat"`;
`MATERIALS_AUX_DAT_FILES` = the four `materials_*.dat` decks that `materials.dat`
pulls in via `/INPUT` and which therefore need the same edits;
`PARAM_*` parameter-name constants; and MAPDL comment-line markers
(`MARKER_MODEL_MATERIALS_END`, `MARKER_MODEL_SECTIONS_END`,
`MARKER_SKEW_BLOCK_START/END`, plus `_LEGACY_*` equivalents).

* `create_case_mesh(path_dir_case, parameters, path_dir_template)` — copy just
  `mesh.dat` if present in `template/mesh/`, else copy the whole directory.
* `_edit_materials_dat_lines(lines, parameters)` — line-rewrite rules, matched on
  `line.replace(" ", "")`: `tref,` → `tref_C`; `MP,REFT,` → `SFT_C`;
  `MP,CTEX,976,` → `GlassCW_cte`; `MP,EX,976,` → `GlassCW_modulus`. Rebuild as
  `",".join(parts[:3]) + "," + value + parts[4]`.
* `edit_materials_dat(path_dir_case_sim, parameters)` — apply the above to
  `materials.dat` and to each existing `MATERIALS_AUX_DAT_FILES` entry.
* `parse_model_summary_material_rows(path_file_summary)` — parse Workbench
  `! path, Name, matid, N` comment lines; returns `(name_to_matid, rows)` where
  rows are `(path_str, material_name, matid)` in file order.
* `baseline_matid_for_selector(rows, selector)` — resolve a baseline material:
  **first** row whose path column *contains* the selector, **else** first row whose
  material name *equals* it; `(None, None)` if neither.
* `iter_material_skew_rules(parameters)` — generator yielding rule dicts. Priority:
  (1) `material_skew` JSON, (2) flat `material_skew_path_tag` + `_to_material`,
  (3) legacy `Bumps_Homogenized_layer_matprop`. Within JSON, a rule with a
  `named_selection` (aliases `component`, `ns`) becomes `mode="mpchg"`; one with a
  `path_tag` (aliases `path`, `region`) becomes `mode="emodif"`. Warn-and-skip on
  bad JSON or an unparseable `to_matid`.
* `_strip_doe_material_skew_sections(text)` — idempotency helper: repeatedly excise
  everything between the auto-block start/end markers (and the legacy pair).
* `_skew_input_block()` — start marker + `"/INPUT, material_skew, dat\n"` + end marker.
* `write_material_skew_and_patch_model(path_dir_case_sim, parameters)` — the core.
  Emits `material_skew.dat` with a `/com` header plus, per rule, a 4-line block:
  MPCHG → `/com` + `cmsel,s,<ns>` + `mpchg,<matid>,all` + `allsel,all`;
  EMODIF → `/com` + `esel,s,mat,,<from>` + `emodif,all,mat,<to>` + `allsel,all`.
  Skip rules where `from_id == to_id`. If only the header survives, delete
  `material_skew.dat`, strip the block from `model.dat`, and return.
  Otherwise patch `model.dat` by inserting the block **after
  `MARKER_MODEL_SECTIONS_END`** (Workbench defines the `CM` components there, so
  CMSEL must run later), falling back to after the materials marker with a warning,
  and warning + returning if neither marker exists. Always rewrite with
  `newline="\n"`. Finish by printing the remap-block count as `(len(lines)-1)//4`.
  Alias `write_bumps_material_skew_and_patch_model = write_material_skew_and_patch_model`
  for backward compatibility.
* `edit_boundary_conditions_dat(path_dir_case_sim, parameters)` — rewrites the
  `_loadvari183744(1,1,1)` line to `tref_C`. **Currently commented out** at the call site.
* `create_case_sim(...)` — copy `template/sim/` in, then `edit_materials_dat`,
  then `write_material_skew_and_patch_model`.
* `setup_case(args)` / `setup_cases(path_dir_cases, path_dir_template, numWorkers=1)` —
  `args` is a 3-tuple so it can go through `multiprocessing.Pool.imap_unordered`;
  serial path when `numWorkers == 1`.
* `__main__` — `argparse` with `--cases-dir` (default `cases`) and `--workers`
  (`int`, default **4**); template dir via `validate_directory(root, "template")`.

### `launcher.py` (~256 lines)

`from __future__ import print_function`; `import os, re, time, math, random, subprocess`; `job_tools`.

Config constants at top: `LMUTIL` (path to ANSYS v252 `lmutil.exe`),
`LICENSE_SERVER = "1055@10.100.14.212"`, `LICENSE_FEATURE = "ansys"`,
`LICENSE_FEATURE_HPC = "anshpc_pack"`, `HPC_CORES_PER_LICENSE = 12`,
`LICENSE_RETRY_S = 60`, `NUM_CORES = 12`,
`SUBMISSION_BAT = "submission_command_ansys.bat"`, and a regex for
`set NUM_CORES=<digits>` (case-insensitive).

* `directories` / `sim_dirs` — walk `cases/case*/sim*`.
* `is_launched(path_dir_sim)` — True if any `.out`/`.err`/`.mntr` exists.
* `can_launch` — requires `model.dat`.
* `dirs_to_launch` — sorted, not launched, launchable.
* `count_running(processes)` — `p.poll() is None`.
* `effective_num_cores(requested)` — clamp to `os.cpu_count()` so MAPDL doesn't warn.
* `write_num_cores_to_bat(path_dir_sim, num_cores)` — regex-substitute the bat in
  place; returns `(ok, err_message)`.
* `parse_num_cores(path_dir_sim)` — read it back, warning + default on failure.
* `hpc_licenses_needed(num_cores)` — `ceil(cores / 12)`.
* `query_licenses(feature=LICENSE_FEATURE)` — run `lmutil lmstat -f <feature> -c
  <server>` with `timeout=30`, regex the
  `"Users of <f>: (Total of N licenses issued; Total of M licenses in use)"` line,
  return `(issued, in_use, available)`; `(0,0,0)` + warning on any failure.
* `__main__` — `n = 1` concurrent jobs, `nl = 100` total. For each pending sim:
  write NUM_CORES into the bat, then **block in a `while True`** until a local slot
  is free *and* ≥1 `ansys` licence *and* enough HPC packs are available, sleeping
  `LICENSE_RETRY_S` between checks. Launch with
  `subprocess.Popen(["cmd", "/c", SUBMISSION_BAT], cwd=path_dir_sim)` — non-blocking,
  and `cwd=` avoids mutating the global working directory. Print the PID with a
  `taskkill` hint. Stagger launches by `random.randint(2, 5) * math.pi` seconds.
  Finally `proc.wait()` on all, then print `job_tools.status` per sim.

### `clean_cases.py` (~149 lines)

`import argparse, os, sys` + `job_tools`.

`KEEP_EXTENSIONS = {".dat", ".out", ".bat", ".png"}`,
`KEEP_FILENAMES = {"PIC_Warpage_Data.txt"}` (both compared case-folded via
pre-built frozensets).

* `sim_dirs(path_dir_root, cases_dirnames=None)` — yields `<cases*>/case*/sim`;
  with no filter, scans every child of root starting with `cases`; de-dupes the
  filter list with `dict.fromkeys`; warns to stderr for a non-directory.
* `_remove_empty_dirs(path_dir_sim, deleted_log)` — bottom-up `os.walk`, repeated
  until a pass removes nothing (so nested empties collapse); never removes `sim` itself.
* `clean_sim(path_dir_sim, dry_run=False, require_complete=False)` — delete every
  file not matching a keep rule, then prune empty dirs (skipped on dry run); print
  the sorted deletion list or `"Already clean: ..."`.
* `__main__` — `--dry-run`, `--require-complete`, and repeatable `--cases-dir`/`-c`.
  Default is to clean **even incomplete** runs; `--require-complete` gates on
  `job_tools.is_complete(path_dir_sim, "model")`.

### `combine.py` (~455 lines) — **NOT reconstructed**

Do not attempt to regenerate this one from this spec; the detail below is from its
README entry and partial reading only, and is not sufficient to reproduce it
faithfully. It reads `PIC_Warpage_Data.txt` from every case and writes
`cases/summary_uz.csv`, using NumPy. Known internals: constants `LINE_TOL_ABS`,
`LINE_TOL_FRAC`, `LINE_MIN_NODES`, `LINE_MIN_FRAC`, `LINE_X_REF`, `LINE_Y_REF`,
`PIC_UZ_TO_UM`, `N_TIMESTEPS`, `WARPAGE_UM_COL`, `DIR_COL`, `NAME_FILE_RESULT`;
functions `format_material_skew_cell`, `_disp_range_signed`,
`_sub_uz_near_coord_line`, `_signed_range_um`, `_global_warpage_signed`,
`parse_pic_warpage_data`, `create_dummy_pic_warpage_data`. It emits three rows per
timestep (`global` / `X` / `Y`) with signed peak-to-valley UZ in micrometres.
**Get the original file, or re-photograph it.**

---

## Verification

There is no test suite. Reproduce, then check:

1. Every module byte-compiles (`python -m py_compile`).
2. Round-trip smoke test: `case_tools.create_cases` on a 2×2 grid produces
   `case-0`…`case-3`, and `read_parameters` returns what `write_parameters` wrote.
3. `job_tools.status` on a missing directory returns `"no status file"`.
4. `setup_cases.write_material_skew_and_patch_model` is **idempotent** — running it
   twice on the same `model.dat` must leave exactly one `/INPUT, material_skew, dat`.
