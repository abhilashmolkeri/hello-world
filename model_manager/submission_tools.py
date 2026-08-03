from __future__ import print_function
import os
import shutil
import os_tools
import file_tools
import job_tools

def find_job_submission_script(path_dir_job):
    # Find Windows batch files instead of bash scripts
    candidates = list(os_tools.file_names(path_dir_job, prefix="subm", suffix=".bat"))

    if len(candidates) == 0:
        return ""
    if len(candidates) > 1:
        print("%s has multiple job submission scripts" % path_dir_job)
        return ""

    return candidates[0]

def can_launch(path_dir_job):
    if not all(os.path.exists(os.path.join(path_dir_job, f)) for f in os.listdir(path_dir_job)):
        print("%s has broken links" % path_dir_job)
        return False

    name_file_script = find_job_submission_script(path_dir_job)
    if not name_file_script:
        return False
    return True

def launch(path_dir_job):
    incoming_wd = os.getcwd()
    os.chdir(path_dir_job)

    name_file_script = find_job_submission_script(path_dir_job)
    rv = os.system(name_file_script)

    print("%s returned %i" % (path_dir_job, rv))
    os.chdir(incoming_wd)
    return rv

def remove_solver_files(path_dir_job):
    # ANSYS specific cleanup for Windows
    extensions = [".err", ".mntr", ".lock", ".log"]
    for ext in extensions:
        for path_file in os_tools.file_paths(path_dir_job, suffix=ext):
            try:
                os.remove(path_file)
            except OSError:
                pass
