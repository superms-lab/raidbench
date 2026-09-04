#!/usr/bin/env python3
"""Fail-closed verification for the Rust data used by paid answers."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import ssl
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

try:
    import certifi
except ImportError:  # pragma: no cover - Linux images use the system CA bundle.
    certifi = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = ROOT / "content" / "rust-raid-data.json"
OFFICIAL_CHANGES_URL = "https://rust.facepunch.com/changes/"
COUNTS_URL = "https://frozen-rust.com/rust-raid-calculator.html"
OFFICIAL_RECIPE_URLS = {
    "explosives": "https://wiki.facepunch.com/rust/item/explosives",
    "c4": "https://wiki.facepunch.com/rust/item/explosive.timed",
    "satchel": "https://wiki.facepunch.com/rust/item/explosive.satchel",
    "beancan": "https://wiki.facepunch.com/rust/item/grenade.beancan",
    "explosive_ammo": "https://wiki.facepunch.com/rust/item/ammo.rifle.explosive",
}
SOURCE_METHODS = {
    "rockets": "rocket",
    "c4": "c4",
    "satchels": "satchel",
    "explosiveAmmo": "expl-556",
}
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where() if certifi else None)


class VerificationError(RuntimeError):
    pass


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.parts.append(value)

    def text(self) -> str:
        return " ".join(self.parts)


def fetch_text(url: str, timeout: int = 25) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "RaidBench paid-data verifier; contact support@raidbench.com",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
        if response.status != 200:
            raise VerificationError(f"Source returned HTTP {response.status}: {url}")
        return response.read().decode("utf-8", errors="replace")


def visible_text(source_html: str) -> str:
    parser = TextExtractor()
    parser.feed(source_html)
    return re.sub(r"\s+", " ", html.unescape(parser.text())).strip()


def parse_latest_patch(source_html: str) -> dict[str, str]:
    sections = source_html.split('<div class="changes-container">')
    if len(sections) < 2:
        raise VerificationError("The official Rust changelist layout could not be parsed.")
    first = sections[1]
    changelist = re.search(r'/changelist/(\d+)', first)
    patch_name = re.search(r'Patch Name</span>\s*<a[^>]*class="title"[^>]*>(.*?)</a>', first, re.S)
    patch_date = re.search(
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+'
        r'((?:[A-Z][a-z]+\s+\d{1,2},?|\d{1,2}\s+[A-Z][a-z]+)\s+\d{4})',
        first,
    )
    if not changelist or not patch_name or not patch_date:
        raise VerificationError("The latest official Rust patch metadata could not be parsed.")
    raw_date = patch_date.group(2)
    date_value = None
    for date_format in ("%B %d, %Y", "%B %d %Y", "%d %B %Y"):
        try:
            date_value = datetime.strptime(raw_date, date_format).date().isoformat()
            break
        except ValueError:
            continue
    if date_value is None:
        raise VerificationError("The latest official Rust patch date could not be parsed.")
    return {
        "id": changelist.group(1),
        "name": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", patch_name.group(1))).strip(),
        "date": date_value,
    }


def parse_count_table(source_html: str) -> dict[str, dict[str, int]]:
    match = re.search(r"const\s+COUNTS\s*=\s*\{(.*?)\n\s*\};", source_html, re.S)
    if not match:
        raise VerificationError("The independent raid count table could not be parsed.")
    block = match.group(1)
    result: dict[str, dict[str, int]] = {}
    for source_method in SOURCE_METHODS.values():
        method_match = re.search(
            rf"(?:'{re.escape(source_method)}'|{re.escape(source_method)})\s*:\s*\{{([^}}]+)\}}",
            block,
            re.S,
        )
        if not method_match:
            raise VerificationError(f"Missing count table for {source_method}.")
        result[source_method] = {
            target: int(value)
            for target, value in re.findall(r"'([^']+)'\s*:\s*(\d+)", method_match.group(1))
        }
    return result


def parse_sulfur_costs(source_html: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for source_method in SOURCE_METHODS.values():
        match = re.search(
            rf"id\s*:\s*'{re.escape(source_method)}'.*?sulfur\s*:\s*(\d+)",
            source_html,
            re.S,
        )
        if not match:
            raise VerificationError(f"Missing sulfur cost for {source_method}.")
        result[source_method] = int(match.group(1))
    return result


def parse_reference_modified(source_html: str) -> str:
    match = re.search(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})"', source_html)
    if not match:
        raise VerificationError("The independent reference modification date is missing.")
    return match.group(1)


def require_recipe_markers(pages: dict[str, str]) -> None:
    checks = {
        "explosives": (
            r"Gun Powder\s+50\b",
            r"Sulfur\s+10\b",
            r"Rocket\s+10\b",
            r"Timed Explosive Charge\s+20\b",
        ),
        "c4": (r"Explosives\s+20\b", r"Yield\s+1\b"),
        "satchel": (r"Beancan Grenade\s+4\b", r"Yield\s+1\b"),
        "beancan": (r"Gun Powder\s+60\b", r"Yield\s+1\b"),
        "explosive_ammo": (r"Gun Powder\s+20\b", r"Sulfur\s+10\b", r"Yield\s+2\b"),
    }
    for page_id, patterns in checks.items():
        text = visible_text(pages[page_id])
        for pattern in patterns:
            if not re.search(pattern, text, re.I):
                raise VerificationError(f"Official recipe marker changed for {page_id}: {pattern}")


def verify_data(
    data: dict[str, Any],
    *,
    changes_html: str,
    counts_html: str,
    recipe_pages: dict[str, str],
) -> dict[str, Any]:
    errors: list[str] = []
    patch = parse_latest_patch(changes_html)
    verification = data.get("verification") or {}
    if patch["id"] != str(verification.get("latestOfficialChangelistId") or ""):
        errors.append(
            f"New official Rust changelist {patch['id']} ({patch['name']}, {patch['date']}) requires review."
        )

    counts = parse_count_table(counts_html)
    sulfur = parse_sulfur_costs(counts_html)
    for target in data.get("targets") or []:
        target_id = str(target.get("id") or "")
        for data_method, source_method in SOURCE_METHODS.items():
            observed = counts.get(source_method, {}).get(target_id)
            expected = int(target.get(data_method, -1))
            if observed != expected:
                errors.append(
                    f"Count mismatch for {target_id}/{data_method}: data={expected}, source={observed}."
                )

    for data_method, source_method in SOURCE_METHODS.items():
        observed = sulfur.get(source_method)
        expected = int((data.get("sulfurPerItem") or {}).get(data_method, -1))
        if observed != expected:
            errors.append(
                f"Sulfur mismatch for {data_method}: data={expected}, source={observed}."
            )

    try:
        require_recipe_markers(recipe_pages)
    except VerificationError as error:
        errors.append(str(error))

    reference_modified = parse_reference_modified(counts_html)
    expected_modified = str(verification.get("countsReferenceModified") or "")
    if expected_modified and reference_modified != expected_modified:
        errors.append(
            f"Independent count reference changed on {reference_modified}; evidence review is required."
        )

    return {
        "ok": not errors,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "latestOfficialPatch": patch,
        "countsReferenceModified": reference_modified,
        "errors": errors,
    }


def refresh_verified_at(path: Path, data: dict[str, Any], result: dict[str, Any]) -> None:
    if not result["ok"]:
        raise VerificationError("Refusing to refresh a dataset that did not pass verification.")
    data["verifiedAt"] = datetime.now(timezone.utc).date().isoformat()
    data.setdefault("verification", {})["lastAutomatedCheckAt"] = result["checkedAt"]
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_verification_status(
    path: Path,
    *,
    data_path: Path,
    data: dict[str, Any],
    result: dict[str, Any],
) -> None:
    patch = result.get("latestOfficialPatch") or {}
    verification = data.get("verification") or {}
    status = {
        "status": "verified" if result.get("ok") else "blocked",
        "checkedAt": result.get("checkedAt") or datetime.now(timezone.utc).isoformat(),
        "dataVerifiedAt": data.get("verifiedAt") or "",
        "dataChangelistId": str(verification.get("latestOfficialChangelistId") or ""),
        "latestOfficialChangelistId": str(patch.get("id") or ""),
        "latestOfficialPatchName": str(patch.get("name") or ""),
        "dataSha256": file_sha256(data_path) if data_path.is_file() else "",
        "errors": [str(error) for error in result.get("errors", [])],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(status, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--refresh-date", action="store_true")
    parser.add_argument("--status-file", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data: dict[str, Any] = {}
    try:
        data = json.loads(args.data.read_text(encoding="utf-8"))
        result = verify_data(
            data,
            changes_html=fetch_text(OFFICIAL_CHANGES_URL),
            counts_html=fetch_text(COUNTS_URL),
            recipe_pages={key: fetch_text(url) for key, url in OFFICIAL_RECIPE_URLS.items()},
        )
        if args.refresh_date and result["ok"]:
            refresh_verified_at(args.data, data, result)
    except (OSError, ValueError, VerificationError) as error:
        result = {
            "ok": False,
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "errors": [str(error)],
        }

    if args.status_file:
        try:
            write_verification_status(
                args.status_file,
                data_path=args.data,
                data=data,
                result=result,
            )
        except OSError as error:
            result["ok"] = False
            result.setdefault("errors", []).append(f"Could not write verification status: {error}")

    if args.json:
        print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    elif result["ok"]:
        patch = result["latestOfficialPatch"]
        print(
            f"Rust paid data verified against changelist {patch['id']} "
            f"({patch['name']}, {patch['date']})."
        )
    else:
        for error in result["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
