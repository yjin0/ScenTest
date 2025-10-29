import os
import glob
import json
import utility # Using direct import as established

# Define the output directory for cleaned spawn point files
CLEANED_MAP_INFO_DIRECTORY = os.path.join(utility.BASE_DIR, 'mapInfo_cleaned')

def clean_spawn_points_in_file(file_path, output_directory):
    """Loads spawn points, removes duplicates keeping the one with the lowest ID, and saves to output_directory."""
    try:
        with open(file_path, 'r') as f:
            spawn_points_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found {file_path}")
        return False
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {file_path}")
        return False

    if not isinstance(spawn_points_data, list):
        print(f"Warning: No spawn points list or invalid format in {file_path}. Skipping.")
        return False

    unique_poses = {}
    # Key: tuple(x, y, z, pitch, yaw, roll), Value: spawn_point_dict (the one with the lowest ID)

    for sp in spawn_points_data:
        if not all(k in sp for k in ('id', 'location', 'rotation')):
            print(f"Warning: Spawn point missing 'id', 'location', or 'rotation' in {file_path}. Data: {sp}. Skipping this entry.")
            continue
        loc = sp.get('location')
        rot = sp.get('rotation')
        if not isinstance(loc, dict) or not isinstance(rot, dict) or \
           not all(k in loc for k in ('x', 'y', 'z')) or \
           not all(k in rot for k in ('pitch', 'yaw', 'roll')):
            print(f"Warning: Spawn point location/rotation data incomplete in {file_path}. Data: {sp}. Skipping this entry.")
            continue

        # Create a hashable key for the pose
        # Using exact float values for the key as per initial understanding of "all the same"
        pose_key = (
            loc['x'], loc['y'], loc['z'],
            rot['pitch'], rot['yaw'], rot['roll']
        )

        if pose_key not in unique_poses or sp['id'] < unique_poses[pose_key]['id']:
            unique_poses[pose_key] = sp
    
    cleaned_spawn_points = list(unique_poses.values())
    # Sort the final list by ID for consistency
    cleaned_spawn_points.sort(key=lambda x: x['id'])

    output_filename = os.path.join(output_directory, os.path.basename(file_path))
    try:
        with open(output_filename, 'w') as outfile:
            json.dump(cleaned_spawn_points, outfile, indent=4)
        print(f"Successfully saved cleaned data to: {output_filename} ({len(cleaned_spawn_points)} unique points)")
        return True
    except IOError as e:
        print(f"Error: Could not write to output file {output_filename}. Reason: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while saving {output_filename}: {e}")
        return False

def main():
    """Main function to find JSON files, clean them, and save to a new directory."""
    print(f"Reading original spawn point files from: {utility.MAP_INFO_DIRECTORY}")
    
    if not os.path.exists(utility.MAP_INFO_DIRECTORY):
        print(f"Error: Original mapInfo directory not found at {utility.MAP_INFO_DIRECTORY}. Aborting.")
        return

    # Ensure the output directory exists
    os.makedirs(CLEANED_MAP_INFO_DIRECTORY, exist_ok=True)
    print(f"Saving cleaned spawn point files to: {CLEANED_MAP_INFO_DIRECTORY}")

    spawn_point_files = glob.glob(os.path.join(utility.MAP_INFO_DIRECTORY, "*_spawn_points.json"))

    if not spawn_point_files:
        print("No spawn point JSON files found to process in the original directory.")
        return

    print(f"Found {len(spawn_point_files)} spawn point files to clean.")
    processed_count = 0
    success_count = 0

    for file_path in spawn_point_files:
        processed_count += 1
        print(f"\nProcessing file {processed_count}/{len(spawn_point_files)}: {os.path.basename(file_path)}...")
        if clean_spawn_points_in_file(file_path, CLEANED_MAP_INFO_DIRECTORY):
            success_count += 1
    
    print(f"\nFinished processing. Successfully cleaned and saved {success_count}/{len(spawn_point_files)} files.")

if __name__ == "__main__":
    main()
