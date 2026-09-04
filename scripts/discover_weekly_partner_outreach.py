#!/usr/bin/env python3
"""Discover, verify, and optionally contact a bounded weekly set of Rust partners."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from send_partner_outreach import OutreachError, send_smtp2go, write_json_atomic


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "partner-outreach-discovery.schema.json"
EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
PROHIBITED_PATTERN = re.compile(r"gambl|casino|skin\s*(?:trade|bet)|real.money.trade|cheat|boosting", re.IGNORECASE)
CONTACT_PATTERN = re.compile(r"partner|collaborat|business|press|media|editor|write for us|contact", re.IGNORECASE)


class DiscoveryError(RuntimeError):
  """Raised when weekly partner discovery cannot be verified safely."""


def utc_now() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def week_key(now: datetime | None = None) -> str:
  iso_year, iso_week, _ = (now or datetime.now(timezone.utc)).isocalendar()
  return f"{iso_year}-W{iso_week:02d}"


def read_json(path: Path, default: Any) -> Any:
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except FileNotFoundError:
    return default
  except json.JSONDecodeError as exc:
    raise DiscoveryError(f"Invalid JSON in {path}: {exc}") from exc


def decode_cfemail(value: str) -> str:
  try:
    key = int(value[:2], 16)
    return "".join(chr(int(value[index:index + 2], 16) ^ key) for index in range(2, len(value), 2))
  except (ValueError, IndexError):
    return ""


def visible_emails(html: str) -> set[str]:
  emails = {match.lower() for match in re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", html, re.IGNORECASE)}
  for encoded in re.findall(r'data-cfemail=["\']([0-9a-f]+)["\']', html, re.IGNORECASE):
    decoded = decode_cfemail(encoded).lower()
    if EMAIL_PATTERN.fullmatch(decoded):
      emails.add(decoded)
  return emails


def fetch_source(url: str) -> str:
  request = urllib.request.Request(url, headers={"User-Agent": "RaidBench partner research; support@raidbench.com"})
  try:
    with urllib.request.urlopen(request, timeout=20) as response:
      if response.status != 200:
        raise DiscoveryError(f"Partner source returned HTTP {response.status}")
      return response.read(800_000).decode("utf-8", "replace")
  except (urllib.error.URLError, TimeoutError) as exc:
    raise DiscoveryError(f"Partner source could not be verified: {url}") from exc


def load_contacted(state: dict[str, Any], sent_state_dir: Path) -> tuple[set[str], set[str]]:
  recipients = {str(value).lower() for value in state.get("contactedRecipients", []) if str(value).strip()}
  domains = {str(value).lower() for value in state.get("contactedDomains", []) if str(value).strip()}
  if sent_state_dir.is_dir():
    for path in sent_state_dir.glob("*.state.json"):
      value = read_json(path, {})
      sent = value.get("sent") if isinstance(value, dict) and isinstance(value.get("sent"), dict) else {}
      for record in sent.values():
        recipient = str(record.get("recipient") or "").lower()
        if EMAIL_PATTERN.fullmatch(recipient):
          recipients.add(recipient)
          domains.add(recipient.rsplit("@", 1)[1])
  return recipients, domains


def build_prompt(contacted_recipients: set[str], contacted_domains: set[str], limit: int) -> str:
  exclusions = ", ".join(sorted(contacted_recipients | contacted_domains)[-150:]) or "none"
  return f"""Find up to {limit} legitimate partnership or editorial contacts for RaidBench, a free and paid planning site for the video game Rust by Facepunch.

Use live web search and official company/community websites only. Each candidate must operate a Rust game server community, Rust guide/resource site, Rust hosting service, or relevant server-owner tool, and its official page must visibly publish a business, partnership, collaboration, press, editorial, or general contact email. Exclude personal contact discovery, scraped directories, gambling, skin betting/trading, cheats, boosting, real-money trading, and any recipient or domain in this exclusion list: {exclusions}.

Prepare one original 120-220 word English email per candidate. Offer the free RaidBench route presets, embeddable calculator, or reviewed data as a useful resource. Do not claim an existing audience, endorsement, guaranteed benefit, or prior relationship. Include exactly one RaidBench URL using a candidate-specific UTM source and disclose that the sender operates RaidBench. Do not propose a paid sponsorship in the first message and do not request personal data.

Return the exact public email, exact official source URL where it appears, a short evidence note, subject, and body. Return fewer than {limit} or status `none` if the requirements cannot be verified. Do not send anything."""


def run_codex(prompt: str, timeout_seconds: int) -> dict[str, Any]:
  with tempfile.TemporaryDirectory(prefix="raidbench-partner-discovery-") as temporary:
    output = Path(temporary) / "result.json"
    command = [
      "codex", "--search", "exec", "--ephemeral", "--skip-git-repo-check", "--ignore-user-config",
      "-m", os.environ.get("RAIDBENCH_PARTNER_SCOUT_MODEL", "gpt-5.6-sol"),
      "-c", f'model_reasoning_effort="{os.environ.get("RAIDBENCH_PARTNER_SCOUT_REASONING", "low")}"',
      "-s", "read-only", "-C", str(ROOT), "--output-schema", str(SCHEMA), "-o", str(output), prompt,
    ]
    try:
      result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as exc:
      raise DiscoveryError("Partner discovery timed out") from exc
    if result.returncode != 0:
      raise DiscoveryError(f"Partner discovery failed: {(result.stderr or result.stdout)[-1200:]}")
    value = read_json(output, {})
    if not isinstance(value, dict):
      raise DiscoveryError("Partner discovery did not return a JSON object")
    return value


def validate_candidate(candidate: dict[str, Any], contacted_recipients: set[str], contacted_domains: set[str]) -> dict[str, str] | None:
  fields = {key: str(candidate.get(key) or "").strip() for key in ("company", "recipient", "source_url", "evidence_note", "subject", "text_body")}
  recipient = fields["recipient"].lower()
  if not EMAIL_PATTERN.fullmatch(recipient):
    return None
  domain = recipient.rsplit("@", 1)[1]
  if recipient in contacted_recipients or domain in contacted_domains:
    return None
  source = urlparse(fields["source_url"])
  if source.scheme != "https" or not source.hostname or PROHIBITED_PATTERN.search(f"{source.hostname} {fields['company']} {fields['text_body']}"):
    return None
  words = len(fields["text_body"].split())
  if not 100 <= words <= 260 or len(fields["subject"]) > 180:
    return None
  urls = URL_PATTERN.findall(fields["text_body"])
  if len(urls) != 1 or not urls[0].startswith("https://raidbench.com/") or "utm_source=" not in urls[0]:
    return None
  html = fetch_source(fields["source_url"])
  visible = re.sub(r"<[^>]+>", " ", html)
  if recipient not in visible_emails(html) or not re.search(r"\brust\b", visible, re.IGNORECASE) or not CONTACT_PATTERN.search(visible):
    return None
  return {**fields, "recipient": recipient, "domain": domain}


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Run bounded weekly RaidBench partner outreach.")
  parser.add_argument("--output", type=Path, required=True)
  parser.add_argument("--state", type=Path, required=True)
  parser.add_argument("--sent-state-dir", type=Path, required=True)
  parser.add_argument("--weekly-limit", type=int, default=6)
  parser.add_argument("--send", action="store_true")
  parser.add_argument("--force", action="store_true")
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  try:
    limit = max(1, min(6, args.weekly_limit))
    state = read_json(args.state, {})
    if not isinstance(state, dict):
      raise DiscoveryError("Partner discovery state must be a JSON object")
    current_week = week_key()
    weekly = state.get("weekly") if isinstance(state.get("weekly"), dict) else {}
    sent_this_week = int(weekly.get(current_week, 0))
    if not args.force and sent_this_week >= limit:
      print(json.dumps({"status": "weekly_limit_reached", "week": current_week, "sent": sent_this_week}))
      return 0
    remaining = limit - sent_this_week
    contacted_recipients, contacted_domains = load_contacted(state, args.sent_state_dir)
    raw = run_codex(build_prompt(contacted_recipients, contacted_domains, remaining), int(os.environ.get("RAIDBENCH_PARTNER_SCOUT_TIMEOUT_SECONDS", "1200")))
    candidates = raw.get("candidates") if raw.get("status") == "candidates" and isinstance(raw.get("candidates"), list) else []
    verified: list[dict[str, str]] = []
    for candidate in candidates:
      if not isinstance(candidate, dict):
        continue
      checked = validate_candidate(candidate, contacted_recipients, contacted_domains)
      if not checked:
        continue
      verified.append(checked)
      contacted_recipients.add(checked["recipient"])
      contacted_domains.add(checked["domain"])
      if len(verified) >= remaining:
        break

    queue = {
      "campaign_id": f"weekly_rust_partners_{current_week}",
      "reply_to": os.environ.get("RAIDBENCH_SUPPORT_EMAIL", "support@raidbench.com"),
      "generated_at": utc_now(),
      "messages": [{
        "message_id": f"partner_{hashlib.sha256(item['recipient'].encode()).hexdigest()[:16]}_{current_week.lower()}",
        "recipient": item["recipient"],
        "subject": item["subject"],
        "source_url": item["source_url"],
        "text_body": item["text_body"],
        "company": item["company"],
        "evidence_note": item["evidence_note"],
      } for item in verified],
    }
    write_json_atomic(args.output, queue)

    sent_results: list[dict[str, str]] = []
    if args.send and verified:
      provider = os.environ.get("RAIDBENCH_EMAIL_PROVIDER", "").lower()
      sender = os.environ.get("RAIDBENCH_EMAIL_FROM", "").strip()
      reply_to = os.environ.get("RAIDBENCH_SUPPORT_EMAIL", "support@raidbench.com").strip()
      api_key = os.environ.get("SMTP2GO_API_KEY", "").strip()
      if provider != "smtp2go" or not sender or not api_key:
        raise DiscoveryError("Weekly partner send requires the configured SMTP2GO sender")
      for message in queue["messages"]:
        provider_id = send_smtp2go(message, sender=sender, reply_to=reply_to, api_key=api_key)
        sent_results.append({"recipient": message["recipient"], "provider_message_id": provider_id})
      sent_this_week += len(sent_results)

    weekly[current_week] = sent_this_week
    state.update({
      "weekly": dict(sorted(weekly.items())[-12:]),
      "contactedRecipients": sorted(contacted_recipients),
      "contactedDomains": sorted(contacted_domains),
      "lastRunAt": utc_now(),
      "lastVerified": len(verified),
      "lastSent": len(sent_results),
    })
    write_json_atomic(args.state, state)
    print(json.dumps({"status": "completed", "week": current_week, "verified": len(verified), "sent": len(sent_results)}))
    return 0
  except (DiscoveryError, OutreachError, OSError) as exc:
    print(f"ERROR: {exc}")
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
