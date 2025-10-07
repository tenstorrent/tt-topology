# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: © 2024 Tenstorrent Inc.

import tt_topology.constants as constants
from tt_tools_common.ui_common.themes import CMD_LINE_COLOR

def flash_asic(dev, addr, data):
    """
    Flash the ASIC with the given data at the specified address.
    """
    print(
        CMD_LINE_COLOR.PURPLE,
        f"Flashing ASIC {dev.get_pci_bdf()} at address {hex(addr)} with data: {data.hex()}",
        CMD_LINE_COLOR.ENDC,
    )
    try:
        dev.as_wh().spi_write(addr, data)
    except Exception as e:
        print(
            CMD_LINE_COLOR.RED,
            f"Error flashing ASIC {dev.get_pci_bdf()} at address {hex(addr)}: {e}",
            CMD_LINE_COLOR.ENDC,
        )
        return
    print(
        CMD_LINE_COLOR.GREEN,
        "Flash completed successfully.",
        CMD_LINE_COLOR.ENDC,
    )

def generate_port_disable_mask(
    disable_3_0: bool = False,
    disable_7_4: bool = False,
    disable_11_8: bool = False,
    disable_15_12: bool = False,
    ) -> int:
    """
    Generate the port disable mask for the chip
    """
    # little endian
    # disableflags: 0000 0000 0000 0000

    # connections
    # [3:0] - 0000 0000 0000 1111: 0x000F
    # [7:4] - 0000 0000 1111 0000 : 0x00F0
    # [11:8] - 0000 1111 0000 0000 : 0x0F00
    # [15:12] - 1111 0000 0000 0000  : 0xF000

    port_disable_mask = 0x0000
    # Local chip
    if disable_3_0:
        # Disable ports 0, 1, 2, 3
        port_disable_mask = port_disable_mask | 0x000F
    if disable_7_4:
        # Disable ports 4, 5, 6, 7
        port_disable_mask = port_disable_mask | 0x00F0
    if disable_11_8:
        # Disable ports 8, 9, 10, 11
        port_disable_mask = port_disable_mask | 0x0F00
    if disable_15_12:
        # Disable ports 12, 13, 14, 15
        port_disable_mask = port_disable_mask | 0xF000

    val = port_disable_mask.to_bytes(4, byteorder="little")

    return val

def get_ubb_device_map(devices):
    """
    Use the pcie bus ID to map all the asics to their respective UBBs.
    Also map the asic number to the device object.

    Return type: {ubb_num: {asic_num, device, ...}}
    """
    # Add warning that this cannot be run in a VM, as the pcie bus IDs will be different
    # and the mapping will be incorrect.
    print(
        CMD_LINE_COLOR.YELLOW,
        f"WARNING: This script should not be run in a VM or Docker as the PCIe bus IDs may be different!!",
        CMD_LINE_COLOR.ENDC,
    )
    ubb_map = {1: {}, 2: {}, 3: {}, 4: {}}
    for _, dev in enumerate(devices):
        bdf_parts = dev.get_pci_bdf().split(":")
        ubb_chip = constants.UBB_PCIE_MAPPING.get(bdf_parts[1][0])
        asic_num = int(bdf_parts[1][1])
        ubb_map[ubb_chip][asic_num] = dev

    # If map is empty, then its not a UBB or it is in a VM
    if not any(ubb_map.values()):
        print(
            CMD_LINE_COLOR.RED,
            f"WARNING: No UBB devices found. Are you running in a VM or Docker?",
            CMD_LINE_COLOR.ENDC,
        )
    return ubb_map

def isolate_ubb(ubb_num, ubb_device_map):
    """
    Given a UBB, flash all asics to disable external eth connections.
    UBB Asic port layout:

        +-------[7:4]-------+
        |                   |
        |                   |
    [3:0]        ASIC       [15:12]
        |                   |
        |                   |
        +------[11:8]-------+

    In each UBB layout, the ASICs are arranged as follows:

    ASIC numbers in each UBB:
    +-------+
    | 1 | 5 |
    +-------+
    | 2 | 6 |
    +-------+
    | 3 | 7 |
    +-------+
    | 4 | 8 |
    +-------+

    Isolating UBB means disabling the following connections on each asic.

    asic 1: disable 3_0, 7_4            asic 5: disable 7_4, 15_12
    asic 2: disable 3_0                 asic 6: disable 15_12
    asic 3: disable 3_0                 asic 7: disable 15_12
    asic 4: disable 3_0, 11_8           asic 8: disable 15_12, 11_8

    """
    flash_asic(
        dev=ubb_device_map[ubb_num].get(1),
        addr=constants.ETH_PARAM_PORT_DISABLE,
        data= generate_port_disable_mask(disable_3_0=True, disable_7_4=True,),
    )
    flash_asic(
        dev=ubb_device_map[ubb_num].get(2),
        addr=constants.ETH_PARAM_PORT_DISABLE,
        data=generate_port_disable_mask(disable_3_0=True),
    )
    flash_asic(
        dev=ubb_device_map[ubb_num].get(3),
        addr=constants.ETH_PARAM_PORT_DISABLE,
        data=generate_port_disable_mask(disable_3_0=True),
    )
    flash_asic(
        dev=ubb_device_map[ubb_num].get(4),
        addr=constants.ETH_PARAM_PORT_DISABLE,
        data=generate_port_disable_mask(disable_3_0=True, disable_11_8=True),
    )
    flash_asic(
        dev=ubb_device_map[ubb_num].get(5),
        addr=constants.ETH_PARAM_PORT_DISABLE,
        data=generate_port_disable_mask(disable_7_4=True, disable_15_12=True),
    )
    flash_asic(
        dev=ubb_device_map[ubb_num].get(6),
        addr=constants.ETH_PARAM_PORT_DISABLE,
        data=generate_port_disable_mask(disable_15_12=True),
    )
    flash_asic(
        dev=ubb_device_map[ubb_num].get(7),
        addr=constants.ETH_PARAM_PORT_DISABLE,
        data=generate_port_disable_mask(disable_15_12=True),
    )
    flash_asic(
        dev=ubb_device_map[ubb_num].get(8),
        addr=constants.ETH_PARAM_PORT_DISABLE,
        data=generate_port_disable_mask(disable_15_12=True, disable_11_8=True),
    )
