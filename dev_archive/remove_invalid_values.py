import json

def remove_invalid_values():
    """
    Remove invalid values from values.json based on invalid.txt
    and create a new filtered JSON file.
    """
    
    # Read invalid values from invalid.txt
    print("Reading invalid values from invalid.txt...")
    with open('invalid.txt', 'r', encoding='utf-8') as f:
        invalid_values = set(line.strip() for line in f if line.strip())
    
    print(f"Found {len(invalid_values)} invalid values to filter out")
    
    # Read the JSON file
    print("\nReading values.json...")
    with open('values.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    original_count = len(data['codes'])
    print(f"Original JSON contains {original_count} entries")
    
    # Filter out invalid values
    print("\nFiltering invalid values...")
    filtered_codes = [
        code for code in data['codes'] 
        if code['value'] not in invalid_values
    ]
    
    # Create new data structure with filtered codes
    filtered_data = {
        'codes': filtered_codes,
        'recordCount': len(filtered_codes)
    }
    
    removed_count = original_count - len(filtered_codes)
    print(f"Removed {removed_count} invalid entries")
    print(f"Remaining entries: {len(filtered_codes)}")
    
    # Write to new JSON file
    output_file = 'values_filtered.json'
    print(f"\nWriting filtered data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Successfully created {output_file}")
    print(f"  - Original entries: {original_count}")
    print(f"  - Filtered entries: {len(filtered_codes)}")
    print(f"  - Removed entries: {removed_count}")
    
    return filtered_data

if __name__ == '__main__':
    remove_invalid_values()
