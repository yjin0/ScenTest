import carla
import glob
import json
import os
import argparse
import time
import utility # Import the utility module
import sys # For sys.exit
from carla import Client
# Add CARLA PythonAPI's 'carla' subdirectory to sys.path
# This directory contains the 'agents' package
CARLA_AGENTS_PARENT_DIR = '/home/si9h/Carla15/PythonAPI/carla/'
if CARLA_AGENTS_PARENT_DIR not in sys.path:
    sys.path.append(CARLA_AGENTS_PARENT_DIR)

# Now that sys.path is set, other imports should find the correct CARLA modules
# Corrected imports for routing modules
from agents.navigation import global_route_planner # DAO is not used in CARLA 0.9.15 GRP

# Default CARLA connection parameters
DEFAULT_HOST = utility.CARLA_HOST # Use from utility
DEFAULT_PORT = utility.CARLA_PORT   # Use from utility
DEFAULT_TIMEOUT = 10.0  # seconds
DEFAULT_CARLA_EXECUTABLE = utility.CARLA_EXECUTABLE_PATH
DEFAULT_SPAWN_POINTS_DIR = '../spawnPointDistances'
DEFAULT_XODR_MAP_DIR = '../maps'  # Default directory for .xodr map files

# Planner sampling resolution
SAMPLING_RESOLUTION = 2.0  # meters

def _ensure_output_dir_exists(dir_path):
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path)
            print(f"Created output directory: {dir_path}")
        except OSError as e:
            print(f"Error creating output directory {dir_path}: {e}. Cannot save results.")
            raise # Re-raise to signal failure upwards

# Helper function to write map results
def _write_map_results(output_dir, map_name, summary, detailed_results):
    _ensure_output_dir_exists(output_dir)
    output_filepath = os.path.join(output_dir, f"{map_name}_validation_results.json")
    current_map_output_data = {
        "map_name_processed": map_name, # Add original map name for clarity
        "summary": summary,
        "detailed_results": detailed_results
    }
    try:
        with open(output_filepath, 'w') as f_out:
            json.dump(current_map_output_data, f_out, indent=4)
        print(f"Results for map {map_name} saved to {output_filepath}")
    except Exception as e:
        print(f"Error saving results for map {map_name} to JSON file {output_filepath}: {e}")

# Re-define the helper function for snapping points to road waypoints
def _snap_points_to_road_waypoints(world, start_transform, end_transform):
    """
    Tries to snap the start and end spawn point transforms to the nearest drivable road waypoints.
    Returns a tuple: (snapped_start_waypoint, snapped_end_waypoint, failure_type)
    failure_type can be None, "start", "end", or "both".
    """
    game_map = world.get_map()
    snapped_start_waypoint = None
    snapped_end_waypoint = None
    failure_type = None

    try:
        snapped_start_waypoint = game_map.get_waypoint(
            start_transform.location, 
            project_to_road=True, 
            lane_type=carla.LaneType.Driving
        )
    except RuntimeError:
        snapped_start_waypoint = None
        
    try:
        snapped_end_waypoint = game_map.get_waypoint(
            end_transform.location,
            project_to_road=True,
            lane_type=carla.LaneType.Driving
        )
    except RuntimeError:
        snapped_end_waypoint = None

    if snapped_start_waypoint is None and snapped_end_waypoint is None:
        failure_type = "both"
    elif snapped_start_waypoint is None:
        failure_type = "start"
    elif snapped_end_waypoint is None:
        failure_type = "end"
        
    return snapped_start_waypoint, snapped_end_waypoint, failure_type

def main(args):
    current_loaded_map_name = None # Keep track of the currently loaded map

    # Initial connection attempt
    try:
        print("Attempting initial connection to CARLA server...")
        carla_ok = utility.check_carla(
            executable_path=args.carla_executable,
            port_to_use=args.port,
        )

        if not carla_ok:
            print("FATAL: Could not establish initial connection to CARLA server. Please check server logs and configuration. Exiting.")
            return 1 # Indicate an error
        client = Client("localhost", args.port)
        world = client.get_world() # Get world from the new client
        current_loaded_map_name = world.get_map().name.split('/')[-1]
        print(f"Initial connection successful. Current map reported by server: {current_loaded_map_name}")
        original_settings = world.get_settings() # Save original settings for final cleanup
    except Exception as e_initial_connect:
        print(f"FATAL: Exception during initial CARLA server connection: {e_initial_connect}")
        import traceback
        traceback.print_exc()
        return 1

    all_distance_files = glob.glob(os.path.join(args.spawn_points_dir, "*_distances.json"))
    all_distance_files.sort() # Sort the files alphabetically

    if not all_distance_files:
        print(f"No '*_distances.json' files found in {args.spawn_points_dir}.")
        # No global JSON to write, but if an output dir was specified, maybe log a status file?
        # For now, just returning as per previous logic.
        return

    for file_path in all_distance_files:
        filename = os.path.basename(file_path)
        map_name_from_file = filename.replace('_distances.json', '')
        
        # Construct the expected output file path
        output_json_filename = f"{map_name_from_file}_validation_results.json"
        output_json_path = os.path.join(args.output_results_dir, output_json_filename)

        # Check if the results file already exists
        if os.path.exists(output_json_path):
            print(f"--- Results file already exists for map: {map_name_from_file} at {output_json_path}. Skipping. ---")
            continue # Skip to the next map

        print(f"\n--- Processing map: {map_name_from_file} (derived from file: {os.path.basename(file_path)}) ---")

        # Check CARLA server health before attempting to load/use it for the new map
        # server_is_responsive = False
        if not utility.is_carla_alive():
            print('asdjslkfahskjfhaskd')
            utility.restart_carla(
                executable_path=args.carla_executable,
                port_to_use=args.port,
            )
            print('asdjslkfahskjfhaskd')

        client = Client("localhost", args.port)

        if not carla_ok or not client:
            error_message = f"CRITICAL: Failed to connect/reconnect to CARLA server for map {map_name_from_file}. Skipping this map."
            print(error_message)
            error_summary = {
                "map_name_processed": map_name_from_file,
                "error": error_message, 
                "status": "SERVER_CONNECT_FAIL",
                "total_pairs_processed": 0, "total_pairs_skipped_invalid_id": 0, "valid_routes": 0,
                "invalid_no_route": 0, "invalid_grp_error": 0, "invalid_snap_fail_start": 0,
                "invalid_snap_fail_end": 0, "invalid_snap_fail_both": 0,
                "skipped_bad_json_format": 0, "processing_stopped_early": False
            }
            _write_map_results(args.output_results_dir, map_name_from_file, error_summary, [])
            # client = None # check_carla will return None or the old client if it fails
            world = None # World is definitely invalid now
            continue # Skip to the next map file
        
        # If check_carla was successful, client is (re)established
        world = client.get_world() # Get the world from the (potentially new) client
        current_loaded_map_name = world.get_map().name.split('/')[-1]
        print(f"Successfully (re)connected to CARLA server. Current map is: {current_loaded_map_name}")
        # Note: original_settings (for global script cleanup) remains from the very first successful connection.
        # Per-map settings (like sync mode) are handled during each map's specific loading process.

        # --- Actual processing for the map if loaded ---
        potential_xodr_filename = f"{map_name_from_file}.xodr"
        potential_xodr_filepath = os.path.join(args.xodr_map_dir, potential_xodr_filename)
        
        map_loaded_successfully = False

        if os.path.exists(potential_xodr_filepath):
            if current_loaded_map_name != map_name_from_file: # Avoid reloading if it's already the target .xodr map by name
                print(f"Found .xodr file: {potential_xodr_filepath}. Loading...")
                try:
                    with open(potential_xodr_filepath, 'r') as f_xodr:
                        xodr_content = f_xodr.read()
                    # Parameters for OpenDRIVE generation (optional but good for visibility)
                    od_params = carla.OpendriveGenerationParameters(
                        vertex_distance=2.0,
                        max_road_length=500.0,
                        wall_height=1.0,
                        additional_width=0.6,
                        smooth_junctions=True,
                        enable_mesh_visibility=True,
                        enable_pedestrian_navigation=True
                    )
                    world = client.generate_opendrive_world(xodr_content, od_params)
                    if not utility.is_carla_alive():
                        print("CARLA server is not responding. Attempting to restart...")
                        utility.restart_carla(
                            executable_path=args.carla_executable,
                            port_to_use=args.port,
                        )
                        continue
                    world.wait_for_tick()
                    time.sleep(args.map_load_delay)

                    # The map name after generate_opendrive_world is often the base name (e.g., 'map_package')
                    # or can be somewhat generic. We'll use map_name_from_file for our tracking.
                    current_loaded_map_name = map_name_from_file # Assume this is the identifier for .xodr loaded map
                    print(f"Map '{map_name_from_file}' loaded successfully from .xodr.")
                    map_loaded_successfully = True
                except RuntimeError as e:
                    print(f"Error loading map '{map_name_from_file}' from .xodr file '{potential_xodr_filepath}': {e}")
                except Exception as e:
                    print(f"An unexpected error occurred while loading .xodr file '{potential_xodr_filepath}': {e}")
            else:
                print(f"Map '{map_name_from_file}' (from .xodr) is already considered loaded.")
                map_loaded_successfully = True # Already loaded this .xodr conceptually
        else:
            print(f".xodr file not found at '{potential_xodr_filepath}'. Map '{map_name_from_file}' will be skipped.")
            map_loaded_successfully = False # Ensure this map is skipped by the subsequent check

        # --- Actual processing for the map if loaded ---
        if not map_loaded_successfully or not utility.is_carla_alive():
            continue # To the next file_path in distance_files

        carla_map = world.get_map()
        map_spawn_points = carla_map.get_spawn_points() # Get all spawn points for the current map

        if not map_spawn_points:
            print(f"Warning: No spawn points found on map '{current_loaded_map_name}'. Cannot validate pairs for {filename}.")
            continue
        print(f"Map '{current_loaded_map_name}' has {len(map_spawn_points)} available spawn points.")

        # Initialize counters for the current map
        map_results_summary = {
            "total_pairs_processed": 0,
            "valid_routes": 0,
            "invalid_routes": 0,
            "skipped_bad_json_format": 0,
            "processing_stopped_early": False
        }
        map_detailed_results = []

        try:
            with open(file_path, 'r') as f_in:
                data_from_json = json.load(f_in)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {filename}: {e}. Skipping this file.")
            # No map_results_summary or map_detailed_results to update here yet for the output file,
            # as this happens before map-specific summary is initialized for output.
            # However, if we want a record of this file even if it's totally corrupt:
            if args.output_results_dir:
                _ensure_output_dir_exists(args.output_results_dir)
                error_output_path = os.path.join(args.output_results_dir, f"{map_name_from_file}_error.json")
                with open(error_output_path, 'w') as f_err:
                    json.dump({"map_name": map_name_from_file, "error": "JSONDecodeError", "details": str(e)}, f_err, indent=4)
                print(f"Error log for {map_name_from_file} saved to {error_output_path}")
            continue # Move to the next file
        except Exception as e:
            print(f"Error reading file {filename}: {e}. Skipping this file.")
            if args.output_results_dir:
                _ensure_output_dir_exists(args.output_results_dir)
                error_output_path = os.path.join(args.output_results_dir, f"{map_name_from_file}_error.json")
                with open(error_output_path, 'w') as f_err:
                    json.dump({"map_name": map_name_from_file, "error": "FileReadError", "details": str(e)}, f_err, indent=4)
                print(f"Error log for {map_name_from_file} saved to {error_output_path}")
            continue
        
        print(f"Found {len(data_from_json)} spawn point pairs in {filename}.")

        if isinstance(data_from_json, dict) and "sorted_spawn_point_distances" in data_from_json:
            spawn_pairs_data = data_from_json["sorted_spawn_point_distances"]
            if not isinstance(spawn_pairs_data, list):
                print(f"Error: Expected 'sorted_spawn_point_distances' in {filename} to be a list, but got {type(spawn_pairs_data)}. Skipping file.")
                map_results_summary = {
                    "total_pairs_processed": 0,
                    "valid_routes": 0,
                    "invalid_routes": 0,
                    "skipped_bad_json_format": 1,
                    "processing_stopped_early": False
                }
                map_detailed_results = [{"error": "'sorted_spawn_point_distances' is not a list", "type": str(type(spawn_pairs_data))}]
                _write_map_results(args.output_results_dir, map_name_from_file, map_results_summary, map_detailed_results)
                continue
        elif isinstance(data_from_json, list):
            # If the top level is already a list, assume it's the old format or a direct list of pairs
            print(f"Warning: JSON file {filename} is a list. Assuming it's a direct list of spawn pairs.")
            spawn_pairs_data = data_from_json
        else:
            print(f"Error: JSON file {filename} does not have the expected structure (object with 'sorted_spawn_point_distances' list, or a direct list). Got {type(data_from_json)}. Skipping file.")
            map_results_summary = {
                "total_pairs_processed": 0,
                "valid_routes": 0,
                "invalid_routes": 0,
                "skipped_bad_json_format": 1,
                "processing_stopped_early": False
            }
            map_detailed_results = [{"error": "Unexpected JSON top-level structure", "type": str(type(data_from_json))}]
            _write_map_results(args.output_results_dir, map_name_from_file, map_results_summary, map_detailed_results)
            continue

        valid_routes_found_this_map = 0

        for i, pair_info in enumerate(spawn_pairs_data):
            try:
                # Assume spawn_point_1_id and spawn_point_2_id are present and valid integers
                start_sp_id = int(pair_info['spawn_point_1_id'])
                end_sp_id = int(pair_info['spawn_point_2_id'])

                status = "UNKNOWN" # Default status
                status_reason = "" # Default reason
                snapped_start_loc_str = "N/A"
                snapped_end_loc_str = "N/A"

                carla_start_transform = map_spawn_points[start_sp_id]
                carla_end_transform = map_spawn_points[end_sp_id]
                
                # 1. Snap spawn points to road waypoints
                snapped_start_waypoint, snapped_end_waypoint, snap_failure_type = \
                    _snap_points_to_road_waypoints(world, carla_start_transform, carla_end_transform)

                # 2. Attempt route planning if snapping was successful
                if snapped_start_waypoint and snapped_end_waypoint:
                    snapped_start_loc_str = f"({snapped_start_waypoint.transform.location.x:.2f}, {snapped_start_waypoint.transform.location.y:.2f}, {snapped_start_waypoint.transform.location.z:.2f})"
                    snapped_end_loc_str = f"({snapped_end_waypoint.transform.location.x:.2f}, {snapped_end_waypoint.transform.location.y:.2f}, {snapped_end_waypoint.transform.location.z:.2f})"
                    try:
                        # CARLA 0.9.15 GlobalRoutePlanner takes map and sampling_resolution directly
                        current_carla_map = world.get_map() # Get current map from world
                        grp = global_route_planner.GlobalRoutePlanner(current_carla_map, SAMPLING_RESOLUTION)
                        route = grp.trace_route(snapped_start_waypoint.transform.location, snapped_end_waypoint.transform.location)
                        if route:
                            status = "VALID"
                            map_results_summary["valid_routes"] += 1
                            valid_routes_found_this_map += 1
                        else:
                            status = "INVALID_NO_ROUTE"
                            map_results_summary["invalid_routes"] += 1
                            status_reason = "No route found by GlobalRoutePlanner between snapped spawn points."
                    except Exception as e_grp:
                        status = "INVALID_GRP_ERROR"
                        map_results_summary["invalid_routes"] += 1
                        status_reason = f"Error during GRP: {type(e_grp).__name__} - {str(e_grp)}."
                else:
                    # Handle snap failures
                    map_results_summary["invalid_routes"] += 1
                    if snap_failure_type == "start":
                        status = "INVALID_SNAP_FAIL_START"
                        status_reason = f"Start SP ID {start_sp_id} (Loc: {carla_start_transform.location}) couldn't be snapped."
                    elif snap_failure_type == "end":
                        status = "INVALID_SNAP_FAIL_END"
                        status_reason = f"End SP ID {end_sp_id} (Loc: {carla_end_transform.location}) couldn't be snapped."
                    elif snap_failure_type == "both":
                        status = "INVALID_SNAP_FAIL_BOTH"
                        status_reason = f"Both SP IDs {start_sp_id} & {end_sp_id} couldn't be snapped."
                    else: # Should not happen if snap_failure_type is always set when waypoints are None
                        status = "INVALID_SNAP_FAIL_UNKNOWN"
                        status_reason = "Unknown snapping failure."

                map_detailed_results.append({
                    "pair_index": i,
                    "spawn_point_1_id": start_sp_id,
                    "spawn_point_2_id": end_sp_id,
                    "status": status,
                    "reason": status_reason,
                    "original_distance": pair_info.get('distance'),
                    "start_location": {"x": carla_start_transform.location.x, "y": carla_start_transform.location.y, "z": carla_start_transform.location.z},
                    "end_location": {"x": carla_end_transform.location.x, "y": carla_end_transform.location.y, "z": carla_end_transform.location.z},
                    "snapped_start_location": snapped_start_loc_str,
                    "snapped_end_location": snapped_end_loc_str
                })

                if args.verbose:
                    print(f"Pair {i+1}: StartID({start_sp_id}) -> EndID({end_sp_id}) -- Status: {status}{' - ' + status_reason if status_reason else ''}")
                map_results_summary["total_pairs_processed"] += 1

                # Check if we need to stop early for this map
                if args.max_valid_per_map > 0 and valid_routes_found_this_map >= args.max_valid_per_map:
                    print(f"Reached max valid routes ({args.max_valid_per_map}) for map {map_name_from_file}. Stopping further validation for this map.")
                    map_results_summary["processing_stopped_early"] = True
                    break # Break from the loop over spawn_pairs_data

            except Exception as e:  
                detailed_reason_for_json = f"Processing Error: {type(e).__name__} - {str(e)}. Original SP IDs: {pair_info.get('spawn_point_1_id', 'N/A')}-{pair_info.get('spawn_point_2_id', 'N/A')}."
                if args.verbose:
                    print(f"Pair {i+1}: SKIPPED - Error processing pair for SP IDs {pair_info.get('spawn_point_1_id', 'N/A')}-{pair_info.get('spawn_point_2_id', 'N/A')}: {type(e).__name__} - {str(e)}. Raw data: {pair_info}")
                map_results_summary["invalid_routes"] += 1 
                map_detailed_results.append({
                    "pair_index": i,
                    "raw_pair_info": pair_info, # Keep raw info for debugging skipped pairs
                    "status": "SKIPPED_PROCESSING_ERROR",
                    "reason": detailed_reason_for_json
                })
                # Ensure total_pairs_processed is incremented even for errors if we consider it an attempt
                map_results_summary["total_pairs_processed"] += 1 
            
        print(f"--- Finished processing {filename} ---")

        # Write results for the current map if output directory is specified
        if args.output_results_dir:
            _write_map_results(args.output_results_dir, map_name_from_file, map_results_summary, map_detailed_results)

    # This code runs if the try block completed the loop successfully
    if args.output_results_dir:
        if os.path.exists(args.output_results_dir) and any(os.scandir(args.output_results_dir)):
                print(f"Validation results for individual maps have been saved in: {args.output_results_dir}")
        elif not os.path.exists(args.output_results_dir):
            print(f"Output directory {args.output_results_dir} was specified, but was not created (e.g., script exited before processing any maps or due to an error)." )
        else: # Directory exists but is empty
                print(f"Output directory {args.output_results_dir} was specified and created, but no result files were saved (e.g., no input files found or errors occurred before saving for any map)." )

    # except ConnectionRefusedError:
    #     print(f"Error: Connection to CARLA server at {args.host}:{args.port} refused. Ensure CARLA is running.")
    #     sys.exit(1) # Exit with an error code
    # except RuntimeError as e: # More specific CARLA error that might occur outside direct client calls
    #     print(f"A CARLA Runtime error occurred: {e}")
    #     sys.exit(1) 
    # except KeyboardInterrupt:
    #     print("\nScript interrupted by user (KeyboardInterrupt).")
    #     sys.exit(1) 
    # except Exception as e: # Catch any other unexpected exceptions during the main loop or setup
    #     print(f"An unexpected error occurred in main: {type(e).__name__} - {e}")
    #     import traceback
    #     traceback.print_exc()
    #     sys.exit(1) 
    # finally:
    #     # This block executes regardless of how the try/except blocks exited (unless os._exit was used)
        
    #     # Restore original CARLA world settings
    #     if client and world and original_settings: # Check all are valid
    #         try:
    #             print("Attempting to restore original CARLA world settings before exiting...")
    #             world.apply_settings(original_settings)
    #             print("Original CARLA world settings restored.")
    #         except RuntimeError as e_restore: # Specifically catch runtime if server is down
    #             print(f"Warning: Could not restore original CARLA world settings (RuntimeError: {e_restore}). Server might have been down.")
    #         except Exception as e_final_restore: # Other errors during restore
    #             print(f"Warning: Exception during final attempt to restore CARLA world settings: {e_final_restore}")
    #     elif not original_settings: # original_settings was never captured
    #         print("No original CARLA settings were captured (initial connection might have failed). Skipping final restore.")
    #     else: # original_settings captured, but client or world is None (e.g. initial connection ok, but later failed)
    #         print("CARLA client/world not available for final settings restore, though original settings were captured. Skipping.")

    #     # Cleanup CARLA server process managed by this script
    #     # The utility.cleanup_carla_server signature is (client, pid_file).
    #     # 'client' can be None if the initial connection failed or was lost.
    #     print("Attempting to cleanup CARLA server process via utility function (from finally block)...")
    #     utility.cleanup_carla_server(client, args.carla_pid_file) 
    #     print("Script finished. (message from finally block)")


def _write_map_results(output_dir, map_name, summary, detailed_results):
    if not output_dir:
        # print("No output directory specified, results will not be saved to file.")
        return

    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")
        except OSError as e:
            print(f"Error creating output directory {output_dir}: {e}. Results will not be saved.")
            return

    # Ensure map_name_processed is in summary, especially for error summaries
    if 'map_name_processed' not in summary:
        summary['map_name_processed'] = map_name

    output_data = {
        "map_name_processed": summary.get('map_name_processed', map_name), # Redundant but ensures it's there
        "summary": summary,
        "detailed_results": detailed_results
    }
    
    filename = f"{map_name}_validation_results.json"
    filepath = os.path.join(output_dir, filename)
    try:
        with open(filepath, 'w') as f:
            json.dump(output_data, f, indent=4)
        # print(f"Results for map {map_name} saved to {filepath}")
    except IOError as e:
        print(f"Error writing results for map {map_name} to {filepath}: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Validate CARLA spawn point pairs from JSON files.")
    parser.add_argument('--host', default=DEFAULT_HOST, help=f"CARLA server host (default: {DEFAULT_HOST} from utility.py)")
    parser.add_argument('--port', default=DEFAULT_PORT, type=int, help=f"CARLA server port (default: {DEFAULT_PORT} from utility.py)")
    parser.add_argument('--timeout', default=DEFAULT_TIMEOUT, type=float, help=f"CARLA client timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument('--spawn-points-dir', default=DEFAULT_SPAWN_POINTS_DIR, 
                        help=f"Directory containing spawn point distance JSON files (default: {DEFAULT_SPAWN_POINTS_DIR} relative to script location)")
    parser.add_argument('--xodr-map-dir', default=DEFAULT_XODR_MAP_DIR,
                        help=f"Directory containing .xodr map files (default: {DEFAULT_XODR_MAP_DIR} relative to script location)")
    parser.add_argument('--map-load-delay', default=4.0, type=float, help="Delay in seconds after loading a map to allow assets to load (default: 4.0s)")
    parser.add_argument('--output-results-dir', type=str, default=None, help="Directory to save the validation results as individual JSON files per map (e.g., ./validation_outputs)")
    parser.add_argument('--carla-executable', default=DEFAULT_CARLA_EXECUTABLE, help=f"Path to CARLA executable (default: {DEFAULT_CARLA_EXECUTABLE})")
    parser.add_argument('--verbose', action='store_true', help="Enable detailed print output for each spawn pair processed.")
    parser.add_argument('--max-valid-per-map', type=int, default=0, help="Maximum number of VALID routes to find per map before stopping (0 for no limit).")

    args = parser.parse_args()
    main(args)
