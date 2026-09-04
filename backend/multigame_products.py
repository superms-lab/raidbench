from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Collection


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_PATH = ROOT / "content" / "multigame-products.json"
DEFAULT_GAME_REGISTRY_PATH = ROOT / "content" / "game-registry.json"

PROHIBITED_REQUEST_PATTERNS = (
    re.compile(r"\b(?:aimbot|wallhack|triggerbot|speedhack)\b", re.IGNORECASE),
    re.compile(r"\b(?:bypass|evade)\s+(?:an?\s+)?anti[- ]?cheat\b", re.IGNORECASE),
    re.compile(r"\b(?:abuse|use|execute)\s+(?:an?\s+)?(?:dupe|duplication|game[- ]breaking)\s+(?:bug|exploit)\b", re.IGNORECASE),
    re.compile(r"\b(?:real[- ]?money trading|rmt|buy|sell)\s+(?:an?\s+)?(?:account|currency|gold)\b", re.IGNORECASE),
    re.compile(r"\b(?:rank|account)\s+boosting\s+(?:service|seller|provider)\b", re.IGNORECASE),
)


class ProductCatalogError(RuntimeError):
    pass


class ProductRoutingError(RuntimeError):
    pass


def _read_object(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProductCatalogError(f"Could not load multi-game product data: {error}") from error
    if not isinstance(value, dict):
        raise ProductCatalogError("Multi-game product data must be a JSON object.")
    return value


def load_product_catalog(
    catalog_path: str | Path = DEFAULT_CATALOG_PATH,
    game_registry_path: str | Path = DEFAULT_GAME_REGISTRY_PATH,
) -> dict[str, Any]:
    catalog = _read_object(catalog_path)
    registry = _read_object(game_registry_path)
    products = catalog.get("products")
    games = registry.get("games")
    if not isinstance(products, list) or not products:
        raise ProductCatalogError("The multi-game product catalog is empty.")
    if not isinstance(games, list) or not games:
        raise ProductCatalogError("The game registry is empty.")

    game_by_id = {
        str(game.get("id")): game
        for game in games
        if isinstance(game, dict) and game.get("id")
    }
    seen_products: set[str] = set()
    seen_games: set[str] = set()
    allowed_statuses = set(catalog.get("policy", {}).get("publicStatuses", [])) | {
        str(catalog.get("policy", {}).get("defaultStatus", "hidden_pending_qa"))
    }

    for product in products:
        if not isinstance(product, dict):
            raise ProductCatalogError("Every multi-game product must be a JSON object.")
        product_id = str(product.get("id", ""))
        game_id = str(product.get("gameId", ""))
        required_inputs = product.get("requiredInputs")
        if not product_id or product_id in seen_products:
            raise ProductCatalogError(f"Duplicate or missing product id: {product_id or '<empty>'}")
        if game_id == "rust" or game_id not in game_by_id:
            raise ProductCatalogError(f"Product {product_id} has an invalid game id: {game_id}")
        if game_id in seen_games:
            raise ProductCatalogError(f"More than one Phase 5 product is assigned to {game_id}.")
        if not isinstance(required_inputs, list) or len(required_inputs) < 4:
            raise ProductCatalogError(f"Product {product_id} has incomplete required inputs.")
        if not isinstance(product.get("credits"), int) or int(product["credits"]) <= 0:
            raise ProductCatalogError(f"Product {product_id} has an invalid credit price.")
        if str(product.get("status", "")) not in allowed_statuses:
            raise ProductCatalogError(f"Product {product_id} has an unsupported status.")
        seen_products.add(product_id)
        seen_games.add(game_id)

    return {
        **catalog,
        "products": products,
        "gameById": game_by_id,
    }


def public_multigame_catalog(
    catalog_path: str | Path = DEFAULT_CATALOG_PATH,
    game_registry_path: str | Path = DEFAULT_GAME_REGISTRY_PATH,
    enabled_product_ids: Collection[str] | None = None,
) -> dict[str, Any]:
    catalog = load_product_catalog(catalog_path, game_registry_path)
    public_statuses = set(catalog.get("policy", {}).get("publicStatuses", ["ready_live"]))
    visible = []
    enabled = set(enabled_product_ids) if enabled_product_ids is not None else None
    for product in catalog["products"]:
        if product["status"] not in public_statuses or (enabled is not None and product["id"] not in enabled):
            continue
        game = catalog["gameById"][product["gameId"]]
        visible.append({
            "id": product["id"],
            "gameId": product["gameId"],
            "game": game.get("name", product["gameId"]),
            "label": product["label"],
            "credits": product["credits"],
            "output": product["output"],
            "requiredInputs": product["requiredInputs"],
        })
    return {
        "asOf": catalog.get("asOf", ""),
        "currency": catalog.get("billingCurrency", "USD"),
        "launchMarkets": catalog.get("markets", ["US", "CA"]),
        "products": visible,
        "hiddenPendingQaCount": len(catalog["products"]) - len(visible),
        "chargePolicy": "Credits are charged only after supported scope and answer QA pass.",
    }


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def _policy_blocked(text: str, inputs: dict[str, Any]) -> bool:
    searchable = f"{text}\n{json.dumps(inputs, ensure_ascii=True)}"
    return any(pattern.search(searchable) for pattern in PROHIBITED_REQUEST_PATTERNS)


def route_multigame_request(
    payload: dict[str, Any],
    *,
    catalog_path: str | Path = DEFAULT_CATALOG_PATH,
    game_registry_path: str | Path = DEFAULT_GAME_REGISTRY_PATH,
    implemented_handlers: Collection[str] = (),
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ProductRoutingError("The request must be a JSON object.")
    product_id = str(payload.get("productId", "")).strip()
    game_id = str(payload.get("gameId", "")).strip()
    question_text = str(payload.get("questionText", "")).strip()
    inputs = payload.get("inputs")
    if not product_id:
        raise ProductRoutingError("Choose an answer product.")
    if len(question_text) < 20 or len(question_text) > 2000:
        raise ProductRoutingError("Question text must be between 20 and 2,000 characters.")
    if not isinstance(inputs, dict):
        raise ProductRoutingError("Product inputs must be a JSON object.")

    catalog = load_product_catalog(catalog_path, game_registry_path)
    product = next((item for item in catalog["products"] if item["id"] == product_id), None)
    if not product:
        raise ProductRoutingError("This multi-game answer product does not exist.")
    if game_id and game_id != product["gameId"]:
        raise ProductRoutingError("The selected game does not match the answer product.")

    missing_inputs = [name for name in product["requiredInputs"] if not _has_value(inputs.get(name))]
    if _policy_blocked(question_text, inputs):
        reason_code = "policy_blocked"
        reason = "This request falls outside the allowed coaching and decision-support scope. No credits were charged."
    elif missing_inputs:
        reason_code = "missing_context"
        reason = f"Required context is missing: {', '.join(missing_inputs)}. No credits were charged."
    elif product["status"] != "ready_live":
        reason_code = "product_pending_qa"
        reason = "This answer workflow is still in independent QA and is not available for purchase. No credits were charged."
    elif product_id not in set(implemented_handlers):
        reason_code = "answer_workflow_unavailable"
        reason = "The verified delivery workflow is unavailable. No credits were charged."
    else:
        game = catalog["gameById"][product["gameId"]]
        return {
            "productId": product["id"],
            "gameId": product["gameId"],
            "game": game.get("name", product["gameId"]),
            "questionType": product["id"],
            "questionText": question_text,
            "inputs": inputs,
            "status": "queued_for_qa",
            "reasonCode": "",
            "reason": "Independent answer drafting and QA have been queued. Credits are reserved, not charged.",
            "missingInputs": [],
            "creditsQuoted": int(product["credits"]),
            "creditsCharged": 0,
            "purchaseAvailable": True,
        }

    game = catalog["gameById"][product["gameId"]]
    return {
        "productId": product["id"],
        "gameId": product["gameId"],
        "game": game.get("name", product["gameId"]),
        "questionType": product["id"],
        "questionText": question_text,
        "inputs": inputs,
        "status": "held_without_charge",
        "reasonCode": reason_code,
        "reason": reason,
        "missingInputs": missing_inputs,
        "creditsQuoted": int(product["credits"]),
        "creditsCharged": 0,
        "purchaseAvailable": False,
    }
