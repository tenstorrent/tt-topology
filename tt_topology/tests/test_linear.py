# SPDX-FileCopyrightText: © 2024 Tenstorrent Inc.
# SPDX-License-Identifier: Apache-2.0
"""Given a graph of nodes, generate a set of coordinates that makes a fully connected cycle """
import os
import networkx as nx

os.environ["MPLCONFIGDIR"] = os.getcwd() + "/configs/"
import matplotlib.pyplot as plt

graph = {
    0: [3, 4, 1],
    1: [2, 5, 0],
    2: [1, 6, 3],
    3: [0, 7, 2],
    4: [0, 5],
    5: [1, 4],
    6: [2, 7],
    7: [3, 6],
}

coordinates = {
    0: (0, 0),
    3: (1, 0),
    7: (2, 0),
    6: (3, 0),
    2: (4, 0),
    1: (5, 0),
    5: (6, 0),
    4: (7, 0),
}


# Create a directed graph
G = nx.DiGraph(graph)

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

coords = final_coord_map

labels = {}
for node in G.nodes():
    board_id = "0100014211703001"
    board_id = f"{board_id[2:4]}-{board_id[4:6]}-{board_id[6:9]}"
    labels[node] = f"NBx2 L\n{node} : {coords[node]}\n{board_id}\nPci: 0"

cycle = [0, 1, 3, 2, 4, 5, 7, 6]
coord = {}
# Calculate the number of nodes in the cycle
num_nodes = len(cycle)

# Determine the size of the grid
grid_size = int(num_nodes / 2)

# Initialize coordinates dictionary
coords = {}

# Assign coordinates for the first four nodes (vertical line)
for i in range(grid_size):
    coords[cycle[i]] = (i, 0)

# Assign coordinates for the last four nodes (horizontal line)
for i in range(grid_size, num_nodes):
    coords[cycle[i]] = (num_nodes - i - 1, 1)


ad_list = {
    0: [1],
    1: [0, 3],
    2: [3, 4],
    3: [1, 2],
    4: [2, 5],
    5: [4, 7],
    6: [7],
    7: [5, 6],
}


G = nx.DiGraph(ad_list)
print(coords)

# nx.draw_spring(G)
G.add_edge(cycle[0], cycle[-1])

nx.draw_networkx_edges(
    G,
    pos=coords,
    node_size=1150,
    node_shape="s",
    edge_color="#786bb0",
    arrows=True,
    arrowstyle="<->",
    min_source_margin=5,
    min_target_margin=5,
)
nx.draw_networkx_nodes(G, coords, node_size=5, node_color="#210070")
label_options = {"fc": "white", "alpha": 1.0}
nx.draw_networkx_labels(G, pos=coords, labels=labels, font_size=7, bbox=label_options)

plt.show()
plt.savefig("chip_data.png", bbox_inches="tight")
