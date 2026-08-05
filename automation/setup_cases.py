import os
import json
import multiprocessing

# Make sure this points to your model manager to import os_utils
import sys
path_dir_scripts = r"D:\work\scripts\DOE_generator\model_manager"
if path_dir_scripts not in sys.path:
    sys.path.append(path_dir_scripts)
from os_utils import *
import case_tools

name_dir_mesh = "mesh"
name_file_mesh = "mesh.dat"
name_dir_sim = "sim"

NAME_FILE_MODEL_SUMMARY = "model_summary.dat"
NAME_FILE_MATERIAL_SKEW = "material_skew.dat"
# Loaded from materials.dat via /INPUT - must receive the same DOE patches as materials.dat
NAME_FILE_MAT999_SKEW_VARIANTS = "materials_mat999_skew_variants.dat"
NAME_FILE_MOLD_DOE_VARIANTS = "materials_mold_doe_variants.dat"
NAME_FILE_MOLD_ELASTIC_VARIANTS = "materials_mold_elastic_variants.dat"
NAME_FILE_MOLD_MA01_EX_TEMPERATURE = "materials_mold_ma01_ex_temperature.dat"
# All sim/*.dat here get tref / SFT_C / GlassCW_* line edits (same rules as materials.dat).
MATERIALS_AUX_DAT_FILES = (
    NAME_FILE_MAT999_SKEW_VARIANTS,
    NAME_FILE_MOLD_DOE_VARIANTS,
    NAME_FILE_MOLD_ELASTIC_VARIANTS,
    NAME_FILE_MOLD_MA01_EX_TEMPERATURE,
)
# Legacy filename / marker (removed when rewriting model.dat skew block)
_NAME_FILE_BUMPS_SKEW_LEGACY = "bumps_mat_skew.dat"

PARAM_BUMPS_LAYER_MAT = "Bumps_Homogenized_layer_matprop"
# JSON (array of objects or one object): [{"path_tag":"Bumps_Homogenized","to_material":"DAF"}, ...]
PARAM_MATERIAL_SKEW_JSON = "material_skew"
# Flat single-rule alternative to JSON (optional)
PARAM_MATERIAL_SKEW_PATH_TAG = "material_skew_path_tag"
PARAM_MATERIAL_SKEW_TO = "material_skew_to_material"
PARAM_MATERIAL_SKEW_FROM = "material_skew_from_material"

MARKER_MODEL_MATERIALS_END = "! **************** end materials ***********************\n"
# Workbench exports define element components (CM) in sections.dat - MPCHG/CMSEL must run after this.
MARKER_MODEL_SECTIONS_END = "! **************** end sections ***********************\n"
MARKER_SKEW_BLOCK_START = "! ************** DOE material skew (auto) start **************\n"
MARKER_SKEW_BLOCK_END = "! ************** DOE material skew (auto) end **************\n"
# Legacy insert from earlier bumps-only helper
_LEGACY_SKEW_START = "! **************** start bumps material skew (DOE) **************\n"
_LEGACY_SKEW_END = "! ***************** end bumps material skew **************\n"

def create_case_mesh(path_dir_case, parameters, path_dir_template):
    path_dir_template_mesh = os.path.join(path_dir_template, name_dir_mesh)
    if not os.path.isdir(path_dir_template_mesh):
        return
    path_dir_case_mesh = os.path.join(path_dir_case, name_dir_mesh)
    if name_file_mesh in list(files(path_dir_template_mesh)):
        copy_file(path_dir_src=path_dir_template_mesh, path_dir_dst=path_dir_case_mesh, name_file=name_file_mesh)
    else:
        if not os.path.isdir(path_dir_case_mesh):
            os.mkdir(path_dir_case_mesh)
        copy_files(path_dir_src=path_dir_template_mesh, path_dir_dst=path_dir_case_mesh)

def _edit_materials_dat_lines(lines, parameters):
    """Apply DOE material line edits (same rules as ``edit_materials_dat``).

    - tref_C -> global ``tref`` at top of file (WB reference temperature).
    - SFT_C -> ``MP,REFT`` material reference temperature for every matching line.
    - GlassCW_cte -> ``MP,CTEX`` for material 976.
    """
    edited = []
    for line in lines:
        compact = line.replace(" ", "")
        if compact.lower().startswith("tref,"):
            if parameters.get("tref_C") is not None:
                line = "tref," + parameters["tref_C"] + ".\n"
        elif compact.upper().startswith("MP,REFT,"):
            parts = line.split(',')
            if len(parts) >= 4 and parameters.get("SFT_C") is not None:
                line = ",".join(parts[:3]) + "," + parameters["SFT_C"] + "\n"
        elif compact.upper().startswith("MP,CTEX,976,"):
            parts = line.split(',')
            if len(parts) >= 4:
                line = ",".join(parts[:3]) + "," + parameters["GlassCW_cte"] + parts[4]
        elif compact.upper().startswith("MP,EX,976,"):
            parts = line.split(',')
            if len(parts) >= 4 and parameters.get("GlassCW_modulus") is not None:
                line = ",".join(parts[:3]) + "," + parameters["GlassCW_modulus"] + parts[4]
        edited.append(line)
    return edited


def edit_materials_dat(path_dir_case_sim, parameters):
    """Patch case ``materials.dat`` and any /INPUT'd material decks with the same line rules.

    Auxiliary files (``MATERIALS_AUX_DAT_FILES``) are edited so ``MP,REFT`` tracks ``SFT_C``
    and other DOE substitutions stay consistent when MAPDL /INPUT's them from ``materials.dat``.

    - tref_C -> global ``tref`` at top of **materials.dat** only (first file).
    - SFT_C -> ``MP,REFT`` on every matching line in each patched file.
    - GlassCW_cte / GlassCW_modulus -> mat 976 lines where present (typically main deck only).
    """
    path_file_materials = os.path.join(path_dir_case_sim, "materials.dat")
    if not os.path.isfile(path_file_materials):
        return
    with open(path_file_materials) as f:
        lines = f.readlines()
    edited = _edit_materials_dat_lines(lines, parameters)
    with open(path_file_materials, "w") as f:
        f.writelines(edited)

    for name_aux in MATERIALS_AUX_DAT_FILES:
        path_aux = os.path.join(path_dir_case_sim, name_aux)
        if not os.path.isfile(path_aux):
            continue
        with open(path_aux) as f:
            lines_aux = f.readlines()
        edited_aux = _edit_materials_dat_lines(lines_aux, parameters)
        with open(path_aux, "w") as f:
            f.writelines(edited_aux)


def parse_model_summary_material_rows(path_file_summary):
    """Parse Workbench model_summary ``!..., Name, matid, N`` lines.

    Returns (name_to_matid, rows):
        name_to_matid: assignment material name (2nd column) -> matid
        rows: list of (path_str, material_name, matid) in file order (for path_tag lookup).
    """
    name_to_matid = {}
    rows = []
    if not os.path.isfile(path_file_summary):
        return name_to_matid, rows
    with open(path_file_summary, encoding="utf-8", errors="surrogateescape") as f:
        for raw in f:
            line = raw.strip()
            if not line.startswith("!") or "matid" not in line.lower():
                continue
            body = line[1:].strip()
            parts = [p.strip() for p in body.split(",")]
            if len(parts) < 4:
                continue
            try:
                j = next(k for k, p in enumerate(parts) if p.lower() == "matid")
            except StopIteration:
                continue
            if j + 1 >= len(parts):
                continue
            try:
                mid = int(parts[j + 1])
            except ValueError:
                continue
            mat_name = parts[1]
            path_str = parts[0]
            name_to_matid[mat_name] = mid
            rows.append((path_str, mat_name, mid))
    return name_to_matid, rows


def baseline_matid_for_selector(rows, selector):
    """Pick baseline (matid, material_name) for a skew rule when ``from_material`` is omitted.

    ``selector`` is the JSON ``path_tag`` / flat ``material_skew_path_tag`` value:

    1. First summary row whose **path** (column 0) contains ``selector`` as a substring
       (e.g. ``PIC_Grind``, ``Streets_Grind``, ``Bumps_Homogenized``).
    2. Else first row whose **assignment material name** (column 1) equals ``selector``
       exactly (e.g. ``Si_TSV_homogenized``, ``Bumps_UF_Homogenized Simple``).

    If you need a different row when several share the same name, set ``from_material``
    explicitly in the rule.
    """
    if not selector:
        return None, None
    for path_str, mat_name, mid in rows:
        if selector in path_str:
            return mid, mat_name
    for path_str, mat_name, mid in rows:
        if mat_name.strip() == selector.strip():
            return mid, mat_name
    return None, None


def iter_material_skew_rules(parameters):
    """Yield rule dicts for ``write_material_skew_and_patch_model``.

    **EMODIF rules** (mat-based selection, same as before):

    - ``path_tag`` (aliases ``path``, ``region``): path substring or exact assignment
      material name for baseline when ``from_material`` is omitted.
    - ``to_material`` (alias ``to``): target assignment name -> matid from model_summary.
    - Optional ``from_material`` (alias ``from``).

    **MPCHG rules** (named selection / component - avoids remapping every element with the
    same matid); MAPDL ``MPCHG`` changes material on selected elements; use ``CMSEL`` first.
    See: https://www.mm.bme.hu/~gyebro/files/ans_help_v182/ans_cmd/Hlp_C_MPCHG.html

    - ``named_selection`` (aliases ``component``, ``ns``): MAPDL **component** name from
      the exported model (Workbench Named Selections usually appear here; confirm in
      ``mesh.dat`` / component lists).
    - ``to_matid`` (integer) **or** ``to_material`` / ``to`` to resolve matid from model_summary.

    Aliases apply to JSON objects only. Flat keys remain EMODIF-only.

    Priority:
    1. ``material_skew`` - JSON array of objects (or one object).
    2. Flat ``material_skew_path_tag`` + ``material_skew_to_material``.
    3. Legacy ``Bumps_Homogenized_layer_matprop`` (selector ``Bumps_Homogenized``).
    """
    raw = (parameters.get(PARAM_MATERIAL_SKEW_JSON) or "").strip()
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as ex:
            print("  WARNING: %s JSON invalid: %s" % (PARAM_MATERIAL_SKEW_JSON, ex))
            return
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            print("  WARNING: %s must be a JSON array or object" % PARAM_MATERIAL_SKEW_JSON)
            return
        for item in data:
            if not isinstance(item, dict):
                continue
            ns = (
                item.get("named_selection")
                or item.get("component")
                or item.get("ns")
                or ""
            ).strip()
            to_mat = (item.get("to_material") or item.get("to") or "").strip()
            to_mid_raw = item.get("to_matid")
            to_matid = None
            if to_mid_raw is not None and str(to_mid_raw).strip() != "":
                try:
                    to_matid = int(to_mid_raw)
                except (TypeError, ValueError):
                    print(
                        "  WARNING: invalid to_matid %r in %s; skipped"
                        % (to_mid_raw, PARAM_MATERIAL_SKEW_JSON)
                    )
                    continue
            if ns and (to_matid is not None or to_mat):
                yield {
                    "mode": "mpchg",
                    "named_selection": ns,
                    "to_material": to_mat or None,
                    "to_matid": to_matid,
                }
                continue

            path_tag = (
                item.get("path_tag")
                or item.get("path")
                or item.get("region")
                or ""
            ).strip()
            from_mat = (item.get("from_material") or item.get("from") or "").strip() or None
            if path_tag and to_mat:
                yield {
                    "mode": "emodif",
                    "path_tag": path_tag,
                    "to_material": to_mat,
                    "from_material": from_mat,
                }
        return

    path_tag = (parameters.get(PARAM_MATERIAL_SKEW_PATH_TAG) or "").strip()
    to_mat = (parameters.get(PARAM_MATERIAL_SKEW_TO) or "").strip()
    from_mat = (parameters.get(PARAM_MATERIAL_SKEW_FROM) or "").strip() or None
    if path_tag and to_mat:
        yield {
            "mode": "emodif",
            "path_tag": path_tag,
            "to_material": to_mat,
            "from_material": from_mat,
        }
        return

    legacy = (parameters.get(PARAM_BUMPS_LAYER_MAT) or "").strip()
    if legacy:
        yield {
            "mode": "emodif",
            "path_tag": "Bumps_Homogenized",
            "to_material": legacy,
            "from_material": None,
        }


def _strip_doe_material_skew_sections(text):
    """Remove auto-inserted skew /INPUT blocks from ``model.dat`` (idempotent rewrite)."""
    while MARKER_SKEW_BLOCK_START in text and MARKER_SKEW_BLOCK_END in text:
        i = text.index(MARKER_SKEW_BLOCK_START)
        j = text.index(MARKER_SKEW_BLOCK_END, i) + len(MARKER_SKEW_BLOCK_END)
        text = text[:i] + text[j:]
    while _LEGACY_SKEW_START in text and _LEGACY_SKEW_END in text:
        i = text.index(_LEGACY_SKEW_START)
        j = text.index(_LEGACY_SKEW_END, i) + len(_LEGACY_SKEW_END)
        text = text[:i] + text[j:]
    return text


def _skew_input_block():
    return (
        MARKER_SKEW_BLOCK_START
        + "/INPUT, material_skew, dat\n"
        + MARKER_SKEW_BLOCK_END
    )


def write_material_skew_and_patch_model(path_dir_case_sim, parameters):
    """Build ``material_skew.dat`` and patch ``model.dat``.

    **EMODIF** path: ``ESEL,S,MAT`` then ``EMODIF,ALL,MAT`` (baseline from ``path_tag`` /
    ``from_material``; target ``to_material`` resolved via ``model_summary.dat``).

    **MPCHG** path ([MPCHG](https://www.mm.bme.hu/~gyebro/files/ans_help_v182/ans_cmd/Hlp_C_MPCHG.html)):
    ``CMSEL`` on a **component** name (Workbench Named Selection in the export), then
    ``MPCHG,<matid>,ALL``. Use ``to_matid`` or ``to_material``. Only elements in that
    component are changed, unlike global mat selection.

    ``model.dat`` is patched so ``/INPUT, material_skew, dat`` runs **after** ``sections.dat``
    (where Workbench writes ``CM`` for named selections). ``materials.dat`` has already run,
    so target ``MP`` data exists. Falls back to after ``materials.dat`` only if the sections
    end marker is missing.
    """
    path_summary = os.path.join(path_dir_case_sim, NAME_FILE_MODEL_SUMMARY)
    path_skew = os.path.join(path_dir_case_sim, NAME_FILE_MATERIAL_SKEW)
    path_model = os.path.join(path_dir_case_sim, "model.dat")
    legacy_skew = os.path.join(path_dir_case_sim, _NAME_FILE_BUMPS_SKEW_LEGACY)

    name_to_id, rows = parse_model_summary_material_rows(path_summary)
    rules = list(iter_material_skew_rules(parameters))

    if os.path.isfile(legacy_skew):
        try:
            os.remove(legacy_skew)
        except EnvironmentError:
            pass

    lines_skew = ["/com, --- DOE material skew (auto-generated) ---\n"]
    for rule in rules:
        mode = rule.get("mode") or "emodif"

        if mode == "mpchg":
            ns = rule["named_selection"]
            to_matid = rule.get("to_matid")
            to_name = rule.get("to_material") or ""
            if to_matid is not None:
                to_id = to_matid
                to_label = "%d" % to_id
            else:
                to_id = name_to_id.get(to_name)
                if to_id is None:
                    print(
                        "  WARNING: to_material %r not in model_summary (named_selection=%r); skipped"
                        % (to_name, ns)
                    )
                    continue
                to_label = to_name
            lines_skew.extend(
                [
                    "/com, --- NS %r -> mat %d (%s) via MPCHG ---\n" % (ns, to_id, to_label),
                    "cmsel,s,%s\n" % ns,
                    "mpchg,%d,all\n" % to_id,
                    "allsel,all\n",
                ]
            )
            continue

        # --- EMODIF (default) ---
        tag = rule["path_tag"]
        to_name = rule["to_material"]
        from_mat = rule.get("from_material")

        to_id = name_to_id.get(to_name)
        if to_id is None:
            print(
                "  WARNING: to_material %r not in model_summary matid table (path_tag=%r); skipped"
                % (to_name, tag)
            )
            continue

        if from_mat:
            from_id = name_to_id.get(from_mat)
            from_label = from_mat
            if from_id is None:
                print(
                    "  WARNING: from_material %r not in model_summary (path_tag=%r); skipped"
                    % (from_mat, tag)
                )
                continue
        else:
            from_id, from_label = baseline_matid_for_selector(rows, tag)
            if from_id is None:
                print(
                    "  WARNING: no baseline matid for selector %r (path substring or exact "
                    "material name) in %s; skipped"
                    % (tag, path_summary)
                )
                continue

        if from_id == to_id:
            continue

        lines_skew.extend(
            [
                "/com, --- %s: mat %d (%s) -> mat %d (%s) ---\n"
                % (tag, from_id, from_label or "?", to_id, to_name),
                "esel,s,mat,,%d\n" % from_id,
                "emodif,all,mat,%d\n" % to_id,
                "allsel,all\n",
            ]
        )

    # Only the header line: no remaps
    if len(lines_skew) <= 1:
        lines_skew = []

    if not lines_skew:
        if os.path.isfile(path_skew):
            try:
                os.remove(path_skew)
            except EnvironmentError:
                pass
        if os.path.isfile(path_model):
            with open(path_model, encoding="utf-8", errors="surrogateescape") as f:
                text = _strip_doe_material_skew_sections(f.read())
            with open(path_model, "w", encoding="utf-8", errors="surrogateescape", newline="\n") as f:
                f.write(text)
        return

    with open(path_skew, "w", encoding="utf-8", errors="surrogateescape", newline="\n") as f:
        f.writelines(lines_skew)

    if not os.path.isfile(path_model):
        return
    with open(path_model, encoding="utf-8", errors="surrogateescape") as f:
        text = _strip_doe_material_skew_sections(f.read())
    text = text.replace("\r\n", "\n")

    insert = _skew_input_block()
    if "/INPUT, material_skew, dat" not in text:
        if MARKER_MODEL_SECTIONS_END in text:
            text = text.replace(MARKER_MODEL_SECTIONS_END, MARKER_MODEL_SECTIONS_END + insert, 1)
        elif MARKER_MODEL_MATERIALS_END in text:
            print(
                "  WARNING: model.dat missing sections end marker; inserting %s after materials"
                % NAME_FILE_MATERIAL_SKEW
            )
            text = text.replace(MARKER_MODEL_MATERIALS_END, MARKER_MODEL_MATERIALS_END + insert, 1)
        else:
            print(
                "  WARNING: model.dat missing sections and materials end markers; cannot insert %s"
                % NAME_FILE_MATERIAL_SKEW
            )
            return

    with open(path_model, "w", encoding="utf-8", errors="surrogateescape", newline="\n") as f:
        f.write(text)

    print("  %s: %d material remap block(s)" % (path_skew, (len(lines_skew) - 1) // 4))


# Backward-compatible name
write_bumps_material_skew_and_patch_model = write_material_skew_and_patch_model


def edit_boundary_conditions_dat(path_dir_case_sim, parameters):
    path_file_bc = os.path.join(path_dir_case_sim, "boundary_conditions.dat")
    if not os.path.isfile(path_file_bc):
        return
    with open(path_file_bc) as f:
        lines = f.readlines()
    edited = []
    for line in lines:
        if line.replace(" ", "").lower().startswith("_loadvari183744(1,1,1)"):
            lhs, _ = line.split("=", 1)
            line = lhs + "= " + parameters["tref_C"] + ".\n"
        edited.append(line)
    with open(path_file_bc, "w") as f:
        f.writelines(edited)

def create_case_sim(path_dir_case, parameters, path_dir_template):
    path_dir_template_sim = validate_directory(path_dir_template, name_dir_sim)
    path_dir_case_sim = os.path.join(path_dir_case, name_dir_sim)
    if not os.path.isdir(path_dir_case_sim):
        os.mkdir(path_dir_case_sim)

    copy_files(path_dir_src=path_dir_template_sim, path_dir_dst=path_dir_case_sim)

    edit_materials_dat(path_dir_case_sim, parameters)
    write_material_skew_and_patch_model(path_dir_case_sim, parameters)
    #edit_boundary_conditions_dat(path_dir_case_sim, parameters)

def setup_case(args):
    name_dir_case, path_dir_cases, path_dir_template = args
    path_dir_case = validate_directory(path_dir_cases, name_dir_case)
    parameters = case_tools.read_parameters(path_dir_case)
    create_case_mesh(path_dir_case, parameters, path_dir_template)
    create_case_sim(path_dir_case, parameters, path_dir_template)
    return path_dir_case

def setup_cases(path_dir_cases, path_dir_template, numWorkers=1):
    cases = [f for f in os.listdir(path_dir_cases) if f.startswith("case-")]
    map_args = [(case, path_dir_cases, path_dir_template) for case in cases]
    if numWorkers == 1:
        for args in map_args:
            print(setup_case(args))
    else:
        with multiprocessing.Pool(numWorkers) as pool:
            for x in pool.imap_unordered(setup_case, map_args):
                print(x)

if __name__ == '__main__':
    import argparse

    path_dir_root = os.path.abspath(os.getcwd())
    parser = argparse.ArgumentParser(description="Copy template sim/mesh into each case-* folder.")
    parser.add_argument(
        "--cases-dir",
        default="cases",
        help="Directory containing case-* folders (default: cases). Example: cases-test",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        metavar="N",
        help="Parallel workers for setup_case (default: 4). Use 1 for easier logs.",
    )
    args = parser.parse_args()
    path_dir_cases = os.path.join(path_dir_root, args.cases_dir)
    path_dir_template = validate_directory(path_dir_root, "template")

    setup_cases(path_dir_cases, path_dir_template, numWorkers=args.workers)
