import json
from urllib.parse import urlencode
from urllib.request import urlopen

base_url = "https://api.energy-charts.info/price"

params = {
    "bzn": "DE-LU",
    "start": "2025-01-01T00:00Z",
    "end": "2025-01-01T23:59Z",
}

url = f"{base_url}?{urlencode(params)}"

with urlopen(url, timeout=30) as response:
    print("HTTP status:", response.status)
    data = json.load(response)

print(json.dumps(data, indent=2))