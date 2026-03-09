# SPDX-FileCopyrightText: © 2024 Tenstorrent Inc.
# SPDX-License-Identifier: Apache-2.0

"""
Tenstorrent Topology (TT-Topology) is a command line utility
to flash ethernet coordinates when multiple NB's are connected together.
"""

import sys
import time
import argparse
import traceback
from importlib.metadata import version
from tt_tools_common.reset_common.wh_reset import WHChipReset
from tt_tools_common.ui_common.themes import CMD_LINE_COLOR
from tt_tools_common.utils_common.system_utils import (
    get_driver_version,
)
from tt_tools_common.utils_common.tools_utils import (
    detect_chips_with_callback,
)
from tt_tools_common.reset_common.reset_utils import (
    generate_reset_logs,
    parse_reset_input,
    ResetType,
)
from tt_topology.backend import (
    TopoBackend,
    detect_current_topology,
    get_board_type,
    ORANGE,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__,
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=version("tt_topology"),
    )
    parser.add_argument(
        "-l",
        "--layout",
        choices=["linear", "torus", "mesh", "mesh_v2", "isolated"],
        default="linear",
        help="Select the layout (linear, torus, mesh, mesh_v2, isolated). Default is linear.",
    )
    parser.add_argument(
        "-f",
        "--filename",
        metavar="filename",
        nargs="?",
        const=None,
        default=None,
        help="Change filename for test log. Default: ~/tt_smi/<timestamp>_snapshot.json",
        dest="filename",
    )
    parser.add_argument(
        "-g",
        "--generate_reset_json",
        default=False,
        action="store_true",
        help=(
            "Generate default reset json file that reset consumes. "
            "Update the generated file and use it as an input for the --reset option"
        ),
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

    parser.add_argument(
        "-r",
        "--reset",
        metavar="config.json",
        default=None,
        nargs="*",
        help=("Provide a valid reset JSON"),
        dest="reset",
    )

    return parser


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
        "Starting flash on pcie chips to default state.",
        CMD_LINE_COLOR.ENDC,
    )
    # Flash to default state (nb300 - left is 0,0 and right is 1,0), then reset
    topo_backend.flash_to_default_state()
    print(
        CMD_LINE_COLOR.PURPLE,
        "Sleeping for 15s ...",
        CMD_LINE_COLOR.ENDC,
    )
    time.sleep(15)
    print(
        CMD_LINE_COLOR.BLUE,
        "Finished flashing pcie chips to default state.",
        CMD_LINE_COLOR.ENDC,
    )

    # Reset all pci devices
    num_local_chips = len(topo_backend.devices)
    reset_obj = WHChipReset()
    pci_interfaces = [dev.get_pci_interface_id() for dev in topo_backend.devices]
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

    # Detect all devices, including remote
    topo_backend.devices = detect_chips_with_callback()

    # Add new config to make sure flash happened correctly
    topo_backend.get_eth_config_state()

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

    if topo_backend.layout == "isolated":
        print(
            CMD_LINE_COLOR.BLUE,
            f"Boards flashed to default isolated state. Exiting.",
            CMD_LINE_COLOR.ENDC,
        )
        sys.exit(0)

    connection_data = topo_backend.generate_connection_map()
    num_connections_missing = topo_backend.check_num_available_connections(
        connection_data
    )

    if num_connections_missing:
        if topo_backend.layout in ["mesh", "mesh_v2"]:
            print(
            CMD_LINE_COLOR.RED,
            f"Error: Detected {num_connections_missing} missing physical connection(s) for mesh layout! It's possible cables are loose or missing.",
            CMD_LINE_COLOR.ENDC,
            )
            sys.exit(1)
        else:
            print(
                ORANGE,
                f"Warning: Detected {num_connections_missing} missing physical connection(s) for mesh layout! It's possible cables are loose or missing.",
                CMD_LINE_COLOR.ENDC,
            )

    print(
        CMD_LINE_COLOR.BLUE,
        "Generated connection map: ",
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

    if topo_backend.layout in ["linear", "torus"]:
        coordinates_map = topo_backend.generate_coordinates_torus_or_linear(
            connection_data
        )
    elif topo_backend.layout == "mesh":
        coordinates_map = topo_backend.generate_mesh_connection_independent(connection_data)
    elif topo_backend.layout == "mesh_v2":
        coordinates_map = topo_backend.apply_mesh_v2_coordinates()
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

    # Flash the boards with generated coordinates
    topo_backend.flash_to_specified_state(connection_data, coordinates_map)
    print(
        CMD_LINE_COLOR.PURPLE,
        "Sleeping for 15s ...",
        CMD_LINE_COLOR.ENDC,
    )
    time.sleep(15)
    print(
        CMD_LINE_COLOR.BLUE,
        "Finished flashing chips to generated coordinates.",
        CMD_LINE_COLOR.ENDC,
    )

    print(
        CMD_LINE_COLOR.BLUE,
        f"Initiating reset on chips at pcie interface: {pci_interfaces}",
        CMD_LINE_COLOR.ENDC,
    )
    reset_devices = reset_obj.full_lds_reset(pci_interfaces)
    topo_backend.devices = detect_chips_with_callback()
    print(
        CMD_LINE_COLOR.BLUE,
        f"Completed reset on {len(topo_backend.devices)} chips",
        CMD_LINE_COLOR.ENDC,
    )
    print()

    # Update connection_data with new backend devices
    connection_data = topo_backend.generate_connection_map()

    # For the n300 enable multi-host mode by default.
    # Check for 8 n300 chips happens in the function
    if topo_backend.layout == "mesh_v2":
        topo_backend.flash_n300_multihost_v2(connection_data, coordinates_map)
    else:
        topo_backend.flash_n300_multihost(connection_data, coordinates_map)

    # TODO: does this need 15s sleep?
    print(
        CMD_LINE_COLOR.PURPLE,
        "Sleeping for 5s ...",
        CMD_LINE_COLOR.ENDC,
    )
    time.sleep(5)
    print(
        CMD_LINE_COLOR.BLUE,
        f"Initiating reset on chips at pcie interface: {pci_interfaces}",
        CMD_LINE_COLOR.ENDC,
    )
    reset_devices = reset_obj.full_lds_reset(pci_interfaces)
    topo_backend.devices = detect_chips_with_callback()
    print(
        CMD_LINE_COLOR.BLUE,
        f"Completed reset on {len(topo_backend.devices)} chips",
        CMD_LINE_COLOR.ENDC,
    )
    print()

    # Get the final eth config state
    topo_backend.get_eth_config_state()

    # Generate graph visualization
    topo_backend.graph_visualization(connection_data, coordinates_map)


def main():
    """
    First entry point for TT-Topo. Detects devices and instantiates backend.
    """
    parser = parse_args()
    args = parser.parse_args()

    driver = get_driver_version()
    if not driver:
        print(
            CMD_LINE_COLOR.RED,
            "No Tenstorrent driver detected! Please install driver using tt-kmd: https://github.com/tenstorrent/tt-kmd",
            CMD_LINE_COLOR.ENDC,
        )
        sys.exit(1)

    if not len(sys.argv) > 1:
        # No arguments have been provided - print help and exit
        print(
            f"{CMD_LINE_COLOR.RED}No arguments provided! Please provide the required arguments....{CMD_LINE_COLOR.ENDC}"
        )
        parser.print_usage()
        sys.exit(1)

    local_only = not args.list

    try:
        if args.list:
            # We need eth of these options to have full noc access
            devices = detect_chips_with_callback(local_only=local_only, ignore_ethernet=False)
        else:
            # Only ignore eth for pcie chip flash
            devices = detect_chips_with_callback(local_only=local_only, ignore_ethernet=True)
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

    # Warn the user if any board is not in the accepted boards list
    supported_devices = []
    unsupported_device_names = []
    for dev in devices:
        board_type = get_board_type(str(hex(dev.board_id())).replace("0x", ""))
        supported_boards = ["n300", "n150"]
        if board_type in supported_boards:
            supported_devices.append(dev)
        else:
            unsupported_device_names.append(board_type)

    # Notify the user; empty lists are falsy
    if unsupported_device_names:
        print(
            ORANGE,
            f"TT-Topology will only run on n300/n150 boards.\n",
            f"Ignoring these devices: {', '.join(unsupported_device_names)}.",
            CMD_LINE_COLOR.ENDC,
        )
        if not supported_devices:
            print(
                CMD_LINE_COLOR.RED,
                "No devices supported by TT-Topology detected. Exiting...",
                CMD_LINE_COLOR.ENDC,
            )
            sys.exit(1)
    # Proceed with only supported devices
    devices = supported_devices

    # List devices and config and exit
    if args.list:
        detect_current_topology(devices)
        sys.exit()

    if args.generate_reset_json:
        file = generate_reset_logs(devices)
        print(
            CMD_LINE_COLOR.PURPLE,
            f"Generated sample reset config file for this host: {file}",
            CMD_LINE_COLOR.ENDC,
        )
        print(
            CMD_LINE_COLOR.YELLOW,
            "Update the generated file and use it as an input for the -r/--reset option.",
            CMD_LINE_COLOR.ENDC,
        )
        sys.exit(0)

    topo_backend = TopoBackend(devices, args.layout, args.plot)
    errors = False
    try:
        run_and_flash(topo_backend)
    except Exception as e:
        print(
            CMD_LINE_COLOR.RED,
            traceback.format_exc(),
            CMD_LINE_COLOR.ENDC,
        )
        topo_backend.log.errors = str(traceback.format_exc())
        errors = True
    finally:
        # Still collect the log if something went wrong
        topo_backend.save_logs(args.log)

    # returncode 1 in case of error for detection during automation
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
