import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

base_url = "https://api.energy-charts.info/price"
zone = "DE-LU"
date_utc = "2025-01-01"

params = {
    "bzn": zone,
    "start": f"{date_utc}T00:00Z",
    "end": f"{date_utc}T23:59Z",
}

url = f"{base_url}?{urlencode(params)}"

with urlopen(url, timeout=30) as response:
    print("HTTP status:", response.status)
    data = json.load(response)

project_dir = Path(__file__).resolve().parent
output_dir = project_dir / "data" / "raw" / "energy_charts" / f"zone={zone}"
output_dir.mkdir(parents=True, exist_ok=True)

output_path = output_dir / f"{date_utc}.json"

with output_path.open("w", encoding="utf-8") as file:
    json.dump(data, file, indent=2, ensure_ascii=False)

print(f"Saved data to: {output_path}")