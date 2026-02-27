"""
Plant identification and species search services.

- PlantNet Identify API (image-based identification, free tier: 500 calls/day)
  API docs: https://my.plantnet.org/
- GBIF Species Suggest API (name-based search, free, no key needed)
  API docs: https://www.gbif.org/developer/species
"""

import logging

import httpx

logger = logging.getLogger(__name__)

PLANTNET_API_URL = "https://my-api.plantnet.org/v2/identify/all"
GBIF_SUGGEST_URL = "https://api.gbif.org/v1/species/suggest"
TIMEOUT = 15  # seconds


# ─── Name-based search (GBIF) ────────────────────────────────────────


def search_species(query: str) -> dict:
    """
    Search for plant species by common or scientific name using GBIF.

    Args:
        query: Search text (e.g. "lavande", "Lavandula").

    Returns:
        dict with keys: success, results (list of species dicts).
    """
    if not query or len(query.strip()) < 2:
        return {"success": True, "results": []}

    params = {
        "q": query.strip(),
        "limit": 8,
        "rank": "SPECIES",
        "highertaxonKey": 6,  # Plantae kingdom key in GBIF
    }

    try:
        response = httpx.get(GBIF_SUGGEST_URL, params=params, timeout=TIMEOUT)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("GBIF HTTP error: %s", exc)
        return {"success": False, "error": f"Erreur API : {exc.response.status_code}"}
    except httpx.RequestError as exc:
        logger.error("GBIF request error: %s", exc)
        return {
            "success": False,
            "error": "Impossible de contacter le service de recherche.",
        }

    data = response.json()

    # Deduplicate by canonical name (GBIF can return synonyms of the same species)
    seen = set()
    results = []
    for item in data:
        canonical = item.get("canonicalName", "")
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        results.append(
            {
                "scientific_name": canonical,
                "family": item.get("family", ""),
                "genus": item.get("genus", ""),
                "gbif_key": item.get("key"),
            }
        )

    return {"success": True, "results": results}


# ─── Image-based identification (PlantNet) ───────────────────────────


def identify_plant(image_url: str, api_key: str) -> dict:
    """
    Identify a plant from an image URL using PlantNet API.

    Args:
        image_url: Public URL of the plant image.
        api_key: PlantNet API key.

    Returns:
        dict with keys: success, common_name, scientific_name, score, family,
                        all_results (list of suggestions).
    """
    if not api_key:
        return {"success": False, "error": "Clé API PlantNet non configurée."}

    params = {
        "images": [image_url],
        "organs": ["auto"],
        "include-related-images": False,
        "no-reject": False,
        "nb-results": 5,
        "lang": "fr",
        "type": "all",
        "api-key": api_key,
    }

    try:
        response = httpx.get(
            PLANTNET_API_URL,
            params=params,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("PlantNet HTTP error: %s", exc)
        return {"success": False, "error": f"Erreur API : {exc.response.status_code}"}
    except httpx.RequestError as exc:
        logger.error("PlantNet request error: %s", exc)
        return {"success": False, "error": "Impossible de contacter PlantNet."}

    data = response.json()
    results = data.get("results", [])

    if not results:
        return {"success": False, "error": "Aucune plante identifiée."}

    best = results[0]
    species = best.get("species", {})
    common_names = species.get("commonNames", [])

    return {
        "success": True,
        "common_name": (
            common_names[0]
            if common_names
            else species.get("scientificNameWithoutAuthor", "")
        ),
        "scientific_name": species.get("scientificNameWithoutAuthor", ""),
        "family": species.get("family", {}).get("scientificNameWithoutAuthor", ""),
        "score": round(best.get("score", 0) * 100, 1),
        "all_results": [
            {
                "common_name": (
                    r["species"].get("commonNames", [""])[0]
                    if r["species"].get("commonNames")
                    else ""
                ),
                "scientific_name": r["species"].get("scientificNameWithoutAuthor", ""),
                "score": round(r.get("score", 0) * 100, 1),
            }
            for r in results[:5]
        ],
    }
