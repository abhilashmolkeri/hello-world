import os

def write_lines(lines, path_file):
    with open(path_file, "w") as f:
        for line in lines:
            f.write(line + os.linesep)

def lines_containing(lines, target):
    if isinstance(target, (list, tuple)):
        return [line for line in lines if any(t in line for t in target)]
    else:
        return [line for line in lines if target in line]

def lines_containing_insensitive(lines, target):
    if isinstance(target, (list, tuple)):
        ltarget = [t.lower() for t in target]
        return [line for line in lines if any(t in line.lower() for t in ltarget)]
    else:
        return [line for line in lines if target.lower() in line.lower()]
