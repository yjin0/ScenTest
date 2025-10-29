# Project Roadmap

This document outlines the plan for uploading and organizing the code for the paper "Coverage-based Evaluation of Scenarios for Autonomous Driving
System"

## Phase 1: Core Logic and Basic Functionality

*   **[In progress]** Upload the core Python scripts for recording and definition the coverage metrics.
*   **[To Do]** Include a requirements.txt file with all necessary dependencies.

## Phase 2: Data and Evaluation

*   **[To Do]** Upload the scripts used for data processing and scenario extraction.
*   **[To Do]** Provide a sample of the dataset used for the evaluation.

## Phase 3: Documentation and Usability

*   **[To Do]** Write a comprehensive `README.md` with detailed instructions on how to run the code.
*   **[To Do]** Add examples and tutorials to demonstrate how to use the coverage metrics on new data.
*   **[To Do]** Clean up the code, add comments, and ensure it follows a consistent style.


# Scenario Testing Framework

A comprehensive testing framework for running and analyzing autonomous driving scenarios in CARLA Simulator. This project provides tools for batch scenario execution, data extraction, and performance analysis using both direct OpenDRIVE maps and ScenarioRunner.

## System Setup

### Hardware
- **RAM**: 64GB
- **CPU**: Intel Core i7-13700
- **GPU**: NVIDIA RTX 3070

### Software Dependencies
- **CARLA Simulator**: v0.9.15
  - Download from: https://github.com/carla-simulator/carla/releases
- **ScenarioRunner**: v0.9.15
  - Download from: https://github.com/carla-simulator/scenario_runner/releases
- **Python**: >=3.7

## Installation

### 1. Install CARLA Simulator

```bash
# Download CARLA 0.9.15
wget https://carla-releases.s3.us-east-005.backblazeb2.com/Linux/CARLA_0.9.15.tar.gz

# Extract
tar -xzf CARLA_0.9.15.tar.gz -C ~/Carla15

# Make executable
chmod +x ~/Carla15/CarlaUE4.sh
```

### 2. Install ScenarioRunner

```bash
# Clone ScenarioRunner 0.9.15
cd /path/to/ScenTest
git clone -b v0.9.15 https://github.com/carla-simulator/scenario_runner.git scenario_runner-0.9.15

# Set up Python path
export PYTHONPATH="${PYTHONPATH}:~/Carla15/PythonAPI/carla/dist/carla-0.9.15-py3.7-linux-x86_64.egg"
export PYTHONPATH="${PYTHONPATH}:~/Carla15/PythonAPI/carla/agents"
export PYTHONPATH="${PYTHONPATH}:~/Carla15/PythonAPI/carla"
```

### 3. Install Python Dependencies

```bash
# Using pip
pip install -r requirements.txt

# Or using uv (if available)
uv pip install -e .
```

### 4. Configure Paths

Update the CARLA executable path in the following files:
- `corescripts/utility.py` (line 13)
- `corescripts/batch_scenarios_xodr.py` (line 20)
- `corescripts/batch_scenario_srunner.py` (line 29)

```python
CARLA_EXECUTABLE_PATH = "/path/to/your/Carla15/CarlaUE4.sh"
```

## Project Structure

```
ScenTest/
├── utility.py                  # Helper functions for scenario construction
├── run_single_carla_100fps.py  # Single scenario execution sample
├── extract_log_data_standalone.py  # Post-analysis log extraction
├── batch_scenarios_xodr.py     # Batch runner for OpenDRIVE files
├── batch_scenario_srunner.py   # Batch runner via ScenarioRunner
└── helper/                     # Helper utilities
    ├── automatic_control_srunner.py
    ├── validate_spawn_routes.py
    ├── verify_map_processing.py
    ├── analyze_distinct_maps.py
    ├── analyze_logic_files.py
    └── cleanup_spawn_points.py
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

## Usage

### Running a Single Scenario

Use `run_single_carla_100fps.py` to test individual scenarios:

```bash
python run_single_carla_100fps.py --host 127.0.0.1 --port 2000 --record --output-dir recordings
```

**Options:**
- `--host`: CARLA server IP (default: 127.0.0.1)
- `--port`: CARLA server port (default: 2000)
- `--record`: Enable automatic recording
- `--output-dir`: Directory for recording files (default: recordings)

### Batch Processing with OpenDRIVE

Run scenarios directly using OpenDRIVE map files:

```bash
python batch_scenarios_xodr.py
```

**Features:**
- Loads scenarios from `all_ego_valid.json`
- Automatically manages CARLA server lifecycle
- Records outcomes to `scenario_outcomes.json`
- Handles connection failures with automatic retry
- Runs at 100 FPS in synchronous mode

### Batch Processing with ScenarioRunner

Run scenarios through the ScenarioRunner framework:

```bash
cd corescripts
python batch_scenario_srunner.py
```

**Features:**
- Executes scenarios via ScenarioRunner
- Automatic ego vehicle control using BasicAgent
- Records outcomes to `srunner_outcomes.json`
- Manages CARLA server restarts on failures
- Configurable FPS and timeout settings

### Extracting Log Data

Extract driving information from CARLA recording logs:

```bash
cd corescripts
python extract_log_data_standalone.py <path_to_log_file> [--output-csv output.csv]
```

**Extracted Data:**
- Frame-by-frame vehicle positions
- Velocity and acceleration
- Control inputs (throttle, brake, steering)
- Collision events
- Transform data (location, rotation)

**Output:** CSV file with timestamped driving metrics

## Core Scripts Overview

### `utility.py`
Provides essential helper functions for scenario construction:
- CARLA server management (start/stop/restart)
- Connection handling with retry logic
- World configuration and synchronization
- Common utility functions for scenario setup

### `run_single_carla_100fps.py`
Sample implementation for running single scenarios:
- Demonstrates proper CARLA initialization
- Shows BasicAgent integration for autonomous driving
- Includes recording functionality
- Spectator camera following ego vehicle
- Clean shutdown and resource cleanup

### `extract_log_data_standalone.py`
Post-analysis tool for extracting driving data:
- Parses CARLA `.log` recording files
- Extracts vehicle telemetry data
- Generates CSV output for analysis
- Supports custom output paths

### `batch_scenarios_xodr.py`
Automated batch runner for OpenDRIVE scenarios:
- Iterates through scenario datasets
- Direct map loading from `.xodr` files
- Automatic CARLA server management
- Outcome tracking and logging
- Failure recovery mechanisms

### `batch_scenario_srunner.py`
Automated batch runner using ScenarioRunner:
- Integrates with ScenarioRunner framework
- Supports `.xosc` scenario files
- Automatic ego vehicle control
- Comprehensive outcome logging
- Server restart on critical failures

## Helper Utilities

The `corescripts/helper/` directory contains specialized utilities:

- **`automatic_control_srunner.py`**: Automated control logic for ScenarioRunner scenarios
- **`validate_spawn_routes.py`**: Validates spawn points and routes for scenarios
- **`verify_map_processing.py`**: Verifies OpenDRIVE map processing correctness
- **`analyze_distinct_maps.py`**: Analyzes unique maps in scenario datasets
- **`analyze_logic_files.py`**: Analyzes scenario logic files
- **`cleanup_spawn_points.py`**: Cleans up and validates spawn point data

## Configuration

### CARLA Server Settings

Default settings in batch runners:
- **Port**: 2000
- **FPS**: 100 (synchronous mode)
- **Timeout**: 20 seconds
- **Connection retry**: 3 attempts

### Output Directories

- `record_ego_100/`: Ego vehicle recordings (xodr method)
- `recordings/`: General recording output
- `logs/`: CARLA server logs
- `ego_data/`: Extracted ego vehicle data

## Quick Start Example

```bash
# 1. Start CARLA server manually (optional, scripts can auto-start)
~/Carla15/CarlaUE4.sh -quality-level=Low -RenderOffScreen

# 2. Run a single test scenario
cd SCTest/corescripts
python run_single_carla_100fps.py --record

# 3. Run batch processing
python batch_scenarios_xodr.py

# 4. Extract data from recordings
python extract_log_data_standalone.py ../recordings/recording_20241029_120000.log --output-csv results.csv
```

## Contact

s2676863@ed.ac.uk
---

**Note**: This framework is designed for research and testing purposes. Ensure proper CARLA and ScenarioRunner configuration before running batch operations.
