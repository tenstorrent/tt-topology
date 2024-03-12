# SPDX-FileCopyrightText: © 2024 Tenstorrent Inc.
# SPDX-License-Identifier: Apache-2.0
"""Given a graph of nodes, generate a set of coordinates that makes a fully connected mesh """
import os
import networkx as nx
from collections import deque

os.environ["MPLCONFIGDIR"] = os.getcwd() + "/configs/"
import matplotlib.pyplot as plt


# Rules for mesh
# 1. Find first node with only 2 edges
# 2. L to R / R to L is always x dir
# 3. TFLY are always in the y direction


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

# Perform DFS and get the edges
dfs_edges = list(nx.dfs_edges(G, source=0))

# Draw the graph with DFS edges highlighted
pos = nx.spring_layout(G)
print(pos)


def bfs(graph, start):
    coordinates = {}
    visited = set()
    queue = deque([start])
    # First remote chip is (0,0)
    coordinates[start] = (0, 0)
    # Dictionary to keep track of parent and connection type
    parent = {start: None}
    parent_used_coord = {a: [False, False] for a in graph.keys()}
    chip_l_or_r = ["L", "R", "L", "R", "L", "R", "L", "R"]
    while queue:
        current_node = queue.popleft()
        if current_node not in visited:
            visited.add(current_node)
            print(current_node, parent[current_node])
            # Assign coordinates to the current node
            if parent[current_node] is not None:
                parent_node = parent[current_node][0]
                parent_child_direction = parent[current_node][1]
                parent_x_coord = coordinates[parent_node][0]
                parent_y_coord = coordinates[parent_node][1]
                # Tfly is always increment in Y direction
                if parent_child_direction == "T":
                    coordinates[current_node] = (parent_x_coord, parent_y_coord + 1)
                    parent_used_coord[parent_node][1] = True
                # L <-> R is always increment in X direction
                elif chip_l_or_r[current_node] != chip_l_or_r[parent_node]:
                    coordinates[current_node] = (parent_x_coord + 1, parent_y_coord)
                    parent_used_coord[parent_node][0] = True
                else:
                    # check unused direction from the parent and assign coordinates
                    # X coord is unused
                    if parent_used_coord[parent_node][0] == False:
                        coordinates[current_node] = (parent_x_coord + 1, parent_y_coord)
                        parent_used_coord[parent_node][0] = True
                    # Y is unused
                    elif parent_used_coord[parent_node][1] == False:
                        coordinates[current_node] = (parent_x_coord, parent_y_coord + 1)
                        parent_used_coord[parent_node][1] = True
                    else:
                        assert False, "No unused direction from parent! Check the graph"

            # Enqueue unvisited neighbors
            for neighbor in graph[current_node]:
                parent[neighbor[0]] = (current_node, neighbor[1])
                if neighbor[0] not in visited:
                    queue.append(neighbor[0])

    print(coordinates)
    return coordinates


# Your chip_data
chip_data = {
    0: [(1, "X"), (2, "T"), (6, "X")],
    1: [(0, "X"), (3, "T")],
    2: [(0, "T"), (3, "X"), (4, "X")],
    3: [(1, "T"), (2, "X")],
    4: [(2, "X"), (5, "X"), (6, "T")],
    5: [(4, "X"), (7, "T")],
    6: [(0, "X"), (4, "T"), (7, "X")],
    7: [(5, "T"), (6, "X")],
}

# Perform DFS starting from node 0
coords = bfs(chip_data, start=1)

labels = {}
for node in G.nodes():
    board_id = "0100014211703001"
    board_id = f"{board_id[2:4]}-{board_id[4:6]}-{board_id[6:9]}"
    labels[node] = f"NBx2 L\n{node} : {coords[node]}\n{board_id}\nPci: 0"


print(coords)
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
nx.draw_networkx_nodes(G, coords, node_size=1150, node_color="#210070", alpha=0.9)
label_options = {"fc": "white", "alpha": 1.0}
nx.draw_networkx_labels(G, pos=coords, labels=labels, font_size=7, bbox=label_options)

plt.show()
plt.savefig("chip_data.png", bbox_inches="tight")
