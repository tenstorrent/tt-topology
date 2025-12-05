# SPDX-FileCopyrightText: © 2024 Tenstorrent Inc.
# SPDX-License-Identifier: Apache-2.0
from tt_tools_common.ui_common.themes import CMD_LINE_COLOR
from tt_tools_common.utils_common.tools_utils import (
    detect_chips_with_callback,
)
from tt_topology.backend import get_board_type


def main():
    devices = detect_chips_with_callback()
    coord_list = []
    print(
        CMD_LINE_COLOR.PURPLE,
        f"Devices on system: ",
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

    if all(element == (0, 0) or element == (0, 1) for element in coord_list):
        print(
            CMD_LINE_COLOR.YELLOW,
            f"Configuration: Not flashed into a configuration",
            CMD_LINE_COLOR.ENDC,
        )
    elif all(
        element[0] == 0 and element[1] in list(range(len(devices)))
        for element in coord_list
    ):
        print(
            CMD_LINE_COLOR.YELLOW,
            f"Configuration: Linear/Torus",
            CMD_LINE_COLOR.ENDC,
        )

    elif (
        element[0] in list(range(len(devices) / 2)) and element[1] in [0, 1]
        for element in coord_list
    ):
        print(
            CMD_LINE_COLOR.YELLOW,
            f"Configuration: Mesh",
            CMD_LINE_COLOR.ENDC,
        )
    else:
        print(
            CMD_LINE_COLOR.RED,
            f"Cannot comprehend configuration!",
            CMD_LINE_COLOR.ENDC,
        )


if __name__ == "__main__":
    main()
