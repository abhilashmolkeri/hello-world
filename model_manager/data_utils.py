import os

def unique(items):
    return sorted(list(set(items)))

def data_LOD_get_all_values(data, key):
    return [d[key] for d in data if key in d]

def data_LOD_get_unique_values(data, key):
    return unique(data_LOD_get_all_values(data, key))

def data_LOD_get_all_keys(data):
    return [key for d in data for key in d.keys()]

def data_LOD_get_unique_keys(data):
    return unique(data_LOD_get_all_keys(data))

def write_lines(lines, path_file):
    with open(path_file, "w") as f:
        for line in lines:
            f.write(line + os.linesep)

def write_data_LOD(data, path_file, sep=","):
    if not data:
        return
    keys = data_LOD_get_unique_keys(data)
    lines = list()
    lines.append(sep.join(keys))

    for d in data:
        tokens = [str(d.get(key, "")) for key in keys]
        lines.append(sep.join(tokens))

    write_lines(lines, path_file)
