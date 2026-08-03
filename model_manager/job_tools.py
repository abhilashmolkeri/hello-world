import os
import os_tools

def all_files(path_dir_job, name_job):
    return list(os_tools.file_names(path_dir_job, prefix=name_job))

def files_no_dat(path_dir_job, name_job):
    # Ignore the .dat input scripts when cleaning up
    return [f for f in all_files(path_dir_job, name_job) if not f.endswith(".dat")]

def remove_files(path_dir_job, name_job):
    job_files = files_no_dat(path_dir_job, name_job)
    for name_file in job_files:
        path_file = os.path.join(path_dir_job, name_file)
        try:
            os.remove(path_file)
        except OSError:
            pass

def status(path_dir_job, name_job):
    name_file_out = "%s.out" % (name_job,)
    path_file_out = os.path.join(path_dir_job, name_file_out)

    if not os.path.isfile(path_file_out):
        return "no status file"

    try:
        with open(path_file_out) as f:
            lines = [line.strip() for line in f]
    except IOError:
        return "cannot read status file"

    failures = [line for line in lines if "*** ERROR ***" in line]
    successes = [line for line in lines if "Run Completed" in line]

    if failures:
        return "job failed"
    if successes:
        return "job succeeded"

    return "no completion message"

def is_complete(path_dir_job, name_job):
    return (status(path_dir_job, name_job) == "job succeeded")
