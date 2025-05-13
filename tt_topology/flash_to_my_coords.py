from tt_tools_common.utils_common.tools_utils import (
    get_board_type,
    detect_chips_with_callback,
    init_fw_defines,
)
import constants
import sys
from tt_tools_common.ui_common.themes import CMD_LINE_COLOR
# import backend

def hex_to_bytearray(value):
    # Make sure it's a 16-bit value
    value &= 0xFFFF
    high_byte = (value >> 8) & 0xFF
    low_byte = value & 0xFF
    return bytearray([high_byte, low_byte, 0x00, 0x00])

def generate_port_disble_mask(disable_qsfp: bool = False, disable_tfly: bool = False, is_remote: bool = False) -> int:
    """
    Generate the port disable mask for the chip
    """
    # little endian
    # port              7654 3210
    # disable 0000 0000 1100 0011
    # L chip:
    #  QSFP ports - 0,1 & 6,7 : 0xC300 = 1100 0011 0000 0000
    #  TFly ports - 14, 15 : 0x0003 = 0000 0000 0000 0011
    #  L <-> R ports = 8,9 : 0x0300 = 0000 0000 1100 0000

    # R chip:
    #  QSFP ports - N/A
    #  TFly ports - 6, 7 : 0x0300 = 0000 0011 0000 0000
    #  L <-> R ports = 0,1 : 0xC000 = 1100 0000 0000 0000

    port_disable_mask = 0x0000
    # Local chip
    if not is_remote:
        if disable_qsfp:
            # Disable QSFP ports
            port_disable_mask = port_disable_mask | 0xC300
        if disable_tfly:
            # Disable TFly ports
            port_disable_mask = port_disable_mask | 0x0003
        return hex_to_bytearray(port_disable_mask)
    # Remote chip
    else:
        if disable_qsfp:
            Exception("QSFP ports are not available on remote chip")
        if disable_tfly:
            # Disable TFly ports
            port_disable_mask = port_disable_mask | 0x0300
        return hex_to_bytearray(port_disable_mask)



def main():
    devices = detect_chips_with_callback(local_only=True, ignore_ethernet=True)

    if not devices:
        print("No TT chips detected.")
        return

    print("Detected devices:")
    local_devs = []
    for i, device in enumerate(devices):
        print(i, device, device.is_remote())
        if not device.is_remote():
            local_devs.append(device)

    port_disable_l = generate_port_disble_mask(
        disable_qsfp=True, disable_tfly=False, is_remote=False
    )
    port_disable_r = generate_port_disble_mask(
        disable_qsfp=False, disable_tfly=False, is_remote=True
    )
    flash_to_coords(local_devs[0], 1, 0, 0, 0, port_disable_l, port_disable_r)
    flash_to_coords(local_devs[1], 1, 1, 0, 1, port_disable_l, port_disable_r)

    hello = generate_port_disble_mask(
        disable_qsfp=True, disable_tfly=False, is_remote=False)
    print(f"Port disable mask:  0x{hello:04x}")
    # Perform LtoR copies for nebula x2 left chips
    for i, device in enumerate(devices):
        if not device.is_remote():
            try:
                device.arc_msg(
                       0x50,
                        wait_for_done=True,
                        arg0=0,
                        arg1=0,
                        timeout=5,)
            except Exception as e:
                print(f"Something went wrong with L to R copy {e}")


def flash_to_coords(device, x_coord_l, y_coord_l, x_coord_r, y_coord_r, port_disable_mask_l, port_disable_mask_r):
    """
    Flash param table to default state
    Check if device is going to be trained
    """
    wh_chip = device.as_wh()
    # Always flash left/local chip
    print(
        CMD_LINE_COLOR.BLUE,
        f"SPI Write L ETH_PARAM_CHIP_COORD: Address = 0x{constants.ETH_PARAM_CHIP_COORD:08x}, Value = 0x{0x0:08x}",
        CMD_LINE_COLOR.ENDC,
    )
    print()
    wh_chip.spi_write(
        int(constants.ETH_PARAM_CHIP_COORD),
        bytearray([x_coord_l, y_coord_l, 0x0, 0x0]),
    )

    chip_coord_l = bytearray(4)

    wh_chip.spi_read(
        int(
            constants.ETH_PARAM_CHIP_COORD
        ),
        chip_coord_l,
    )
    print("Readback L chip coord: ", chip_coord_l)
    # Convert port_disable_mask_l to bytearray and write to SPI
    wh_chip.spi_write(
        int(constants.ETH_PARAM_PORT_DISABLE),
        port_disable_mask_l,
    )
    print(
    CMD_LINE_COLOR.BLUE,
    f"SPI Write L ETH_PARAM_RACK_SHELF: Address = 0x{constants.ETH_PARAM_RACK_SHELF:08x}, Value = 0x{0}",
    CMD_LINE_COLOR.ENDC,
    )
    wh_chip.spi_write(
        int(constants.ETH_PARAM_RACK_SHELF),
        port_disable_mask_r
    )

    # flash R chip info
    print("Right chip flashing")
    print(
    CMD_LINE_COLOR.BLUE,
    f"SPI Write L ETH_PARAM_CHIP_COORD + ETH_PARAM_RIGHT_OFFSET : Address = 0x{(constants.ETH_PARAM_CHIP_COORD + constants.ETH_PARAM_RIGHT_OFFSET):08x}, Value = 0x{1}",
    CMD_LINE_COLOR.ENDC,
    )
    wh_chip.spi_write(
        int(
            constants.ETH_PARAM_CHIP_COORD
            + constants.ETH_PARAM_RIGHT_OFFSET
        ),
        # int(0x1).to_bytes(4, byteorder="little"),
        bytearray([x_coord_r, y_coord_r, 0x0, 0x0]),
    )
    chip_coord_r = bytearray(4)

    wh_chip.spi_read(
        int(
            constants.ETH_PARAM_CHIP_COORD
            + constants.ETH_PARAM_RIGHT_OFFSET
        ),
        chip_coord_r,
    )
    print("Readback R chip coord: ", chip_coord_r)
    # If in isolated mode, set ethernet port to disabled
    print(
    CMD_LINE_COLOR.BLUE,
    f"SPI Write L ETH_PARAM_PORT_DISABLE + ETH_PARAM_RIGHT_OFFSET : Address = 0x{(constants.ETH_PARAM_PORT_DISABLE + constants.ETH_PARAM_RIGHT_OFFSET):08x}",
    CMD_LINE_COLOR.ENDC,
    )
    wh_chip.spi_write(
        int(
            constants.ETH_PARAM_PORT_DISABLE
            + constants.ETH_PARAM_RIGHT_OFFSET
        ),
        # int(0x0).to_bytes(4, byteorder="little"),
        bytearray([0x00, 0x00, 0x00, 0x00]),
    )
    board_id = str(hex(device.board_id())).replace("0x", "")
    # Left to right copy
    print("DO L to R COPY")
    try:
        device.arc_msg(
                0x50,
                wait_for_done=True,
                arg0=0,
                arg1=0,
                timeout=5,)
    except Exception as e:
        print(
            CMD_LINE_COLOR.RED,
            f"Something went wrong with L to R copy for chip {i}: {board_id}!!\nError: {e}",
            CMD_LINE_COLOR.ENDC,
        )
        sys.exit(1)
    print(
        CMD_LINE_COLOR.GREEN,
        f"Completed default flash for board {board_id}",
        CMD_LINE_COLOR.ENDC,
    )

if __name__ == "__main__":
    main()