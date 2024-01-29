# SPDX-FileCopyrightText: © 2024 Tenstorrent Inc.
# SPDX-License-Identifier: Apache-2.0
"""Given a graph of nodes, generate a set of coordinates that makes a fully connected cycle """
import os
import networkx as nx

os.environ["MPLCONFIGDIR"] = os.getcwd() + "/configs/"
import matplotlib.pyplot as plt


# Sample
chip_data = {
    0: [1, 2, 6],
    1: [0, 3],
    2: [0, 3, 4],
    3: [1, 2],
    4: [2, 5, 6],
    5: [4, 7],
    6: [0, 4, 7],
    7: [5, 6],
}

# Create a directed graph
G = nx.DiGraph(chip_data)

options = {
    "font_size": 36,
    "node_size": 3000,
    "node_color": "white",
    "edgecolors": "black",
    "linewidths": 5,
    "width": 5,
    "with_labels": True,
}
nx.draw(G, nx.spring_layout(G), **options)
plt.draw()
plt.show()
plt.savefig("chip_data.png")

# Generate a list of cycles
try:
    has_cycle = nx.simple_cycles(G)
except Exception as e:
    print("NO CYCLES DETECTED!", e)

torus_cycle = []
for i in has_cycle:
    if len(i) == len(G.nodes):
        print("Cycle detected: ", i)
        # Take the first viable cycle
        torus_cycle = i
        break

final_coord_map = {}
for idx, node in enumerate(torus_cycle):
    final_coord_map[node] = (idx, 0)

print("Final coord map: ", final_coord_map)
