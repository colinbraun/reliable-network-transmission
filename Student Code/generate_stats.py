import os
import re
import numpy as np

def get_value(lines, value_name):
    for line in lines:
        if value_name in line:
            return float(re.findall("[0-9]+\.?[0-9]*", line)[0])

goodputs = []
overheads = []
for filename in os.listdir("results"):
    # print(f"Processing {filename}")
    with open(f"results/{filename}", 'r') as f:
        lines = f.readlines()
        overhead_bytes = get_value(lines, "Overhead")
        total_bytes_sent = get_value(lines, "Total Bytes Transmitted")
        overheads.append(overhead_bytes/total_bytes_sent)
        goodputs.append(get_value(lines, "Goodput"))

print(f"Goodputs: {goodputs}")
print(f"Overheads: {overheads}\n")
print(f"Goodput Mean[std]: {np.average(goodputs)}[{np.std(goodputs)}]") 
print(f"Overheads Mean[std]: {np.average(overheads)}[{np.std(overheads)}]") 
