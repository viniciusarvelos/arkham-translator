import os
import json
import csv

# Folders
SOURCE_FOLDER = "/app/source"
OUTPUT_FOLDER = "/app/out"
OUTPUT_FILE = os.path.join(OUTPUT_FOLDER, "output.csv")

# Fields to extract
FIELDS = ["code", "name", "subname", "text", "traits", "flavor", "back_text", "back_flavor"]

def json_to_csv():
    rows = []

    # Make sure /out folder exists
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # Iterate over all JSON files in /source
    for filename in os.listdir(SOURCE_FOLDER):
        if filename.endswith(".json"):
            filepath = os.path.join(SOURCE_FOLDER, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"⚠️ Skipping {filename}: invalid JSON ({e})")
                    continue

                # JSON can be a dict or list
                if isinstance(data, dict):
                    items = [data]
                elif isinstance(data, list):
                    items = data
                else:
                    print(f"⚠️ Skipping {filename}: unsupported JSON structure")
                    continue

                for item in items:
                    row = {field: item.get(field, "") for field in FIELDS}
                    rows.append(row)

    # Write to CSV in /out
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Conversion complete. CSV saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    json_to_csv()
