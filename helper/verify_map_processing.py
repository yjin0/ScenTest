import os
import glob
import json

# Define the directory containing the .xodr map files
MAPS_DIRECTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'maps')

# Define the output directory for map information
MAP_INFO_DIRECTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mapInfo')

def verify_processing():
    print(f"Verifying map processing...")
    print(f"Searching for .xodr files in: {MAPS_DIRECTORY}")
    print(f"Looking for corresponding JSON files in: {MAP_INFO_DIRECTORY}\n")

    xodr_map_files = glob.glob(os.path.join(MAPS_DIRECTORY, "*.xodr"))
    xodr_map_files.sort()  # Sort for consistent reporting

    total_xodr_maps = len(xodr_map_files)
    processed_maps_count = 0
    successfully_processed_maps = []
    missing_json_for_maps = []

    if not os.path.exists(MAP_INFO_DIRECTORY):
        print(f"Error: mapInfo directory not found at {MAP_INFO_DIRECTORY}. Cannot verify.")
        return

    for xodr_file_path in xodr_map_files:
        map_basename = os.path.basename(xodr_file_path)
        expected_json_filename = f"{map_basename.replace('.xodr', '')}_spawn_points.json"
        expected_json_path = os.path.join(MAP_INFO_DIRECTORY, expected_json_filename)

        if os.path.exists(expected_json_path):
            processed_maps_count += 1
            successfully_processed_maps.append(map_basename)
        else:
            missing_json_for_maps.append(map_basename)

    print(f"--- Verification Summary ---")
    print(f"Total .xodr maps found in '{MAPS_DIRECTORY}': {total_xodr_maps}")
    print(f"JSON files found in '{MAP_INFO_DIRECTORY}' (processed maps): {processed_maps_count}")

    if successfully_processed_maps:
        print(f"\nSuccessfully processed maps ({len(successfully_processed_maps)}):")
        for map_name in successfully_processed_maps:
            print(f"  - {map_name}")
    else:
        print("\nNo maps appear to have been successfully processed (no JSON files found).")

    if missing_json_for_maps:
        print(f"\nMaps with MISSING JSON files ({len(missing_json_for_maps)}):")
        for map_name in missing_json_for_maps:
            print(f"  - {map_name}")
    else:
        if total_xodr_maps > 0:
            print("\nAll .xodr maps seem to have a corresponding JSON file!")
        elif total_xodr_maps == 0:
            print("\nNo .xodr maps were found to verify.")

    # Create summary dictionary
    summary_data = {
        "total_xodr_maps_in_maps_dir": total_xodr_maps,
        "processed_maps_found_in_mapInfo_dir": processed_maps_count,
        "missing_json_files_count": len(missing_json_for_maps),
        "successfully_processed_map_names": successfully_processed_maps,
        "maps_with_missing_json_files": missing_json_for_maps
    }

    # Define output JSON file path
    output_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'map_processing_summary.json')

    # Write summary to JSON file
    try:
        with open(output_json_path, 'w') as f:
            json.dump(summary_data, f, indent=4)
        print(f"\nVerification summary also saved to: {output_json_path}")
    except IOError as e:
        print(f"\nError writing summary to JSON file {output_json_path}: {e}")

if __name__ == "__main__":
    verify_processing()
