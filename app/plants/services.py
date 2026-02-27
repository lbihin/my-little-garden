"""
Plant identification and species search services.

- PlantNet Identify API (image-based identification, free tier: 500 calls/day)
  API docs: https://my.plantnet.org/
- iNaturalist Taxa Autocomplete API (name-based search with photos, free)
  API docs: https://api.inaturalist.org/v1/docs/
"""

import logging

import httpx

logger = logging.getLogger(__name__)

PLANTNET_API_URL = "https://my-api.plantnet.org/v2/identify/all"
INAT_AUTOCOMPLETE_URL = "https://api.inaturalist.org/v1/taxa/autocomplete"
INAT_TAXA_URL = "https://api.inaturalist.org/v1/taxa/{taxon_id}"
TIMEOUT = 15  # seconds

# iNaturalist Plantae kingdom taxon ID
INAT_PLANTAE_TAXON_ID = 47126


# ─── Name-based search (iNaturalist) ─────────────────────────────────


def search_species(query: str) -> dict:
    """
    Search for plant species by common or scientific name using iNaturalist.

    Returns species with photos (default_photo) and French common names in a
    single API call.  Much richer than GBIF for visual identification.

    Args:
        query: Search text — works with French names ("lavande") and Latin
               names ("Lavandula").

    Returns:
        dict with keys: success, results (list of species dicts with photo_url).
    """
    if not query or len(query.strip()) < 2:
        return {"success": True, "results": []}

    params = {
        "q": query.strip(),
        "per_page": 8,
        "rank": "species",
        "locale": "fr",
        "is_active": True,
        "taxon_id": INAT_PLANTAE_TAXON_ID,
    }

    try:
        response = httpx.get(INAT_AUTOCOMPLETE_URL, params=params, timeout=TIMEOUT)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("iNaturalist HTTP error: %s", exc)
        return {"success": False, "error": f"Erreur API : {exc.response.status_code}"}
    except httpx.RequestError as exc:
        logger.error("iNaturalist request error: %s", exc)
        return {
            "success": False,
            "error": "Impossible de contacter le service de recherche.",
        }

    data = response.json()

    # Deduplicate by scientific name
    seen = set()
    results = []
    for item in data.get("results", []):
        name = item.get("name", "")
        if not name or name in seen:
            continue
        seen.add(name)

        # Extract photo URL (medium = ~500px, square = 75×75 thumbnail)
        default_photo = item.get("default_photo") or {}
        photo_url = default_photo.get("medium_url", "")
        square_url = default_photo.get("square_url", "")

        # Extract ancestors to get family name
        ancestors = item.get("ancestors", [])
        family = ""
        for a in ancestors:
            if a.get("rank") == "family":
                family = a.get("name", "")
                break

        results.append(
            {
                "scientific_name": name,
                "common_name": item.get("preferred_common_name", ""),
                "family": family,
                "photo_url": photo_url,
                "square_url": square_url,
                "inat_id": item.get("id"),
            }
        )

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
            files={
                "images": (image_file.name, image_file.read(), image_file.content_type)
            },
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
            images.append(
                {
                    "url": url.get("m", url.get("s", "")),  # medium or small
                    "organ": organ,
                    "label": labels.get(organ, "📷 Photo"),
                }
            )
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
