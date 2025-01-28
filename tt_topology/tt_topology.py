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
from typing import List
from tt_tools_common.reset_common.wh_reset import WHChipReset
from tt_tools_common.ui_common.themes import CMD_LINE_COLOR
from tt_tools_common.utils_common.system_utils import (
    get_driver_version,
)
from tt_tools_common.utils_common.tools_utils import (
    get_board_type,
    detect_chips_with_callback,
)
from tt_tools_common.reset_common.reset_utils import (
    generate_reset_logs,
    parse_reset_input,
)
from tt_topology.backend import (
    TopoBackend,
    TopoBackend_Octopus,
    detect_current_topology,
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
        "-o",
        "--octopus",
        action="store_true",
        default=False,
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
        type=parse_reset_input,
        metavar="0,1 ... or config.json",
        default=None,
        help=("Provide a list of mobos and their credos to reset."),
        dest="reset",
    )

    return parser


def run_and_flash(topo_backend: TopoBackend, reset_idx: List[int]):
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

    # Add new config to make sure flash happened correctly
    topo_backend.get_eth_config_state()

    # Reset all pci devices
    num_local_chips = len(topo_backend.devices)
    reset_obj = WHChipReset()
    pci_interfaces = reset_idx
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
    topo_backend.devices = detect_chips_with_callback()

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
        "Sleeping for 15s ...",
        CMD_LINE_COLOR.ENDC,
    )
    time.sleep(15)
    print(
        CMD_LINE_COLOR.BLUE,
        "Finished flashing chips to generated coordinates.",
        CMD_LINE_COLOR.ENDC,
    )

    topo_backend.get_eth_config_state()
    pci_interfaces = reset_idx
    print(
        CMD_LINE_COLOR.BLUE,
        f"Initiating reset on chips at pcie interface: {pci_interfaces}",
        CMD_LINE_COLOR.ENDC,
    )
    reset_devices = reset_obj.full_lds_reset(pci_interfaces)
    chips = detect_chips_with_callback()
    print(
        CMD_LINE_COLOR.BLUE,
        f"Completed reset on {len(chips)} chips",
        CMD_LINE_COLOR.ENDC,
    )
    print()

    # Generate graph visualization
    topo_backend.graph_visualization(connection_data, coordinates_map)


def program_galaxy(topo_backend_octo: TopoBackend_Octopus):
    """
    Main function of tt-topology for galaxy. Performs the following steps -
    1. set eth-mobo-enable on every n150
    2. program the shelf/rack
    3. program all n150s to R0, S0, X0, Y0
    4. Reset with retimer_sel and disable_sel and wait for training
    5. check QSFP link and change shelf number for each n150
    6. program the x/y coords of the local n150s
    7. reset with retimer_sel and disable_sel and wait for training, and verify all chips show up
    """
    disabled_ports_before = [
        "0:0",
        "0:1",
        "0:2",
        "1:0",
        "1:1",
        "1:2",
        "6:0",
        "6:1",
        "6:2",
        "7:0",
        "7:1",
        "7:2",
    ]

    if topo_backend_octo.mobo_dict_list is None:
        print(
            CMD_LINE_COLOR.RED,
            "No reset json file provided for octopus",
            CMD_LINE_COLOR.ENDC,
        )
        sys.exit(1)
    else:
        mobo_dict_list = topo_backend_octo.mobo_dict_list["wh_mobo_reset"]

    mobo_dict_before = []
    mobo_dict_after = []

    for item in mobo_dict_list:
        mobo_dict_before.append(
            {
                "nb_host_pci_idx": item["nb_host_pci_idx"],
                "mobo": item["mobo"],
                "credo": item["credo"],
                # disabled_ports_before always disables all by default, should exclude the specified nb->galaxy ports in the config
                "disabled_ports": list(set(disabled_ports_before) - set(item["credo"])),
            }
        )
        mobo_dict_after.append(
            {
                "nb_host_pci_idx": item["nb_host_pci_idx"],
                "mobo": item["mobo"],
                "credo": item["credo"],
                "disabled_ports": item["disabled_ports"],
            }
        )

    print("set eth-mobo-enable on every n150")
    topo_backend_octo.eth_mobo_enable()

    print("program the remote shelf/rack")
    topo_backend_octo.set_rack_shelf_remote(mobo_dict_list)

    print("program all n150s to R0, S0, X0, Y0")
    topo_backend_octo.set_initial_chip_coords()

    print("reset with retimer_sel and disable_sel and wait for training")

    topo_backend_octo.galaxy_reset(mobo_dict_before)

    print(
        "check QSFP link and change rack, shelf, x, y coordinated for each of the local n150s"
    )
    topo_backend_octo.read_remote_set_local()

    print(
        "reset with retimer_sel and disable_sel and wait for training, and verify all chips show up"
    )

    topo_backend_octo.galaxy_reset(mobo_dict_after)

    # wait time to make sure devices enumerate
    # Detect all devices, including remote
    print("detecting all local devices after reset...")
    post_reset_devices_local = detect_chips_with_callback(local_only=True)
    print("detecting all local and remote devices after reset...")
    post_reset_devices = detect_chips_with_callback(local_only=False)

    if len(topo_backend_octo.devices_local) != len(post_reset_devices_local):
        print(
            CMD_LINE_COLOR.RED,
            f"NOT ALL LOCAL BOARDS DETECTED!, detected {len(post_reset_devices_local)}, expecting {len(topo_backend_octo.devices_local)}",
            CMD_LINE_COLOR.ENDC,
        )
        sys.exit(1)

    if len(topo_backend_octo.devices_remote) * 32 != (
        len(post_reset_devices) - len(post_reset_devices_local)
    ):
        print(
            CMD_LINE_COLOR.RED,
            f"NOT ALL REMOTE BOARDS DETECTED!, detected {len(post_reset_devices)-len(post_reset_devices_local)}, expecting {len(topo_backend_octo.devices_remote)*32}",
            CMD_LINE_COLOR.ENDC,
        )
        sys.exit(1)

    print(
        CMD_LINE_COLOR.GREEN,
        "All devices detected after reset",
        CMD_LINE_COLOR.ENDC,
    )

    print()


def main():
    """
    First entry point for TT-Topo. Detects devices and instantiates backend.
    """
    driver = get_driver_version()
    if not driver:
        print(
            CMD_LINE_COLOR.RED,
            "No Tenstorrent driver detected! Please install driver using tt-kmd: https://github.com/tenstorrent/tt-kmd",
            CMD_LINE_COLOR.ENDC,
        )
        sys.exit(1)

    parser = parse_args()
    args = parser.parse_args()
    if not len(sys.argv) > 1:
        # No arguments have been provided - print help and exit
        print(
            f"{CMD_LINE_COLOR.RED}No arguments provided! Please provide the required arguments....{CMD_LINE_COLOR.ENDC}"
        )
        parser.print_usage()
        sys.exit(1)

    local_only = not args.list

    try:
        devices = detect_chips_with_callback(local_only=local_only)
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

    # Quit if any board is not in the accepted boards list
    for dev in devices:
        board_type = get_board_type(str(hex(dev.board_id())).replace("0x", ""))
        accepted_boards = ["n300", "n150", "GALAXY"]
        if board_type not in accepted_boards:
            print(
                CMD_LINE_COLOR.RED,
                f"TT-Topology will only run on n300/n150/GALAXY boards. Detected another board type - {board_type}. Exiting...",
                CMD_LINE_COLOR.ENDC,
            )
            sys.exit(1)

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

    if args.octopus:
        if args.reset is not None:
            mobo_dict_list = args.reset
        else:
            e = "Please provide a reset json file for octopus"
            print(
                CMD_LINE_COLOR.RED,
                e,
                CMD_LINE_COLOR.ENDC,
            )
            sys.exit(1)
        topo_backend_octo = TopoBackend_Octopus(devices, mobo_dict_list)
        program_galaxy(topo_backend_octo)
        sys.exit()

    else:
        topo_backend = TopoBackend(devices, args.layout, args.plot)
        errors = False
    try:
        run_and_flash(topo_backend, args.reset)
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
