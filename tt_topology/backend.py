# SPDX-FileCopyrightText: © 2024 Tenstorrent Inc.
# SPDX-License-Identifier: Apache-2.0
import os
import sys
import datetime
from pathlib import Path
import networkx as nx
from typing import List
from pyluwen import PciChip, detect_chips_fallible
from collections import deque
import matplotlib.pyplot as plt
import tt_topology.constants as constants
from tt_tools_common.ui_common.themes import CMD_LINE_COLOR
from tt_tools_common.utils_common.tools_utils import (
    init_fw_defines,
    get_board_type,
    init_logging,
)
from tt_tools_common.utils_common.system_utils import get_host_info
from tt_tools_common.reset_common.galaxy_reset import GalaxyReset
from tt_tools_common.reset_common.wh_reset import WHChipReset
from tt_tools_common.reset_common import host_reset_log
from tt_topology import log

LOG_FOLDER = os.path.expanduser("~/tt_topology_logs/")


def detect_current_topology(devices: List[PciChip]):
    """
    Print all chips on host with their coordinates.
    Decipher if the chips have been flashed in any layout based on coordinates alone.
    TODO: Add prompt to run eth-mobo-status to get a detailed view of chip layout
    """
    coord_list = []
    print(
        CMD_LINE_COLOR.PURPLE,
        "Devices on system: ",
        CMD_LINE_COLOR.ENDC,
    )
    for i, dev in enumerate(devices):
        board_id = str(hex(dev.board_id())).replace("0x", "")
        board_type = get_board_type(board_id)
        board_type = board_type + (" R" if dev.is_remote() else " L")
        coords = (
            dev.as_wh().get_local_coord().shelf_x,
            dev.as_wh().get_local_coord().shelf_y,
        )
        coord_list.append(coords)
        print(
            CMD_LINE_COLOR.BLUE,
            f"{i}: {board_type} {board_id} - {coords}",
            CMD_LINE_COLOR.ENDC,
        )

    if all(element == (0, 0) or element == (1, 0) for element in coord_list):
        print(
            CMD_LINE_COLOR.YELLOW,
            "Configuration: Not flashed into a configuration",
            CMD_LINE_COLOR.ENDC,
        )
    elif all(
        element[0] == 0 and element[1] in list(range(len(devices)))
        for element in coord_list
    ):
        print(
            CMD_LINE_COLOR.YELLOW,
            "Configuration: Linear/Torus",
            CMD_LINE_COLOR.ENDC,
        )
    elif all(
        element[0] in list(range(len(devices) // 2)) and element[1] in [0, 1]
        for element in coord_list
    ):
        print(
            CMD_LINE_COLOR.YELLOW,
            "Configuration: Mesh",
            CMD_LINE_COLOR.ENDC,
        )
    else:
        print(
            CMD_LINE_COLOR.RED,
            "Cannot comprehend configuration!",
            CMD_LINE_COLOR.ENDC,
        )


class TopoBackend:
    """
    Backend for topology tool that handles chip related functions
    """

    def __init__(
        self,
        devices: List[PciChip],
        layout: str = "linear",
        plot_filename: str = "chip_layout.png",
    ):
        self.devices = devices
        self.layout = layout
        self.plot_filename = plot_filename
        self.log = log.TTToplogyLog(
            time=datetime.datetime.now(),
            host_info=get_host_info(),
            chip_layout=layout,
            png_filename=plot_filename,
            starting_configs=[],
            post_default_flashing_configs=[],
            connection_map=[],
            coords_flash_config=[],
            errors="",
        )

    @staticmethod
    def eth_xy_decode(eth_id):
        if (eth_id % 2) == 1:
            eth_x = 1 + ((eth_id % 8) // 2)
        else:
            eth_x = 9 - ((eth_id % 8) // 2)
        if eth_id > 7:
            eth_y = 6
        else:
            eth_y = 0
        return eth_x, eth_y

    def save_logs(self, result_filename: str = None):
        time_now = datetime.datetime.now()
        date_string = time_now.strftime("%m-%d-%Y_%H:%M:%S")
        if not os.path.exists(LOG_FOLDER):
            init_logging(LOG_FOLDER)
        log_filename = f"{LOG_FOLDER}{date_string}_log.json"
        if result_filename:
            dir_path = os.path.dirname(os.path.realpath(result_filename))
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            log_filename = result_filename
        self.log.save_as_json(log_filename)
        print(
            CMD_LINE_COLOR.YELLOW,
            f"Saved json log file to {log_filename}",
            CMD_LINE_COLOR.ENDC,
        )
        return log_filename

    def get_eth_config_state(self):
        config_state = []
        config_state_log = []
        for device in self.devices:
            dev_config_log = log.ChipConfig()
            wh_chip = device.as_wh()
            fw_version = bytearray(4)
            chip_coord_l = bytearray(4)
            port_disable_l = bytearray(4)
            rack_self_l = bytearray(4)
            wh_chip.spi_read(int(constants.ETH_FW_VERSION_ADDR), fw_version)
            wh_chip.spi_read(int(constants.ETH_PARAM_CHIP_COORD), chip_coord_l)
            wh_chip.spi_read(int(constants.ETH_PARAM_PORT_DISABLE), port_disable_l)
            wh_chip.spi_read(int(constants.ETH_PARAM_RACK_SHELF), rack_self_l)
            data = {
                "wh_chip": wh_chip,
                "fw_version": hex(int.from_bytes(fw_version, "little")),
                "chip_coord_l": hex(int.from_bytes(chip_coord_l, "little")),
                "port_disable_l": hex(int.from_bytes(port_disable_l, "little")),
                "rack_shelf_l": hex(int.from_bytes(rack_self_l, "little")),
            }
            dev_config_log.board_id = str(hex(device.board_id())).replace("0x", "") + (
                " R" if device.is_remote() else " L"
            )
            dev_config_log.fw_version = data["fw_version"]
            dev_config_log.chip_coord_l = data["chip_coord_l"]
            dev_config_log.port_disable_l = data["port_disable_l"]
            dev_config_log.rack_shelf_l = data["rack_shelf_l"]

            if not device.is_remote():
                chip_coord_r = bytearray(4)
                port_disable_r = bytearray(4)
                rack_self_r = bytearray(4)
                wh_chip.spi_read(
                    int(
                        constants.ETH_PARAM_CHIP_COORD
                        + constants.ETH_PARAM_RIGHT_OFFSET
                    ),
                    chip_coord_r,
                )
                wh_chip.spi_read(
                    int(
                        constants.ETH_PARAM_PORT_DISABLE
                        + constants.ETH_PARAM_RIGHT_OFFSET
                    ),
                    port_disable_r,
                )
                wh_chip.spi_read(
                    int(
                        constants.ETH_PARAM_RACK_SHELF
                        + constants.ETH_PARAM_RIGHT_OFFSET
                    ),
                    rack_self_r,
                )
                data["chip_coord_r"] = hex(int.from_bytes(chip_coord_r, "little"))
                data["port_disable_r"] = hex(int.from_bytes(port_disable_r, "little"))
                data["rack_shelf_r"] = hex(int.from_bytes(rack_self_r, "little"))
                dev_config_log.chip_coord_r = data["chip_coord_r"]
                dev_config_log.port_disable_r = data["port_disable_r"]
                dev_config_log.rack_shelf_r = data["rack_shelf_r"]
            config_state.append(data)
            config_state_log.append(dev_config_log)

        # Verify all fws are the same
        for data in config_state:
            assert (
                data["fw_version"] == config_state[0]["fw_version"]
            ), "Firmware versions do not match"
        if not self.log.starting_configs:
            self.log.starting_configs = config_state_log
        elif not self.log.post_default_flashing_configs:
            self.log.post_default_flashing_configs = config_state_log
        else:
            self.log.final_coords_flash_config = config_state_log
        return config_state

    def flash_to_default_state(self):
        """
        Flash param table to default state
        Check if device is going to be trained
        """
        for i, device in enumerate(self.devices):
            wh_chip = device.as_wh()
            # Always flash left/local chip
            wh_chip.spi_write(
                int(constants.ETH_PARAM_CHIP_COORD),
                int(0x0).to_bytes(4, byteorder="little"),
            )
            wh_chip.spi_write(
                int(constants.ETH_PARAM_PORT_DISABLE),
                int(0x0).to_bytes(4, byteorder="little")
                # bytearray([0xFF, 0xFC, 0x00, 0x00]),
            )
            wh_chip.spi_write(
                int(constants.ETH_PARAM_RACK_SHELF),
                int(0x0).to_bytes(4, byteorder="little")
                # bytearray([0x0, 0x0, 0x0, 0x0])
            )

            # flash R chip info
            if get_board_type(str(hex(device.board_id())).replace("0x", "")) == "n300":
                wh_chip.spi_write(
                    int(
                        constants.ETH_PARAM_CHIP_COORD
                        + constants.ETH_PARAM_RIGHT_OFFSET
                    ),
                    int(0x1).to_bytes(4, byteorder="little"),
                )
                chip_coord_r = bytearray(4)
                wh_chip.spi_read(
                    int(
                        constants.ETH_PARAM_CHIP_COORD
                        + constants.ETH_PARAM_RIGHT_OFFSET
                    ),
                    chip_coord_r,
                )
                wh_chip.spi_write(
                    int(
                        constants.ETH_PARAM_PORT_DISABLE
                        + constants.ETH_PARAM_RIGHT_OFFSET
                    ),
                    int(0x0).to_bytes(4, byteorder="little")
                    # bytearray([0xFC, 0xFF, 0x0, 0x0]),
                )
                wh_chip.spi_write(
                    int(
                        constants.ETH_PARAM_RACK_SHELF
                        + constants.ETH_PARAM_RIGHT_OFFSET
                    ),
                    int(0x0).to_bytes(4, byteorder="little")
                    # bytearray([0x0, 0x0, 0x0, 0x0]),
                )
            board_id = str(hex(device.board_id())).replace("0x", "")
            # Left to right copy
            try:
                wh_chip.arc_msg(
                    init_fw_defines("wormhole", "tt_topology")[
                        "MSG_TRIGGER_SPI_COPY_LtoR"
                    ],
                    wait_for_done=True,
                    arg0=0,
                    arg1=0,
                    timeout=5,
                )
            except Exception as e:
                print(
                    CMD_LINE_COLOR.RED,
                    f"Something went wrong with L to R copy for chip {i}: {board_id}!!\nError: {e}",
                    CMD_LINE_COLOR.ENDC,
                )
                sys.exit(1)
            print(
                CMD_LINE_COLOR.GREEN,
                f"Completed default flash for board {i}: {board_id}",
                CMD_LINE_COLOR.ENDC,
            )

    def generate_connection_map(self):
        """
        Generate an map with chip data and a list of connections

        Returns:
            map of chip_data with the following information:
                "id": idx,
                "chip_obj": chip,
                "board_type": board_type,
                "board_id": board_id,
                "connections": [(neighbor_chip_id, connection_type), ...],
        """
        chip_data = {}
        log_connection_map = []
        for idx, device in enumerate(self.devices):
            chip = device.as_wh()
            board_id = str(hex(device.board_id())).replace("0x", "")
            board_type = get_board_type(board_id)

            # print(board_id, board_type)
            eth_board_type = bytearray(4)
            eth_board_id = bytearray(4)
            chip.noc_read(0, 9, 0, constants.ETH_L1_PARAM_BOARD_TYPE, eth_board_type)
            chip.noc_read(0, 9, 0, constants.ETH_L1_PARAM_BOARD_ID, eth_board_id)
            eth_board_type = int.from_bytes(eth_board_type, "little")
            eth_board_id = int.from_bytes(eth_board_id, "little")
            eth_board_info = f"{(eth_board_type << 32) | eth_board_id:016x}"

            chip_data[eth_board_info] = {
                "id": idx,
                "chip_obj": device,
                "board_type": board_type,
                "board_id": board_id,
                "connections": [],
            }
            # Log the same info for the json dump
            connection_map_log_obj = log.ConnectionMap()
            connection_map_log_obj.id = idx
            connection_map_log_obj.board_id = board_id + (
                " R" if device.is_remote() else " L"
            )
            connection_map_log_obj.board_type = board_type
            connection_map_log_obj.eth_board_info = eth_board_info
            log_connection_map.append(connection_map_log_obj)
        # Vectorized representation of the connections
        # Each chip will have a list of if indices of which chip it's connected to
        # It will also have a list of connection types - X : Regular, T : Tfly
        # Simplified example for 2 NBx2s connected with QSFP cables:
        # a: {"id": 0, connections: [(1, "X"), (2, "X")]}
        # b: {"id": 1, connections: [(0, "X"), (3, "X")]}
        # c: {"id": 2, connections: [(0, "X"), (3, "X")]}
        # d: {"id": 3, connections: [(1, "T"), (2, "X")]}
        for eth_board_info, data in chip_data.items():
            device = data["chip_obj"]
            chip = data["chip_obj"].as_wh()
            connection_map_log_obj = None
            for log_obj in log_connection_map:
                if log_obj.eth_board_info == eth_board_info:
                    connection_map_log_obj = log_obj
                    break

            # Go through all 16 ETH ports and read their remote chip ids (if applicable)
            # Use those IDs to construct the vectorized representation
            for port in range(16):
                eth_x, eth_y = self.eth_xy_decode(port)
                remote_type = bytearray(4)
                chip.noc_read(
                    0, eth_x, eth_y, constants.ETH_TEST_RESULT_REMOTE_TYPE, remote_type
                )
                remote_id = bytearray(4)
                chip.noc_read(
                    0, eth_x, eth_y, constants.ETH_TEST_RESULT_REMOTE_ID, remote_id
                )
                remote_type = int.from_bytes(remote_type, "little")
                remote_id = int.from_bytes(remote_id, "little")
                remote_info = f"{(remote_type << 32) | remote_id:016x}"
                # If there is no remote chip, continue
                if remote_info == "0" * 16:
                    continue

                # If there is a remote chip, add it to the connections list
                # if it's not already there
                remote_data = chip_data[remote_info]
                if not any(remote_data["id"] == tup[0] for tup in data["connections"]):
                    if (
                        data["board_type"] in ["n300", "n150"]
                        and port in [14, 15]
                        and not (device.is_remote())
                    ):
                        # Port 14 and 16 are Tfly ports on NB for local chips
                        data["connections"].append((remote_data["id"], "T"))
                    elif (
                        data["board_type"] in ["n300"]
                        and port in [6, 7]
                        and device.is_remote()
                    ):
                        # Port 6 and 7 are Tfly ports on NB for remote chips
                        data["connections"].append((remote_data["id"], "T"))
                    else:
                        # All other ports are regular connections
                        data["connections"].append((remote_data["id"], "X"))
                connection_map_log_obj.connections = data["connections"]

        self.log.connection_map = log_connection_map
        return chip_data

    def generate_coordinates_mesh(self, chip_data):
        """
        Generate coordinates for a fully connected topology using breadth first search
        Rules for generating BFS coordinates:
            1. Start with the first node that has 2 connections and make it (0,0)
            2. TFLY ("T") is always increment in Y direction
            3. L to R / R to L is always increment in X direction
            4. If connection type is "X" and rule 3 is not applicable, then increment in the direction that hasn't been used yet

        Returns:
            map - {chip_idx: (x_coord, y_coord), ...}
        """
        adjacency_map = {data["id"]: data["connections"] for data in chip_data.values()}
        coordinates = {}
        visited = set()
        chip_l_or_r = ["R" if chip.is_remote() else "L" for chip in self.devices]

        for chip in adjacency_map:
            if len(adjacency_map[chip]) == 2:
                start = chip
                break
        queue = deque([start])
        # First remote chip is (0,0)
        coordinates[start] = (0, 0)
        # Dictionary to keep track of parent and connection type
        parent = {start: None}
        # Keep track of which direction has been used in going from parent to current node
        parent_used_coord = {a: [False, False] for a in adjacency_map.keys()}

        while queue:
            current_node = queue.popleft()
            if current_node not in visited:
                visited.add(current_node)
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
                        if not parent_used_coord[parent_node][0]:
                            coordinates[current_node] = (
                                parent_x_coord + 1,
                                parent_y_coord,
                            )
                            parent_used_coord[parent_node][0] = True
                        # Y is unused
                        elif not parent_used_coord[parent_node][1]:
                            coordinates[current_node] = (
                                parent_x_coord,
                                parent_y_coord + 1,
                            )
                            parent_used_coord[parent_node][1] = True
                        else:
                            assert (
                                False
                            ), "No unused direction from parent! Check the graph"

                # Enqueue unvisited neighbors
                for neighbor in adjacency_map[current_node]:
                    parent[neighbor[0]] = (current_node, neighbor[1])
                    if neighbor[0] not in visited:
                        queue.append(neighbor[0])
        self.log.coordinate_map = coordinates
        return coordinates

    def generate_coordinates_torus_or_linear(self, chip_data):
        """
        Generate coordinates for torus/linear topology
        Look for the first cycle in the graph and assign coordinates to it
        In both cases the coordinates are the same.

        Returns:
            map - {chip_idx: (x_coord, y_coord), ...}
        """

        # Only taking the index from chip data, since the connection type is irrelevant
        adjacency_map = {
            data["id"]: [index[0] for index in data["connections"]]
            for data in chip_data.values()
        }
        # Create a directed graph
        G = nx.DiGraph(adjacency_map)
        # Generate a list of cycles
        try:
            has_cycle = nx.simple_cycles(G)
        except Exception as e:
            print(
                CMD_LINE_COLOR.RED,
                "There is no torus or linear connection possible with this layout!",
                e,
                CMD_LINE_COLOR.ENDC,
            )

        torus_cycle = []
        for i in has_cycle:
            if len(i) == len(G.nodes):
                # Take the first viable cycle
                torus_cycle = i
                break

        final_coord_map = {}
        #  Since x/y coordinates are the same for both torus and linear, we can just assign x = 0
        for idx, node in enumerate(torus_cycle):
            final_coord_map[node] = (0, idx)

        self.log.coordinate_map = final_coord_map

        return final_coord_map

    def flash_to_specified_state(self, chip_data, coord_map):
        """Given the chips and the coordinates assigned to them, flash the boards with the correct port disables anc coordinates"""
        connection_type = self.layout

        def get_adj_chips(cid, connection_type):
            cycle = list(coord_map.keys())
            idx = cycle.index(cid)

            if connection_type == "torus":
                next_chip = cycle[(idx + 1) % len(cycle)]
                prev_chip = cycle[idx - 1]  # chip[-1] is the last element in the list
            elif connection_type == "linear":
                next_chip = cycle[idx + 1] if idx < len(cycle) - 1 else None
                prev_chip = cycle[idx - 1] if idx > 0 else None
            return [prev_chip, next_chip]

        for cid, coord in coord_map.items():
            x, y = coord

            for _, data in chip_data.items():
                if data["id"] == cid:
                    curr_flash_data = data
                    break

            chip_to_flash = curr_flash_data["chip_obj"]
            if curr_flash_data["board_type"] in ["n300", "n150"] and not (
                chip_to_flash.is_remote()
            ):
                coord_addr = constants.ETH_PARAM_CHIP_COORD
                port_disable_addr = constants.ETH_PARAM_PORT_DISABLE

            elif chip_to_flash.is_remote():
                remote_chip_board_id = curr_flash_data["board_id"]
                # find the local chip to the remote chip
                for _, data in chip_data.items():
                    if data["board_id"] == remote_chip_board_id and (
                        not data["chip_obj"].is_remote()
                    ):
                        chip_to_flash = data["chip_obj"]
                        break

                coord_addr = (
                    constants.ETH_PARAM_CHIP_COORD + constants.ETH_PARAM_RIGHT_OFFSET
                )
                port_disable_addr = (
                    constants.ETH_PARAM_PORT_DISABLE + constants.ETH_PARAM_RIGHT_OFFSET
                )
            else:
                raise Exception("UNEXPECTED CHIP TYPE!")

            # Port disables:
            # 1. if it's a mesh, then don't disable anything
            # 2. if it's a torus or line, then disable the ports that aren't connected to the previous and next chip
            chip_to_flash = chip_to_flash.as_wh()
            if connection_type == "mesh":
                port_disable = 0x0
            else:
                port_disable = 0xFFFF

                # Get the adjacent chips
                adj_chips = get_adj_chips(cid, connection_type)

                # Go through all 16 ETH ports and read their remote chip ids (if applicable)
                # See if those IDs are in the list of adjacent chips
                for port in range(16):
                    eth_x, eth_y = self.eth_xy_decode(port)

                    # Read the remote type and idq
                    remote_type = bytearray(4)
                    curr_flash_data["chip_obj"].noc_read(
                        0,
                        eth_x,
                        eth_y,
                        constants.ETH_TEST_RESULT_REMOTE_TYPE,
                        remote_type,
                    )
                    remote_id = bytearray(4)
                    curr_flash_data["chip_obj"].noc_read(
                        0, eth_x, eth_y, constants.ETH_TEST_RESULT_REMOTE_ID, remote_id
                    )
                    remote_type = int.from_bytes(remote_type, "little")
                    remote_id = int.from_bytes(remote_id, "little")
                    remote_info = f"{(remote_type << 32) | remote_id:016x}"

                    # If there is no remote chip, continue
                    if remote_info == "0" * 16:
                        continue

                    # If the remote chip is an adjacent chip, then don't disable the port
                    remote_data = chip_data[remote_info]
                    if remote_data["id"] in adj_chips:
                        port_disable &= ~(1 << port)

            # Flash the coord and port disable
            print(
                CMD_LINE_COLOR.BLUE,
                f"Flashing {curr_flash_data['board_type']} - {curr_flash_data['board_id']} coord address : 0x{coord_addr:08x} to {x}, {y}",
                CMD_LINE_COLOR.ENDC,
            )
            print(
                CMD_LINE_COLOR.BLUE,
                f"Flashing {curr_flash_data['board_type']} - {curr_flash_data['board_id']} port disable address : 0x{port_disable_addr:08x} to {port_disable:04x}",
                CMD_LINE_COLOR.ENDC,
            )
            print()

            # TODO: make sure local chips are getting flashed twice correctly

            chip_to_flash.spi_write(coord_addr, bytearray([x, y, 0x0, 0x0]))
            chip_to_flash.spi_write(
                port_disable_addr,
                bytearray([port_disable & 0xFF, (port_disable >> 8) & 0xFF, 0x0, 0x0]),
            )
            readback_local = bytearray(4)
            readback_remote = bytearray(4)
            chip_to_flash.spi_read(coord_addr, readback_local)
            chip_to_flash.spi_read(
                port_disable_addr,
                readback_remote,
            )
        # Perform LtoR copies for nebula x2 left chips
        for _, data in chip_data.items():
            board_id = data["board_id"]
            # If the chip is a nebula x2, perform the LtoR copy
            if data["board_type"] == "n300" and not data["chip_obj"].is_remote():
                try:
                    data["chip_obj"].arc_msg(
                        init_fw_defines("wormhole", "tt_topology")[
                            "MSG_TRIGGER_SPI_COPY_LtoR"
                        ],
                        wait_for_done=True,
                        arg0=0,
                        arg1=0,
                        timeout=5,
                    )
                except Exception as e:
                    print(
                        CMD_LINE_COLOR.RED,
                        f"Something went wrong with L to R copy for chip {board_id}!!\nError: {e}",
                        CMD_LINE_COLOR.ENDC,
                    )
                    sys.exit(1)
                print(
                    CMD_LINE_COLOR.GREEN,
                    f"Completed coord flash for board {board_id}",
                    CMD_LINE_COLOR.ENDC,
                )

    def graph_visualization(self, chip_data, coordinates):
        """
        Visualize the graph
        """
        # Create a directed graph
        graph = {
            data["id"]: [index[0] for index in data["connections"]]
            for data in chip_data.values()
        }
        G = nx.DiGraph(graph)

        # Visualize graph components
        labels = {node: None for node in G.nodes()}
        for i, chip in enumerate(chip_data):
            board_id = str(chip_data[chip]["board_id"])
            pos_suffix = " R" if chip_data[chip]["chip_obj"].is_remote() else " L"
            board_type = chip_data[chip]["board_type"] + pos_suffix
            board_id = f"{board_id[8:10]}-{board_id[10:12]}-{board_id[12:15]}"
            index = chip_data[chip]["id"]
            labels[index] = f"{board_type}\n{board_id}\n{index} : {coordinates[i]}"

        # make a 2-d flat layout for linear and torus
        if self.layout == "linear" or self.layout == "torus":
            cycle = list(coordinates.keys())
            #  Generate a new graph with the given cycle
            G = nx.cycle_graph(cycle)
            num_nodes = len(cycle)
            grid_size = int(num_nodes / 2)
            graph_coords = {}
            # Assign coordinates for the first four nodes (vertical line)
            for i in range(grid_size):
                graph_coords[cycle[i]] = (i, 0)

            # Assign coordinates for the last four nodes (horizontal line)
            for i in range(grid_size, num_nodes):
                graph_coords[cycle[i]] = (num_nodes - i - 1, 1)
            #  if torus, add edge between first and last node
            if self.layout == "linear":
                G.remove_edge(cycle[0], cycle[-1])
        elif self.layout == "mesh":
            graph_coords = coordinates

        nx.draw_networkx_edges(
            G,
            pos=graph_coords,
            node_size=1300,
            node_shape="s",
            edge_color="#786bb0",
            arrows=True,
            arrowstyle="<->",
            min_source_margin=5,
            min_target_margin=5,
        )
        nx.draw_networkx_nodes(G, graph_coords, node_size=5, node_color="#210070")
        label_options = {"fc": "white", "alpha": 1.0}
        nx.draw_networkx_labels(
            G, pos=graph_coords, labels=labels, font_size=7, bbox=label_options
        )
        plt.show()
        plt.savefig(self.plot_filename)
        print(
            CMD_LINE_COLOR.PURPLE,
            f"Saved board layout to {self.plot_filename}",
            CMD_LINE_COLOR.ENDC,
        )


class TopoBackend_Octopus:
    def __init__(
        self,
        devices: List[PciChip],
        mobo_dict_list: List[dict],
    ):
        self.devices_local = devices
        self.devices_remote = [
            entry["mobo"] for entry in mobo_dict_list["wh_mobo_reset"]
        ]
        self.mobo_dict_list = mobo_dict_list

    def eth_mobo_enable(self):
        """
        Set eth-mobo-enable on every n150
        """
        for device in self.devices_local:
            device = device.as_wh()
            device.spi_write(
                int(constants.ETH_PARAM_MOBO_ETH_EN),
                int(0xC3).to_bytes(4, byteorder="little"),
            )

    def set_rack_shelf_remote(self, mobo_dict):
        mobo_list = [entry["mobo"] for entry in mobo_dict]
        galaxy_reset_obj = GalaxyReset()
        for i, mobo in enumerate(mobo_list):
            cmd = "rackshelf"
            data = {"rack": 0, "shelf": i + 1}
            galaxy_reset_obj.server_communication(
                post=True, mobo=mobo, command=cmd, data=data
            )

    def set_initial_chip_coords(self):
        """
        Setup the initial chip coordinated to be all R0, S0, X0, Y0
        """
        xy_addr = constants.ETH_PARAM_CHIP_COORD
        rack_shelf_addr = constants.ETH_PARAM_RACK_SHELF

        for device in self.devices_local:
            device = device.as_wh()
            device.spi_write(int(xy_addr), bytearray([0x0, 0x0, 0x0, 0x0]))
            device.spi_write(int(rack_shelf_addr), bytearray([0x0, 0x0, 0x0, 0x0]))

    def galaxy_reset(self, mobo_dict):
        """
        Reset all galaxies
        """
        mobo_reset_obj = GalaxyReset()
        mobo_reset_obj.warm_reset_mobo(mobo_dict)

        chips = detect_chips_fallible(local_only=True, noc_safe=False)
        for device in chips:
            device.init()

    def read_remote_set_local(self):
        """
        Based on the remote coordinates, set the local coordinates
        The n150s connected to shelf 1 in a TGG should stay shelf 0
        The n150s connected to shelf 2 in a TGG should become shelf 3

        On each shelf for the n150s, the y coordinates should be set to 0,1,2,3 based on
        where they connect to on the galaxy
        """
        xy_addr = constants.ETH_PARAM_CHIP_COORD
        shelf_rack_addr = constants.ETH_PARAM_RACK_SHELF

        coord_map = {}
        for i, device in enumerate(self.devices_local):
            device = device.as_wh()
            neighbours = device.get_neighbouring_chips()

            if len(neighbours) > 0:
                remote_shelf = neighbours[0].eth_addr.rack_y
                remote_x = neighbours[0].eth_addr.shelf_x
                remote_y = neighbours[0].eth_addr.shelf_y
            else:
                print("no neighbours found")
                continue

            if remote_shelf not in coord_map:
                coord_map[remote_shelf] = {}

            coord_map[remote_shelf][i] = (remote_x, remote_y)

        for remote_shelf, remote_coord_map in coord_map.items():
            # For all n150s connected to each remote shelf, sort them based on the remote x/y coordinate
            # Then assign the local x/y coordinate based on the sorted order
            sorted_coord_map = sorted(remote_coord_map.items(), key=lambda x: x[1])

            if remote_shelf == 2:
                nb_shelf = 3
            elif remote_shelf == 1:
                nb_shelf = 0
            else:
                print("Invalid remote shelf")
                sys.exit(1)
            shelf_rack = (nb_shelf << 8) | 0 # Set rack to 0 for now

            for i, (idx, _) in enumerate(sorted_coord_map):
                device = self.devices_local[idx].as_wh()

                xy = (i << 8) | 0
                device.spi_write(int(xy_addr), int(xy).to_bytes(4, byteorder="little"))
                device.spi_write(int(shelf_rack_addr), int(shelf_rack).to_bytes(4, byteorder="little"))
