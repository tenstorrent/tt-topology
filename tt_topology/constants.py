# SPDX-FileCopyrightText: © 2024 Tenstorrent Inc.
# SPDX-License-Identifier: Apache-2.0

ETH_FW_BASE_ADDR    = 0x23000
ETH_FW_VERSION_ADDR = ETH_FW_BASE_ADDR + 0x210

# Param table addresses in the SPI relevant to tt-topology
ETH_PARAM_BASE_ADDR     = 0x21100
ETH_PARAM_CHIP_COORD    = ETH_PARAM_BASE_ADDR + (0x4) * 0
ETH_PARAM_PORT_DISABLE  = ETH_PARAM_BASE_ADDR + (0x4) * 2
ETH_PARAM_MOBO_ETH_EN   = ETH_PARAM_BASE_ADDR + (0x4) * 52  # Set to 0xC3 to enable and 0 to disable
ETH_PARAM_RACK_SHELF    = ETH_PARAM_BASE_ADDR + (0x4) * 53

# Offset for params on right chip
ETH_PARAM_RIGHT_OFFSET = 0x100

# Addresses needed to read the "board_id" generated for eth fw
ETH_L1_PARAM_BASE_ADDR  = 0x1000
ETH_L1_PARAM_BOARD_TYPE = ETH_L1_PARAM_BASE_ADDR + (0x4) * 56
ETH_L1_PARAM_BOARD_ID   = ETH_L1_PARAM_BASE_ADDR + (0x4) * 59

# Addresses needd to read the connections of the chips
ETH_TEST_RESULT_BASE_ADDR           = 0x1EC0
ETH_TEST_RESULT_REMOTE_TYPE         = ETH_TEST_RESULT_BASE_ADDR + (0x4) * 72
ETH_TEST_RESULT_REMOTE_ID           = ETH_TEST_RESULT_BASE_ADDR + (0x4) * 73
ETH_TEST_RESULT_REMOTE_COORD        = ETH_TEST_RESULT_BASE_ADDR + (0x4) * 74  # 0x0000YYXX
ETH_TEST_RESULT_REMOTE_SHELF_RACK   = ETH_TEST_RESULT_BASE_ADDR + (0x4) * 75  # 0x0000SSRR
