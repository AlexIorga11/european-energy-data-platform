from datetime import date

from locations import LOCATIONS


PRICE_ZONES = sorted({
    location["energy_zone"]
    for location in LOCATIONS.values()
    if location["energy_zone"] is not None
})
TRANSITION_DAY = date(2025, 9, 30)
HOURLY_ZONES = {"CH", "RS", "ME", "UA-IPS"}


def price_interval(zone: str, start_date: date, end_date: date) -> int:
    """Return the expected interval for a period with uniform resolution."""
    if zone not in PRICE_ZONES:
        raise ValueError(f"Price zone is not configured: {zone}")
    if start_date > end_date:
        raise ValueError("Start date must be on or before end date")
    if zone == "CH" and end_date >= date(2026, 11, 2):
        raise ValueError(
            "The configured Swiss hourly rule ends on 1 November 2026. "
            "Check the announced market transition before loading later dates."
        )
    if zone in HOURLY_ZONES:
        return 60
    if start_date <= TRANSITION_DAY <= end_date:
        raise ValueError(
            "The selected period includes the resolution transition on "
            "30 September 2025 (UTC). Mixed intervals are not supported yet. "
            "Select dates ending by 29 September or starting from 1 October."
        )
    if end_date < TRANSITION_DAY:
        return 60
    return 30 if zone == "IE(SEM)" else 15
