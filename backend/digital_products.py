from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.answer_engine import EngineResult, build_raid_answer


STAGING_PACK_SKU = "rust-staging-pack-v1"
STAGING_PACK_PRICE_USD = 4.99


def staging_pack_sample_input() -> dict[str, Any]:
    return {
        "serverType": "vanilla",
        "targets": [
            {"targetId": "garage-door", "quantity": 2, "method": "rockets"},
            {"targetId": "armored-door", "quantity": 1, "method": "c4"},
        ],
        "bufferPercent": 15,
        "availableSulfur": 18_000,
        "teamSize": 2,
        "routePreference": "fewest_items",
        "ownedInventory": {
            "rockets": 6,
            "c4": 3,
            "satchels": 0,
            "explosiveAmmo": 0,
        },
        "notes": "Public sample: two garage doors into one armored door; preserve a separate seal kit.",
    }


def staging_pack_product(*, available: bool, demo: bool = False) -> dict[str, Any]:
    return {
        "id": STAGING_PACK_SKU,
        "name": "Rust Full Raid Staging Pack",
        "game": "Rust",
        "price": {"amount": STAGING_PACK_PRICE_USD, "currency": "USD"},
        "purchaseType": "one_time",
        "accountRequired": False,
        "available": bool(available),
        "demo": bool(demo),
        "freePreview": [
            "Selected route totals",
            "Planning-buffer target",
            "One current inventory or sulfur gap",
            "Evidence date and scope",
        ],
        "paidReport": [
            "Selected, lowest-sulfur, and fewest-placement routes",
            "Four-method comparison for every target",
            "Inventory requirements and exact shortfalls",
            "Gunpowder and charcoal crafting queue",
            "Team roles, checkpoints, and stop conditions",
            "Evidence, recalculation QA, JSON, and print-ready report",
        ],
    }


def _primary_gap(answer: dict[str, Any]) -> dict[str, Any]:
    totals = answer["totals"]
    available_sulfur = totals.get("availableSulfur")
    buffered_sulfur = int(totals["bufferedSulfur"])
    if available_sulfur is not None and int(available_sulfur) < buffered_sulfur:
        return {
            "kind": "sulfur",
            "label": "Sulfur below the selected buffer",
            "amount": buffered_sulfur - int(available_sulfur),
            "unit": "sulfur",
        }

    inventory = answer["routeReview"]["inventory"]
    if inventory["provided"]:
        shortfalls = inventory["selected"]["shortfalls"]
        method, amount = max(shortfalls.items(), key=lambda item: int(item[1]))
        if int(amount) > 0:
            labels = {
                "rockets": "Rockets missing from the selected route",
                "c4": "C4 missing from the selected route",
                "satchels": "Satchels missing from the selected route",
                "explosiveAmmo": "Explosive ammo missing from the selected route",
            }
            return {
                "kind": "inventory",
                "label": labels[method],
                "amount": int(amount),
                "unit": method,
            }

    return {
        "kind": "ready" if answer["plan"]["readiness"] == "ready_to_stage" else "stock_check",
        "label": answer["plan"]["readinessReason"],
        "amount": 0,
        "unit": "",
    }


def build_staging_pack(
    payload: dict[str, Any],
    data: dict[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = now or datetime.now(timezone.utc)
    result: EngineResult = build_raid_answer(
        payload,
        data,
        answer_type="raid_plan",
        now=generated_at,
    )
    answer = result.answer
    selected_route = next(
        option for option in answer["routeReview"]["options"] if option["id"] == "selected"
    )
    preview = {
        "schemaVersion": "raidbench-staging-preview-v1",
        "productId": STAGING_PACK_SKU,
        "generatedAt": answer["generatedAt"],
        "reviewedAt": answer["reviewedAt"],
        "gameScope": answer["gameScope"],
        "routeLines": len(answer["totals"]["lineItems"]),
        "selected": {
            "itemCount": int(selected_route["itemCount"]),
            "sulfur": int(selected_route["sulfur"]),
            "gunpowder": int(selected_route["gunpowder"]),
            "bufferPercent": int(answer["totals"]["bufferPercent"]),
            "bufferedSulfur": int(answer["totals"]["bufferedSulfur"]),
        },
        "readiness": {
            "status": answer["plan"]["readiness"],
            "label": answer["plan"]["readinessLabel"],
            "reason": answer["plan"]["readinessReason"],
        },
        "primaryGap": _primary_gap(answer),
        "lockedSections": staging_pack_product(available=True)["paidReport"],
    }
    report = {
        "schemaVersion": "raidbench-staging-report-v1",
        "productId": STAGING_PACK_SKU,
        "productName": "Rust Full Raid Staging Pack",
        "pricePaid": {"amount": STAGING_PACK_PRICE_USD, "currency": "USD"},
        "generatedAt": answer["generatedAt"],
        "reviewedAt": answer["reviewedAt"],
        "title": answer["title"],
        "summary": answer["summary"],
        "decision": answer["decision"],
        "gameScope": answer["gameScope"],
        "inputs": answer["inputs"],
        "totals": answer["totals"],
        "routeReview": answer["routeReview"],
        "crafting": answer["crafting"],
        "plan": answer["plan"],
        "assumptions": answer["assumptions"],
        "evidence": answer["evidence"],
        "qa": answer["qa"],
        "correctionPolicy": (
            "Material factual or calculation errors reported within 14 days receive a corrected "
            "report or a refund when appropriate."
        ),
    }
    return preview, report


def build_staging_pack_sample(
    data: dict[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    preview, report = build_staging_pack(staging_pack_sample_input(), data, now=now)
    return preview, {
        **report,
        "reportKind": "public_sample",
        "pricePaid": None,
        "sampleLabel": "Two garage doors into one armored door",
    }
