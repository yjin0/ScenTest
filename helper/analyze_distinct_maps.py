import os
import json
import re

def extract_distinct_map_identifiers(scenario_dir):
    """Extracts distinct map identifiers from .xosc scenario filenames.

    A map identifier is defined as the first four underscore-separated
    components of the filename (e.g., country_city_number1_number2).

    Args:
        scenario_dir (str): The directory containing .xosc scenario files.

    Returns:
        set: A set of unique map identifiers.
    """
    distinct_identifiers = set()
    # Regex to capture the first four underscore-separated parts of the filename
    # e.g., from 'Country_City_Num1_Num2_ExtraInfo.xosc' -> 'Country_City_Num1_Num2'
    # It handles cases where parts might contain hyphens, like 'Putte-2'.
    regex = r"^([^_]+_[^_]+_[^_]+)(?:_.*)?\.xosc$"  # Capture first three underscore-separated parts

    if not os.path.isdir(scenario_dir):
        print(f"Error: Scenario directory '{scenario_dir}' not found.")
        return distinct_identifiers

    for filename in os.listdir(scenario_dir):
        if filename.endswith('.xosc'):
            match = re.match(regex, filename)
            if match:
                distinct_identifiers.add(match.group(1))
            else:
                print(f"Warning: Filename '{filename}' did not match expected pattern and was skipped.")
                
    return distinct_identifiers

def main():
    # Assuming 'opscenarios/' refers to '/home/si9h/car/maps/' based on user's active file context
    scenario_directory = '/home/si9h/car/maps/' 
    output_base_dir = '/home/si9h/car/SCTest/'
    output_subdir = 'ego_action_ana'
    output_dir = os.path.join(output_base_dir, output_subdir)

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    output_filepath = os.path.join(output_dir, 'distinct_maps.json')

    distinct_map_names_set = extract_distinct_map_identifiers(scenario_directory)
    sorted_distinct_map_names = sorted(list(distinct_map_names_set))

    result = {
        "total_distinct_maps": len(sorted_distinct_map_names),
        "distinct_map_names": sorted_distinct_map_names
    }

    try:
        with open(output_filepath, 'w') as f:
            json.dump(result, f, indent=4)
        print(f"Successfully analyzed distinct maps. Output saved to '{output_filepath}'")
        if not sorted_distinct_map_names:
            print("Warning: No distinct map names were found. Check the scenario directory and file naming convention.")
    except IOError as e:
        print(f"Error writing output JSON file '{output_filepath}': {e}")

if __name__ == '__main__':
    main()
