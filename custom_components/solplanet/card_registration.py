"""Serve and register the bundled Solplanet Lovelace cards.

The cards ship inside the integration (frontend/solplanet-card.js, which defines
custom:solplanet-flow-card and custom:solplanet-stats-card). Two things are needed for
dashboards to use them:

1. the folder has to be served over HTTP (a static path), and
2. the browser has to be told to load the script.

For (2) we prefer a real Lovelace *resource* (type "module"): it is visible under
Settings > Dashboards > Resources, Home Assistant reports a clear "Failed to load
Lovelace resource" error if it cannot be loaded, and it loads together with every other
card. Dashboards whose resources are managed in YAML (or any case where the resource store
is not usable) fall back to ``add_extra_js_url``, which injects the script into every page.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_FILENAME = "solplanet-card.js"
CARD_URL_BASE = f"/{DOMAIN}_static"
CARD_URL = f"{CARD_URL_BASE}/{CARD_FILENAME}"
# Serve the folder with long-lived cache headers: every URL we hand out carries a ?v= that
# changes whenever the card file changes, so browsers never keep a stale copy.
CACHE_HEADERS = True

_REGISTERED_KEY = f"{DOMAIN}_card_registered"
_LOVELACE_KEY = "lovelace"


# --------------------------------------------------------------------------- #
# Lovelace access. Home Assistant changed how this is exposed over the years:
#   < 2025.2   hass.data["lovelace"] is a dict: {"mode": ..., "resources": ...}
#   2025.2+    LovelaceData dataclass with .mode and .resources
#   2026.2+    LovelaceData.resource_mode (.mode kept as a deprecated fallback)
# --------------------------------------------------------------------------- #
def _lovelace_resources(hass: HomeAssistant) -> tuple[str | None, Any]:
    """Return (resource_mode, resource_collection), or (None, None) if unavailable."""
    data = hass.data.get(_LOVELACE_KEY)
    if data is None:
        return None, None
    if isinstance(data, dict):
        return data.get("mode"), data.get("resources")
    mode = getattr(data, "resource_mode", None)
    if mode is None:
        mode = getattr(data, "mode", None)
    return mode, getattr(data, "resources", None)


async def _async_ensure_loaded(resources: Any) -> bool:
    """Make sure the resource store has been read from disk.

    Listing resources before that returns an empty list, which would make us create a
    duplicate of an entry that already exists. Reading ``async_get_info`` loads the store.
    """
    if getattr(resources, "loaded", True):
        return True
    try:
        await resources.async_get_info()
    except Exception:  # noqa: BLE001 - never let card registration break setup
        _LOGGER.debug("Could not load Lovelace resources", exc_info=True)
    return bool(getattr(resources, "loaded", False))


def _our_resources(resources: Any) -> list[dict[str, Any]]:
    return [
        item
        for item in (resources.async_items() or [])
        if str(item.get("url", "")).split("?", 1)[0] == CARD_URL
    ]


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card and make dashboards load it. Runs once per Home Assistant start."""
    if hass.data.get(_REGISTERED_KEY):
        return
    if getattr(hass, "http", None) is None:  # e.g. tests without the http component
        return
    hass.data[_REGISTERED_KEY] = True

    card_path = Path(__file__).parent / "frontend" / CARD_FILENAME
    if not card_path.is_file():
        _LOGGER.warning("%s not found at %s", CARD_FILENAME, card_path)
        return

    await _async_register_static_path(hass, card_path.parent)

    # The cache-busting version changes whenever the card file changes, so a card update
    # always reaches browsers even if the integration version was not bumped.
    integration = await async_get_integration(hass, DOMAIN)
    digest = await hass.async_add_executor_job(_file_digest, card_path)
    version = f"{integration.version or '0'}-{digest}"
    url = f"{CARD_URL}?v={version}"

    mode, resources = _lovelace_resources(hass)
    if mode == "storage" and resources is not None:
        try:
            if await _async_ensure_loaded(resources):
                await _async_sync_resource(resources, url)
                _LOGGER.debug("%s registered as Lovelace resource %s", CARD_FILENAME, url)
                return
            _LOGGER.debug("Lovelace resources not loaded; injecting the card script instead")
        except Exception:  # noqa: BLE001
            _LOGGER.warning(
                "Could not register %s as a Lovelace resource; injecting it instead",
                CARD_FILENAME,
                exc_info=True,
            )

    # YAML-managed resources, or the resource store was not usable.
    try:
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, url)
        _LOGGER.debug("%s injected via add_extra_js_url: %s", CARD_FILENAME, url)
    except (ImportError, KeyError):  # frontend not loaded
        _LOGGER.debug("Frontend not loaded; %s not injected", CARD_FILENAME)


async def async_unregister_card(hass: HomeAssistant) -> None:
    """Remove our Lovelace resource (called when the integration is removed)."""
    mode, resources = _lovelace_resources(hass)
    if mode != "storage" or resources is None:
        return
    try:
        if not await _async_ensure_loaded(resources):
            return
        for item in _our_resources(resources):
            await resources.async_delete_item(item["id"])
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Could not remove the %s Lovelace resource", CARD_FILENAME, exc_info=True)


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #
async def _async_register_static_path(hass: HomeAssistant, folder: Path) -> None:
    from homeassistant.components.http import StaticPathConfig

    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL_BASE, str(folder), CACHE_HEADERS)]
        )
    except RuntimeError:
        _LOGGER.debug("%s static path already registered", CARD_URL_BASE)


async def _async_sync_resource(resources: Any, url: str) -> None:
    """Create our resource, or bring an existing one (even a manual one) up to date."""
    existing = _our_resources(resources)

    if not existing:
        await resources.async_create_item({"res_type": "module", "url": url})
        return

    keep, duplicates = existing[0], existing[1:]
    if keep.get("url") != url or keep.get("type") != "module":
        await resources.async_update_item(keep["id"], {"res_type": "module", "url": url})
    for extra in duplicates:
        await resources.async_delete_item(extra["id"])
