PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS credit_accounts (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sku_packs (
  sku TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  credits INTEGER NOT NULL,
  price_usd REAL NOT NULL,
  price_eur REAL,
  price_gbp REAL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS credit_actions (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  credits INTEGER NOT NULL,
  output TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  provider_transaction_id TEXT NOT NULL UNIQUE,
  product_id TEXT NOT NULL,
  amount_usd REAL NOT NULL,
  credits_granted INTEGER NOT NULL,
  status TEXT NOT NULL,
  buyer_email TEXT NOT NULL,
  purchased_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS credit_ledger (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  order_id TEXT,
  entry_type TEXT NOT NULL,
  amount INTEGER NOT NULL,
  balance_after INTEGER NOT NULL,
  reason TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (account_id) REFERENCES credit_accounts(id),
  FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS generated_plans (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  ledger_id TEXT NOT NULL,
  plan_type TEXT NOT NULL,
  input_json TEXT NOT NULL,
  output_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (ledger_id) REFERENCES credit_ledger(id)
);

CREATE TABLE IF NOT EXISTS delivery_records (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  action_id TEXT NOT NULL,
  ledger_id TEXT,
  input_json TEXT NOT NULL,
  output_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (action_id) REFERENCES credit_actions(id),
  FOREIGN KEY (ledger_id) REFERENCES credit_ledger(id)
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
  key TEXT PRIMARY KEY,
  scope TEXT NOT NULL,
  response_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_credit_ledger_account_created
  ON credit_ledger(account_id, created_at);

CREATE INDEX IF NOT EXISTS idx_orders_user_created
  ON orders(user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_generated_plans_user_created
  ON generated_plans(user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_delivery_records_user_created
  ON delivery_records(user_id, created_at);
