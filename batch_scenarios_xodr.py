import json
import subprocess
import os
import sys
import time
import re

# --- Configuration ---
JSON_FILE_PATH = os.path.join(os.path.dirname(__file__), 'all_ego_valid.json')
DEBUG_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), 'debug_single_scenario.py')
PYTHON_EXECUTABLE = "python"
RECORD_OUTPUT_DIR_NAME = "record_ego_100"
DEFAULT_SYNC_FPS = "100" # Default FPS for synchronous mode in batch runs
MAX_CONSECUTIVE_CONNECTION_FAILURES = 3 # Max attempts before trying to restart CARLA
CARLA_CONNECTION_TIMEOUT_ERROR_MSG = "Error connecting to CARLA: time-out"

# --- CARLA Server Configuration (Inlined) ---
DEFAULT_CARLA_PORT = 2000
CARLA_KILL_PROCESS_NAME = "CarlaUE4-Linux-"  # Process name used by pkill
CARLA_EXECUTABLE_PATH = "/home/si9h/Carla15/CarlaUE4.sh" # Path to CARLA executable
KILL_COMMAND_WAIT_SECONDS = 3  # Time to wait after issuing pkill
START_WAIT_SECONDS = 10      # Time to wait after starting CARLA server

# --- Outcome Logging Configuration ---
OUTCOME_JSON_FILE_PATH = os.path.join(os.path.dirname(__file__), "scenario_outcomes.json")


def load_scenarios(json_file_path):
    """Loads scenario data from the given JSON file path.

    Args:
        json_file_path (str): The absolute path to the JSON file.

    Returns:
        dict: A dictionary of scenario data, or None if loading fails.
    """
    try:
        with open(json_file_path, 'r') as f:
            all_scenarios_data = json.load(f)
        print(f"Successfully loaded {len(all_scenarios_data)} scenarios from {json_file_path}")
        return all_scenarios_data
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_file_path}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_file_path}")
        sys.exit(1)


def get_expected_log_path(scenario_filename, base_record_dir):
    """Constructs the expected absolute path for a scenario's log file.

    Args:
        scenario_filename (str): The .xosc filename (e.g., 'Scenario.xosc').
        base_record_dir (str): The base directory where 'record_ego' logs are stored.

    Returns:
        str: The absolute path to the expected log file.
    """
    base_scenario_name = os.path.splitext(scenario_filename)[0]
    safe_scenario_name = re.sub(r'[^a-zA-Z0-9_\.-]', '_', base_scenario_name)
    expected_log_filename = f"{safe_scenario_name}_recording.log"
    return os.path.join(base_record_dir, expected_log_filename)


def run_scenario_debug(scenario_filename, python_exe, debug_script_path, sync_fps):
    """Constructs and runs the command for debug_single_scenario.py for a given scenario.

    Args:
        scenario_filename (str): The .xosc scenario file name.
        python_exe (str): The Python executable (e.g., '/path/to/.venv/bin/python').
        debug_script_path (str): Path to debug_single_scenario.py.
        sync_fps (str): FPS value to use with --sync flag.
    
    Returns:
        str: The outcome status of the scenario.
    """
    print(f"\n--- Processing scenario: {scenario_filename} ---")
    command = [
        *python_exe.split(), # Handles cases like 'uv run python' or a direct path
        debug_script_path,
        scenario_filename,
        "--record",
        "--sync",
        sync_fps
    ]

    print(f"Executing command: {' '.join(command)}")
    try:
        result = subprocess.run(command, check=False, text=True, capture_output=True)
        print(f"--- Finished processing {scenario_filename} --- ")
        if result.stdout:
            # print("Output from debug script:") # Keep this commented unless full stdout is needed for batch log
            # output_lines = result.stdout.splitlines()
            # for line in output_lines:
            # print(line)
            
            # Find and extract the FINAL_STATUS
            match = re.search(r"FINAL_STATUS:\s*(.+)", result.stdout)
            if match:
                status = match.group(1).strip()
                print(f"Extracted scenario status for {scenario_filename}: {status}")
                return status
            else:
                # Print relevant part of stdout if FINAL_STATUS is missing, for debugging
                print(f"Warning: FINAL_STATUS not found in debug script output for {scenario_filename}.")
                relevant_output = "\n".join(result.stdout.splitlines()[-10:]) # Last 10 lines
                print(f"Last few lines of output:\n{relevant_output}")
                return "UNKNOWN_SCRIPT_OUTPUT"

        # Fallback if no stdout or specific status found, but script completed (returncode 0)
        if result.returncode == 0:
             print(f"Warning: Script for {scenario_filename} completed with code 0 but no FINAL_STATUS was captured from stdout.")
             return "COMPLETED_NO_STATUS_PARSE"

        # If script itself failed (non-zero return code) and no FINAL_STATUS was parsed from potential stdout
        print(f"Warning: {scenario_filename} processed with script errors (return code: {result.returncode}). Check logs.")
        return f"SCRIPT_ERROR_CODE_{result.returncode}"

    except FileNotFoundError:
        print(f"Error: Could not execute command. Make sure '{python_exe}' and script path are correct.")
        return "SCRIPT_NOT_FOUND"
    except Exception as e:
        print(f"An unexpected error occurred while processing {scenario_filename}: {e}")
        return "BATCH_PROCESSING_ERROR"


# --- JSON Outcome Handling Functions ---
def load_outcomes(filepath):
    """Loads previously recorded scenario outcomes from a JSON file."""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON from {filepath}. Starting with no previous outcomes.")
            return {}
        except Exception as e:
            print(f"Warning: Error loading outcomes from {filepath}: {e}. Starting with no previous outcomes.")
            return {}
    return {}

def save_outcomes(filepath, data):
    """Saves scenario outcomes to a JSON file."""
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        # print(f"Outcomes saved to {filepath}") # Optional: print save confirmation
    except IOError as e:
        print(f"Error: Could not write outcomes to {filepath}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while saving outcomes to {filepath}: {e}")


def main():
    """Main function to orchestrate batch recording of scenarios."""
    script_dir = os.path.dirname(__file__)
    base_recording_dir = os.path.join(script_dir, RECORD_OUTPUT_DIR_NAME)
    os.makedirs(base_recording_dir, exist_ok=True)

    if not os.path.isfile(DEBUG_SCRIPT_PATH):
        print(f"Error: Debug script not found at {DEBUG_SCRIPT_PATH}")
        sys.exit(1)

    all_scenarios_data = load_scenarios(JSON_FILE_PATH)
    if not all_scenarios_data:
        print("No scenarios loaded. Exiting.")
        return

    scenario_keys = list(all_scenarios_data.keys())
    total_scenarios = len(scenario_keys)
    print(f"Found {total_scenarios} scenarios to potentially process.")

    # Load previously processed outcomes
    processed_outcomes = load_outcomes(OUTCOME_JSON_FILE_PATH)
    print(f"Loaded {len(processed_outcomes)} previously processed scenario outcomes.")

    scenarios_to_run_count = 0

    for i, scenario_filename in enumerate(scenario_keys):
        if not scenario_filename.endswith(".xosc"):
            print(f"Skipping non-.xosc entry: {scenario_filename}")
            continue

        # Check if scenario has already been processed based on outcome log
        if scenario_filename in processed_outcomes:
            print(f"Scenario '{scenario_filename}' found in outcome log with status: '{processed_outcomes[scenario_filename]}'. Skipping.")
            continue

        scenarios_to_run_count += 1
        print(f"\n--- Preparing to run scenario ({scenarios_to_run_count} of remaining): {scenario_filename} ---")
        
        # --- Inlined CARLA Server Restart Logic ---
        print(f"\n--- Preparing to run scenario: {scenario_filename} ---")
        
        # 1. Kill existing CARLA server processes
        print(f"Attempting to kill existing CARLA server processes (name: {CARLA_KILL_PROCESS_NAME})...")
        try:
            subprocess.run(["pkill", "-f", CARLA_KILL_PROCESS_NAME], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"Kill command issued for '{CARLA_KILL_PROCESS_NAME}'. Waiting {KILL_COMMAND_WAIT_SECONDS}s...")
            time.sleep(KILL_COMMAND_WAIT_SECONDS)
        except FileNotFoundError:
            print("Warning: 'pkill' command not found. Cannot guarantee CARLA server is stopped by name.")
        except Exception as e:
            print(f"Warning: An error occurred during pkill: {e}")

        # 2. Start new CARLA server instance
        print(f"Attempting to start CARLA server from: {CARLA_EXECUTABLE_PATH} on port {DEFAULT_CARLA_PORT}...")
        # carla_start_command = [CARLA_EXECUTABLE_PATH, f"-carla-rpc-port={DEFAULT_CARLA_PORT}", "-RenderOffScreen"]
        carla_start_command = [CARLA_EXECUTABLE_PATH, f"-carla-rpc-port={DEFAULT_CARLA_PORT}"]
        # carla_start_command = [CARLA_EXECUTABLE_PATH, f"-carla-rpc-port={DEFAULT_CARLA_PORT}"]
        try:
            # stdout and stderr are DEVNULL to prevent CARLA server logs from cluttering batch script output.
            # preexec_fn=os.setsid helps CARLA run in its own session, detaching it slightly.
            subprocess.Popen(carla_start_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
            print(f"CARLA server start command issued. Waiting {START_WAIT_SECONDS} seconds for initialization...")
            time.sleep(START_WAIT_SECONDS)
        except FileNotFoundError:
            print(f"Critical Error: CARLA executable not found at '{CARLA_EXECUTABLE_PATH}'. Aborting batch process.")
            sys.exit(1)
        except Exception as e:
            print(f"Critical Error: Failed to start CARLA server: {e}. Aborting batch process.")
            sys.exit(1)
        # --- End of Inlined CARLA Server Restart Logic ---

        # Now run the scenario debug script and get its outcome
        outcome_status = run_scenario_debug(scenario_filename, PYTHON_EXECUTABLE, DEBUG_SCRIPT_PATH, DEFAULT_SYNC_FPS)
        
        # Update and save outcomes immediately
        processed_outcomes[scenario_filename] = outcome_status
        save_outcomes(OUTCOME_JSON_FILE_PATH, processed_outcomes)

        # Delay before processing the next scenario, unless it's the last one
        if i < total_scenarios - 1:
            print(f"Waiting for 1 seconds before starting the next scenario...")
            time.sleep(1)

    print("\nBatch recording process finished.")

    final_total_processed = len(load_outcomes(OUTCOME_JSON_FILE_PATH)) # Re-load for final count
    print(f"Total scenarios in outcome log: {final_total_processed}")


if __name__ == "__main__":
    main()
