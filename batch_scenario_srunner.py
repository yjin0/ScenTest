import os
import json
import subprocess
import argparse
import sys
import math
import time

try:
    import carla
    from agents.navigation.basic_agent import BasicAgent
except ImportError as e:
    sys.exit(f"Failed to import CARLA or BasicAgent: {e}. Please check your PYTHONPATH.")

# --- General Configuration ---
SCTEST_DIR = os.path.dirname(os.path.abspath(__file__))
SCENARIO_RUNNER_VERSION_DIR = "scenario_runner-0.9.15"
SCENARIO_RUNNER_EXECUTABLE_REL = os.path.join(SCENARIO_RUNNER_VERSION_DIR, "scenario_runner.py")
ALL_EGO_VALID_JSON_PATH = os.path.join(SCTEST_DIR, "all_ego_valid.json")
DEFAULT_CARLA_HOST = 'localhost'
DEFAULT_CARLA_PORT = 2000
DEFAULT_TIMEOUT = 20.0
DEFAULT_FPS = 100.0
EGO_VEHICLE_ROLE_NAME = "ego_vehicle"
SRUNNER_INIT_WAIT_TIME = 7

# --- CARLA Server Configuration ---
CARLA_KILL_PROCESS_NAME = "CarlaUE4-Linux-"
CARLA_EXECUTABLE_PATH = "/home/si9h/Carla15/CarlaUE4.sh"
KILL_COMMAND_WAIT_SECONDS = 3
START_WAIT_SECONDS = 10

# --- Outcome Logging Configuration ---
OUTCOME_JSON_FILE_PATH = os.path.join(SCTEST_DIR, "srunner_outcomes.json")

def load_outcomes(filepath):
    """Loads previously recorded scenario outcomes from a JSON file."""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            print(f"Warning: Could not read or decode outcome file at {filepath}. Starting fresh.")
    return {}

def save_outcomes(filepath, data):
    """Saves scenario outcomes to a JSON file."""
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        print(f"Error: Could not write outcomes to {filepath}: {e}")

def create_carla_transform(pose_data, world):
    """Creates a carla.Transform, adjusting coordinates and snapping to the road."""
    location = carla.Location(x=float(pose_data['x']), y=-float(pose_data['y']), z=float(pose_data['z']))
    yaw_deg = -math.degrees(float(pose_data['h'])) - 90.0
    rotation = carla.Rotation(pitch=0, yaw=(yaw_deg + 180) % 360 - 180, roll=0)
    transform = carla.Transform(location, rotation)

    if world:
        waypoint = world.get_map().get_waypoint(location, project_to_road=True, lane_type=carla.LaneType.Driving)
        if waypoint:
            transform.location.z = max(transform.location.z, waypoint.transform.location.z + 0.3)
            transform.rotation = waypoint.transform.rotation # Align with road direction
    return transform

def drive_scenario_with_agent(args, dest_pose_json, record_file_path=None):
    """Connects to CARLA, controls an agent, and manages simulation with stuck/fallen detection."""
    client, world, original_settings = None, None, None
    try:
        client = carla.Client(args.host, args.port)
        client.set_timeout(args.timeout)
        world = client.get_world()
        original_settings = world.get_settings()

        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1.0 / float(args.fps)
        world.apply_settings(settings)

        ego_vehicle = None
        for _ in range(int(args.timeout)):
            for actor in world.get_actors().filter('vehicle.*'):
                if actor.attributes.get('role_name') == EGO_VEHICLE_ROLE_NAME:
                    ego_vehicle = actor
                    break
            if ego_vehicle:
                break
            time.sleep(1)
        
        if not ego_vehicle:
            raise RuntimeError(f"Ego vehicle '{EGO_VEHICLE_ROLE_NAME}' not found.")

        destination_transform = create_carla_transform(dest_pose_json, world)
        agent = BasicAgent(ego_vehicle, target_speed=30, opt_dict={'sync_mode': True, 'fixed_delta_seconds': settings.fixed_delta_seconds})
        agent.set_destination(destination_transform.location)

        if record_file_path:
            client.start_recorder(record_file_path, True)
            print(f"Recording to {record_file_path}")

        max_duration = 180
        start_time = time.time()

        # --- Stuck/Fallen Detector Initialization ---
        last_location = None
        stuck_timer_start = None
        STUCK_TIME_THRESHOLD = 2.0  # seconds

        while time.time() - start_time < max_duration:
            world.tick()
            current_location = ego_vehicle.get_location()

            # 1. Fallen detector
            if current_location.z < 0:
                print("Ego vehicle has fallen through the map. Ending scenario.")
                break

            # 2. Stuck detector
            if last_location is None or current_location.distance(last_location) > 0.1:
                last_location = current_location
                stuck_timer_start = time.time()
            elif time.time() - stuck_timer_start > STUCK_TIME_THRESHOLD:
                print(f"Ego vehicle is stuck (no movement for {STUCK_TIME_THRESHOLD}s). Ending scenario.")
                break

            if agent.done():
                print("Agent reached destination.")
                break
            
            ego_vehicle.apply_control(agent.run_step())
        else:
            print("Simulation timed out.")

    finally:
        if client:
            if record_file_path: 
                client.stop_recorder()
                print(f"Stopped recording {record_file_path}")
            if world and original_settings: world.apply_settings(original_settings)

def main():
    parser = argparse.ArgumentParser(description="Batch run CARLA scenarios with a custom agent and automatic server restart.")
    parser.add_argument('--record-folder', required=True, help="Folder to save CARLA recorder files.")
    parser.add_argument('--scenarios-folder', default='opscenarios', help="Folder where .xosc scenario files are located.")
    parser.add_argument('--host', default=DEFAULT_CARLA_HOST, help="IP of the host server.")
    parser.add_argument('--port', default=DEFAULT_CARLA_PORT, type=int, help="TCP port to listen to.")
    parser.add_argument('--timeout', default=DEFAULT_TIMEOUT, type=float, help="CARLA client timeout.")
    parser.add_argument('--fps', default=DEFAULT_FPS, type=float, help="Simulation FPS.")
    args = parser.parse_args()

    try:
        with open(ALL_EGO_VALID_JSON_PATH, 'r') as f:
            scenario_data = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        sys.exit(f"Error reading {ALL_EGO_VALID_JSON_PATH}: {e}")

    processed_outcomes = load_outcomes(OUTCOME_JSON_FILE_PATH)
    print(f"Loaded {len(processed_outcomes)} previously processed scenario outcomes.")

    record_folder_abs = os.path.join(SCTEST_DIR, args.record_folder)
    os.makedirs(record_folder_abs, exist_ok=True)
    print(f"Recording files will be saved to: {record_folder_abs}")

    srunner_executable_abs = os.path.join(SCTEST_DIR, SCENARIO_RUNNER_EXECUTABLE_REL)
    scenarios_folder_abs = os.path.join(SCTEST_DIR, args.scenarios_folder)

    for scenario_filename, data in scenario_data.items():
        if scenario_filename in processed_outcomes:
            print(f"Skipping '{scenario_filename}' as it is already in the outcome log.")
            continue

        print(f"\n{'='*20}\n--- Preparing to run scenario: {scenario_filename} ---")

        # --- CARLA Server Restart Logic ---
        print(f"Attempting to kill existing CARLA server processes...")
        try:
            subprocess.run(["pkill", "-f", CARLA_KILL_PROCESS_NAME], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"Kill command issued. Waiting {KILL_COMMAND_WAIT_SECONDS}s...")
            time.sleep(KILL_COMMAND_WAIT_SECONDS)
        except Exception as e:
            print(f"Warning: pkill command failed: {e}")

        print(f"Attempting to start CARLA server on port {args.port}...")
        try:
            carla_start_command = [CARLA_EXECUTABLE_PATH, f"-carla-rpc-port={args.port}"]
            subprocess.Popen(carla_start_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
            print(f"CARLA server start command issued. Waiting {START_WAIT_SECONDS} seconds for initialization...")
            time.sleep(START_WAIT_SECONDS)
        except Exception as e:
            print(f"Critical Error: Failed to start CARLA server: {e}. Skipping scenario.")
            processed_outcomes[scenario_filename] = "failed_server_start"
            save_outcomes(OUTCOME_JSON_FILE_PATH, processed_outcomes)
            continue
        # --- End of CARLA Server Restart Logic ---

        xosc_file_path = os.path.join(scenarios_folder_abs, scenario_filename)
        if not os.path.exists(xosc_file_path):
            print(f"Warning: Scenario file not found, skipping: {xosc_file_path}")
            processed_outcomes[scenario_filename] = "failed_file_not_found"
            save_outcomes(OUTCOME_JSON_FILE_PATH, processed_outcomes)
            continue

        dest_pose_json = data.get('acquire_position_actions', [None])[0]
        if not dest_pose_json:
            print(f"Skipping scenario {scenario_filename} due to missing destination.")
            processed_outcomes[scenario_filename] = "failed_missing_destination"
            save_outcomes(OUTCOME_JSON_FILE_PATH, processed_outcomes)
            continue

        agent_record_file_path = os.path.join(record_folder_abs, f"{os.path.splitext(scenario_filename)[0]}.log")
        srunner_cmd = ["python3", srunner_executable_abs, "--openscenario", xosc_file_path, "--host", args.host, "--port", str(args.port)]
        
        srunner_process = None
        outcome_status = "failed"
        try:
            srunner_process = subprocess.Popen(srunner_cmd, cwd=SCTEST_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print(f"Waiting {SRUNNER_INIT_WAIT_TIME}s for scenario_runner to initialize...")
            time.sleep(SRUNNER_INIT_WAIT_TIME)

            if srunner_process.poll() is not None:
                raise RuntimeError("scenario_runner.py failed to start.")

            drive_scenario_with_agent(args, dest_pose_json, record_file_path=agent_record_file_path)
            outcome_status = "success"

        except Exception as e:
            print(f"An error occurred during scenario {scenario_filename}: {e}")
            # If scenario_runner fails and terminates, its output is useful.
            # Otherwise, don't hang waiting for a running process.
            if srunner_process and srunner_process.poll() is not None:
                stdout, stderr = srunner_process.communicate()
                print("--- scenario_runner.py output ---")
                if stdout: print(f"STDOUT:\n{stdout}")
                if stderr: print(f"STDERR:\n{stderr}")
        finally:
            if srunner_process and srunner_process.poll() is None:
                print("Terminating scenario_runner.py...")
                srunner_process.kill()
                srunner_process.wait()
            
            processed_outcomes[scenario_filename] = outcome_status
            save_outcomes(OUTCOME_JSON_FILE_PATH, processed_outcomes)
            print(f"--- Finished scenario: {scenario_filename} (Outcome: {outcome_status}) ---")

    print("\n--- Batch run finished. Killing final CARLA server instance. ---")
    try:
        subprocess.run(["pkill", "-f", CARLA_KILL_PROCESS_NAME], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Final CARLA server kill command issued.")
    except Exception as e:
        print(f"Warning: Final pkill command failed: {e}")

if __name__ == '__main__':
    main()