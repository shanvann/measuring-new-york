"""Canonical neighborhood names for NYC's 59 Community Districts.

Single source of truth for the human-readable label that ships next
to each CD code in chapter visuals (hover tooltips, table labels,
inline prose). Sourced from NYC DCP Community District neighborhood
listings.

Keys are the 3-digit BoroCD strings ("101"–"503"); values are the
canonical short form used in the series.
"""

from __future__ import annotations

CD_NEIGHBORHOOD: dict[str, str] = {
    # Manhattan
    "101": "Financial District / Battery Park City",
    "102": "Greenwich Village / Soho",
    "103": "Lower East Side / Chinatown",
    "104": "Chelsea / Hell's Kitchen",
    "105": "Midtown",
    "106": "Stuyvesant Town / Turtle Bay",
    "107": "Upper West Side",
    "108": "Upper East Side",
    "109": "Manhattanville / Hamilton Heights",
    "110": "Central Harlem",
    "111": "East Harlem",
    "112": "Washington Heights / Inwood",
    # Bronx
    "201": "Mott Haven / Melrose",
    "202": "Hunts Point / Longwood",
    "203": "Morrisania / Crotona",
    "204": "Highbridge / Concourse",
    "205": "University Heights / Fordham",
    "206": "Belmont / East Tremont",
    "207": "Kingsbridge Heights / Bedford Park",
    "208": "Riverdale / Fieldston",
    "209": "Soundview / Parkchester",
    "210": "Throgs Neck / Co-op City",
    "211": "Pelham Parkway / Morris Park",
    "212": "Williamsbridge / Baychester",
    # Brooklyn
    "301": "Williamsburg / Greenpoint",
    "302": "Fort Greene / Brooklyn Heights",
    "303": "Bedford-Stuyvesant",
    "304": "Bushwick",
    "305": "East New York / Cypress Hills",
    "306": "Park Slope / Carroll Gardens",
    "307": "Sunset Park",
    "308": "Crown Heights / Prospect Heights",
    "309": "South Crown Heights / Lefferts Gardens",
    "310": "Bay Ridge / Dyker Heights",
    "311": "Bensonhurst / Bath Beach",
    "312": "Borough Park",
    "313": "Coney Island / Brighton Beach",
    "314": "Flatbush / Midwood",
    "315": "Sheepshead Bay / Manhattan Beach",
    "316": "Brownsville",
    "317": "East Flatbush / Farragut",
    "318": "Canarsie / Flatlands",
    # Queens
    "401": "Astoria",
    "402": "Sunnyside / Woodside",
    "403": "Jackson Heights / North Corona",
    "404": "Elmhurst / Corona",
    "405": "Ridgewood / Maspeth",
    "406": "Forest Hills / Rego Park",
    "407": "Flushing / Bay Terrace",
    "408": "Hillcrest / Fresh Meadows",
    "409": "Kew Gardens / Woodhaven",
    "410": "South Ozone Park / Howard Beach",
    "411": "Bayside / Little Neck",
    "412": "Jamaica / Hollis",
    "413": "Queens Village / Cambria Heights",
    "414": "Rockaway / Broad Channel",
    # Staten Island
    "501": "St. George / Stapleton",
    "502": "South Beach / Willowbrook",
    "503": "Tottenville / Great Kills",
}


def name_for(boro_cd: str) -> str:
    """Return the canonical neighborhood name for a BoroCD, or the code itself
    if the CD is unknown (JIAs like parks/airports, or invalid codes)."""
    return CD_NEIGHBORHOOD.get(boro_cd, boro_cd)
