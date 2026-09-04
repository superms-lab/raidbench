#!/usr/bin/env python3
"""Build a private fail-closed manifest for products that passed every activation gate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_READINESS = ROOT / "local" / "multigame-shadow-readiness.json"
DEFAULT_OUTPUT = ROOT / "local" / "multigame-activation-candidates.json"


class ActivationManifestError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ActivationManifestError(f"Expected a JSON object in {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def build_manifest(readiness: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    if readiness.get("mode") != "shadow_no_charge":
        raise ActivationManifestError("Readiness input is not a no-charge shadow report.")
    if int(readiness.get("summary", {}).get("creditsCharged", -1)) != 0:
        raise ActivationManifestError("Shadow readiness reports nonzero charged credits.")
    catalog_by_id = {item["id"]: item for item in catalog.get("products", [])}
    candidates = []
    for item in readiness.get("products", []):
        if item.get("decision") != "ready_live":
            continue
        product = catalog_by_id.get(item.get("productId"))
        if not product:
            raise ActivationManifestError(f"Readiness references an unknown product: {item.get('productId')}")
        failed_gates = [gate.get("id") for gate in item.get("gateResults", []) if gate.get("passed") is not True]
        if failed_gates or not item.get("gateResults"):
            raise ActivationManifestError(f"{product['id']} is marked ready with failed or missing gates: {', '.join(failed_gates)}")
        if product.get("status") not in {"hidden_pending_qa", "ready_live"}:
            raise ActivationManifestError(f"{product['id']} has an unsupported activation state.")
        candidates.append({
            "productId": product["id"],
            "gameId": product["gameId"],
            "label": product["label"],
            "credits": int(product["credits"]),
            "currentCatalogStatus": product["status"],
            "gateCount": len(item["gateResults"]),
            "allGatesPassed": True,
            "shadowCases": int(item["shadowCases"]),
            "supportedQaPassRate": float(item["supportedQaPassRate"]),
            "noChargeAccuracy": float(item["noChargeAccuracy"]),
            "idempotencyPassed": bool(item["idempotencyPassed"]),
            "inAccountDeliveryPassed": bool(item["inAccountDeliveryPassed"]),
            "activationStatus": "live_monitored" if product["status"] == "ready_live" else "eligible_not_published",
        })
    return {
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "sourceReportGeneratedAt": readiness.get("generatedAt", ""),
        "mode": "private_activation_candidates",
        "summary": {
            "eligibleProducts": len(candidates),
            "publicCatalogMutationPerformed": False,
            "productionOrdersCreated": 0,
            "productionCreditsCharged": 0,
        },
        "candidates": candidates,
        "phase8Required": any(item["activationStatus"] == "eligible_not_published" for item in candidates),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the private RaidBench multi-game activation candidate manifest.")
    parser.add_argument("--readiness", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--catalog", type=Path, default=ROOT / "content" / "multigame-products.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = build_manifest(read_json(args.readiness), read_json(args.catalog))
        write_json(args.output, manifest)
    except (ActivationManifestError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}")
        return 1
    print(json.dumps(manifest["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
