#!/usr/bin/env python3
"""
Split Workbench-exported ANSYS MAPDL Mechanical .dat files into modular chunks
and emit a driver model.dat with /INPUT includes.

Default: Workbench sentinel lines (/wb,elem,end, /wb,mat,start, etc.) required.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class LineRange:
    """1-based inclusive line indices."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 1 or self.end < self.start:
            raise ValueError(f"Invalid range: {self.start}-{self.end}")


def _norm_upper(s: str) -> str:
    return s.strip().upper()


def _line_key(line: str) -> str:
    """First token / directive for WB marker detection (upper)."""
    return _norm_upper(line.split("!")[0])


@dataclass
class WbMarkers:
    wb_file_start: int | None = None
    wb_elem_start: int | None = None
    wb_elem_end: int | None = None
    wb_mat_start: int | None = None
    wb_mat_end: int | None = None
    wb_contact_start: int | None = None
    wb_contact_end: int | None = None
    wb_load_start: int | None = None
    wb_load_end: int | None = None
    wb_file_end: int | None = None
    prep7: int | None = None
    solu: int | None = None
    post1: int | None = None


def scan_markers(lines: list[str]) -> WbMarkers:
    m = WbMarkers()
    for i, line in enumerate(lines, start=1):
        key = _line_key(line)
        if key.startswith("/WB,"):
            if key.startswith("/WB,FILE,START"):
                m.wb_file_start = i
            elif key.startswith("/WB,FILE,END"):
                m.wb_file_end = i
            elif key.startswith("/WB,ELEM,START"):
                m.wb_elem_start = i
            elif key.startswith("/WB,ELEM,END"):
                m.wb_elem_end = i
            elif key.startswith("/WB,MAT,START"):
                m.wb_mat_start = i
            elif key.startswith("/WB,MAT,END"):
                m.wb_mat_end = i
            elif key.startswith("/WB,CONTACT,START"):
                m.wb_contact_start = i
            elif key.startswith("/WB,CONTACT,END"):
                m.wb_contact_end = i
            elif key.startswith("/WB,LOAD,START"):
                m.wb_load_start = i
            elif key.startswith("/WB,LOAD,END"):
                m.wb_load_end = i
        elif key.startswith("/PREP7"):
            if m.prep7 is None:
                m.prep7 = i
        elif key.startswith("/SOLU"):
            if m.solu is None:
                m.solu = i
        elif key.startswith("/POST1"):
            if m.post1 is None:
                m.post1 = i
    return m


def _first_etcon_line(lines: list[str]) -> int:
    for i, line in enumerate(lines, start=1):
        if re.match(r"^\s*etcon\s*,\s*set\s*", line, re.I):
            return i
    raise ValueError(
        "Could not find 'etcon,set' line (expected in Workbench exports after /prep7)."
    )


def build_ranges(lines: list[str], m: WbMarkers) -> dict[str, LineRange]:
    """Compute 1-based inclusive ranges for each output chunk."""
    n = len(lines)
    required = [
        ("wb_elem_end", m.wb_elem_end),
        ("wb_mat_end", m.wb_mat_end),
        ("wb_contact_start", m.wb_contact_start),
        ("wb_contact_end", m.wb_contact_end),
        ("wb_load_start", m.wb_load_start),
        ("wb_load_end", m.wb_load_end),
        ("post1", m.post1),
    ]
    missing = [name for name, v in required if v is None]
    if missing:
        raise ValueError(
            "Missing Workbench markers required for split: "
            + ", ".join(missing)
            + ". Use a Mechanical-exported .dat or inspect /wb, lines."
        )

    etcon = _first_etcon_line(lines)
    preamble = LineRange(1, etcon)
    mesh = LineRange(etcon + 1, m.wb_elem_end)  # type: ignore[arg-type]
    materials = LineRange(m.wb_elem_end + 1, m.wb_mat_end)  # type: ignore[arg-type]
    model_summary = LineRange(m.wb_mat_end + 1, m.wb_contact_start - 1)  # type: ignore[arg-type]
    contacts = LineRange(m.wb_contact_start, m.wb_contact_end)  # type: ignore[arg-type]
    sections = LineRange(m.wb_contact_end + 1, m.wb_load_start - 1)  # type: ignore[arg-type]
    loads = LineRange(m.wb_load_start, m.wb_load_end)  # type: ignore[arg-type]
    solve = LineRange(m.wb_load_end + 1, m.post1 - 1)  # type: ignore[arg-type]
    post = LineRange(m.post1, n)

    return {
        "preamble": preamble,
        "mesh": mesh,
        "materials": materials,
        "model_summary": model_summary,
        "contacts": contacts,
        "sections": sections,
        "loads_and_BCs": loads,
        "solve": solve,
        "post_processing": post,
    }


def slice_lines(lines: list[str], r: LineRange) -> list[str]:
    return lines[r.start - 1 : r.end]


def write_lines(path: Path, chunk: Iterable[str], newline: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        for line in chunk:
            if line.endswith("\r\n") or line.endswith("\n"):
                core = line.rstrip("\r\n")
                f.write(core + newline)
            else:
                f.write(line + newline)


def _read_lines_simple(path: Path) -> tuple[list[str], str]:
    """Read with newline='' to preserve \\n or \\r\\n per line end; detect dominant nl."""
    text = path.read_text(encoding="utf-8", errors="surrogateescape", newline="")
    if "\r\n" in text[:4096]:
        nl = "\r\n"
    else:
        nl = "\n"
    lines = text.splitlines(keepends=True)
    if not lines:
        return [], nl
    return lines, nl


def bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def join_for_verify(
    lines: list[str],
    ranges_order: list[tuple[str, LineRange]],
) -> str:
    out: list[str] = []
    for _name, r in ranges_order:
        out.extend(lines[r.start - 1 : r.end])
    return "".join(out)


def emit_model_dat(
    out_path: Path,
    preamble_lines: list[str],
    newline: str,
) -> None:
    """Razorcrest-style driver: no /solu here (solve.dat begins with /solu)."""
    lines_out: list[str] = []
    lines_out.extend(preamble_lines)
    if not preamble_lines[-1].endswith(("\n", "\r\n")):
        lines_out[-1] = lines_out[-1] + newline

    def add_block(label: str, fname: str) -> None:
        lines_out.append(f"! *************** start {label} ***********************\n")
        lines_out.append(f"/INPUT, {fname}, dat\n")
        lines_out.append(f"! *************** end {label} ***********************\n")

    add_block("mesh", "mesh")
    add_block("materials", "materials")
    add_block("model summary", "model_summary")
    add_block("contacts", "contacts")
    add_block("sections", "sections")
    add_block("BC", "loads_and_BCs")
    lines_out.append("! ******************************************************\n")
    lines_out.append("! *************** start solve ***********************\n")
    lines_out.append("/INPUT, solve, dat\n")
    lines_out.append("! *************** end solve ***********************\n")
    lines_out.append("/INPUT, post_processing, dat\n")

    write_lines(out_path, lines_out, newline)


def verify_reconstruction(
    original_path: Path,
    lines: list[str],
    ranges_order: list[tuple[str, LineRange]],
) -> tuple[bool, str, str]:
    orig_bytes = original_path.read_bytes()
    orig_hash = bytes_sha256(orig_bytes)
    joined = join_for_verify(lines, ranges_order)
    joined_bytes = joined.encode("utf-8", errors="surrogateescape")
    join_hash = bytes_sha256(joined_bytes)
    ok = joined_bytes == orig_bytes
    return ok, orig_hash, join_hash


def main() -> int:
    p = argparse.ArgumentParser(description="Split Workbench MAPDL .dat into modular chunks.")
    p.add_argument("input_dat", type=Path, help="Source Mechanical .dat file")
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: <input_stem>_split next to input)",
    )
    p.add_argument(
        "--verify-only",
        action="store_true",
        help="Only print marker/range diagnostics for input (no writes)",
    )
    args = p.parse_args()

    inp = args.input_dat.resolve()
    if not inp.is_file():
        print(f"Not found: {inp}", file=sys.stderr)
        return 1

    lines, newline = _read_lines_simple(inp)
    if not lines:
        print("Empty input.", file=sys.stderr)
        return 1

    markers = scan_markers(lines)
    ranges = build_ranges(lines, markers)

    order = [
        ("preamble", ranges["preamble"]),
        ("mesh", ranges["mesh"]),
        ("materials", ranges["materials"]),
        ("model_summary", ranges["model_summary"]),
        ("contacts", ranges["contacts"]),
        ("sections", ranges["sections"]),
        ("loads_and_BCs", ranges["loads_and_BCs"]),
        ("solve", ranges["solve"]),
        ("post_processing", ranges["post_processing"]),
    ]

    print("Manifest (1-based inclusive line ranges):")
    for name, r in order:
        nlines = r.end - r.start + 1
        print(f"  {name:20} {r.start:10}-{r.end:<10} ({nlines} lines)")

    # Marker sanity: every /wb, line in source must appear exactly once in union of chunk bodies
    wb_lines: list[tuple[int, str]] = []
    for i, line in enumerate(lines, start=1):
        if _line_key(line).startswith("/WB,"):
            wb_lines.append((i, line.rstrip("\r\n")))
    covered = set()
    chunk_files = [
        "mesh",
        "materials",
        "model_summary",
        "contacts",
        "sections",
        "loads_and_BCs",
        "solve",
        "post_processing",
    ]
    for name in ["preamble", *chunk_files]:
        r = ranges[name]
        for i in range(r.start, r.end + 1):
            if _line_key(lines[i - 1]).startswith("/WB,"):
                covered.add(i)
    missing_wb = [wl for wl in wb_lines if wl[0] not in covered]
    extra_in_chunks = covered - {wl[0] for wl in wb_lines}
    if missing_wb:
        print("ERROR: /wb, lines not placed in any chunk:", file=sys.stderr)
        for ln, text in missing_wb[:20]:
            print(f"  line {ln}: {text}", file=sys.stderr)
        return 1
    if extra_in_chunks:
        print("WARN: unexpected /wb, coverage mismatch", file=sys.stderr)

    ok, oh, jh = verify_reconstruction(inp, lines, order)
    original_text = "".join(lines)
    text_ok = join_for_verify(lines, order) == original_text
    print(f"\nReconstruction line-exact (text): {text_ok}")
    print(f"Reconstruction bytes equal file: {ok}")
    print(f"SHA256(original)= {oh}")
    print(f"SHA256(rejoined)= {jh}")

    if args.verify_only:
        return 0 if text_ok else 1

    out_dir = args.out_dir or (inp.parent / f"{inp.stem}_split")
    out_dir.mkdir(parents=True, exist_ok=True)

    names = {
        "mesh": "mesh.dat",
        "materials": "materials.dat",
        "model_summary": "model_summary.dat",
        "contacts": "contacts.dat",
        "sections": "sections.dat",
        "loads_and_BCs": "loads_and_BCs.dat",
        "solve": "solve.dat",
        "post_processing": "post_processing.dat",
    }

    for key, fname in names.items():
        write_lines(out_dir / fname, slice_lines(lines, ranges[key]), newline)

    emit_model_dat(out_dir / "model.dat", slice_lines(lines, ranges["preamble"]), newline)

    print(f"\nWrote chunks and model.dat to {out_dir}")
    return 0 if text_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
