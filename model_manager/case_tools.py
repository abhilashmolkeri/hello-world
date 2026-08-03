import os
import math
import itertools
import os_tools
import file_tools

name_file_parameters = "parameters.dat"
case_prefix = "case"

def write_parameters(path_dir_case, parameters):
    keyWidth = max(len(key) for key in parameters.keys())
    lines = []
    for key, value in parameters.items():
        line = "%-*s = %s" % (keyWidth, key, value)
        lines.append(line)

    path_file_parameters = os.path.join(path_dir_case, name_file_parameters)
    file_tools.write_lines(lines, path_file_parameters)

def read_parameters(path_dir_case):
    parameters = dict()
    path_file_parameters = os.path.join(path_dir_case, name_file_parameters)
    with open(path_file_parameters) as f:
        for line in f:
            if "=" in line:
                key, value = line.split("=", 1)
                parameters[key.strip()] = value.strip()
    return parameters

def labeled(items, prefix):
    numItems = len(items)
    if numItems == 0:
        return
    digits = 1 + int(math.log10(numItems))
    for i, item in enumerate(items):
        name = "%s-%0*i" % (prefix, digits, i)
        yield name, item

def create_case_parameters(variables, case_filter=None):
    keys = list(variables.keys())
    vals = list(variables.values())
    case_parameters = list()
    for v in itertools.product(*vals):
        p = dict(zip(keys, v))
        if case_filter and not case_filter(p):
            continue
        case_parameters.append(p)
    return case_parameters

def create_cases(path_dir_cases, case_variables, prefix=case_prefix, case_filter=None):
    if not os.path.isdir(path_dir_cases):
        os.mkdir(path_dir_cases)

    all_parameters = create_case_parameters(case_variables, case_filter)
    for name_dir_case, case_parameters in labeled(all_parameters, prefix):
        path_dir_case = os.path.join(path_dir_cases, name_dir_case)
        if not os.path.isdir(path_dir_case):
            os.mkdir(path_dir_case)
        write_parameters(path_dir_case, case_parameters)
