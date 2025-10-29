import os
import json
import xml.etree.ElementTree as ET

def extract_distinct_logic_files(scenario_dir):
    """Extracts distinct LogicFile filepaths from .xosc scenario files.

    Args:
        scenario_dir (str): The directory containing .xosc scenario files.

    Returns:
        set: A set of unique LogicFile filepaths.
    """
    distinct_filepaths = set()

    if not os.path.isdir(scenario_dir):
        print(f"Error: Scenario directory '{scenario_dir}' not found.")
        return distinct_filepaths

    for filename in os.listdir(scenario_dir):
        if filename.endswith('.xosc'):
            file_path = os.path.join(scenario_dir, filename)
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
                road_network_element = root.find('RoadNetwork')
                if road_network_element is not None:
                    logic_file_element = road_network_element.find('LogicFile')
                    if logic_file_element is not None:
                        filepath_attr = logic_file_element.get('filepath')
                        if filepath_attr:
                            distinct_filepaths.add(filepath_attr)
                        else:
                            print(f"Warning: LogicFile tag in '{filename}' has no 'filepath' attribute.")
                    else:
                        print(f"Warning: No LogicFile tag found in RoadNetwork for '{filename}'.")
                else:
                    print(f"Warning: No RoadNetwork tag found in '{filename}'.")
            except ET.ParseError:
                print(f"Warning: Could not parse XML from '{filename}'. Skipping.")
            except Exception as e:
                print(f"Warning: An unexpected error occurred while processing '{filename}': {e}. Skipping.")
                
    return distinct_filepaths

def main():
    scenario_directory = '/home/si9h/car/maps/' 
    output_base_dir = '/home/si9h/car/SCTest/'
    output_subdir = 'ego_action_ana'
    output_dir = os.path.join(output_base_dir, output_subdir)

    os.makedirs(output_dir, exist_ok=True)

    output_filepath = os.path.join(output_dir, 'distinct_logic_files.json')

    distinct_set = extract_distinct_logic_files(scenario_directory)
    sorted_distinct_list = sorted(list(distinct_set))

    result = {
        "total_distinct_logic_files": len(sorted_distinct_list),
        "distinct_logic_filepaths": sorted_distinct_list
    }

    try:
        with open(output_filepath, 'w') as f:
            json.dump(result, f, indent=4)
        print(f"Successfully analyzed distinct logic files. Output saved to '{output_filepath}'")
        if not sorted_distinct_list:
            print("Warning: No distinct logic filepaths were found. Check the scenario directory and .xosc file contents.")
    except IOError as e:
        print(f"Error writing output JSON file '{output_filepath}': {e}")

if __name__ == '__main__':
    main()
