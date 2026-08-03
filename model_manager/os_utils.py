import os
import shutil

def _absolute_src_dst(path_dir_src, path_dir_dst, name_file, new_name=None):
    src = os.path.abspath(os.path.join(path_dir_src, name_file))
    dst_name = new_name if new_name else name_file
    dst = os.path.abspath(os.path.join(path_dir_dst, dst_name))
    return src, dst

def symlink_file(path_dir_src, path_dir_dst, name_file, new_name=None):
    src, dst = _absolute_src_dst(path_dir_src, path_dir_dst, name_file, new_name)

    # Check if target already exists to prevent crashes
    if os.path.exists(dst):
        os.remove(dst)

    relsrc = os.path.relpath(src, path_dir_dst)
    return os.symlink(relsrc, dst)

def symlink_dir(path_dir_src, path_dir_dst, new_name=None):
    relsrc = os.path.relpath(path_dir_src, os.path.dirname(path_dir_dst))
    if os.path.exists(path_dir_dst):
        shutil.rmtree(path_dir_dst)
    return os.symlink(relsrc, path_dir_dst)

def copy_file(path_dir_src, path_dir_dst, name_file, new_name=None):
    src, dst = _absolute_src_dst(path_dir_src, path_dir_dst, name_file, new_name)
    if os.path.isdir(src):
        shutil.copytree(src, dst)
    else:
        shutil.copy(src, dst)

def copy_files(path_dir_src, path_dir_dst, file_names=None):
    if not file_names:
        file_names = os.listdir(path_dir_src)
    for name_file in file_names:
        copy_file(path_dir_src, path_dir_dst, name_file)

def validate_directory(path, *paths):
    path_dir = os.path.join(path, *paths)
    if not os.path.isdir(path_dir):
        raise IOError("cannot find directory \"%s\"" % (path_dir,))
    return path_dir

def validate_file(path, *paths):
    path_file = os.path.join(path, *paths)
    if not os.path.isfile(path_file):
        raise IOError("cannot find file \"%s\"" % (path_file,))
    return path_file

def files(path, *paths):
    path_dir = validate_directory(path, *paths)
    for f in os.listdir(path_dir):
        path_f = os.path.join(path_dir, f)
        if os.path.isfile(path_f):
            yield f
