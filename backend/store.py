from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class StoreError(RuntimeError):
    pass


class InsufficientCreditsError(StoreError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(12)}"


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path), timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
    if column not in _columns(connection, table):
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


def init_database(
    db_path: str | Path,
    schema_path: str | Path,
    skus_path: str | Path,
    multigame_products_path: str | Path | None = None,
) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema = Path(schema_path).read_text(encoding="utf-8")
    sku_data = json.loads(Path(skus_path).read_text(encoding="utf-8"))
    multigame_path = Path(multigame_products_path) if multigame_products_path else Path(skus_path).with_name("multigame-products.json")
    multigame_products = []
    if multigame_path.is_file():
        multigame_products = json.loads(multigame_path.read_text(encoding="utf-8")).get("products", [])
    connection = connect(db_path)
    try:
        connection.executescript(schema)
        _ensure_column(connection, "credit_actions", "delivery_class", "TEXT NOT NULL DEFAULT 'custom_verified'")
        _ensure_column(connection, "customers", "display_name", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "customers", "password_hash", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "customers", "region", "TEXT NOT NULL DEFAULT 'US'")
        _ensure_column(connection, "customers", "currency", "TEXT NOT NULL DEFAULT 'USD'")
        _ensure_column(connection, "customers", "updated_at", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "orders", "updated_at", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "orders", "raw_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(connection, "orders", "provider_capture_id", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "orders", "terms_version", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "orders", "refund_policy_version", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "orders", "consented_at", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "payment_events", "signature_status", "TEXT NOT NULL DEFAULT 'unverified'")
        _ensure_column(connection, "payment_events", "processing_status", "TEXT NOT NULL DEFAULT 'received'")
        _ensure_column(connection, "payment_events", "error", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "payment_events", "updated_at", "TEXT NOT NULL DEFAULT ''")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_provider_capture ON orders(provider_capture_id)"
        )
        connection.execute(
            """
            UPDATE owner_notifications
            SET status = 'failed', last_error = 'Delivery interrupted before completion', updated_at = ?
            WHERE status = 'sending'
            """,
            (utc_now(),),
        )

        now = utc_now()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE sku_packs SET status = 'retired'")
        connection.execute("UPDATE credit_actions SET status = 'retired'")
        for pack in sku_data["packs"]:
            prices = pack["prices"]
            connection.execute(
                """
                INSERT INTO sku_packs (sku, name, credits, price_usd, price_eur, price_gbp, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sku) DO UPDATE SET
                  name = excluded.name,
                  credits = excluded.credits,
                  price_usd = excluded.price_usd,
                  price_eur = excluded.price_eur,
                  price_gbp = excluded.price_gbp,
                  status = excluded.status
                """,
                (
                    pack["sku"],
                    pack["name"],
                    int(pack["credits"]),
                    float(prices["USD"]),
                    float(prices.get("EUR", 0)),
                    float(prices.get("GBP", 0)),
                    pack["status"],
                ),
            )
        for action in sku_data["actions"]:
            connection.execute(
                """
                INSERT INTO credit_actions (id, label, credits, output, delivery_class, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  label = excluded.label,
                  credits = excluded.credits,
                  output = excluded.output,
                  delivery_class = excluded.delivery_class,
                  status = excluded.status
                """,
                (
                    action["id"],
                    action["label"],
                    int(action["credits"]),
                    action["output"],
                    action.get("deliveryClass", "custom_verified"),
                    action.get("status", "draft"),
                ),
            )
        for action in multigame_products:
            connection.execute(
                """
                INSERT INTO credit_actions (id, label, credits, output, delivery_class, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  label = excluded.label,
                  credits = excluded.credits,
                  output = excluded.output,
                  delivery_class = excluded.delivery_class,
                  status = excluded.status
                """,
                (
                    action["id"],
                    action["label"],
                    int(action["credits"]),
                    action["output"],
                    action["deliveryClass"],
                    action.get("status", "hidden_pending_qa"),
                ),
            )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (id, applied_at) VALUES (?, ?)",
            ("local-commerce-v2", now),
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (id, applied_at) VALUES (?, ?)",
            ("account-recovery-v1", now),
        )
        connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()


def create_customer(
    connection: sqlite3.Connection,
    email: str,
    password_hash: str,
    display_name: str = "",
    region: str = "US",
) -> dict[str, Any]:
    now = utc_now()
    customer_id = new_id("cus")
    try:
        connection.execute(
            """
            INSERT INTO customers (id, email, display_name, password_hash, region, currency, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'USD', ?, ?)
            """,
            (customer_id, email.lower(), display_name.strip()[:80], password_hash, region, now, now),
        )
    except sqlite3.IntegrityError as error:
        raise StoreError("An account already exists for this email.") from error
    return get_customer(connection, customer_id)


def get_customer(connection: sqlite3.Connection, customer_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT id, email, display_name, region, currency, created_at FROM customers WHERE id = ?",
        (customer_id,),
    ).fetchone()
    if not row:
        raise StoreError("Customer not found.")
    return dict(row)


def get_customer_auth(connection: sqlite3.Connection, email: str) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM customers WHERE email = ?", (email.lower(),)).fetchone()
    return dict(row) if row else None


def get_or_create_demo_customer(connection: sqlite3.Connection) -> dict[str, Any]:
    existing = get_customer_auth(connection, "demo@raidbench.local")
    if existing:
        return get_customer(connection, existing["id"])
    return create_customer(
        connection,
        "demo@raidbench.local",
        "",
        display_name="Local Demo Player",
        region="US",
    )


def create_session(connection: sqlite3.Connection, customer_id: str, lifetime_days: int = 14) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    connection.execute(
        "INSERT INTO sessions (id, customer_id, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
        (new_id("ses"), customer_id, token_hash, now.isoformat(), (now + timedelta(days=lifetime_days)).isoformat()),
    )
    return token


def customer_for_session(connection: sqlite3.Connection, token: str) -> dict[str, Any] | None:
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = connection.execute(
        """
        SELECT c.id, c.email, c.display_name, c.region, c.currency, c.created_at
        FROM sessions s
        JOIN customers c ON c.id = s.customer_id
        WHERE s.token_hash = ? AND s.expires_at > ?
        """,
        (token_hash, utc_now()),
    ).fetchone()
    return dict(row) if row else None


def delete_session(connection: sqlite3.Connection, token: str) -> None:
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def password_reset_request_allowed(
    connection: sqlite3.Connection,
    email: str,
    *,
    cooldown_seconds: int = 60,
    window_minutes: int = 60,
    max_requests: int = 5,
) -> bool:
    identifier_hash = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "DELETE FROM password_reset_requests WHERE last_requested_at < ?",
            ((now - timedelta(days=2)).isoformat(),),
        )
        row = connection.execute(
            "SELECT * FROM password_reset_requests WHERE identifier_hash = ?",
            (identifier_hash,),
        ).fetchone()
        if not row:
            connection.execute(
                """
                INSERT INTO password_reset_requests (
                  identifier_hash, window_started_at, request_count, last_requested_at
                ) VALUES (?, ?, 1, ?)
                """,
                (identifier_hash, now.isoformat(), now.isoformat()),
            )
            allowed = True
        else:
            window_started = datetime.fromisoformat(row["window_started_at"])
            last_requested = datetime.fromisoformat(row["last_requested_at"])
            window_expired = now - window_started >= timedelta(minutes=window_minutes)
            if window_expired:
                request_count = 1
                window_started = now
                allowed = True
            else:
                request_count = int(row["request_count"]) + 1
                allowed = bool(
                    request_count <= max_requests
                    and now - last_requested >= timedelta(seconds=cooldown_seconds)
                )
            connection.execute(
                """
                UPDATE password_reset_requests
                SET window_started_at = ?, request_count = ?, last_requested_at = ?
                WHERE identifier_hash = ?
                """,
                (window_started.isoformat(), request_count, now.isoformat(), identifier_hash),
            )
        connection.execute("COMMIT")
        return allowed
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def create_password_reset_token(
    connection: sqlite3.Connection,
    customer_id: str,
    *,
    lifetime_minutes: int = 30,
) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "DELETE FROM password_reset_tokens WHERE expires_at < ?",
            ((now - timedelta(days=1)).isoformat(),),
        )
        connection.execute(
            "UPDATE password_reset_tokens SET used_at = ? WHERE customer_id = ? AND used_at = ''",
            (now.isoformat(), customer_id),
        )
        connection.execute(
            """
            INSERT INTO password_reset_tokens (
              id, customer_id, token_hash, created_at, expires_at, used_at
            ) VALUES (?, ?, ?, ?, ?, '')
            """,
            (
                new_id("rst"),
                customer_id,
                token_hash,
                now.isoformat(),
                (now + timedelta(minutes=lifetime_minutes)).isoformat(),
            ),
        )
        connection.execute("COMMIT")
        return token
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def invalidate_password_reset_token(connection: sqlite3.Connection, token: str) -> None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    connection.execute(
        "UPDATE password_reset_tokens SET used_at = ? WHERE token_hash = ? AND used_at = ''",
        (utc_now(), token_hash),
    )


def consume_password_reset_token(
    connection: sqlite3.Connection,
    token: str,
    password_hash: str,
) -> str:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = utc_now()
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = connection.execute(
            """
            SELECT customer_id
            FROM password_reset_tokens
            WHERE token_hash = ? AND used_at = '' AND expires_at > ?
            """,
            (token_hash, now),
        ).fetchone()
        if not row:
            raise StoreError("This password reset link is invalid or has expired.")
        customer_id = str(row["customer_id"])
        connection.execute(
            "UPDATE customers SET password_hash = ?, updated_at = ? WHERE id = ?",
            (password_hash, now, customer_id),
        )
        connection.execute(
            "UPDATE password_reset_tokens SET used_at = ? WHERE customer_id = ? AND used_at = ''",
            (now, customer_id),
        )
        connection.execute("DELETE FROM sessions WHERE customer_id = ?", (customer_id,))
        connection.execute("COMMIT")
        return customer_id
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def credit_balance(connection: sqlite3.Connection, customer_id: str) -> int:
    row = connection.execute(
        "SELECT COALESCE(SUM(credits_delta), 0) AS balance FROM credit_ledger WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()
    return int(row["balance"])


def reserved_credits(connection: sqlite3.Connection, customer_id: str) -> int:
    row = connection.execute(
        """
        SELECT COALESCE(SUM(credits_cost), 0) AS reserved
        FROM questions
        WHERE customer_id = ? AND status = 'queued' AND credits_charged = 0
        """,
        (customer_id,),
    ).fetchone()
    return int(row["reserved"])


def available_credit_balance(connection: sqlite3.Connection, customer_id: str) -> int:
    return max(0, credit_balance(connection, customer_id) - reserved_credits(connection, customer_id))


def account_summary(connection: sqlite3.Connection, customer_id: str) -> dict[str, Any]:
    customer = get_customer(connection, customer_id)
    customer["creditBalance"] = credit_balance(connection, customer_id)
    customer["reservedCredits"] = reserved_credits(connection, customer_id)
    customer["availableCredits"] = max(0, customer["creditBalance"] - customer["reservedCredits"])
    customer["answerCount"] = int(connection.execute(
        "SELECT COUNT(*) AS count FROM questions WHERE customer_id = ? AND status = 'ready'",
        (customer_id,),
    ).fetchone()["count"])
    return customer


def catalog(connection: sqlite3.Connection, include_demo: bool) -> dict[str, Any]:
    pack_rows = connection.execute(
        """
        SELECT sku, name, credits, price_usd, status
        FROM sku_packs
        WHERE status = 'ready_after_payment_setup'
        ORDER BY price_usd
        """
    ).fetchall()
    allowed_action_statuses = ("ready_private_demo", "ready_live") if include_demo else ("ready_live",)
    placeholders = ",".join("?" for _ in allowed_action_statuses)
    action_rows = connection.execute(
        f"""
        SELECT id, label, credits, output, delivery_class, status
        FROM credit_actions
        WHERE status IN ({placeholders})
        ORDER BY credits
        """,
        allowed_action_statuses,
    ).fetchall()
    return {
        "currency": "USD",
        "launchMarkets": ["US", "CA"],
        "packs": [dict(row) for row in pack_rows],
        "actions": [dict(row) for row in action_rows],
    }


def list_orders(connection: sqlite3.Connection, customer_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, provider_transaction_id, sku, amount, currency, credits_granted,
               status, created_at, updated_at
        FROM orders
        WHERE customer_id = ?
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (customer_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "paymentReference": row["provider_transaction_id"],
            "sku": row["sku"],
            "amount": float(row["amount"]),
            "currency": row["currency"],
            "credits": int(row["credits_granted"]),
            "status": row["status"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
        for row in rows
    ]


def _pack(connection: sqlite3.Connection, sku: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM sku_packs WHERE sku = ? AND status = 'ready_after_payment_setup'",
        (sku,),
    ).fetchone()
    if not row:
        raise StoreError("Credit pack is unavailable.")
    return row


def grant_demo_order(
    connection: sqlite3.Connection,
    customer_id: str,
    sku: str,
    idempotency_key: str,
) -> dict[str, Any]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        existing = connection.execute(
            "SELECT order_id FROM credit_ledger WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if existing:
            order = connection.execute("SELECT * FROM orders WHERE id = ?", (existing["order_id"],)).fetchone()
            connection.execute("COMMIT")
            return {"order": dict(order), "creditBalance": credit_balance(connection, customer_id)}

        pack = _pack(connection, sku)
        order_id = new_id("ord")
        now = utc_now()
        transaction_id = new_id("demo_paypal")
        connection.execute(
            """
            INSERT INTO orders (
              id, customer_id, provider, provider_transaction_id, sku, amount, currency,
              credits_granted, status, created_at, updated_at, raw_json
            ) VALUES (?, ?, 'demo_paypal_sandbox', ?, ?, ?, 'USD', ?, 'completed', ?, ?, ?)
            """,
            (
                order_id,
                customer_id,
                transaction_id,
                pack["sku"],
                pack["price_usd"],
                pack["credits"],
                now,
                now,
                json_text({"mode": "local_demo", "simulated": True}),
            ),
        )
        balance_after = credit_balance(connection, customer_id) + int(pack["credits"])
        connection.execute(
            """
            INSERT INTO credit_ledger (
              id, customer_id, order_id, entry_type, credits_delta, balance_after,
              reason, idempotency_key, created_at
            ) VALUES (?, ?, ?, 'purchase', ?, ?, ?, ?, ?)
            """,
            (
                new_id("led"),
                customer_id,
                order_id,
                int(pack["credits"]),
                balance_after,
                f"Local PayPal sandbox simulation: {pack['name']}",
                idempotency_key,
                now,
            ),
        )
        connection.execute("COMMIT")
        return {
            "order": {
                "id": order_id,
                "sku": pack["sku"],
                "amount": pack["price_usd"],
                "currency": "USD",
                "creditsGranted": pack["credits"],
                "status": "completed",
            },
            "creditBalance": balance_after,
        }
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def _question_row(connection: sqlite3.Connection, question_id: str, customer_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM questions WHERE id = ? AND customer_id = ?",
        (question_id, customer_id),
    ).fetchone()


def _question_dict(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    answer = json.loads(row["answer_json"] or "{}")
    inputs = json.loads(row["input_json"] or "{}")
    events = [dict(item) for item in connection.execute(
        "SELECT event_type, label, detail, created_at FROM question_events WHERE question_id = ? ORDER BY created_at, rowid",
        (row["id"],),
    ).fetchall()]
    return {
        "id": row["id"],
        "game": row["game"],
        "questionType": row["question_type"],
        "questionText": row["question_text"],
        "status": row["status"],
        "qaStatus": row["qa_status"],
        "creditsCost": row["credits_cost"],
        "creditsCharged": row["credits_charged"],
        "blockedReason": row["blocked_reason"],
        "submittedAt": row["submitted_at"],
        "completedAt": row["completed_at"],
        "inputs": inputs,
        "answer": answer,
        "events": events,
    }


def create_verified_question(
    connection: sqlite3.Connection,
    customer_id: str,
    action_id: str,
    question_type: str,
    question_text: str,
    inputs: dict[str, Any],
    answer: dict[str, Any],
    idempotency_key: str,
    game: str = "Rust",
) -> dict[str, Any]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        existing = connection.execute(
            "SELECT * FROM questions WHERE idempotency_key = ? AND customer_id = ?",
            (idempotency_key, customer_id),
        ).fetchone()
        if existing:
            connection.execute("COMMIT")
            return _question_dict(connection, existing)

        action = connection.execute(
            "SELECT * FROM credit_actions WHERE id = ? AND status IN ('ready_private_demo', 'ready_live')",
            (action_id,),
        ).fetchone()
        if not action:
            raise StoreError("This answer product is unavailable.")
        ledger_balance = credit_balance(connection, customer_id)
        balance = available_credit_balance(connection, customer_id)
        cost = int(action["credits"])
        if balance < cost:
            raise InsufficientCreditsError(f"This answer costs {cost} credits; the current balance is {balance}.")

        now = utc_now()
        question_id = new_id("qst")
        ledger_id = new_id("led")
        balance_after = ledger_balance - cost
        game_name = str(game).strip()[:80]
        if not game_name:
            raise StoreError("Question game is required.")
        connection.execute(
            """
            INSERT INTO questions (
              id, customer_id, game, question_type, question_text, input_json, answer_json,
              status, qa_status, credits_cost, credits_charged, idempotency_key,
              blocked_reason, submitted_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ready', 'approved', ?, ?, ?, '', ?, ?)
            """,
            (
                question_id,
                customer_id,
                game_name,
                question_type,
                question_text[:2000],
                json_text(inputs),
                json_text(answer),
                cost,
                cost,
                idempotency_key,
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO credit_ledger (
              id, customer_id, order_id, entry_type, credits_delta, balance_after,
              reason, idempotency_key, created_at
            ) VALUES (?, ?, NULL, 'answer_debit', ?, ?, ?, ?, ?)
            """,
            (
                ledger_id,
                customer_id,
                -cost,
                balance_after,
                f"{action['label']} delivered in customer account",
                f"answer:{idempotency_key}",
                now,
            ),
        )
        delivery_id = new_id("del")
        connection.execute(
            """
            INSERT INTO delivery_records (
              id, customer_id, action_id, ledger_id, input_json, output_json, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'delivered_in_account', ?)
            """,
            (delivery_id, customer_id, action_id, ledger_id, json_text(inputs), json_text(answer), now),
        )
        for event_type, label, detail in (
            ("submitted", "Request received", "Inputs were stored in the local order database."),
            ("evidence_checked", "Evidence checked", "Current official and independent source records were attached."),
            ("calculation_verified", "Calculation verified", "A separate deterministic pass reproduced every total."),
            ("published", "Answer published", "The approved answer was released directly to this account."),
        ):
            connection.execute(
                "INSERT INTO question_events (id, question_id, event_type, label, detail, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (new_id("evt"), question_id, event_type, label, detail, now),
            )
        for evidence in answer.get("evidence", []):
            connection.execute(
                """
                INSERT INTO answer_evidence (
                  id, question_id, evidence_type, source_title, source_url, claim_supported, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("evi"),
                    question_id,
                    evidence["type"],
                    evidence["title"],
                    evidence["url"],
                    evidence["supports"],
                    evidence["checkedAt"],
                ),
            )
        connection.execute("COMMIT")
        return _question_dict(connection, _question_row(connection, question_id, customer_id))
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def create_deferred_question(
    connection: sqlite3.Connection,
    customer_id: str,
    question_type: str,
    question_text: str,
    inputs: dict[str, Any],
    reason: str,
    idempotency_key: str,
    game: str = "Rust",
    credits_cost: int = 0,
) -> dict[str, Any]:
    existing = connection.execute(
        "SELECT * FROM questions WHERE idempotency_key = ? AND customer_id = ?",
        (idempotency_key, customer_id),
    ).fetchone()
    if existing:
        return _question_dict(connection, existing)
    question_id = new_id("qst")
    now = utc_now()
    game_name = str(game).strip()[:80]
    if not game_name:
        raise StoreError("Question game is required.")
    connection.execute(
        """
        INSERT INTO questions (
          id, customer_id, game, question_type, question_text, input_json, answer_json,
          status, qa_status, credits_cost, credits_charged, idempotency_key,
          blocked_reason, submitted_at, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, '{}', 'needs_review', 'blocked', ?, 0, ?, ?, ?, NULL)
        """,
        (
            question_id,
            customer_id,
            game_name,
            question_type,
            question_text[:2000],
            json_text(inputs),
            max(0, int(credits_cost)),
            idempotency_key,
            reason,
            now,
        ),
    )
    connection.execute(
        "INSERT INTO question_events (id, question_id, event_type, label, detail, created_at) VALUES (?, ?, 'held', 'No charge - review required', ?, ?)",
        (new_id("evt"), question_id, reason, now),
    )
    return _question_dict(connection, _question_row(connection, question_id, customer_id))


def create_queued_question(
    connection: sqlite3.Connection,
    customer_id: str,
    action_id: str,
    question_text: str,
    inputs: dict[str, Any],
    idempotency_key: str,
    game: str,
) -> dict[str, Any]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        existing = connection.execute(
            "SELECT * FROM questions WHERE idempotency_key = ? AND customer_id = ?",
            (idempotency_key, customer_id),
        ).fetchone()
        if existing:
            same_request = (
                existing["question_type"] == action_id
                and existing["game"] == str(game).strip()[:80]
                and existing["question_text"] == question_text[:2000]
                and json.loads(existing["input_json"] or "{}") == inputs
            )
            if not same_request:
                raise StoreError("This idempotency key was already used for a different answer request.")
            connection.execute("COMMIT")
            return _question_dict(connection, existing)

        action = connection.execute(
            "SELECT * FROM credit_actions WHERE id = ? AND status = 'ready_live'",
            (action_id,),
        ).fetchone()
        if not action:
            raise StoreError("This answer product is unavailable.")
        cost = int(action["credits"])
        balance = available_credit_balance(connection, customer_id)
        if balance < cost:
            raise InsufficientCreditsError(
                f"This review reserves {cost} credits; the current available balance is {balance}."
            )

        now = utc_now()
        question_id = new_id("qst")
        game_name = str(game).strip()[:80]
        if not game_name:
            raise StoreError("Question game is required.")
        connection.execute(
            """
            INSERT INTO questions (
              id, customer_id, game, question_type, question_text, input_json, answer_json,
              status, qa_status, credits_cost, credits_charged, idempotency_key,
              blocked_reason, submitted_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, '{}', 'queued', 'pending', ?, 0, ?, '', ?, NULL)
            """,
            (
                question_id,
                customer_id,
                game_name,
                action_id,
                question_text[:2000],
                json_text(inputs),
                cost,
                idempotency_key,
                now,
            ),
        )
        for event_type, label, detail in (
            ("submitted", "Request received", "Your game context was stored in the private order database."),
            (
                "qa_queued",
                "Independent QA queued",
                f"{cost} credits are reserved but will not be charged unless the reviewed answer is approved.",
            ),
        ):
            connection.execute(
                "INSERT INTO question_events (id, question_id, event_type, label, detail, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (new_id("evt"), question_id, event_type, label, detail, now),
            )
        connection.execute("COMMIT")
        return _question_dict(connection, _question_row(connection, question_id, customer_id))
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def _reviewed_answer_evidence(answer: dict[str, Any]) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for claim in answer.get("claims", []):
        if not isinstance(claim, dict):
            continue
        for item in claim.get("evidence", []):
            if not isinstance(item, dict):
                continue
            key = (
                str(item.get("sourceType") or ""),
                str(item.get("title") or ""),
                str(item.get("url") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            evidence.append({
                "type": key[0],
                "title": key[1],
                "url": key[2],
                "supports": str(item.get("supports") or claim.get("text") or "")[:1000],
                "checkedAt": str(item.get("retrievedAt") or answer.get("generatedAt") or utc_now()),
            })
    return evidence


def complete_queued_question(
    connection: sqlite3.Connection,
    question_id: str,
    answer: dict[str, Any],
) -> dict[str, Any]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = connection.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        if not row:
            raise StoreError("Queued answer request was not found.")
        if row["status"] == "ready":
            connection.execute("COMMIT")
            return _question_dict(connection, row)
        if row["status"] != "queued" or int(row["credits_charged"]) != 0:
            raise StoreError("This answer request is no longer eligible for delivery.")

        action = connection.execute(
            "SELECT * FROM credit_actions WHERE id = ? AND status = 'ready_live'",
            (row["question_type"],),
        ).fetchone()
        if not action:
            raise StoreError("This answer product was paused before delivery.")
        cost = int(row["credits_cost"])
        if cost != int(action["credits"]):
            raise StoreError("The queued price no longer matches the live product price.")
        balance = credit_balance(connection, row["customer_id"])
        if balance < cost:
            raise InsufficientCreditsError("The account balance changed before the answer could be delivered.")

        now = utc_now()
        ledger_id = new_id("led")
        balance_after = balance - cost
        connection.execute(
            """
            INSERT INTO credit_ledger (
              id, customer_id, order_id, entry_type, credits_delta, balance_after,
              reason, idempotency_key, created_at
            ) VALUES (?, ?, NULL, 'answer_debit', ?, ?, ?, ?, ?)
            """,
            (
                ledger_id,
                row["customer_id"],
                -cost,
                balance_after,
                f"{action['label']} delivered in customer account",
                f"queued-answer:{question_id}",
                now,
            ),
        )
        connection.execute(
            """
            UPDATE questions
            SET answer_json = ?, status = 'ready', qa_status = 'approved',
                credits_charged = ?, blocked_reason = '', completed_at = ?
            WHERE id = ? AND status = 'queued' AND credits_charged = 0
            """,
            (json_text(answer), cost, now, question_id),
        )
        connection.execute(
            """
            INSERT INTO delivery_records (
              id, customer_id, action_id, ledger_id, input_json, output_json, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'delivered_in_account', ?)
            """,
            (
                new_id("del"),
                row["customer_id"],
                row["question_type"],
                ledger_id,
                row["input_json"],
                json_text(answer),
                now,
            ),
        )
        for event_type, label, detail in (
            ("evidence_checked", "Evidence checked", "Current publisher records and the supplied player context were checked."),
            ("independent_qa", "Independent QA approved", "A separate review blocked unsupported claims before delivery."),
            ("published", "Answer published", "The approved answer was released to this account and charged once."),
        ):
            connection.execute(
                "INSERT INTO question_events (id, question_id, event_type, label, detail, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (new_id("evt"), question_id, event_type, label, detail, now),
            )
        for evidence in _reviewed_answer_evidence(answer):
            connection.execute(
                """
                INSERT INTO answer_evidence (
                  id, question_id, evidence_type, source_title, source_url, claim_supported, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("evi"), question_id, evidence["type"], evidence["title"],
                    evidence["url"], evidence["supports"], evidence["checkedAt"],
                ),
            )
        connection.execute("COMMIT")
        return _question_dict(
            connection,
            connection.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone(),
        )
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def hold_queued_question(
    connection: sqlite3.Connection,
    question_id: str,
    reason: str,
) -> dict[str, Any]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = connection.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        if not row:
            raise StoreError("Queued answer request was not found.")
        if row["status"] != "queued":
            connection.execute("COMMIT")
            return _question_dict(connection, row)
        now = utc_now()
        safe_reason = str(reason).strip()[:1000] or "Independent QA could not verify a complete answer. No credits were charged."
        connection.execute(
            """
            UPDATE questions
            SET status = 'needs_review', qa_status = 'blocked', credits_charged = 0,
                blocked_reason = ?, completed_at = ?
            WHERE id = ? AND status = 'queued'
            """,
            (safe_reason, now, question_id),
        )
        connection.execute(
            "INSERT INTO question_events (id, question_id, event_type, label, detail, created_at) VALUES (?, ?, 'held', 'QA hold - no charge', ?, ?)",
            (new_id("evt"), question_id, safe_reason, now),
        )
        connection.execute("COMMIT")
        return _question_dict(
            connection,
            connection.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone(),
        )
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def list_questions(connection: sqlite3.Connection, customer_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM questions WHERE customer_id = ? ORDER BY submitted_at DESC LIMIT 100",
        (customer_id,),
    ).fetchall()
    return [_question_dict(connection, row) for row in rows]


def get_question(connection: sqlite3.Connection, customer_id: str, question_id: str) -> dict[str, Any]:
    row = _question_row(connection, question_id, customer_id)
    if not row:
        raise StoreError("Answer not found.")
    return _question_dict(connection, row)


def create_pending_paypal_order(
    connection: sqlite3.Connection,
    customer_id: str,
    sku: str,
    paypal_order_id: str,
    raw_payload: dict[str, Any],
    local_order_id: str | None = None,
    consent: dict[str, str] | None = None,
) -> dict[str, Any]:
    pack = _pack(connection, sku)
    existing = connection.execute(
        "SELECT * FROM orders WHERE provider_transaction_id = ?",
        (paypal_order_id,),
    ).fetchone()
    if existing:
        return dict(existing)
    now = utc_now()
    order_id = local_order_id or new_id("ord")
    consent = consent or {}
    connection.execute(
        """
        INSERT INTO orders (
          id, customer_id, provider, provider_transaction_id, sku, amount, currency,
          credits_granted, terms_version, refund_policy_version, consented_at,
          status, created_at, updated_at, raw_json
        ) VALUES (?, ?, 'paypal', ?, ?, ?, 'USD', ?, ?, ?, ?, 'pending_approval', ?, ?, ?)
        """,
        (
            order_id,
            customer_id,
            paypal_order_id,
            pack["sku"],
            pack["price_usd"],
            pack["credits"],
            str(consent.get("termsVersion") or "")[:40],
            str(consent.get("refundPolicyVersion") or "")[:40],
            str(consent.get("consentedAt") or now)[:40],
            now,
            now,
            json_text(raw_payload),
        ),
    )
    return dict(connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())


def paypal_order(connection: sqlite3.Connection, customer_id: str, paypal_order_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM orders WHERE customer_id = ? AND provider = 'paypal' AND provider_transaction_id = ?",
        (customer_id, paypal_order_id),
    ).fetchone()
    if not row:
        raise StoreError("PayPal order not found.")
    return dict(row)


def paypal_order_by_provider(connection: sqlite3.Connection, paypal_order_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM orders WHERE provider = 'paypal' AND provider_transaction_id = ?",
        (paypal_order_id,),
    ).fetchone()
    if not row:
        raise StoreError("PayPal order not found.")
    return dict(row)


def paypal_order_by_capture(connection: sqlite3.Connection, capture_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM orders WHERE provider = 'paypal' AND provider_capture_id = ?",
        (capture_id,),
    ).fetchone()
    if not row:
        raise StoreError("PayPal capture not found.")
    return dict(row)


def completed_paypal_order_result(
    connection: sqlite3.Connection,
    customer_id: str,
    paypal_order_id: str,
) -> dict[str, Any] | None:
    order = paypal_order(connection, customer_id, paypal_order_id)
    if order["status"] != "completed":
        return None
    return {"order": order, "creditBalance": credit_balance(connection, customer_id)}


def _completed_captures(capture_payload: dict[str, Any]) -> list[dict[str, Any]]:
    captures: list[dict[str, Any]] = []
    for unit in capture_payload.get("purchase_units") or []:
        for capture in ((unit.get("payments") or {}).get("captures") or []):
            if capture.get("status") == "COMPLETED":
                captures.append(capture)
    return captures


def _complete_paypal_order_record(
    connection: sqlite3.Connection,
    order: dict[str, Any],
    *,
    capture_id: str,
    paid: float,
    currency: str,
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    if order["status"] == "completed":
        existing_capture = str(order.get("provider_capture_id") or "")
        if existing_capture and capture_id and existing_capture != capture_id:
            raise StoreError("PayPal capture does not match the completed order.")
        return {"order": order, "creditBalance": credit_balance(connection, order["customer_id"])}
    if currency != order["currency"] or abs(paid - float(order["amount"])) > 0.001:
        raise StoreError("Captured PayPal amount does not match the stored order.")
    if not capture_id:
        raise StoreError("PayPal capture id is missing.")

    balance_after = credit_balance(connection, order["customer_id"]) + int(order["credits_granted"])
    now = utc_now()
    connection.execute(
        """
        UPDATE orders
        SET status = 'completed', provider_capture_id = ?, updated_at = ?, raw_json = ?
        WHERE id = ?
        """,
        (capture_id, now, json_text(raw_payload), order["id"]),
    )
    connection.execute(
        """
        INSERT INTO credit_ledger (
          id, customer_id, order_id, entry_type, credits_delta, balance_after,
          reason, idempotency_key, created_at
        ) VALUES (?, ?, ?, 'purchase', ?, ?, 'PayPal credit purchase', ?, ?)
        """,
        (
            new_id("led"),
            order["customer_id"],
            order["id"],
            int(order["credits_granted"]),
            balance_after,
            f"paypal-capture:{capture_id}",
            now,
        ),
    )
    completed = dict(connection.execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone())
    return {"order": completed, "creditBalance": balance_after}


def complete_paypal_order(
    connection: sqlite3.Connection,
    customer_id: str,
    paypal_order_id: str,
    capture_payload: dict[str, Any],
) -> dict[str, Any]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        order = paypal_order(connection, customer_id, paypal_order_id)
        if capture_payload.get("status") != "COMPLETED":
            raise StoreError("PayPal has not completed this order.")
        captures = _completed_captures(capture_payload)
        if not captures:
            raise StoreError("PayPal capture response is incomplete.")
        paid = sum(float(capture.get("amount", {}).get("value", 0)) for capture in captures)
        currencies = {capture.get("amount", {}).get("currency_code") for capture in captures}
        if len(currencies) != 1:
            raise StoreError("PayPal capture currencies are inconsistent.")
        result = _complete_paypal_order_record(
            connection,
            order,
            capture_id=str(captures[0].get("id") or ""),
            paid=paid,
            currency=str(next(iter(currencies)) or ""),
            raw_payload=capture_payload,
        )
        connection.execute("COMMIT")
        return result
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def complete_paypal_capture_event(
    connection: sqlite3.Connection,
    paypal_order_id: str,
    capture_resource: dict[str, Any],
    raw_event: dict[str, Any],
) -> dict[str, Any]:
    if capture_resource.get("status") != "COMPLETED":
        raise StoreError("PayPal webhook capture is not completed.")
    amount = capture_resource.get("amount") or {}
    connection.execute("BEGIN IMMEDIATE")
    try:
        order = paypal_order_by_provider(connection, paypal_order_id)
        result = _complete_paypal_order_record(
            connection,
            order,
            capture_id=str(capture_resource.get("id") or ""),
            paid=float(amount.get("value", 0)),
            currency=str(amount.get("currency_code") or ""),
            raw_payload=raw_event,
        )
        connection.execute("COMMIT")
        return result
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def record_payment_event(
    connection: sqlite3.Connection,
    *,
    provider_event_id: str,
    event_type: str,
    payload: dict[str, Any],
    order_id: str | None = None,
    signature_status: str = "verified",
) -> dict[str, Any]:
    now = utc_now()
    connection.execute(
        """
        INSERT OR IGNORE INTO payment_events (
          id, provider, provider_event_id, event_type, order_id, payload_json,
          signature_status, processing_status, error, created_at, updated_at
        ) VALUES (?, 'paypal', ?, ?, ?, ?, ?, 'received', '', ?, ?)
        """,
        (
            new_id("pev"),
            provider_event_id,
            event_type,
            order_id,
            json_text(payload),
            signature_status,
            now,
            now,
        ),
    )
    row = connection.execute(
        "SELECT * FROM payment_events WHERE provider = 'paypal' AND provider_event_id = ?",
        (provider_event_id,),
    ).fetchone()
    if not row:
        raise StoreError("Payment event could not be recorded.")
    return dict(row)


def mark_payment_event(
    connection: sqlite3.Connection,
    provider_event_id: str,
    *,
    status: str,
    order_id: str | None = None,
    error: str = "",
) -> None:
    connection.execute(
        """
        UPDATE payment_events
        SET processing_status = ?, order_id = COALESCE(?, order_id), error = ?, updated_at = ?
        WHERE provider = 'paypal' AND provider_event_id = ?
        """,
        (status, order_id, error[:1000], utc_now(), provider_event_id),
    )


def claim_owner_notification(
    connection: sqlite3.Connection,
    order_id: str,
    notification_type: str,
    *,
    max_attempts: int = 5,
) -> str | None:
    notification_key = f"paypal-order:{order_id}:{notification_type}"
    now = utc_now()
    connection.execute("BEGIN IMMEDIATE")
    try:
        existing = connection.execute(
            "SELECT * FROM owner_notifications WHERE notification_key = ?",
            (notification_key,),
        ).fetchone()
        if existing and (existing["status"] in {"sending", "sent"} or int(existing["attempts"]) >= max_attempts):
            connection.execute("COMMIT")
            return None
        if existing:
            connection.execute(
                """
                UPDATE owner_notifications
                SET status = 'sending', attempts = attempts + 1, last_error = '', updated_at = ?
                WHERE notification_key = ?
                """,
                (now, notification_key),
            )
        else:
            connection.execute(
                """
                INSERT INTO owner_notifications (
                  notification_key, order_id, notification_type, status, attempts,
                  last_error, created_at, updated_at, sent_at
                ) VALUES (?, ?, ?, 'sending', 1, '', ?, ?, '')
                """,
                (notification_key, order_id, notification_type, now, now),
            )
        connection.execute("COMMIT")
        return notification_key
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def finish_owner_notification(
    connection: sqlite3.Connection,
    notification_key: str,
    *,
    sent: bool,
    error: str = "",
) -> None:
    now = utc_now()
    connection.execute(
        """
        UPDATE owner_notifications
        SET status = ?, last_error = ?, updated_at = ?, sent_at = CASE WHEN ? THEN ? ELSE sent_at END
        WHERE notification_key = ?
        """,
        ("sent" if sent else "failed", error[:1000], now, sent, now, notification_key),
    )


def update_paypal_order_status(
    connection: sqlite3.Connection,
    paypal_order_id: str,
    status: str,
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    allowed = {"payment_pending", "payment_denied", "completed", "refund_review", "refunded", "reversed"}
    if status not in allowed:
        raise StoreError("Unsupported PayPal order status.")
    order = paypal_order_by_provider(connection, paypal_order_id)
    if order["status"] not in {"completed", "refunded", "reversed"}:
        connection.execute(
            "UPDATE orders SET status = ?, raw_json = ?, updated_at = ? WHERE id = ?",
            (status, json_text(raw_payload), utc_now(), order["id"]),
        )
    return dict(connection.execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone())


def reverse_paypal_credits(
    connection: sqlite3.Connection,
    *,
    provider_event_id: str,
    capture_id: str,
    amount: float,
    currency: str,
    status: str,
    raw_event: dict[str, Any],
) -> dict[str, Any]:
    if status not in {"refunded", "reversed"}:
        raise StoreError("Unsupported PayPal reversal status.")
    connection.execute("BEGIN IMMEDIATE")
    try:
        order = paypal_order_by_capture(connection, capture_id)
        if order["status"] in {"refunded", "reversed"}:
            connection.execute("COMMIT")
            return {"order": order, "creditBalance": credit_balance(connection, order["customer_id"])}
        if currency != order["currency"] or abs(amount - float(order["amount"])) > 0.001:
            connection.execute(
                "UPDATE orders SET status = 'refund_review', raw_json = ?, updated_at = ? WHERE id = ?",
                (json_text(raw_event), utc_now(), order["id"]),
            )
            connection.execute("COMMIT")
            return {
                "order": dict(connection.execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()),
                "creditBalance": credit_balance(connection, order["customer_id"]),
                "manualReview": True,
            }

        balance_after = credit_balance(connection, order["customer_id"]) - int(order["credits_granted"])
        now = utc_now()
        connection.execute(
            "UPDATE orders SET status = ?, raw_json = ?, updated_at = ? WHERE id = ?",
            (status, json_text(raw_event), now, order["id"]),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO credit_ledger (
              id, customer_id, order_id, entry_type, credits_delta, balance_after,
              reason, idempotency_key, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("led"),
                order["customer_id"],
                order["id"],
                "refund" if status == "refunded" else "reversal",
                -int(order["credits_granted"]),
                balance_after,
                f"PayPal payment {status}",
                f"paypal-{status}:{provider_event_id}",
                now,
            ),
        )
        connection.execute("COMMIT")
        current = dict(connection.execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone())
        return {"order": current, "creditBalance": balance_after}
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
