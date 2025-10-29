"""
Validates characteristic names from values.json to identify those with only text data.
Creates invalid.txt containing characteristic names that have no numeric ResultMeasureValue.
"""

import os
import json
import requests
import pandas as pd
import re
from urllib.parse import urlencode
from pathlib import Path
import time


_BAD = re.compile(r'[\\/:*?"<>|]+')
def _safe_tag(name):
    s = _BAD.sub("_", name)
    s = re.sub(r"\s+", "_", s)
    s = s.strip("._")[:80] or "value"
    return s


def fetch_API(characteristicName, startDate):
    """
    Fetch data from Water Quality API for a specific characteristic name.
    Returns path to saved CSV file, or empty string on error.
    """
    url = "https://www.waterqualitydata.us/data/Result/search?"
    
    params = {
        "characteristicName": characteristicName,
        "bBox": "-98.5,17.8,-80,31",
        "startDateLo": startDate,
        "mimeType": "csv"
    }
    
    full_url = url + urlencode(params, safe=',')
    
    # Create ResponseData directory if it doesn't exist
    target_dir = os.path.join(os.getcwd(), "ValidationData")
    os.makedirs(target_dir, exist_ok=True)
    
    safe = _safe_tag(characteristicName)
    filename = f"validate_{safe}.csv"
    raw_path = os.path.join(target_dir, filename)
    
    try:
        response = requests.get(full_url)
        if response.status_code != 200:
            print(f"  ❌ Error Code {response.status_code}")
            return ""
        
        with open(raw_path, "wb") as f:
            f.write(response.content)
        
        return raw_path
    except Exception as e:
        print(f"  ❌ Request failed: {e}")
        return ""


def validate_numeric_data(raw_path, characteristicName):
    """
    Check if the characteristic has valid numeric data in ResultMeasureValue.
    Returns True if it has numeric data, False if only text/invalid data.
    """
    cols = ["ActivityStartDate", "ResultMeasureValue"]
    
    try:
        # Try to read with specified columns
        df = pd.read_csv(raw_path, usecols=lambda c: c in cols)
    except:
        try:
            # Fallback: read all and filter
            df = pd.read_csv(raw_path)
            df = df[[c for c in cols if c in df.columns]]
        except Exception as e:
            print(f"  ❌ Failed to read CSV: {e}")
            return False
    
    # Check if CSV has any data rows (not just headers)
    if len(df) == 0:
        print(f"  ⚠️  CSV is empty (no data rows)")
        return False
    
    # Drop rows missing critical data
    df = df.dropna(subset=["ActivityStartDate", "ResultMeasureValue"])
    
    if len(df) == 0:
        print(f"  ⚠️  No data rows with valid ActivityStartDate and ResultMeasureValue")
        return False
    
    # Convert ResultMeasureValue to numeric (same as create_chart does)
    df['ResultMeasureValue'] = pd.to_numeric(df['ResultMeasureValue'], errors='coerce')
    
    # Drop rows where conversion to numeric failed
    df_numeric = df.dropna(subset=["ResultMeasureValue"])
    
    # Check if we have at least 4 numeric data points
    if len(df_numeric) <= 3:
        print(f"  ❌ Only {len(df_numeric)} numeric data points (need >3)")
        return False
    
    print(f"  ✅ Valid: {len(df_numeric)} numeric data points")
    return True


def validate_all_values():
    """
    Main function to validate all characteristic names from values.json
    and create invalid.txt with those that have no numeric data.
    """
    # Load values.json
    path = Path("values.json")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    values = [v["value"] for v in data.get("codes", [])]
    print(f"Found {len(values)} characteristic names to validate\n")
    
    # Load already processed invalid values if file exists
    invalid_values = []
    if os.path.exists("invalid.txt"):
        with open("invalid.txt", "r", encoding="utf-8") as f:
            invalid_values = [line.strip() for line in f if line.strip()]
        print(f"Found {len(invalid_values)} already processed invalid values")
        print(f"Resuming from where we left off...\n")
    
    # Filter out already processed values
    processed_values = set(invalid_values)
    remaining_values = [v for v in values if v not in processed_values]
    
    if len(remaining_values) == 0:
        print("All values have already been processed!")
        return
    
    print(f"Skipping {len(processed_values)} already processed values")
    print(f"Remaining to process: {len(remaining_values)}\n")
    
    valid_values = []
    
    # Process each characteristic name (only remaining ones)
    for idx, characteristic_name in enumerate(remaining_values, 1):
        print(f"[{idx}/{len(remaining_values)}] Testing: {characteristic_name}")
        
        # Fetch data from API
        raw_path = fetch_API(characteristic_name, "01-01-1980")
        
        if not raw_path:
            invalid_values.append(characteristic_name)
            continue
        
        # Validate if it has numeric data
        is_valid = validate_numeric_data(raw_path, characteristic_name)
        
        # Clean up the validation file
        if os.path.exists(raw_path):
            os.remove(raw_path)
        
        if is_valid:
            valid_values.append(characteristic_name)
        else:
            invalid_values.append(characteristic_name)
        
        # Small delay to avoid overwhelming the API
        time.sleep(0.5)
        
        # Progress update every 50 items
        if idx % 50 == 0:
            print(f"\n--- Progress: {idx}/{len(remaining_values)} ---")
            print(f"Valid: {len(valid_values)} | Invalid (new): {len(invalid_values) - len(processed_values)}\n")
    
    # Save invalid values to file
    invalid_path = "invalid.txt"
    with open(invalid_path, "w", encoding="utf-8") as f:
        for invalid_name in invalid_values:
            f.write(f"{invalid_name}\n")
    
    print(f"\n{'='*60}")
    print(f"Validation Complete!")
    print(f"{'='*60}")
    print(f"Total characteristics in values.json: {len(values)}")
    print(f"Previously processed: {len(processed_values)}")
    print(f"Newly processed: {len(remaining_values)}")
    print(f"✅ Valid (numeric data): {len(valid_values)}")
    print(f"❌ Total Invalid (text only or insufficient data): {len(invalid_values)}")
    print(f"❌ Newly found invalid: {len(invalid_values) - len(processed_values)}")
    print(f"\nAll invalid values saved to: {invalid_path}")
    print(f"{'='*60}")
    
    # Clean up ValidationData directory
    validation_dir = os.path.join(os.getcwd(), "ValidationData")
    if os.path.exists(validation_dir):
        try:
            os.rmdir(validation_dir)
            print(f"Cleaned up validation directory")
        except:
            print(f"Note: ValidationData directory not empty, kept for reference")


if __name__ == "__main__":
    print("="*60)
    print("Water Quality Characteristic Name Validator")
    print("="*60)
    print("This will test all values from values.json")
    print("and identify those with only text data (no numeric values).")
    print("="*60)
    print()
    
    response = input("This will make many API calls. Continue? (y/n): ")
    if response.lower() == 'y':
        validate_all_values()
    else:
        print("Validation cancelled.")
