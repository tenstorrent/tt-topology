# SPDX-FileCopyrightText: © 2024 Tenstorrent Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Tenstorrent Topology (TT-Topology) is a command line utility
to flash ethernet coordinates when multiple NB's are connected together.
"""

import sys
import time
import argparse
import pkg_resources
from pyluwen import detect_chips
from tt_tools_common.wh_reset import WHChipReset
from tt_tools_common.ui_common.themes import CMD_LINE_COLOR
from tt_topology.backend import TopoBackend, detect_current_topology
from tt_tools_common.utils_common.system_utils import (
    get_driver_version,
)
from tt_tools_common.utils_common.tools_utils import (
    get_board_type,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__,
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=pkg_resources.get_distribution("tt_topology").version,
    )
    parser.add_argument(
        "-l",
        "--layout",
        choices=["linear", "torus", "mesh"],
        default="linear",
        help="Select the layout (linear, torus, mesh). Default is linear.",
    )
    parser.add_argument(
        "-ls",
        "--list",
        action="store_true",
        default=False,
        help="List out all the boards on host with their coordinates and layout.",
    )
    parser.add_argument(
        "--log",
        metavar="log",
        nargs="?",
        const=None,
        default=None,
        help="Change filename for the topology flash log. Default: ~/tt_topology_logs/<timestamp>_log.json",
        dest="log",
    )
    parser.add_argument(
        "-p",
        "--plot_filename",
        metavar="plot",
        nargs="?",
        const=None,
        default="chip_layout.png",
        help="Change the plot of the png that will have the graph layout of the chips. Default: chip_layout.png",
        dest="plot",
    )
    return parser.parse_args()


def run_and_flash(topo_backend: TopoBackend):
    """
    Main function of tt-topology. Performs the following steps -
    1. Flash all the boards to default - set all eth port disables to 0 and reset coordinates.
    2. Issue a board level reset to apply the new flash to the chips.
    3. Generate a mapping of all possible connections and their type between the available chips.
    4. Using a graph algorithm generate coordinates for each chip based on user input.
    5. Write the new coordinates to the chips.
    6. Issue a board level reset to apply the new flash to the chips.
    7. Return a png with a graphic representation of the layout
    """
    # Store the the original eth config in the log
    topo_backend.get_eth_config_state()

    print(
        CMD_LINE_COLOR.BLUE,
        f"Starting flash on pcie chips to default state.",
        CMD_LINE_COLOR.ENDC,
    )
    # Flash to default state (nb300 - left is 0,0 and right is 1,0), then reset
    topo_backend.flash_to_default_state()
    print(
        CMD_LINE_COLOR.PURPLE,
        f"Sleeping for 15s ...",
        CMD_LINE_COLOR.ENDC,
    )
    time.sleep(15)
    print(
        CMD_LINE_COLOR.BLUE,
        f"Finished flashing pcie chips to default state.",
        CMD_LINE_COLOR.ENDC,
    )

    # Add new config to make sure flash happened correctly
    topo_backend.get_eth_config_state()

    # Reset all pci devices
    num_local_chips = len(topo_backend.devices)
    reset_obj = WHChipReset()
    pci_interfaces = list(range(num_local_chips))
    print(
        CMD_LINE_COLOR.BLUE,
        f"Initiating reset on chips at pcie interface: {pci_interfaces}",
        CMD_LINE_COLOR.ENDC,
    )
    reset_devices = reset_obj.full_lds_reset(pci_interfaces)
    print(
        CMD_LINE_COLOR.BLUE,
        f"Completed reset on {len(reset_devices)} chips",
        CMD_LINE_COLOR.ENDC,
    )

    # wait time to make sure devices enumerate
    # Detect all devices, including remote
    topo_backend.devices = detect_chips()

    print(
        CMD_LINE_COLOR.PURPLE,
        f"Post reset detected : {len(topo_backend.devices)} chips",
        CMD_LINE_COLOR.ENDC,
    )
    # check number of devices
    #  TODO: FIX THIS THIS IS FOR NBX1
    if len(topo_backend.devices) < num_local_chips * 2:
        print(
            CMD_LINE_COLOR.RED,
            f"NOT ALL BOARDS DETECTED!, detected {len(topo_backend.devices)}, expecting {num_local_chips * 2}",
            CMD_LINE_COLOR.ENDC,
        )
        sys.exit(1)

    connection_data = topo_backend.generate_connection_map()

    print(
        CMD_LINE_COLOR.BLUE,
        f"Generated connection map: ",
        CMD_LINE_COLOR.ENDC,
    )
    for _, data in connection_data.items():
        print(
            CMD_LINE_COLOR.YELLOW,
            data["id"],
            " : ",
            data["connections"],
            CMD_LINE_COLOR.ENDC,
        )

    if topo_backend.layout == "linear" or topo_backend.layout == "torus":
        coordinates_map = topo_backend.generate_coordinates_torus_or_linear(
            connection_data
        )
    elif topo_backend.layout == "mesh":
        coordinates_map = topo_backend.generate_coordinates_mesh(connection_data)
    else:
        print(
            CMD_LINE_COLOR.RED,
            "Invalid layout type!",
            CMD_LINE_COLOR.ENDC,
        )
        raise Exception("Invalid layout type!")

    print(
        CMD_LINE_COLOR.PURPLE,
        f"Coordinates for {topo_backend.layout} layout: ",
        coordinates_map,
        CMD_LINE_COLOR.ENDC,
    )

    # # Flash the boards with generated coordinates
    topo_backend.flash_to_specified_state(connection_data, coordinates_map)
    print(
        CMD_LINE_COLOR.PURPLE,
        f"Sleeping for 15s ...",
        CMD_LINE_COLOR.ENDC,
    )
    time.sleep(15)
    print(
        CMD_LINE_COLOR.BLUE,
        f"Finished flashing chips to generated coordinates.",
        CMD_LINE_COLOR.ENDC,
    )

    topo_backend.get_eth_config_state()
    pci_interfaces = list(range(num_local_chips))
    print(
        CMD_LINE_COLOR.BLUE,
        f"Initiating reset on chips at pcie interface: {pci_interfaces}",
        CMD_LINE_COLOR.ENDC,
    )
    reset_devices = reset_obj.full_lds_reset(pci_interfaces)
    chips = detect_chips()
    print(
        CMD_LINE_COLOR.BLUE,
        f"Completed reset on {len(chips)} chips",
        CMD_LINE_COLOR.ENDC,
    )
    print()

    # Generate graph visualization
    topo_backend.graph_visualization(connection_data, coordinates_map)


def main():
    """
    First entry point for TT-Topo. Detects devices and instantiates backend.
    """
    driver = get_driver_version()
    if not driver:
        print(
            CMD_LINE_COLOR.RED,
            "No Tenstorrent driver detected! Please install driver using tt-kmd: https://github.com/tenstorrent/tt-kmd ",
            CMD_LINE_COLOR.ENDC,
        )
        sys.exit(1)

    args = parse_args()
    local_only = True if not args.list else False

    try:
        devices = detect_chips(local_only=local_only)
    except Exception as e:
        print(
            CMD_LINE_COLOR.RED,
            "No Tenstorrent devices detected! Please check your hardware and try again. Exiting...",
            CMD_LINE_COLOR.ENDC,
        )
        sys.exit(1)
    if not devices:
        print(
            CMD_LINE_COLOR.RED,
            "No Tenstorrent devices detected! Please check your hardware and try again. Exiting...",
            CMD_LINE_COLOR.ENDC,
        )
        sys.exit(1)

    # Quit if any board is not nb300
    for dev in devices:
        board_type = get_board_type(str(hex(dev.board_id())).replace("0x", ""))
        if board_type != "n300":
            print(
                CMD_LINE_COLOR.RED,
                f"TT-Topology will only run on nb300 boards. Detected another board type - {board_type}. Exiting...",
                CMD_LINE_COLOR.ENDC,
            )
            sys.exit(1)

    # List devices and config and exit
    if args.list:
        detect_current_topology(devices)
        sys.exit()

    topo_backend = TopoBackend(devices, args.layout, args.plot)
    errors = False
    try:
        run_and_flash(topo_backend)
    except Exception as e:
        print(
            CMD_LINE_COLOR.RED,
            e,
            CMD_LINE_COLOR.ENDC,
        )
        topo_backend.log.errors = str(e)
        errors = True
    finally:
        # Still collect the log if something went wrong
        topo_backend.save_logs(args.log)

    # returncode 1 in case of error for detection during automation
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
