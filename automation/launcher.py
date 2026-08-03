from __future__ import print_function
import os
import re
import time
import math
import random
import subprocess

import sys
path_dir_scripts = r"D:\work\scripts\DOE_generator\model_manager"
if path_dir_scripts not in sys.path:
    sys.path.append(path_dir_scripts)
import job_tools

name_job = "model"
name_file_inp = "%s.dat" % (name_job,)
name_file_out = "%s.out" % (name_job,)

# ------------------------------------------------------------------
# License settings (lmutil from ANSYS 2025 R2 licensing client)
# ------------------------------------------------------------------
LMUTIL          = r"C:\Program Files\ANSYS Inc\v252\licensingclient\winx64\lmutil.exe"
LICENSE_SERVER  = "1055@10.100.14.212"
LICENSE_FEATURE = "ansys"
LICENSE_FEATURE_HPC = "anshpc_pack"
HPC_CORES_PER_LICENSE = 12
LICENSE_RETRY_S = 60   # seconds to wait before re-checking when no licence is free

# ------------------------------------------------------------------
# MAPDL parallelism (written into each case's submission_command_ansys.bat)
# ------------------------------------------------------------------
# Requested -np for each MAPDL run. Capped automatically to this machine's
# logical CPU count (os.cpu_count()) so MAPDL does not warn / clamp at runtime.
NUM_CORES = 12

SUBMISSION_BAT = "submission_command_ansys.bat"
_NUM_CORES_BAT_RE = re.compile(r"set\s+NUM_CORES\s*=\s*(\d+)", re.IGNORECASE)

def directories(path_dir_root, prefix=""):
    contents = os.listdir(path_dir_root)
    for f in contents:
        if f.startswith(prefix):
            path_f = os.path.join(path_dir_root, f)
            if os.path.isdir(path_f):
                yield path_f

def sim_dirs(path_dir_cases):
    for path_dir_case in directories(path_dir_cases, prefix="case"):
        for path_dir_sim in directories(path_dir_case, prefix="sim"):
            yield path_dir_sim

def is_launched(path_dir_sim):
    contents = os.listdir(path_dir_sim)
    if any(f.endswith((".out", ".err", ".mntr")) for f in contents):
        return True
    return False

def can_launch(path_dir_sim):
    required = [name_file_inp]
    return all(os.path.isfile(os.path.join(path_dir_sim, f)) for f in required)

def dirs_to_launch(path_dir_cases):
    dirs = sorted(list(sim_dirs(path_dir_cases)))
    for path_dir_sim in dirs:
        if not is_launched(path_dir_sim) and can_launch(path_dir_sim):
            yield path_dir_sim

def count_running(processes):
    """Return number of subprocess.Popen jobs still running."""
    return sum(1 for p in processes if p.poll() is None)

def effective_num_cores(requested):
    """Cap MAPDL -np at this machine's logical CPU count (avoids MAPDL warning)."""
    req = max(1, int(requested))
    ncpu = os.cpu_count()
    if ncpu is None or ncpu < 1:
        return req
    return min(req, ncpu)

def write_num_cores_to_bat(path_dir_sim, num_cores):
    """Update `set NUM_CORES=...` in submission_command_ansys.bat (in place).

    Returns (ok, err_message).  ok is False if the bat is missing or has no
    matching NUM_CORES line.
    """
    path_bat = os.path.join(path_dir_sim, SUBMISSION_BAT)
    try:
        with open(path_bat, "r") as f:
            text = f.read()
    except EnvironmentError as e:
        return False, "cannot read %s (%s)" % (path_bat, e)
    new_text, n = _NUM_CORES_BAT_RE.subn(
        "set NUM_CORES=%d" % int(num_cores), text, count=1
    )
    if n != 1:
        return False, "no `set NUM_CORES=<digits>` line in %s" % path_bat
    try:
        with open(path_bat, "w") as f:
            f.write(new_text)
    except EnvironmentError as e:
        return False, "cannot write %s (%s)" % (path_bat, e)
    return True, None

def parse_num_cores(path_dir_sim):
    """Read NUM_CORES from submission_command_ansys.bat in the sim directory."""
    path_bat = os.path.join(path_dir_sim, SUBMISSION_BAT)
    try:
        with open(path_bat, "r") as f:
            text = f.read()
    except EnvironmentError:
        print("  [license] WARNING: %s not found; assuming NUM_CORES=%d"
              % (path_bat, NUM_CORES))
        return NUM_CORES
    m = _NUM_CORES_BAT_RE.search(text)
    if not m:
        print("  [license] WARNING: no NUM_CORES in %s; assuming %d"
              % (path_bat, NUM_CORES))
        return NUM_CORES
    return int(m.group(1))

def hpc_licenses_needed(num_cores):
    """ANSYS HPC packs: one pack per 12 cores (ceiling)."""
    if num_cores <= 0:
        return 0
    return int(math.ceil(num_cores / float(HPC_CORES_PER_LICENSE)))

def query_licenses(feature=LICENSE_FEATURE):
    """Query FlexNet for the named feature via lmutil.

    Returns (total_issued, in_use, available).
    Returns (0, 0, 0) and prints a warning if the query fails.
    """
    try:
        result = subprocess.run(
            [LMUTIL, "lmstat", "-f", feature, "-c", LICENSE_SERVER],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout + result.stderr
        #print(output)
        m = re.search(
            r"Users of %s:\s+\(Total of (\d+) licenses? issued;\s+Total of (\d+) licenses? in use\)" % feature,
            output
        )
        if m:
            issued = int(m.group(1))
            in_use = int(m.group(2))
            return issued, in_use, issued - in_use
        print("  [license] WARNING: could not parse lmstat output.")
        return 0, 0, 0
    except Exception as e:
        print("  [license] WARNING: lmutil query failed: %s" % e)
        return 0, 0, 0

if __name__ == '__main__':
    path_dir_root = os.path.abspath(os.getcwd())
    path_dir_cases = os.path.join(path_dir_root, "cases")
    if not os.path.isdir(path_dir_cases):
        print("Cases directory not found: %s" % path_dir_cases)
        sys.exit(1)

    n  = 1    # Max concurrent jobs running at the same time
    nl = 100  # Max total jobs to launch

    #dwell = 3*3600
    #print("  Wait %.1d hours before launching..." % (dwell/3600))
    #time.sleep(dwell)

    if NUM_CORES < 1:
        print("NUM_CORES must be >= 1 (got %d)" % NUM_CORES)
        sys.exit(1)

    num_cores_launch = effective_num_cores(NUM_CORES)
    if num_cores_launch < NUM_CORES:
        print(
            "[launcher] NUM_CORES=%d exceeds this PC's logical CPUs (%s): "
            "using %d for -np and HPC licence count (avoids MAPDL warning)."
            % (NUM_CORES, os.cpu_count(), num_cores_launch)
        )

    # Collect all pending dirs up front
    pending = list(dirs_to_launch(path_dir_cases))
    if not pending:
        print("No jobs to launch.")
        sys.exit(0)

    processes = []   # track all launched subprocesses
    i = 0

    for path_dir_sim in pending:
        if i >= nl:
            break

        ok, err = write_num_cores_to_bat(path_dir_sim, num_cores_launch)
        if not ok:
            print("Skipping %s: %s" % (path_dir_sim, err))
            continue

        # Block until a local concurrency slot AND required licences are free
        while True:
            if count_running(processes) >= n:
                time.sleep(10)
                continue

            num_cores = num_cores_launch
            need_hpc = hpc_licenses_needed(num_cores)

            issued, in_use, available = query_licenses(LICENSE_FEATURE)
            print("  [license] %s: %d issued, %d in use, %d available (need >= 1)"
                  % (LICENSE_FEATURE, issued, in_use, available))

            if available < 1:
                print("  [license] %s short: need 1, have %d. Retrying in %ds..."
                      % (LICENSE_FEATURE, available, LICENSE_RETRY_S))
                time.sleep(LICENSE_RETRY_S)
                continue

            issued_h, in_use_h, available_h = query_licenses(LICENSE_FEATURE_HPC)
            print("  [license] %s: %d issued, %d in use, %d available (job %d cores -> need %d HPC pack(s))"
                  % (LICENSE_FEATURE_HPC, issued_h, in_use_h, available_h,
                     num_cores, need_hpc))

            if available_h < need_hpc:
                print("  [license] %s short: need %d, have %d. Retrying in %ds..."
                      % (LICENSE_FEATURE_HPC, need_hpc, available_h, LICENSE_RETRY_S))
                time.sleep(LICENSE_RETRY_S)
                continue

            break

        print("Launching (%d): %s  (-np=%d)" % (i + 1, path_dir_sim, num_cores_launch))
        # subprocess.Popen is non-blocking: returns immediately and lets the
        # ANSYS job run in the background while the loop continues.
        # cwd=path_dir_sim avoids os.chdir() changing the global working dir.
        proc = subprocess.Popen(
            ["cmd", "/c", "submission_command_ansys.bat"],
            cwd=path_dir_sim
        )
        processes.append(proc)
        i += 1
        print("  PID %d  (to kill: taskkill /F /T /PID %d)" % (proc.pid, proc.pid))

        # Small stagger between launches to avoid simultaneous licence checkout
        dwell = random.randint(2, 5) * math.pi
        print("  Stagger wait %.1fs before next launch..." % dwell)
        time.sleep(dwell)

    print("\nAll %d job(s) submitted. Waiting for completion..." % i)
    print("Running PIDs: %s" % ", ".join(str(p.pid) for p in processes if p.poll() is None))
    for proc in processes:
        proc.wait()

    print("\n--- Job Status ---")
    for path_dir_sim in sim_dirs(path_dir_cases):
        s = job_tools.status(path_dir_sim, name_job)
        print("%s : %s" % (path_dir_sim, s))
