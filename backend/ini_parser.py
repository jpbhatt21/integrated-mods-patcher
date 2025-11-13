import re
from typing import Dict
from pathlib import Path
from flask import json


def parse_ini_by_hash(ini_content: str) -> Dict[str, str]:
    """
    Parse INI content and extract hash mappings.
    
    Args:
        ini_content: The string content of the INI file
        
    Returns:
        Dictionary mapping paths to hash values
    """
    result = {}
    current_category = "Unknown"
    current_section = "Unknown"
    
    # Pattern to match category headers like "; Overrides ---------------------------" or "; Shading: Draw Call Stacks Processing -------------------------"
    category_pattern = re.compile(r'^;\s*(.+?)\s*-+\s*$')
    
    # Pattern to match section headers like "[TextureOverrideMarkBoneDataCB]"
    section_pattern = re.compile(r'^\[(.+)\]$')
    
    # Pattern to match hash lines like "hash = f02baf77"
    hash_pattern = re.compile(r'^hash\s*=\s*([a-fA-F0-9]+)\s*$')
    
    lines = ini_content.splitlines()
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Check if this is a category header
        category_match = category_pattern.match(line)
        if category_match:
            # Use the matched text as category name (includes colons if present)
            current_category = category_match.group(1).strip()
            continue
        
        # Check if this is a section header
        section_match = section_pattern.match(line)
        if section_match:
            current_section = section_match.group(1)
            continue
        
        # Check if this is a hash line
        hash_match = hash_pattern.match(line)
        if hash_match and current_category and current_section:
            hash_value = hash_match.group(1)
            
            # Create the path by removing all spaces from category and section
            category_no_spaces = current_category.replace(" ", "")
            section_no_spaces = current_section.replace(" ", "")
            path = f"{category_no_spaces}/{section_no_spaces}"
            
            # Map path to hash
            result[path] = hash_value
    
    return result


def print_parsed_ini(data: Dict[str, str]):
    """
    Pretty print the parsed INI data.
    
    Args:
        data: The dictionary returned by parse_ini_by_hash
    """
    print("{")
    for path, hash_value in data.items():
        print(f"  \"{path}\": \"{hash_value}\",")
    print("}")


def compare_data_list(data_list: list) -> Dict[str, Dict[str, int]]:
    """
    Compare consecutive elements in data_list and build a hash mapping.
    For each data[i-1] vs data[i], maps hash values that differ.
    For the last element, adds all its hashes to the hash map.
    
    Args:
        data_list: List of dictionaries from parse_ini_by_hash
        
    Returns:
        A dictionary mapping hash values to their replacement counts.
        Structure:
        {
            "hash_from_prev": {
                "hash_from_current": count,
                ...
            },
            ...
        }
    """
    hash_map = {}
    
    for i in range(len(data_list)):
        if i == 0:
            # Skip the first element as there's no previous to compare
            continue
        
        # Compare data[i-1] with data[i]
        prev_data = data_list[i-1]
        curr_data = data_list[i]
        
        for key, prev_hash in prev_data.items():
            if prev_hash not in hash_map:
                hash_map[prev_hash] = {}
            
            if key in curr_data and curr_data[key] != prev_hash:
                curr_hash = curr_data[key]
                if curr_hash not in hash_map[prev_hash]:
                    hash_map[prev_hash][curr_hash] = 0
                hash_map[prev_hash][curr_hash] += 1
        
        # If this is the last element, add all its hashes
        if i == len(data_list) - 1:
            for key, curr_hash in curr_data.items():
                if curr_hash not in hash_map:
                    hash_map[curr_hash] = {}
    
    return hash_map

def process_ini_for_mapping(ini_files: list):
    data_list = []
    for ini_file in ini_files:
        try:
            data = parse_ini_by_hash(ini_file)
            data_list.append(data)            
        except Exception as e:
            print(f"Error: {e}")
    
    return compare_data_list(data_list)

if __name__ == "__main__":
    # Example usage
    ini_files = ["temp_A.ini", "temp_B.ini"]  
    data_list = []
    for ini_file in ini_files:
        try:
            # Read file content
            with open(ini_file, 'r', encoding='utf-8') as f:
                ini_content = f.read()
            
            data = parse_ini_by_hash(ini_content)
            data_list.append(data)
            print_parsed_ini(data)            

            print(f"\nTotal entries: {len(data)}")

            # Count by category
            category_counts = {}
            for path in data.keys():
                category = path.split('/')[0]
                category_counts[category] = category_counts.get(category, 0) + 1

            print("\nEntries per category:")
            for category, count in sorted(category_counts.items()):
                print(f"  {category}: {count}")

            # Count unique hashes
            unique_hashes = set(data.values())
            print(f"\nUnique hash values: {len(unique_hashes)}")

        except FileNotFoundError:
            print(f"Error: File '{ini_file}' not found.")
        except Exception as e:
            print(f"Error: {e}")   
   
    hash_map = compare_data_list(data_list)
    print(hash_map)

