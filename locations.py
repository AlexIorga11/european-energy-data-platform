DEFAULT_LOCATION = "berlin"


# id, city, country, latitude, longitude, configured Energy-Charts zone
# None means no price-zone mapping has been configured for this city.
CAPITAL_DATA = [
    ("amsterdam", "Amsterdam", "Netherlands", 52.3676, 4.9041, "NL"),
    ("andorra_la_vella", "Andorra la Vella", "Andorra", 42.5063, 1.5218, None),
    ("ankara", "Ankara", "Turkey", 39.9334, 32.8597, None),
    ("astana", "Astana", "Kazakhstan", 51.1694, 71.4491, None),
    ("athens", "Athens", "Greece", 37.9838, 23.7275, "GR"),
    ("baku", "Baku", "Azerbaijan", 40.4093, 49.8671, None),
    ("belgrade", "Belgrade", "Serbia", 44.7866, 20.4489, "RS"),
    ("berlin", "Berlin", "Germany", 52.52, 13.41, "DE-LU"),
    ("bern", "Bern", "Switzerland", 46.9480, 7.4474, "CH"),
    ("bratislava", "Bratislava", "Slovakia", 48.1486, 17.1077, "SK"),
    ("brussels", "Brussels", "Belgium", 50.8503, 4.3517, "BE"),
    ("bucharest", "Bucharest", "Romania", 44.4268, 26.1025, "RO"),
    ("budapest", "Budapest", "Hungary", 47.4979, 19.0402, "HU"),
    ("chisinau", "Chisinau", "Moldova", 47.0105, 28.8638, None),
    ("copenhagen", "Copenhagen", "Denmark", 55.6761, 12.5683, "DK2"),
    ("dublin", "Dublin", "Ireland", 53.3498, -6.2603, "IE(SEM)"),
    ("helsinki", "Helsinki", "Finland", 60.1699, 24.9384, "FI"),
    ("kyiv", "Kyiv", "Ukraine", 50.4501, 30.5234, "UA-IPS"),
    ("lisbon", "Lisbon", "Portugal", 38.7223, -9.1393, "PT"),
    ("ljubljana", "Ljubljana", "Slovenia", 46.0569, 14.5058, "SI"),
    ("london", "London", "United Kingdom", 51.5074, -0.1278, None),
    ("luxembourg", "Luxembourg", "Luxembourg", 49.6116, 6.1319, "DE-LU"),
    ("madrid", "Madrid", "Spain", 40.4168, -3.7038, "ES"),
    ("minsk", "Minsk", "Belarus", 53.9006, 27.5590, None),
    ("monaco", "Monaco", "Monaco", 43.7311, 7.4197, None),
    ("moscow", "Moscow", "Russia", 55.7558, 37.6173, None),
    ("nicosia", "Nicosia", "Cyprus", 35.1856, 33.3823, None),
    ("oslo", "Oslo", "Norway", 59.9139, 10.7522, "NO1"),
    ("paris", "Paris", "France", 48.8566, 2.3522, "FR"),
    ("podgorica", "Podgorica", "Montenegro", 42.4304, 19.2594, "ME"),
    ("prague", "Prague", "Czechia", 50.0755, 14.4378, "CZ"),
    ("pristina", "Pristina", "Kosovo", 42.6629, 21.1655, None),
    ("reykjavik", "Reykjavik", "Iceland", 64.1466, -21.9426, None),
    ("riga", "Riga", "Latvia", 56.9496, 24.1052, "LV"),
    ("rome", "Rome", "Italy", 41.9028, 12.4964, "IT-Centre-South"),
    ("san_marino", "San Marino", "San Marino", 43.9367, 12.4473, None),
    ("sarajevo", "Sarajevo", "Bosnia and Herzegovina", 43.8563, 18.4131, None),
    ("skopje", "Skopje", "North Macedonia", 41.9973, 21.4280, None),
    ("sofia", "Sofia", "Bulgaria", 42.6977, 23.3219, "BG"),
    ("stockholm", "Stockholm", "Sweden", 59.3293, 18.0686, "SE3"),
    ("tallinn", "Tallinn", "Estonia", 59.4370, 24.7536, "EE"),
    ("tbilisi", "Tbilisi", "Georgia", 41.7151, 44.8271, None),
    ("tirana", "Tirana", "Albania", 41.3275, 19.8187, None),
    ("vaduz", "Vaduz", "Liechtenstein", 47.1410, 9.5209, None),
    ("valletta", "Valletta", "Malta", 35.8992, 14.5141, None),
    ("vatican_city", "Vatican City", "Vatican City", 41.9029, 12.4534, None),
    ("vienna", "Vienna", "Austria", 48.2082, 16.3738, "AT"),
    ("vilnius", "Vilnius", "Lithuania", 54.6872, 25.2797, "LT"),
    ("warsaw", "Warsaw", "Poland", 52.2297, 21.0122, "PL"),
    ("yerevan", "Yerevan", "Armenia", 40.1792, 44.4991, None),
    ("zagreb", "Zagreb", "Croatia", 45.8150, 15.9819, "HR"),
]


LOCATIONS = {
    location_id: {
        "name": name,
        "country": country,
        "latitude": latitude,
        "longitude": longitude,
        "energy_zone": energy_zone,
    }
    for location_id, name, country, latitude, longitude, energy_zone
    in CAPITAL_DATA
}


def get_location(location_id: str) -> dict:
    if location_id not in LOCATIONS:
        available = ", ".join(LOCATIONS)
        raise ValueError(
            f"Unknown location: {location_id}. Available locations: {available}"
        )
    return LOCATIONS[location_id]