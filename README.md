# TT-Topology

Tenstorrent Topology (TT-Topology) is a command line utility
used to flash multiple NB cards on a system to use specific eth routing configurations.

It curretly supports three configurtions - mesh, linear and torus

## Official Repository

[https://github.com/tenstorrent/tt-topology/](https://github.com/tenstorrent/tt-topology/)

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
pip3 install --upgrade pip
```
## Required

Install tt-topology.
```
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
usage: tt-topology [-h] [-v] [-l {linear,torus,mesh}] [-ls] [--log [log]] [-p [plot]]

Tenstorrent Topology (TT-Topology) is a command line utility to flash ethernet coordinates when multiple NB's are connected together.

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -l {linear,torus,mesh}, --layout {linear,torus,mesh}
                        Select the layout (linear, torus, mesh). Default is linear.
  -ls, --list           List out all the boards on host with their coordinates and layout.
  --log [log]           Change filename for the topology flash log. Default:
                        ~/tt_topology_logs/<timestamp>_log.json
  -p [plot], --plot_filename [plot]
                        Change the plot of the png that will have the graph layout of the chips. Default:
                        chip_layout.png
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

# Logging

TT-Topology records the pre and post flash relevant SPI registers, connection map and coordinates of the chips in a .json file for record keeping and debugging.
By default it is stored at ```~/tt_topology_logs/<timestamp>_log.json```. This can be changed by using the log command line argument as follows
```
$ tt-topology -log new_log.json ...
```

# License

Apache 2.0 - https://www.apache.org/licenses/LICENSE-2.0.txt
