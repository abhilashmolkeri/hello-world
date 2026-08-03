import os
import shutil

def directory_paths(path_dir_root, prefix="", suffix=""):
    for f in os.listdir(path_dir_root):
        if f.startswith(prefix) and f.endswith(suffix):
            path_f = os.path.join(path_dir_root, f)
            if os.path.isdir(path_f):
                yield path_f

def file_names(path_dir_root, prefix="", suffix=""):
    for f in os.listdir(path_dir_root):
        if f.startswith(prefix) and f.endswith(suffix):
            path_f = os.path.join(path_dir_root, f)
            if os.path.isfile(path_f):
                yield f

def file_paths(path_dir_root, prefix="", suffix=""):
    for f in os.listdir(path_dir_root):
        if f.startswith(prefix) and f.endswith(suffix):
            path_f = os.path.join(path_dir_root, f)
            if os.path.isfile(path_f):
                yield path_f
