import io
import csv
import json


def read_csv_or_json(uploaded_file):
    """
    Reads an uploaded Django File (opened in 'rb' mode) and detects if it's CSV or JSON.
    Returns a list of dictionaries (rows), or raises an exception if the content is invalid.
    """

    try:
        content = uploaded_file.read().decode('utf-8-sig').strip()
    except Exception as e:
        raise Exception(f"❌ Failed to decode file content: {e}")

    # Case: JSON File
    if content.startswith('['):
        try:
            json_data = json.loads(content)

            # Support phpMyAdmin-style JSON structure
            for item in json_data:
                if isinstance(item, dict) and item.get("type") == "table" and "data" in item:
                    return item["data"]

            # Fallback: raw JSON array of records
            if isinstance(json_data, list) and all(isinstance(row, dict) for row in json_data):
                return json_data

            raise Exception("❌ JSON format is invalid or unsupported.")

        except json.JSONDecodeError as e:
            raise Exception(f"❌ Invalid JSON format: {e}")

    # Case: CSV File
    else:
        try:
            file = io.StringIO(content)
            reader = csv.DictReader(file)
            rows = list(reader)

            if not rows or not isinstance(rows[0], dict):
                raise Exception("❌ CSV file is empty or improperly formatted.")

            return rows

        except Exception as e:
            raise Exception(f"❌ Failed to parse CSV file: {e}")
