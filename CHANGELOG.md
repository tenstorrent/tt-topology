# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 1.2.4 - 05/03/2025

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
