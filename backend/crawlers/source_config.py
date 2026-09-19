"""Reviewed endpoint corrections shared by live crawls and diagnostics.

These corrections establish source identity, not availability or parser coverage.
Do not manufacture ASP.NET session IDs or disable TLS verification.
"""

from copy import deepcopy


# Verified official pages: https://dopt.gov.in/,
# https://erajyapatra.karnataka.gov.in/,
# https://eitbt.karnataka.gov.in/it/public/policy5/en.
DOPT_DOMAINS = [
    "dopt.gov.in", "www.dopt.gov.in",
    "doptcirculars.nic.in", "documents.doptcirculars.nic.in",
]
PIB_RSS_URL = "https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"

_CORRECTIONS = {
    "dopt": ({
        "https://www.dopt.gov.in/orders-circulars": "https://dopt.gov.in/",
        "https://www.dopt.gov.in/circulars-orders": "https://dopt.gov.in/",
        "https://www.dopt.gov.in/rti": "https://dopt.gov.in/",
    }, DOPT_DOMAINS),
    "egazette": ({
        "https://egazette.gov.in/(S(a))/default.aspx": "https://egazette.gov.in/",
        "https://egazette.gov.in/WriteReadData/2026": "https://egazette.gov.in/",
    }, ["egazette.gov.in", "www.egazette.gov.in"]),
    "karnataka_egazette": ({
        "https://egazette.karnataka.gov.in/Gazettes.aspx": "https://erajyapatra.karnataka.gov.in/",
        "https://egazette.karnataka.gov.in/": "https://erajyapatra.karnataka.gov.in/",
    }, ["erajyapatra.karnataka.gov.in"]),
    "karnataka_itbt": ({
        "https://itbt.karnataka.gov.in/page/Notifications-and-Circulars/en": "https://eitbt.karnataka.gov.in/it/public/policy5/en",
        "https://itbt.karnataka.gov.in/page/Policies/en": "https://eitbt.karnataka.gov.in/it/public/policy5/en",
        "https://itbt.karnataka.gov.in/": "https://eitbt.karnataka.gov.in/it/public/policy5/en",
    }, ["eitbt.karnataka.gov.in"]),
}


def normalize_source_config(config: dict) -> dict:
    """Flatten stored policy and repair only known obsolete seed URLs.

    Custom seeds, source IDs, and MongoDB records are not rewritten. The IT-BT
    replacement is a verified policy page; it is not a notifications listing.
    """
    result = deepcopy(config)
    policy = result.pop("crawl_policy", {})
    result.update(policy)
    result["enabled"] = result.get("enabled", True) and result.get("status", "active") == "active"
    replacements, domains = _CORRECTIONS.get(result.get("source_id"), ({}, []))
    if "seed_urls" in result:
        result["seed_urls"] = list(dict.fromkeys(
            replacements.get(url, url) for url in result["seed_urls"]
        ))
    if domains:
        result["base_domains"] = list(dict.fromkeys(result.get("base_domains", []) + domains))
    return result
