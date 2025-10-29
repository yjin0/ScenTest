import carla
import os
import sys
import re
import pandas as pd
import numpy as np
import math

def parse_vector(text_tuple):
    """Parses a string like '(x=1.0,y=2.0,z=3.0)' into a carla.Vector3D-like dict."""
    m = re.match(r'\(x=(-?[\d\.]+),y=(-?[\d\.]+),z=(-?[\d\.]+)\)', text_tuple)
    if m:
        return {'x': float(m.group(2)), 'y': float(m.group(3)), 'z': float(m.group(4))}
    return {'x': 0.0, 'y': 0.0, 'z': 0.0}

def parse_transform(text_transform):
    """Parses a string for location and rotation."""
    loc_match = re.search(r'Location:\(x=(-?[\d\.]+),y=(-?[\d\.]+),z=(-?[\d\.]+)\)', text_transform)
    rot_match = re.search(r'Rotation:\(p=(-?[\d\.]+),y=(-?[\d\.]+),r=(-?[\d\.]+)\)', text_transform)
    
    location = {'x': 0.0, 'y': 0.0, 'z': 0.0}
    rotation = {'pitch': 0.0, 'yaw': 0.0, 'roll': 0.0}

    if loc_match:
        location = {'x': float(loc_match.group(2)), 'y': float(loc_match.group(3)), 'z': float(loc_match.group(4))}
    if rot_match:
        rotation = {'pitch': float(rot_match.group(2)), 'yaw': float(rot_match.group(3)), 'roll': float(rot_match.group(4))}
    return location, rotation

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_log_data_standalone.py <full_path_to_logfile> [output_csv_path]")
        sys.exit(1)

    recorder_file_full_path = sys.argv[1]
    output_csv_path = sys.argv[2] if len(sys.argv) > 2 else "extracted_ego_data.csv"

    client = None
    try:
        client = carla.Client('127.0.0.1', 2000)
        client.set_timeout(10.0)
        print(f"Attempting to connect to CARLA server at 127.0.0.1:2000...")
        server_version = client.get_server_version()
        print(f"Successfully connected to CARLA server (Version: {server_version}).")

        if not os.path.exists(recorder_file_full_path):
            print(f"ERROR: Log file not found at {recorder_file_full_path}")
            sys.exit(1)
        
        print(f"Reading recorder info from: {recorder_file_full_path}")
        # The True flag asks for a detailed summary
        log_data_str = client.show_recorder_file_info(recorder_file_full_path, True)
        print(f"Successfully read log file info. Total length: {len(log_data_str)} chars.")
        
        # Save the full log_data_str to a file for inspection
        log_dump_file_path = "log_data_dump.txt"
        try:
            with open(log_dump_file_path, 'w', encoding='utf-8') as f_dump:
                f_dump.write(log_data_str)
            print(f"Full log data string saved to: {os.path.abspath(log_dump_file_path)}")
        except IOError as e:
            print(f"Error saving log data string to file: {e}")

        # 1. Extract map name and load map
        map_name_match = re.search(r"Map: (\S+)", log_data_str)
        if not map_name_match:
            print("ERROR: Could not find map name in log info.")
            sys.exit(1)
        map_name = map_name_match.group(1)
        print(f"Found map: {map_name}. Loading map in CARLA...")
        world = client.load_world(map_name) # load_world implicitly waits
        town_map = world.get_map()
        print(f"Map '{map_name}' loaded successfully.")

        # 2. Find ego vehicle ID (more robustly, by 'hero' role_name)
        ego_id = None
        # Search for 'Create actor: ... type=vehicle.*, role_name=hero ... id=(<id>)
        # This regex looks for the creation event of an actor with role_name 'hero'
        ego_creation_match = re.search(r"Create actor: .*?type=vehicle\..*?,.*?role_name=(hero).*?,.*?id=(\d+)", log_data_str)
        if ego_creation_match:
            ego_id = int(ego_creation_match.group(2)) # Group 2 is the id
            print(f"Found ego vehicle (role_name='{ego_creation_match.group(1)}') with ID: {ego_id}")
        else:
            print("ERROR: Could not find ego vehicle (role_name='hero' or 'ego_vehicle') creation event in log.")
            # Fallback: Try to find any vehicle if no 'hero' is found (less reliable)
            any_vehicle_match = re.search(r"Create actor: .*?type=vehicle\..*?,.*?id=(\d+)", log_data_str)
            if any_vehicle_match:
                ego_id = int(any_vehicle_match.group(1))
                print(f"WARNING: No ego vehicle with role_name 'hero' or 'ego_vehicle' found. Using first vehicle found with ID: {ego_id}")
            else:
                print("ERROR: Could not find any vehicle actor in the log.")
                sys.exit(1)

        # 3. Parse frame data for the ego vehicle
        frame_data = []
        # Regex to find frame section and then actor states within that frame
        # This pattern looks for "Frame <frame_id>" and captures everything until the next "Frame" or end of string
        for frame_block_match in re.finditer(r"Frame (\d+)(.*?)(?=Frame \d+|$)", log_data_str, re.DOTALL):
            frame_id = int(frame_block_match.group(1))
            frame_content = frame_block_match.group(2)

            # Search for the state of our ego vehicle within this frame's content
            # State entry: "State actor <id>: Location:(...), Rotation:(...), Vel:(...), AngVel:(...), Accel:(...)"
            actor_state_match = re.search(
                r"State actor {}:\s+".format(ego_id) + 
                r"Transform:\s*(.*?)\s+" + # Capture Transform block
                r"Velocity:\s*(\(.*?\))\s+" + # Capture Velocity tuple
                r"AngVelocity:\s*(\(.*?\))\s+" + # Capture Angular Velocity tuple
                r"(Accel:\s*(\(.*?\)))?", # Optional Acceleration tuple
                frame_content, re.DOTALL
            )

            if actor_state_match:
                transform_str = actor_state_match.group(1)
                vel_str = actor_state_match.group(2)
                ang_vel_str = actor_state_match.group(3)
                # accel_str might be None if acceleration is not present
                accel_str = actor_state_match.group(5) if actor_state_match.group(4) else None

                location_dict, rotation_dict = parse_transform(transform_str)
                velocity_dict = parse_vector(vel_str)
                ang_velocity_dict = parse_vector(ang_vel_str)
                acceleration_dict = parse_vector(accel_str) if accel_str else {'x': 0.0, 'y': 0.0, 'z': 0.0}
                
                # Calculate distance to lane center
                ego_location = carla.Location(x=location_dict['x'], y=location_dict['y'], z=location_dict['z'])
                ego_waypoint = town_map.get_waypoint(ego_location, project_to_road=True, lane_type=carla.LaneType.Driving)
                
                dist_to_center = 0.0
                if ego_waypoint:
                    # Vector from waypoint center to ego vehicle
                    vec_to_ego = ego_location - ego_waypoint.transform.location
                    # Waypoint's right vector ( već_to_ego dot right_vector gives distance from center line)
                    # Note: y-axis is typically to the left in CARLA's default UE coordinate system from a vehicle's perspective
                    # So, a positive dot product with the right_vector means the vehicle is to the right of the lane center.
                    right_vec = ego_waypoint.transform.get_right_vector()
                    dist_to_center = vec_to_ego.x * right_vec.x + vec_to_ego.y * right_vec.y + vec_to_ego.z * right_vec.z
                
                frame_data.append({
                    'frame': frame_id,
                    'pos_x': location_dict['x'], 'pos_y': location_dict['y'], 'pos_z': location_dict['z'],
                    'rot_pitch': rotation_dict['pitch'], 'rot_yaw': rotation_dict['yaw'], 'rot_roll': rotation_dict['roll'],
                    'vel_x': velocity_dict['x'], 'vel_y': velocity_dict['y'], 'vel_z': velocity_dict['z'],
                    'ang_vel_x': ang_velocity_dict['x'], 'ang_vel_y': ang_velocity_dict['y'], 'ang_vel_z': ang_velocity_dict['z'],
                    'acc_x': acceleration_dict['x'], 'acc_y': acceleration_dict['y'], 'acc_z': acceleration_dict['z'],
                    'dist_to_lane_center': dist_to_center
                })
        
        if not frame_data:
            print("WARNING: No frame data extracted for the ego vehicle. The log might be empty or actor ID not found in frames.")
        else:
            print(f"Successfully parsed {len(frame_data)} frames of data for ego ID {ego_id}.")

        # 4. Save to CSV
        df = pd.DataFrame(frame_data)
        # Ensure directory for output_csv_path exists
        output_dir = os.path.dirname(os.path.abspath(output_csv_path))
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")

        df.to_csv(output_csv_path, index=False)
        print(f"Data saved to {os.path.abspath(output_csv_path)}")

    except RuntimeError as e:
        print(f"RuntimeError during CARLA client operation: {e}")
        print("Please ensure the CARLA simulator is running and accessible, and the log file is valid.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if client:
            # Optional: revert to original map if you changed it, or just disconnect.
            # For this script, simple disconnect is fine.
            pass 

if __name__ == '__main__':
    main()
