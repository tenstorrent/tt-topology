# SPDX-FileCopyrightText: © 2024 Tenstorrent Inc.
# SPDX-License-Identifier: Apache-2.0

from tt_tools_common.reset_common.galaxy_reset import GalaxyReset


def main():
    mobo = "mobo-ce-44"
    credo = ["6:0", "6:1", "7:0", "7:1"]
    disabled_ports = [
        "0:0",
        "0:1",
        "0:2",
        "1:0",
        "1:1",
        "1:2",
        "6:2",
        "7:2",
    ]

    mobo_dict_list = [
        {
            "nb_host_pci_idx": [0, 1, 2, 3],
            "mobo": mobo,
            "credo": credo,
            "disabled_ports": disabled_ports,
        }
    ]
    mobo_reset_obj = GalaxyReset()
    mobo_reset_obj.warm_reset_mobo(mobo_dict_list)


if __name__ == "__main__":
    main()
