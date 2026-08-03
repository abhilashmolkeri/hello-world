import sys
import os
import json
import itertools

# Windows-safe path to the model_manager directory
path_dir_scripts = r"D:\work\scripts\DOE_generator\model_manager"
if path_dir_scripts not in sys.path:
    sys.path.append(path_dir_scripts)

import case_tools


def material_skew_part_keys(variables):
    """Keys whose values are merged into ``material_skew`` (see ``create_cases_with_merged_skew``).

    Convention: any key in ``variables`` whose name ends with ``_Material`` (e.g.
    ``Bumps_Material``, ``Mold_Material``, ``UF_Material``). Merge order is **sorted by
    key name** so the result is deterministic.
    """
    return tuple(sorted(k for k in variables if k.endswith("_Material")))


def merge_material_skew_json_fragments(*fragments):
    """Concatenate skew rule JSON from each fragment into one JSON array string.

    Each fragment is a string containing JSON: either one object ``{...}`` or an array
    ``[{...}, ...]``. Empty or whitespace-only fragments are skipped.
    """
    rules = []
    for frag in fragments:
        s = (frag if frag is not None else "").strip()
        if not s:
            continue
        data = json.loads(s)
        if isinstance(data, dict):
            rules.append(data)
        elif isinstance(data, list):
            rules.extend(data)
        else:
            raise TypeError(
                "material skew fragment must decode to a JSON object or array, got %s"
                % type(data).__name__
            )
    return json.dumps(rules)


def create_cases_with_merged_skew(path_dir_cases, variables, case_filter=None):
    """Like ``case_tools.create_cases``, but merges ``*_Material`` columns into ``material_skew``.

    Any ``variables`` key ending with ``_Material`` is treated as a skew fragment column
    (see ``material_skew_part_keys``). You must **not** also set ``material_skew`` when
    using those keys (raises ``ValueError``). For each factorial combination, those keys
    are removed from the written parameters and replaced by one ``material_skew`` JSON
    array string (rules concatenated in **sorted key name** order).

    Example::

        variables["Bumps_Material"] = [
            '[{"named_selection":"BUMPS_HOMOGENIZED_ALL","to_matid":999}]',
        ]
        variables["Mold_Material"] = [
            '[{"named_selection":"MOLD_ALL","to_matid":1}]',
            '[{"named_selection":"MOLD_ALL","to_matid":2}]',
        ]
    """
    part_keys_ordered = material_skew_part_keys(variables)
    if part_keys_ordered and "material_skew" in variables:
        raise ValueError(
            "Use either ``material_skew`` alone OR ``*_Material`` split keys (got %s), not both."
            % (part_keys_ordered,)
        )
    if not part_keys_ordered:
        return case_tools.create_cases(path_dir_cases, variables, case_filter=case_filter)

    keys = list(variables.keys())
    vals = list(variables.values())
    all_parameters = []
    for row in itertools.product(*vals):
        p = dict(zip(keys, row))
        frags = [p[k] for k in part_keys_ordered]
        for k in part_keys_ordered:
            del p[k]
        p["material_skew"] = merge_material_skew_json_fragments(*frags)
        if case_filter and not case_filter(p):
            continue
        all_parameters.append(p)

    if not os.path.isdir(path_dir_cases):
        os.mkdir(path_dir_cases)
    for name_dir_case, case_parameters in case_tools.labeled(all_parameters, case_tools.case_prefix):
        path_dir_case = os.path.join(path_dir_cases, name_dir_case)
        if not os.path.isdir(path_dir_case):
            os.mkdir(path_dir_case)
        case_tools.write_parameters(path_dir_case, case_parameters)


def case_filter(parameters):
    if parameters.get("Greentea_Stress_MPa") == "-290.0" and parameters.get("LT_Hardox_Stress_MPa") == "-70.0":
        return False
    elif parameters.get("Greentea_Stress_MPa") == "-405.0" and parameters.get("LT_Hardox_Stress_MPa") == "-60.0":
        return False
    else:
        return True

if __name__ == '__main__':
    path_dir_root = os.path.abspath(os.getcwd())
    path_dir_cases = os.path.join(path_dir_root, "cases")

    # ================================================================
    # How to define ``variables`` (DOE grid -> case-*/parameters.dat)
    # ================================================================
    #
    # General rules
    # -------------
    #   * Each key becomes a parameter name; each value must be a **list** of strings.
    #   * Cases are the **Cartesian product** of all lists (same rules as case_tools.create_cases).
    #   * Key order in this dict affects product ordering / case indices (Python 3.7+ order).
    #
    # Template / setup_cases keys (examples)
    # ---------------------------------------
    #   * GlassCW_cte, GlassCW_modulus, SFT_C, tref_C - consumed by setup_cases when copying
    #     the template sim (see setup_cases.edit_materials_dat); use exact key spelling there.
    #
    # Material skew - pick ONE style per run
    # ---------------------------------------
    # Read by setup_cases from parameters.dat as JSON (see iter_material_skew_rules).
    #
    #   (1) Single column ``material_skew``
    #       * List of JSON strings; each string is one **object** { ... } or **array** [ {...}, ... ].
    #       * Do **not** define any key ending in ``_Material`` in the same dict.
    #       * MPCHG example:
    #             variables["material_skew"] = [
    #                 '[{"named_selection":"BUMPS_HOMOGENIZED_ALL","to_matid":999}]',
    #             ]
    #       * EMODIF example (path_tag / to_material / optional from_material):
    #             variables["material_skew"] = [
    #                 '[{"path_tag":"Bumps_Homogenized","to_material":"DAF",'
    #                 '"from_material":"Bumps_UF_Homogenized Simple"}]',
    #             ]
    #       * Mixed rules in one case: one JSON array with several objects.
    #
    #   (2) Split columns - any key whose name ends with ``_Material``
    #       * e.g. Bumps_Material, Mold_Material; each list entry is JSON (object or array).
    #       * For each case, all ``*_Material`` fragments are merged into one ``material_skew``
    #         in **sorted key name** order (Bumps_Material before Mold_Material).
    #       * Do **not** set ``material_skew`` when using ``*_Material`` keys.
    #
    #   (3) Legacy flat bumps remap (no JSON):
    #             variables["Bumps_Homogenized_layer_matprop"] = ["Bumps_UF_Homogenized Simple", "DAF"]
    #       Omit ``material_skew`` and ``*_Material`` when using this.
    #
    # MPCHG vs EMODIF (short)
    # ------------------------
    #   * MPCHG: named_selection (+ to_matid or to_material). Targets a component only.
    #   * EMODIF: path_tag (+ to_material, optional from_material). Remaps by material ID.
    #
    # Case filter
    # ------------
    #   * ``case_filter(parameters)`` below can return False to drop a combination before
    #     a case folder is created.
    #
    # ================================================================

    variables = dict()

    variables["GlassCW_cte"] = ["3.2e-06",
                                "3.4e-06",
                          #     "3.6e-06",
                                "3.8e-06",
                          #      "4.0e-06",
                                "4.4e-06"
                                ]
    variables["GlassCW_modulus"] = ["73600",]
    variables["SFT_C"] = ["125",]
    variables["Bumps_Material"] = [
        '[{"named_selection":"BUMPS_HOMOGENIZED_ALL","to_matid":999}]',
    ]
    variables["Mold_Material"] = [
        #'[{"named_selection":"MOLD_ALL","to_matid":1}]',
        #'[{"named_selection":"MOLD_ALL","to_matid":2}]',
        '[{"named_selection":"MOLD_ALL","to_matid":3}]', #MA05
        '[{"named_selection":"MOLD_ALL","to_matid":4}]', #MA37
        #'[{"named_selection":"MOLD_ALL","to_matid":5}]',
        #'[{"named_selection":"MOLD_ALL","to_matid":6}]',
        '[{"named_selection":"MOLD_ALL","to_matid":7}]', #MA01
        #'[{"named_selection":"MOLD_ALL","to_matid":8}]',
        #'[{"named_selection":"MOLD_ALL","to_matid":9}]',
        #'[{"named_selection":"MOLD_ALL","to_matid":10}]',
        #'[{"named_selection":"MOLD_ALL","to_matid":7}]',
    ]
    variables["tref_C"] = ["25",]

    create_cases_with_merged_skew(path_dir_cases, variables, case_filter=case_filter)
