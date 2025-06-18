# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 1.2.11 - 17/06/2025

### Updated

- Updated mesh coord generation to be connection type agnostic
- Added failure and exit if mesh type detected, but not enough connections
- Added warning in README about lack of supoort for BH and 6U boards

## 1.2.10 - 05/06/2025

### Updated

- Bumped tt-tools-common version to fix driver version check for compatability with tt-kmd 2.0.0

## 1.2.9 - 30/05/2025

### Updated

- Bug fix for https://github.com/tenstorrent/tt-topology/issues/39. Now the tool will use a DFS longest path to determine a linear layout if its not a fully connected graph.
- Updated initial device detection - now it needs full noc access for octopus and list options

## 1.2.8 - 08/05/2025

### Updated

- Fixed issue where tool would fail when PCI interfaces don't start from ID 0
- Now using actual PCI interface IDs from devices instead of assuming sequential numbering

## 1.2.7 - 07/05/2025

### Updated

- Use tools-common 1.4.15
- Use type checking in octopus reset

## 1.2.6 - 05/05/2025

### Updated

- Bug fix: added "ignore-eth" flag to first chip detect to avoid eth training loops forever and truly detect pcie only chips
- Chore: bumped luwen

## 1.2.5 - 15/04/2025

### Updated

- When flashing to isolated mode, we now flash the WH ethernet ports to a disabled state,
  in order to prevent their use.

## 1.2.4 - 02/04/2025

### Updated

- You can now run `tt-topology -l isolated` to flash cards to the default (non-connected) state
- Users are now warned about missing or loose cables

## 1.2.3 - 21/03/2025

### Fixed

- Bumped luwen (0.6.2 -> 0.6.3) to include eth version check bug for TG setup

## 1.2.2 - 13/03/2025

### Fixed

- Bumped luwen version to make it more robust against eth fw updates

## 1.2.1 - 13/03/2025

### Fixed

- Moved the spi reads after the reset to increase stability during M3 L2R copy
- Bumped luwen version

## 1.2.0 - 06/03/2025

### Fixed

- Updated how local eth board info is calculated to make it agnostic to eth fw version
- bumped tt-tools-common version
- Added traceback printing when catching exceptions in main.

## 1.1.5 - 14/05/2024

### Updated

- Bumped luwen (0.3.8) and tt_tools_common (1.4.3) lib versions
- Removed unused python libraries

## 1.1.4 - 25/03/2024

### Fixed
- Changed detect_chips with detect_chips_with_callback to enable detailed debug info.

## 1.1.3 - 22/03/2024

### Fixed
- Bumped tt-tools-common version to avoid pip discrepancy.

## 1.1.2 - 22/03/2024

### Fixed
- Fixed command line bug when no args are provided.

## 1.1.1 - 21/03/2024

### Fixed
- Fixed reference to pyluwen lib

## 1.1.0 - 12/03/2024

### Added
- Octopus Configuration (4 n150s connected to 1 galaxy)


## 1.0.2 - 12/03/2024

### Fixed
- Dependency bug with tt_tools_common

## 1.0.1 - 12/02/2024

### Fixed
- Updated luwen to 0.2.1 to fix crash when running on broken systems

## 1.0.0 - 31/01/2024

First release of opensource tt-topology
