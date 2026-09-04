import json
import math
from pathlib import Path

project_dir = Path(__file__).resolve().parent
input_path = (
    project_dir
    / "data"
    / "raw"
    / "energy_charts"
    / "zone=DE-LU"
    / "2025-01-01.json"
)

with input_path.open("r", encoding="utf-8") as file:
    data = json.load(file)

if not isinstance(data, dict):
    raise ValueError("Expected a JSON object")

timestamps = data.get("unix_seconds")
prices = data.get("price")

if not isinstance(timestamps, list) or not isinstance(prices, list):
    raise ValueError("Timestamps and prices must be lists")

if not timestamps or not prices:
    raise ValueError("The dataset is empty")

if len(timestamps) != len(prices):
    raise ValueError("Timestamp and price counts do not match")

for timestamp in timestamps:
    if type(timestamp) is not int:
        raise ValueError(f"Invalid timestamp: {timestamp}")

if len(set(timestamps)) != len(timestamps):
    raise ValueError("Duplicate timestamps found")

for price in prices:
    if type(price) not in (int, float) or not math.isfinite(price):
        raise ValueError(f"Invalid price: {price}")

print(f"Validation passed: {len(prices)} price records")