# SPDX-FileCopyrightText: © 2024 Tenstorrent Inc.
# SPDX-License-Identifier: Apache-2.0

from tt_tools_common.utils_common.tools_utils import (
    detect_chips_with_callback,
)
from tt_tools_common.ui_common.themes import CMD_LINE_COLOR
from tt_topology.ubb_topo.ubb_topology import (
    get_ubb_device_map,
    isolate_ubb,
)

def main():

    devices = detect_chips_with_callback(local_only=True, ignore_ethernet=True)
    print(
        CMD_LINE_COLOR.PURPLE,
        f"Devices on system: ",
        CMD_LINE_COLOR.ENDC,
    )
    ubb_device_map = get_ubb_device_map(devices)
    print(ubb_device_map)
    ubb_num = input("Enter UBB number to isolate (1-4): ")
    if ubb_num not in ["1", "2", "3", "4"]:
        print(
            CMD_LINE_COLOR.RED,
            f"ERROR: Invalid UBB number {ubb_num}. Must be 1-4",
            CMD_LINE_COLOR.ENDC,
        )
    else:
        isolate_ubb(ubb_num, ubb_device_map)

if __name__ == "__main__":
    main()
