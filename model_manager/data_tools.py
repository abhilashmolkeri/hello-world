import file_tools

def write_dict_file(d, path_file):
    keyWidth = max(len(key) for key in d.keys())
    lines = list()
    for key, value in d.items():
        line = "%-*s = %s" % (keyWidth, key, value)
        lines.append(line)
    file_tools.write_lines(lines, path_file)
    return

def read_dict_file(path_file):
    d = dict()
    with open(path_file) as f:
        for line in f:
            if "=" in line:
                key, value = line.split("=", 1)
                d[key.strip()] = value.strip()
    return d
