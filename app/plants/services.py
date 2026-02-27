"""
Plant identification and species search services.

- PlantNet Identify API (image-based identification, free tier: 500 calls/day)
  API docs: https://my.plantnet.org/
- GBIF Species Suggest API (name-based search, free, no key needed)
  API docs: https://www.gbif.org/developer/species
- GBIF Species Media API (photos for species, free, no key needed)
"""

import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

PLANTNET_API_URL = "https://my-api.plantnet.org/v2/identify/all"
GBIF_SUGGEST_URL = "https://api.gbif.org/v1/species/suggest"
GBIF_MEDIA_URL = "https://api.gbif.org/v1/species/{key}/media"
TIMEOUT = 15  # seconds


# ─── Name-based search (GBIF) ────────────────────────────────────────


def _fetch_species_media(gbif_key: int) -> list[dict]:
    """Fetch photos for a GBIF species key, grouped by type when possible."""
    try:
        response = httpx.get(
            GBIF_MEDIA_URL.format(key=gbif_key),
            params={"limit": 12},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except (httpx.HTTPStatusError, httpx.RequestError):
        return []

    data = response.json()
    results = data.get("results", [])

    photos = []
    for item in results:
        url = item.get("identifier", "")
        if not url or not url.startswith("http"):
            continue
        # Try to detect organ type from description/title
        desc = (item.get("description", "") or "").lower()
        title = (item.get("title", "") or "").lower()
        combined = f"{desc} {title}"

        if any(w in combined for w in ("leaf", "feuille", "leaves", "foliage")):
            organ = "leaf"
            label = "🍃 Feuille"
        elif any(w in combined for w in ("flower", "fleur", "bloom", "blossom")):
            organ = "flower"
            label = "🌸 Fleur"
        elif any(w in combined for w in ("bark", "trunk", "tronc", "écorce", "stem")):
            organ = "bark"
            label = "🪵 Tronc"
        elif any(w in combined for w in ("fruit", "seed", "graine")):
            organ = "fruit"
            label = "🍎 Fruit"
        elif any(w in combined for w in ("habit", "whole", "plant", "plante", "general")):
            organ = "habit"
            label = "🌿 Plante entière"
        else:
            organ = "other"
            label = "📷 Photo"

        photos.append({"url": url, "organ": organ, "label": label})

    # Deduplicate by organ — keep max 1 per organ type, plus up to 2 "other"
    seen_organs = set()
    deduped = []
    others = 0
    for p in photos:
        if p["organ"] == "other":
            if others < 2:
                deduped.append(p)
                others += 1
        elif p["organ"] not in seen_organs:
            seen_organs.add(p["organ"])
            deduped.append(p)

    # If no organ-classified photos, take first 4 generic ones
    if not deduped and photos:
        deduped = photos[:4]

    return deduped[:6]


def search_species(query: str, include_media: bool = False) -> dict:
    """
    Search for plant species by common or scientific name using GBIF.

    Args:
        query: Search text (e.g. "lavande", "Lavandula").
        include_media: If True, fetch photos for each result (slower).

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

        species_data = {
            "scientific_name": canonical,
            "family": item.get("family", ""),
            "genus": item.get("genus", ""),
            "gbif_key": item.get("key"),
            "photos": [],
        }

        # Fetch media if requested
        if include_media and item.get("key"):
            species_data["photos"] = _fetch_species_media(item["key"])

        results.append(species_data)

    return {"success": True, "results": results}


# ─── Image-based identification (PlantNet) ───────────────────────────


def identify_plant_from_file(image_file, api_key: str) -> dict:
    """
    Identify a plant from an uploaded image file using PlantNet API.

    Args:
        image_file: An uploaded file object (e.g. request.FILES['photo']).
        api_key: PlantNet API key.

    Returns:
        dict with keys: success, common_name, scientific_name, score, family,
                        all_results (list of suggestions with images).
    """
    if not api_key:
        return {"success": False, "error": "Clé API PlantNet non configurée."}

    try:
        response = httpx.post(
            PLANTNET_API_URL,
            params={
                "include-related-images": True,
                "no-reject": False,
                "nb-results": 5,
                "lang": "fr",
                "type": "all",
                "api-key": api_key,
            },
            files={"images": (image_file.name, image_file.read(), image_file.content_type)},
            data={"organs": "auto"},
            timeout=30,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("PlantNet HTTP error: %s", exc)
        return {"success": False, "error": f"Erreur API : {exc.response.status_code}"}
    except httpx.RequestError as exc:
        logger.error("PlantNet request error: %s", exc)
        return {"success": False, "error": "Impossible de contacter PlantNet."}

    return _parse_plantnet_response(response.json())


def identify_plant(image_url: str, api_key: str) -> dict:
    """
    Identify a plant from an image URL using PlantNet API.

    Args:
        image_url: Public URL of the plant image.
        api_key: PlantNet API key.

    Returns:
        dict with keys: success, common_name, scientific_name, score, family,
                        all_results (list of suggestions with images).
    """
    if not api_key:
        return {"success": False, "error": "Clé API PlantNet non configurée."}

    params = {
        "images": [image_url],
        "organs": ["auto"],
        "include-related-images": True,
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

    return _parse_plantnet_response(response.json())


def _parse_plantnet_response(data: dict) -> dict:
    """Parse PlantNet API response into a standardized result dict."""
    results = data.get("results", [])

    if not results:
        return {"success": False, "error": "Aucune plante identifiée."}

    best = results[0]
    species = best.get("species", {})
    common_names = species.get("commonNames", [])

    def _extract_images(result: dict) -> list[dict]:
        """Extract reference images from a PlantNet result."""
        images = []
        for img in result.get("images", [])[:4]:
            url = img.get("url", {})
            organ = img.get("organ", "")
            labels = {
                "leaf": "🍃 Feuille",
                "flower": "🌸 Fleur",
                "bark": "🪵 Tronc",
                "fruit": "🍎 Fruit",
                "habit": "🌿 Plante entière",
            }
            images.append({
                "url": url.get("m", url.get("s", "")),  # medium or small
                "organ": organ,
                "label": labels.get(organ, "📷 Photo"),
            })
        return images

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
                "images": _extract_images(r),
            }
            for r in results[:5]
        ],
    }
