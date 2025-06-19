from collections import deque
import sys

def assign_mesh_coordinates(adj_list):
    # If bigger mesh - start with first node that has just 2 neighbours
    if len(adj_list.keys()) == 8:
        start_node = next(node for node, neighbors in adj_list.items() if len(neighbors) == 2)
        coordinates = {start_node: (0, 0)}
        visited = {start_node}
        queue = deque([start_node])
    else:
        coordinates = {0: (0, 0)}
        visited = {0}
        queue = deque([0])

    while queue:
        u = queue.popleft()

        for v in adj_list[u]:
            if v not in visited:
                print("u: ", u, " v not visited : ", v)
                print("coordinates: ", coordinates)
                # Try to assign coordinates to v based on u's coordinates
                # Choose a direction that is consistent with other neighbors of v
                # Here, we prioritize directions that align with the grid
                # For simplicity, we can try right, up, left, down in order
                for dx, dy in [(1, 0), (0, 1), (-1, 0), (0, -1)]:
                    candidate = (coordinates[u][0] + dx, coordinates[u][1] + dy)
                    print("candidate: ", candidate)
                    # Check if this candidate is already assigned to another node
                    if candidate in coordinates.values():
                        print(f"Candidate {candidate} already assigned to another node.")
                        consistent = False
                        continue
                    # Check if this candidate is consistent with v's other assigned neighbors
                    consistent = True
                    for neighbor in adj_list[v]:
                        # If the neighbor has coordinates assigned, check consistency
                        if neighbor in coordinates:
                            nx, ny = coordinates[neighbor]
                            if not ((abs(nx - candidate[0]) == 1 and ny == candidate[1]) or \
                                    (abs(ny - candidate[1]) == 1 and nx == candidate[0])):
                                consistent = False
                                print(f"Inconsistent candidate {candidate} for node {v} with neighbor {neighbor} at {coordinates[neighbor]}")
                                break
                    # Ensure coordinates never go into the negative
                    if candidate[0] < 0 or candidate[1] < 0:
                        consistent = False
                        print(f"Candidate {candidate} has negative coordinates, skipping.")
                    if consistent:
                        coordinates[v] = candidate
                        visited.add(v)
                        queue.append(v)
                        break
                else:
                    print(f"Could not assign consistent coordinates to node {v}")
                    sys.exit(1)

    return coordinates

def main():
    # Example adjacency list for a mesh
    adj_list_2x2 = {
        0  :  [1,2],
        1  :  [0,3],
        2  :  [0,3],
        3  :  [1,2],
    }

    adj_list_2x4 = {
        0: [3, 4, 1],
        1: [2, 5, 0],
        2: [1, 6, 3],
        3: [0, 7, 2],
        4: [0, 5],
        5: [1, 4],
        6: [2, 7],
        7: [3, 6]
    }
    print("coordinates for 2x2 mesh:")
    coordinates = assign_mesh_coordinates(adj_list_2x2)
    print("Assigned Coordinates:")
    for node, coord in coordinates.items():
        print(f"Node {node}: {coord}")
    print()
    print("\ncoordinates for 2x4 mesh:")
    coordinates = assign_mesh_coordinates(adj_list_2x4)
    print("Assigned Coordinates:")
    for node, coord in coordinates.items():
        print(f"Node {node}: {coord}")

if __name__ == "__main__":
    main()