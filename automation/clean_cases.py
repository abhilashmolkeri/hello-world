"""Remove MAPDL/WB scratch from each cases*/case*/sim, keeping only KEEP_EXTENSIONS
and filenames in KEEP_FILENAMES (e.g. PIC_Warpage_Data.txt).

CLI:

  python clean_cases.py [--dry-run] [--require-complete] [--cases-dir NAME ...]

``--cases-dir`` / ``-c`` selects a cases tree by basename under cwd (repeatable).
If omitted, every directory whose name starts with ``cases`` is used.

By default every matching sim dir is cleaned even if job_tools does not see the job as
complete. Pass ``--require-complete`` to skip incomplete runs.
"""
import argparse
import os
import sys

path_dir_scripts = r"D:\work\scripts\DOE_generator\model_manager"
if path_dir_scripts not in sys.path:
    sys.path.append(path_dir_scripts)
import job_tools

# Only files with these extensions are kept; everything else under sim/ is removed
# (recursively). Empty directories left after that are removed (e.g. MAPDL DB folders).
# Basenames listed in KEEP_FILENAMES are always kept regardless of extension.
KEEP_EXTENSIONS = {".dat", ".out", ".bat", ".png"}
KEEP_FILENAMES = {"PIC_Warpage_Data.txt"}
_KEEP_EXT_LOWER = frozenset(e.lower() for e in KEEP_EXTENSIONS)
_KEEP_NAME_LOWER = frozenset(n.lower() for n in KEEP_FILENAMES)


def sim_dirs(path_dir_root, cases_dirnames=None):
    """Yield ``.../<casesDir>/case*/sim`` paths.

    ``cases_dirnames``: basenames under ``path_dir_root`` (e.g. ``cases``, ``cases-foo``).
    If None or empty, use every child of ``path_dir_root`` whose name starts with ``cases``.
    """
    if cases_dirnames:
        names_to_scan = list(dict.fromkeys(cases_dirnames))
    else:
        names_to_scan = sorted(
            n
            for n in os.listdir(path_dir_root)
            if n.startswith("cases") and os.path.isdir(os.path.join(path_dir_root, n))
        )
    for name_cases in names_to_scan:
        path_dir_cases = os.path.join(path_dir_root, name_cases)
        if not os.path.isdir(path_dir_cases):
            print("  WARNING: not a directory, skipping: %s" % path_dir_cases, file=sys.stderr)
            continue
        for name_case in os.listdir(path_dir_cases):
            if not name_case.startswith("case"):
                continue
            path_dir_sim = os.path.join(path_dir_cases, name_case, "sim")
            if os.path.isdir(path_dir_sim):
                yield path_dir_sim


def _remove_empty_dirs(path_dir_sim, deleted_log):
    """Bottom-up remove empty directories under sim (not sim itself). Repeat until stable."""
    while True:
        removed_any = False
        for root, _dirs, _files in os.walk(path_dir_sim, topdown=False):
            if os.path.normpath(root) == os.path.normpath(path_dir_sim):
                continue
            try:
                if os.path.isdir(root) and not os.listdir(root):
                    rel = os.path.relpath(root, path_dir_sim)
                    deleted_log.append(rel)
                    os.rmdir(root)
                    removed_any = True
            except OSError:
                pass
        if not removed_any:
            break


def clean_sim(path_dir_sim, dry_run=False, require_complete=False):
    if require_complete and not job_tools.is_complete(path_dir_sim, "model"):
        print("  SKIP (not complete): %s" % path_dir_sim)
        return
    deleted = []
    for root, _dirs, files in os.walk(path_dir_sim):
        for name in files:
            path_file = os.path.join(root, name)
            if not os.path.isfile(path_file):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in _KEEP_EXT_LOWER:
                continue
            if name.lower() in _KEEP_NAME_LOWER:
                continue
            rel = os.path.relpath(path_file, path_dir_sim)
            deleted.append(rel)
            if not dry_run:
                os.remove(path_file)

    if not dry_run:
        _remove_empty_dirs(path_dir_sim, deleted)

    if deleted:
        print("  Cleaned %s:" % path_dir_sim)
        for name in sorted(set(deleted)):
            print("    - %s" % name)
    else:
        print("  Already clean: %s" % path_dir_sim)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Delete scratch files under cases*/case*/sim, keeping extensions %s "
            "and files: %s."
            % (", ".join(sorted(KEEP_EXTENSIONS)), ", ".join(sorted(KEEP_FILENAMES)))
        )
    )
    parser.add_argument("--dry-run", action="store_true", help="List files that would be removed only.")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Skip sim dirs where job_tools does not mark the model job complete.",
    )
    parser.add_argument(
        "--cases-dir",
        "-c",
        action="append",
        dest="cases_dirs",
        metavar="NAME",
        help=(
            "Basename of a cases directory under cwd (repeatable). "
            "Example: -c cases -c cases-SFT_mold_MA01_elastic_skews. "
            "Default: all directories whose names start with 'cases'."
        ),
    )
    args = parser.parse_args()

    if args.dry_run:
        print("=== DRY RUN - no files will be deleted ===\n")
    if args.require_complete and not args.dry_run:
        print("=== --require-complete: skip sim dirs where model is not marked complete ===\n")

    path_dir_root = os.path.abspath(os.getcwd())
    cases_filter = args.cases_dirs if args.cases_dirs else None
    if cases_filter:
        print("Cases roots: %s\n" % ", ".join(cases_filter))

    for path_dir_sim in sorted(sim_dirs(path_dir_root, cases_dirnames=cases_filter)):
        clean_sim(path_dir_sim, dry_run=args.dry_run, require_complete=args.require_complete)
