from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


METHOD_LABELS = {
    "rockets": "rockets",
    "c4": "timed explosive charges",
    "satchels": "satchel charges",
    "explosiveAmmo": "explosive 5.56 rifle ammo",
}

ROUTE_PREFERENCES = {
    "lowest_sulfur": "Lowest sulfur",
    "fewest_items": "Fewest placements",
}

class AnswerEngineError(ValueError):
    """Base error for inputs that cannot receive a verified answer."""


class UnsupportedScopeError(AnswerEngineError):
    pass


class StaleEvidenceError(AnswerEngineError):
    pass


@dataclass(frozen=True)
class EngineResult:
    answer: dict[str, Any]
    qa_status: str


def load_raid_data(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    required = {
        "verifiedAt",
        "scope",
        "sources",
        "gunpowderCrafting",
        "sulfurPerItem",
        "gunpowderPerItem",
        "targets",
    }
    missing = required.difference(data)
    if missing:
        raise AnswerEngineError(f"Raid data is missing: {', '.join(sorted(missing))}")
    return data


def _parse_verified_at(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _freshness_hours(data: dict[str, Any], now: datetime) -> float:
    return (now - _parse_verified_at(data["verifiedAt"])).total_seconds() / 3600


def _normalize_lines(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_lines = payload.get("targets")
    if raw_lines is None:
        raw_lines = [{
            "targetId": payload.get("targetId"),
            "quantity": payload.get("quantity", 1),
            "method": payload.get("method"),
        }]
    if not isinstance(raw_lines, list) or not 1 <= len(raw_lines) <= 12:
        raise AnswerEngineError("A plan must contain between 1 and 12 target lines.")

    normalized = []
    for line in raw_lines:
        if not isinstance(line, dict):
            raise AnswerEngineError("Every target line must be an object.")
        target_id = str(line.get("targetId") or "")
        method = str(line.get("method") or "")
        try:
            quantity = int(line.get("quantity", 1))
        except (TypeError, ValueError) as error:
            raise AnswerEngineError("Target quantity must be a whole number.") from error
        if not target_id or method not in METHOD_LABELS:
            raise AnswerEngineError("Choose a supported target and breach method.")
        if not 1 <= quantity <= 99:
            raise AnswerEngineError("Target quantity must be between 1 and 99.")
        normalized.append({"targetId": target_id, "quantity": quantity, "method": method})
    return normalized


def _recalculate(lines: list[dict[str, Any]], data: dict[str, Any]) -> dict[str, Any]:
    target_map = {target["id"]: target for target in data["targets"]}
    calculated_lines = []
    sulfur_total = 0
    gunpowder_total = 0
    item_total = 0

    for line in lines:
        target = target_map.get(line["targetId"])
        if target is None:
            raise AnswerEngineError(f"Unsupported target: {line['targetId']}")
        method = line["method"]
        item_count = int(target[method]) * line["quantity"]
        sulfur = item_count * int(data["sulfurPerItem"][method])
        gunpowder = item_count * int(data["gunpowderPerItem"][method])
        calculated_lines.append({
            **line,
            "targetLabel": target["label"],
            "methodLabel": METHOD_LABELS[method],
            "itemsPerTarget": int(target[method]),
            "itemCount": item_count,
            "sulfur": sulfur,
            "gunpowder": gunpowder,
        })
        item_total += item_count
        sulfur_total += sulfur
        gunpowder_total += gunpowder

    workbench_recipe = data["gunpowderCrafting"]["workbench"]
    batch_yield = int(workbench_recipe["yield"])
    gunpowder_batches = (gunpowder_total + batch_yield - 1) // batch_yield

    return {
        "lineItems": calculated_lines,
        "itemCount": item_total,
        "sulfur": sulfur_total,
        "gunpowder": gunpowder_total,
        "gunpowderCraftBatches": gunpowder_batches,
        "gunpowderProduced": gunpowder_batches * batch_yield,
        "sulfurForGunpowder": gunpowder_batches * int(workbench_recipe["sulfur"]),
        "workbenchCharcoal": gunpowder_batches * int(workbench_recipe["charcoal"]),
    }


def _normalize_owned_inventory(payload: dict[str, Any]) -> tuple[bool, dict[str, int]]:
    raw = payload.get("ownedInventory")
    if not isinstance(raw, dict):
        return False, {method: 0 for method in METHOD_LABELS}

    provided = any(raw.get(method) not in (None, "") for method in METHOD_LABELS)
    owned: dict[str, int] = {}
    for method in METHOD_LABELS:
        value = raw.get(method)
        if value in (None, ""):
            owned[method] = 0
            continue
        try:
            owned[method] = max(0, min(99999, int(value)))
        except (TypeError, ValueError) as error:
            raise AnswerEngineError("Owned explosive counts must be whole numbers.") from error
    return provided, owned


def _route_inventory(lines: list[dict[str, Any]], data: dict[str, Any], owned: dict[str, int]) -> dict[str, Any]:
    totals = _recalculate(lines, data)
    required = {method: 0 for method in METHOD_LABELS}
    for line in totals["lineItems"]:
        required[line["method"]] += int(line["itemCount"])
    shortfalls = {
        method: max(0, required[method] - owned[method])
        for method in METHOD_LABELS
    }
    return {
        "required": required,
        "shortfalls": shortfalls,
        "fits": not any(shortfalls.values()),
    }


def _route_option(option_id: str, label: str, lines: list[dict[str, Any]], data: dict[str, Any]) -> dict[str, Any]:
    totals = _recalculate(lines, data)
    return {
        "id": option_id,
        "label": label,
        "targets": lines,
        "itemCount": totals["itemCount"],
        "sulfur": totals["sulfur"],
        "gunpowder": totals["gunpowder"],
    }


def _build_route_review(lines: list[dict[str, Any]], data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    preference = str(payload.get("routePreference") or "lowest_sulfur")
    if preference not in ROUTE_PREFERENCES:
        raise AnswerEngineError("Route priority must be lowest sulfur or fewest placements.")

    target_map = {target["id"]: target for target in data["targets"]}
    comparisons = []
    lowest_sulfur_lines = []
    fewest_items_lines = []
    for line in lines:
        target = target_map[line["targetId"]]
        alternatives = []
        for method, method_label in METHOD_LABELS.items():
            alternative_line = {**line, "method": method}
            totals = _recalculate([alternative_line], data)
            alternatives.append({
                "method": method,
                "methodLabel": method_label,
                "itemCount": totals["itemCount"],
                "sulfur": totals["sulfur"],
                "gunpowder": totals["gunpowder"],
            })
        lowest_sulfur = min(alternatives, key=lambda item: (item["sulfur"], item["itemCount"], item["method"]))
        fewest_items = min(alternatives, key=lambda item: (item["itemCount"], item["sulfur"], item["method"]))
        lowest_sulfur_lines.append({**line, "method": lowest_sulfur["method"]})
        fewest_items_lines.append({**line, "method": fewest_items["method"]})
        comparisons.append({
            "targetId": line["targetId"],
            "targetLabel": target["label"],
            "quantity": line["quantity"],
            "selectedMethod": line["method"],
            "alternatives": sorted(alternatives, key=lambda item: (item["sulfur"], item["itemCount"])),
        })

    selected = _route_option("selected", "Your selected route", lines, data)
    lowest_sulfur = _route_option("lowest_sulfur", "Lowest-sulfur route", lowest_sulfur_lines, data)
    fewest_items = _route_option("fewest_items", "Fewest-placement route", fewest_items_lines, data)
    preferred = lowest_sulfur if preference == "lowest_sulfur" else fewest_items
    inventory_provided, owned = _normalize_owned_inventory(payload)
    selected_inventory = _route_inventory(lines, data, owned)
    preferred_inventory = _route_inventory(preferred["targets"], data, owned)

    if inventory_provided and selected_inventory["fits"] and not preferred_inventory["fits"]:
        recommendation = selected
        reason = "Your selected route fits the explosive inventory entered; the priority route does not."
    else:
        recommendation = preferred
        if inventory_provided and preferred_inventory["fits"]:
            reason = f"The {ROUTE_PREFERENCES[preference].lower()} route also fits the explosive inventory entered."
        elif inventory_provided:
            reason = f"This is the {ROUTE_PREFERENCES[preference].lower()} route, with exact inventory shortfalls shown below."
        else:
            reason = f"This route minimizes {ROUTE_PREFERENCES[preference].lower()}; inventory was not supplied."

    recommendation_inventory = _route_inventory(recommendation["targets"], data, owned)
    return {
        "preference": preference,
        "preferenceLabel": ROUTE_PREFERENCES[preference],
        "recommendationId": recommendation["id"],
        "recommendationLabel": recommendation["label"],
        "recommendationReason": reason,
        "selectedSulfurDelta": selected["sulfur"] - lowest_sulfur["sulfur"],
        "selectedItemDelta": selected["itemCount"] - fewest_items["itemCount"],
        "options": [selected, lowest_sulfur, fewest_items],
        "lineComparisons": comparisons,
        "inventory": {
            "provided": inventory_provided,
            "owned": owned,
            "selected": selected_inventory,
            "recommended": recommendation_inventory,
        },
        "scopeNote": "Method comparison is target-by-target. It does not assume rocket splash, mixed-method finishes, hidden layers, misses, or custom-server rules.",
    }


def _answer_sources(lines: list[dict[str, Any]], data: dict[str, Any]) -> list[dict[str, Any]]:
    methods = {line["method"] for line in lines}
    targets = {line["targetId"] for line in lines}
    selected = []
    for index, source in enumerate(data["sources"], start=1):
        source_methods = set(source.get("methods") or [])
        source_targets = set(source.get("targets") or [])
        if not (methods.intersection(source_methods) or targets.intersection(source_targets)):
            continue
        selected.append({
            "id": str(source.get("id") or f"ev-{index}"),
            "type": str(source.get("type") or "independent"),
            "title": source["label"],
            "url": source["url"],
            "supports": source["supports"],
            "checkedAt": data["verifiedAt"],
        })
    if len(selected) < 2 or not any(source["type"] == "official" for source in selected):
        raise AnswerEngineError("The selected method does not have enough current evidence.")
    return selected


def _build_calculations(totals: dict[str, Any], data: dict[str, Any]) -> list[dict[str, Any]]:
    calculations = []
    for index, line in enumerate(totals["lineItems"], start=1):
        count_expression = f"{line['itemsPerTarget']} x {line['quantity']}"
        calculations.extend([
            {
                "id": f"calc-{index}-count",
                "label": f"{line['targetLabel']} item count",
                "expression": count_expression,
                "expected": line["itemCount"],
                "actual": line["itemsPerTarget"] * line["quantity"],
                "passed": line["itemCount"] == line["itemsPerTarget"] * line["quantity"],
            },
            {
                "id": f"calc-{index}-sulfur",
                "label": f"{line['targetLabel']} sulfur",
                "expression": f"{line['itemCount']} x {data['sulfurPerItem'][line['method']]}",
                "expected": line["sulfur"],
                "actual": line["itemCount"] * int(data["sulfurPerItem"][line["method"]]),
                "passed": line["sulfur"] == line["itemCount"] * int(data["sulfurPerItem"][line["method"]]),
            },
            {
                "id": f"calc-{index}-gunpowder",
                "label": f"{line['targetLabel']} gunpowder",
                "expression": f"{line['itemCount']} x {data['gunpowderPerItem'][line['method']]}",
                "expected": line["gunpowder"],
                "actual": line["itemCount"] * int(data["gunpowderPerItem"][line["method"]]),
                "passed": line["gunpowder"] == line["itemCount"] * int(data["gunpowderPerItem"][line["method"]]),
            },
        ])
    workbench_recipe = data["gunpowderCrafting"]["workbench"]
    batch_yield = int(workbench_recipe["yield"])
    expected_batches = (totals["gunpowder"] + batch_yield - 1) // batch_yield
    calculations.extend([
        {
            "id": "calc-gunpowder-batches",
            "label": "Standard workbench gunpowder batches",
            "expression": f"ceil({totals['gunpowder']} / {batch_yield})",
            "expected": totals["gunpowderCraftBatches"],
            "actual": expected_batches,
            "passed": totals["gunpowderCraftBatches"] == expected_batches,
        },
        {
            "id": "calc-workbench-charcoal",
            "label": "Standard workbench charcoal",
            "expression": f"{expected_batches} x {workbench_recipe['charcoal']}",
            "expected": totals["workbenchCharcoal"],
            "actual": expected_batches * int(workbench_recipe["charcoal"]),
            "passed": totals["workbenchCharcoal"] == expected_batches * int(workbench_recipe["charcoal"]),
        },
    ])
    return calculations


def _team_roles(team_size: int) -> list[dict[str, str]]:
    if team_size == 1:
        return [{
            "role": "Solo operator",
            "instruction": "Stage one layer at a time, keep a separate seal kit, and preserve a clear exit before committing the full resource stack.",
        }]
    if team_size == 2:
        return [
            {
                "role": "Breacher",
                "instruction": "Carry and call the current layer's breach items; record actual spend before moving to the next layer.",
            },
            {
                "role": "Security and seal",
                "instruction": "Watch the approach, hold the seal kit, and call a stop when the observed route differs from the saved plan.",
            },
        ]
    roles = [
        {
            "role": "Breacher",
            "instruction": "Carry and call the current layer's breach items; record actual spend before moving to the next layer.",
        },
        {
            "role": "Security",
            "instruction": "Watch the approach and preserve the planned exit while the active layer is breached.",
        },
        {
            "role": "Seal and loot",
            "instruction": "Carry the seal kit, compare the opened route with the plan, and organize the first safe return load.",
        },
    ]
    if team_size > 3:
        roles.append({
            "role": "Reserve and transport",
            "instruction": f"Assign the remaining {team_size - 3} teammate(s) to reserve security and staged transport rather than duplicating the breach call.",
        })
    return roles


def _raid_plan_details(
    totals: dict[str, Any],
    *,
    team_size: int,
    available_sulfur: int | None,
    buffered_sulfur: int,
    notes: str,
) -> dict[str, Any]:
    if available_sulfur is None:
        readiness = "stock_check_required"
        readiness_label = "Stock check required"
        readiness_reason = "Enter or verify the sulfur currently available before moving the full plan out of base."
    elif available_sulfur >= buffered_sulfur:
        readiness = "ready_to_stage"
        readiness_label = "Ready to stage"
        readiness_reason = (
            f"The entered sulfur covers the selected buffer with "
            f"{available_sulfur - buffered_sulfur:,} sulfur remaining."
        )
    else:
        readiness = "hold_for_resources"
        readiness_label = "Hold for resources"
        readiness_reason = (
            f"The entered sulfur is {buffered_sulfur - available_sulfur:,} below the selected buffer."
        )

    stop_conditions = [
        "Stop if the server uses custom damage, crafting, or stack rules; this plan is verified only for vanilla Rust PC.",
        "Stop if the observed breach path differs from the entered layer sequence; recalculate before committing the next layer.",
        "Stop if actual spend exceeds the verified count for a completed layer; do not assume later layers remain unchanged.",
        "Stop if the saved data is outside RaidBench's 72-hour verification window.",
    ]
    if available_sulfur is not None and available_sulfur < buffered_sulfur:
        stop_conditions.insert(0, "Do not stage the full route while the entered sulfur remains below the selected planning buffer.")

    return {
        "readiness": readiness,
        "readinessLabel": readiness_label,
        "readinessReason": readiness_reason,
        "teamSize": team_size,
        "teamRoles": _team_roles(team_size),
        "checkpoints": [
            {
                "phase": "Stage at base",
                "action": "Craft the verified gunpowder queue, separate the selected sulfur buffer, and keep sealing materials outside the breach-cost total.",
            },
            {
                "phase": "Confirm the first layer",
                "action": "Verify vanilla server rules, the target type, quantity, and breach method before moving the full route forward.",
            },
            {
                "phase": "Reconcile each layer",
                "action": "Compare actual items spent with the saved line before continuing; recalculate when the route or spend changes.",
            },
            {
                "phase": "Seal and exit",
                "action": "Treat sealing, counter pressure, misses, transport, and return trips as separate costs that are not included in the breach total.",
            },
        ],
        "stopConditions": stop_conditions,
        "savedNotes": notes,
        "baseSulfur": totals["sulfur"],
        "bufferedSulfur": buffered_sulfur,
    }


def validate_answer(answer: dict[str, Any], data: dict[str, Any]) -> list[str]:
    errors = []
    evidence = answer.get("evidence") or []
    if len(evidence) < 2:
        errors.append("At least two evidence records are required.")
    if not any(item.get("type") == "official" for item in evidence):
        errors.append("At least one official source is required.")
    if answer.get("qa", {}).get("authorId") == answer.get("qa", {}).get("reviewerId"):
        errors.append("The independent reviewer must differ from the author.")
    if any(not item.get("passed") for item in answer.get("calculations") or []):
        errors.append("Every numerical calculation must pass.")

    try:
        independently_calculated = _recalculate(answer["inputs"]["targets"], data)
    except (AnswerEngineError, KeyError):
        errors.append("The independent recalculation could not run.")
    else:
        for key in (
            "itemCount",
            "sulfur",
            "gunpowder",
            "gunpowderCraftBatches",
            "gunpowderProduced",
            "sulfurForGunpowder",
            "workbenchCharcoal",
        ):
            if independently_calculated[key] != answer.get("totals", {}).get(key):
                errors.append(f"Independent recalculation failed for {key}.")

    route_review = answer.get("routeReview") or {}
    options = route_review.get("options") or []
    option_ids = {str(option.get("id")) for option in options if isinstance(option, dict)}
    if option_ids != {"selected", "lowest_sulfur", "fewest_items"}:
        errors.append("Route review must contain the three required comparison options.")
    if route_review.get("recommendationId") not in option_ids:
        errors.append("Route review recommendation must reference a calculated option.")
    for option in options:
        if not isinstance(option, dict):
            errors.append("Every route comparison option must be an object.")
            continue
        try:
            recalculated_option = _recalculate(option["targets"], data)
        except (AnswerEngineError, KeyError, TypeError):
            errors.append(f"Route comparison could not be recalculated for {option.get('id', 'unknown')}.")
            continue
        for key in ("itemCount", "sulfur", "gunpowder"):
            if recalculated_option[key] != option.get(key):
                errors.append(f"Route comparison failed for {option.get('id', 'unknown')} {key}.")
    return errors


def build_raid_answer(
    payload: dict[str, Any],
    data: dict[str, Any],
    *,
    answer_type: str,
    now: datetime | None = None,
) -> EngineResult:
    now = now or datetime.now(timezone.utc)
    if str(payload.get("serverType", "vanilla")) != "vanilla":
        raise UnsupportedScopeError(
            "Custom and modded servers can change damage or crafting values. No credits were charged; this request needs server-specific evidence."
        )
    if _freshness_hours(data, now) > 72:
        raise StaleEvidenceError(
            "The verified Rust dataset is older than 72 hours. No credits were charged; Patch Watch must refresh it first."
        )

    lines = _normalize_lines(payload)
    totals = _recalculate(lines, data)
    route_review = _build_route_review(lines, data, payload)
    evidence_lines = [
        {"targetId": line["targetId"], "quantity": line["quantity"], "method": method}
        for line in lines
        for method in METHOD_LABELS
    ]
    sources = _answer_sources(evidence_lines, data)
    calculations = _build_calculations(totals, data)
    buffer_percent = int(payload.get("bufferPercent", 0) or 0) if answer_type == "raid_plan" else 0
    if buffer_percent not in (0, 10, 15, 20):
        raise AnswerEngineError("Buffer must be 0, 10, 15, or 20 percent.")
    buffered_sulfur = (totals["sulfur"] * (100 + buffer_percent) + 99) // 100
    available_sulfur = payload.get("availableSulfur")
    if available_sulfur in (None, ""):
        available_sulfur = None
    else:
        try:
            available_sulfur = max(0, int(available_sulfur))
        except (TypeError, ValueError) as error:
            raise AnswerEngineError("Available sulfur must be a whole number.") from error

    source_ids = [source["id"] for source in sources]
    claims = []
    for index, line in enumerate(totals["lineItems"], start=1):
        claims.append({
            "id": f"claim-{index}",
            "kind": "critical_numeric",
            "text": (
                f"Plan for {line['itemCount']} {line['methodLabel']} to breach "
                f"{line['quantity']} x {line['targetLabel']} in the verified vanilla Rust dataset."
            ),
            "evidenceRefs": source_ids,
        })

    if answer_type == "instant":
        recommended = next(
            option for option in route_review["options"]
            if option["id"] == route_review["recommendationId"]
        )
        selected = route_review["options"][0]
        if route_review["recommendationId"] == "selected":
            decision = f"Keep the selected route: {route_review['recommendationReason']}"
        else:
            sulfur_saving = max(0, selected["sulfur"] - recommended["sulfur"])
            item_saving = max(0, selected["itemCount"] - recommended["itemCount"])
            saving_note = (
                f" It saves {sulfur_saving:,} sulfur against the selected route."
                if route_review["preference"] == "lowest_sulfur"
                else f" It uses {item_saving:,} fewer breach items than the selected route."
            )
            decision = f"Use the {recommended['label'].lower()}.{saving_note}"
    elif available_sulfur is None:
        decision = f"Budget {buffered_sulfur:,} sulfur before committing to this plan."
    elif available_sulfur >= buffered_sulfur:
        decision = (
            f"Your entered sulfur covers the {buffer_percent}% planning buffer with "
            f"{available_sulfur - buffered_sulfur:,} sulfur remaining."
        )
    else:
        decision = (
            f"Pause the plan or reduce the route: the entered amount is "
            f"{buffered_sulfur - available_sulfur:,} sulfur below the selected buffer."
        )

    workbench_recipe = data["gunpowderCrafting"]["workbench"]
    notes = str(payload.get("notes", ""))[:1000]
    answer = {
        "schemaVersion": "raidbench-answer-v1",
        "answerType": answer_type,
        "title": "Verified Rust route check" if answer_type == "instant" else "Verified Rust raid plan",
        "summary": (
            f"The selected route requires {totals['itemCount']:,} breach items, "
            f"{totals['sulfur']:,} sulfur, {totals['gunpowder']:,} gunpowder, and "
            f"{totals['workbenchCharcoal']:,} charcoal with the standard workbench recipe."
        ),
        "decision": decision,
        "gameScope": data["scope"],
        "reviewedAt": data["verifiedAt"],
        "generatedAt": now.isoformat(),
        "inputs": {
            "serverType": "vanilla",
            "targets": lines,
            "bufferPercent": buffer_percent,
            "availableSulfur": available_sulfur,
            "teamSize": max(1, min(20, int(payload.get("teamSize", 1) or 1))),
            "notes": notes,
            "routePreference": route_review["preference"],
            "ownedInventory": route_review["inventory"]["owned"],
        },
        "totals": {
            **totals,
            "bufferPercent": buffer_percent,
            "bufferedSulfur": buffered_sulfur,
            "availableSulfur": available_sulfur,
        },
        "crafting": {
            "method": "Standard workbench gunpowder recipe",
            "recipe": {
                "sulfur": int(workbench_recipe["sulfur"]),
                "charcoal": int(workbench_recipe["charcoal"]),
                "yield": int(workbench_recipe["yield"]),
            },
            "gunpowderRequired": totals["gunpowder"],
            "batches": totals["gunpowderCraftBatches"],
            "gunpowderProduced": totals["gunpowderProduced"],
            "sulfurRequired": totals["sulfurForGunpowder"],
            "charcoalRequired": totals["workbenchCharcoal"],
            "note": "The overall sulfur total also includes sulfur used outside the gunpowder recipe. Mixing Table costs can differ.",
        },
        "assumptions": [
            "Vanilla Rust PC values are used.",
            "Counts cover the selected breach layer only; doors or walls behind it are not inferred.",
            "Counts are full-method planning values; mixed-method finishes can use fewer items.",
            "Custom server multipliers, splash routing, misses, counters, and sealing costs are not included.",
        ],
        "claims": claims,
        "evidence": sources,
        "calculations": calculations,
        "routeReview": route_review,
        "qa": {
            "status": "pending",
            "authorId": "raidbench-calculator-v1",
            "reviewerId": "raidbench-independent-recalculation-v1",
            "checks": [
                "current_source_window",
                "official_source_present",
                "two_source_minimum",
                "independent_recalculation",
                "no_guaranteed_outcome_language",
            ],
        },
        "correctionPolicy": "Material factual errors reported within 14 days receive a corrected answer or a credit restoration.",
    }
    if answer_type == "raid_plan":
        answer["plan"] = _raid_plan_details(
            totals,
            team_size=answer["inputs"]["teamSize"],
            available_sulfur=available_sulfur,
            buffered_sulfur=buffered_sulfur,
            notes=notes,
        )
    errors = validate_answer(answer, data)
    if errors:
        raise AnswerEngineError("Answer QA failed: " + " ".join(errors))
    answer["qa"]["status"] = "approved"
    return EngineResult(answer=answer, qa_status="approved")
