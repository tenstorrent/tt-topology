# TT-Topology

Tenstorrent Topology (TT-Topology) is a command line utility
used to flash multiple NB cards on a system to use specific eth routing configurations.

It curretly supports three configurtions - mesh, linear and torus

## Official Repository

[https://github.com/tenstorrent/tt-topology/](https://github.com/tenstorrent/tt-topology/)

# Warning
tt-topology is not applicable on the following:
- BH pcie cards
- WH 6U Galaxy systems
- BH 6U Galaxy systems
The tool will error out if used with unsupported baords

# Getting started
Build and editing instruction are as follows -

## Building from Git

Install and source rust for the luwen library
```
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
```

## Optional
Generate and source a python environment.  This is useful not only to isolate
your environment, but potentially easier to debug and use.  This environment
can be shared if you want to use a single environment for all your Tenstorrent
tools

```
python3 -m venv .venv
source .venv/bin/activate
```
## Required

Install tt-topology - clone the repo, enter the folder and pip install
```
git clone https://github.com/tenstorrent/tt-topology.git
cd tt-topology
pip3 install --upgrade pip
pip3 install .
```

## Optional - for TT-Topology developers

Generate and source a python3 environment
```
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pre-commit
```

For users who would like to edit the code without re-building, install SMI in editable mode.
```
pip install --editable .
```
Recommended: install the pre-commit hooks so there is auto formatting for all files on committing.
```
pre-commit install
```

# Usage

Command line arguments
```
usage: tt-topology [-h] [-v] [-l {linear,torus,mesh,isolated}] [-o] [-f [filename]] [-g] [-ls] [--log [log]] [-p [plot]] [-r [config.json ...]]

Tenstorrent Topology (TT-Topology) is a command line utility to flash ethernet coordinates when multiple NB's are connected together.

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -l {linear,torus,mesh,isolated}, --layout {linear,torus,mesh,isolated}
                        Select the layout (linear, torus, mesh, isolated). Default is linear.
  -o, --octopus
  -f [filename], --filename [filename]
                        Change filename for test log. Default: ~/tt_smi/<timestamp>_snapshot.json
  -g, --generate_reset_json
                        Generate default reset json file that reset consumes. Update the generated file and use it as an input for the --reset option
  -ls, --list           List out all the boards on host with their coordinates and layout.
  --log [log]           Change filename for the topology flash log. Default: ~/tt_topology_logs/<timestamp>_log.json
  -p [plot], --plot_filename [plot]
                        Change the plot of the png that will have the graph layout of the chips. Default: chip_layout.png
  -r [config.json ...], --reset [config.json ...]
                        Provide a valid reset JSON

```
# TT-Topology Procedure

TT-Topology does the following when calculating and flashing the coordinates -
1. Flash all the boards to default - set all eth port disables to 0 and reset coordinates to (0,0) for local chips and (1,0) for n300 remote chips.
2. Issue a board level reset to apply the new flash to the chips.
3. Generate a mapping of all possible connections and their type between the available chips.
4. Using a graph algorithm generate coordinates for each chip based on user input. These layouts are discussed in detail in the sections below.
5. Write the new coordinates to the chips.
6. Issue a board level reset to apply the new flash to the chips.
7. Return a png with a graphic representation of the layout and a .json log file with details of the above steps.


# Chip layouts

TT-topology can be used to flash one of the three chip layouts - mesh, linear and torus.

## Mesh

In the mesh layout is a trivalent graph where each node can have a max of 3 connection. A BFS algorithm is used to assign the coordinates.
Command to generate a mesh layout
```
$ tt-topology -l mesh -p mesh_layout.png
```
For a host with 2 n300 cards and 4 n300 cards, the command will generate a layouts that look as follows -

<p align="center">
  <img src="images/mesh_layout_2x4.png?raw=true" alt="mesh_layout_2x4" width="47%"/>
  &nbsp; &nbsp;
  <img src="images/mesh_layout.png?raw=true" alt="mesh_layout_2x8" width="47%"/>
</p>

## Linear

The linear layout, as the name suggests is a layout where all chips are connected by a single line. The coordinates are assigned by finding a cycle in the graph and then assigning coordinates in order.
Command to generate a linear layout
```
$ tt-topology -l linear -f linear_layout.png
```
For a host with 2 n300 cards and 4 n300 cards, the command will generate a layouts that look as follows -

<p align="center">
  <img src="images/linear_layout_2x4.png?raw=true" alt="linear_layout_2x4" width="47%"/>
  &nbsp; &nbsp;
  <img src="images/linear_layout.png?raw=true" alt="linear_layout_2x8" width="47%"/>
</p>


## Torus

The torus layout is a cyclic graph where all chips have a single line connecting all nodes.
The coordinates are assigned by finding a cycle in the graph and then assigning coordinates in order.
Command to generate a torus layout
```
$ tt-topology -l torus -p torus_layout.png
```
For a host with four n300 cards, the command will generate a layout that looks as follows

<p align="center">
  <img src="images/torus_layout_2x4.png?raw=true" alt="torus_layout_2x4" width="47%"/>
  &nbsp; &nbsp;
  <img src="images/torus_layout.png?raw=true" alt="torus_layout_2x8" width="47%"/>
</p>

# Octopus(TGG/TG) Support in TT-Topology
- TGG setting: 8 n150s connected to 2 galaxies
- TG setting: 4 n150s connected to 1 galaxy

## Usage
1. Generate a default mobo reset json file saved at ```~/.config/tenstorrent/reset_config.json``` by running the following command

    ```
    $ tt-topology -g
    ```

2. Fill in *"mobo"*, *"credo"*, and *"disabled_ports"* under *"wh_mobo_reset"*

    Here is an example of what your reset_config.json file may look like:
    ```
    {
        "time": "2024-03-06T20:12:27.640859",
        "host_name": "yyz-lab-212",
        "gs_tensix_reset": {
            "pci_index": []
        },
        "wh_link_reset": {
            "pci_index": [
                0,
                1,
                2,
                3
            ]
        },
        "re_init_devices": true,
        "wh_mobo_reset": [
            {
                "nb_host_pci_idx": [
                    0,
                    1,
                    2,
                    3
                  ],
                "mobo": "mobo-ce-44",
                "credo": [
                    "6:0",
                    "6:1",
                    "7:0",
                    "7:1"
                ],
                "disabled_ports": [
                    "0:2",
                    "1:2",
                    "6:2",
                    "7:2"
                ]
            }
        ]
    }
    ```

3. Flashing multiple NB cards to use specific eth routing configurations by running the following command

    ```
    $ tt-topology -o -r ~/.config/tenstorrent/reset_config.json
    ```

## Internal Procedure
1. Setup `mobo_eth_en` on every local n150 to train with the Galaxy
2. Program the shelf/rack of the Galaxies
3. Program all local n150s to rack 0, shelf 0, x 0, y 0
4. Reset with the following `retimer_sel` and `disable_sel` and wait for training
    - `retimer_sel`: From the `credo` field of the reset json file for the specific Galaxy
    - `disable_sel`: All the other ports not specified by the `retimer_sel`
5. Check QSFP link and change shelf number for each n150 according to the shelf on the connected Galaxy
6. Program the x, y coords of the local n150s based on the other side of the link
7. Reset again with the `retimer_sel` and `disable_sel` and wait for training, and verify all chips show up
    - `retimer_sel`: From the `credo` field of the reset json file for the specific Galaxy
    - `disable_sel`: From the `disabled_ports` field of the reset json file for the specific Galaxy

# Logging

TT-Topology records the pre and post flash relevant SPI registers, connection map and coordinates of the chips in a .json file for record keeping and debugging.
By default it is stored at ```~/tt_topology_logs/<timestamp>_log.json```. This can be changed by using the log command line argument as follows
```
$ tt-topology -log new_log.json ...
```

# License

Apache 2.0 - https://www.apache.org/licenses/LICENSE-2.0.txt
