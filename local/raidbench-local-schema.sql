PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS content_sources (
  id TEXT PRIMARY KEY,
  game TEXT NOT NULL,
  source_type TEXT NOT NULL,
  url TEXT NOT NULL,
  cadence TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS game_catalog (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  short_name TEXT NOT NULL,
  genre TEXT NOT NULL,
  status TEXT NOT NULL,
  indexable INTEGER NOT NULL DEFAULT 0,
  paid_answers TEXT NOT NULL DEFAULT 'planned',
  registry_version TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS content_source_profiles (
  source_id TEXT PRIMARY KEY,
  game_id TEXT NOT NULL,
  source_role TEXT NOT NULL,
  authority TEXT NOT NULL,
  fetch_mode TEXT NOT NULL,
  freshness_hours INTEGER NOT NULL,
  generation_eligible INTEGER NOT NULL DEFAULT 0,
  policy_json TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL,
  FOREIGN KEY (source_id) REFERENCES content_sources(id),
  FOREIGN KEY (game_id) REFERENCES game_catalog(id)
);

CREATE TABLE IF NOT EXISTS agent_runs (
  id TEXT PRIMARY KEY,
  run_type TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  summary_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS source_snapshots (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  ok INTEGER NOT NULL,
  status_code INTEGER NOT NULL DEFAULT 0,
  title TEXT NOT NULL DEFAULT '',
  body_sample TEXT NOT NULL DEFAULT '',
  error TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (run_id) REFERENCES agent_runs(id),
  FOREIGN KEY (source_id) REFERENCES content_sources(id)
);

CREATE TABLE IF NOT EXISTS content_signals (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  game TEXT NOT NULL,
  topic TEXT NOT NULL,
  signal_title TEXT NOT NULL,
  signal_url TEXT NOT NULL DEFAULT '',
  pain_score INTEGER NOT NULL DEFAULT 0,
  commercial_score INTEGER NOT NULL DEFAULT 0,
  patch_sensitive INTEGER NOT NULL DEFAULT 0,
  evidence_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES agent_runs(id),
  FOREIGN KEY (source_id) REFERENCES content_sources(id)
);

CREATE TABLE IF NOT EXISTS demand_backlog (
  id TEXT PRIMARY KEY,
  game_id TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  source_id TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_title TEXT NOT NULL,
  normalized_question TEXT NOT NULL,
  topic TEXT NOT NULL,
  intent_zh TEXT NOT NULL DEFAULT '',
  pain_score INTEGER NOT NULL DEFAULT 0,
  commercial_score INTEGER NOT NULL DEFAULT 0,
  freshness_score INTEGER NOT NULL DEFAULT 0,
  patch_score INTEGER NOT NULL DEFAULT 0,
  opportunity_score INTEGER NOT NULL DEFAULT 0,
  patch_sensitive INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'observed',
  occurrence_count INTEGER NOT NULL DEFAULT 1,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE (game_id, fingerprint),
  FOREIGN KEY (game_id) REFERENCES game_catalog(id),
  FOREIGN KEY (source_id) REFERENCES content_sources(id)
);

CREATE TABLE IF NOT EXISTS demand_observations (
  id TEXT PRIMARY KEY,
  demand_id TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_title TEXT NOT NULL,
  published_at TEXT NOT NULL DEFAULT '',
  observed_at TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE (demand_id, source_url),
  FOREIGN KEY (demand_id) REFERENCES demand_backlog(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS guide_pages (
  slug TEXT PRIMARY KEY,
  game TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  last_checked_at TEXT NOT NULL,
  patch_sensitive INTEGER NOT NULL DEFAULT 1,
  source_notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS publish_queue (
  id TEXT PRIMARY KEY,
  guide_slug TEXT NOT NULL,
  action TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 3,
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'needs_review',
  created_at TEXT NOT NULL,
  FOREIGN KEY (guide_slug) REFERENCES guide_pages(slug)
);

CREATE TABLE IF NOT EXISTS content_automation_items (
  id TEXT PRIMARY KEY,
  signal_id TEXT NOT NULL UNIQUE,
  source_type TEXT NOT NULL,
  status TEXT NOT NULL,
  case_id TEXT NOT NULL DEFAULT '',
  case_path TEXT NOT NULL DEFAULT '',
  run_dir TEXT NOT NULL DEFAULT '',
  output_slug TEXT NOT NULL DEFAULT '',
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  published_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS community_post_drafts (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL UNIQUE,
  game TEXT NOT NULL,
  guide_slug TEXT NOT NULL,
  artifact_path TEXT NOT NULL,
  status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  notified_at TEXT NOT NULL DEFAULT ''
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
  delivery_class TEXT NOT NULL DEFAULT 'custom_verified',
  status TEXT NOT NULL DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS customers (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL DEFAULT '',
  region TEXT NOT NULL DEFAULT 'US',
  currency TEXT NOT NULL DEFAULT 'USD',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS password_reset_requests (
  identifier_hash TEXT PRIMARY KEY,
  window_started_at TEXT NOT NULL,
  request_count INTEGER NOT NULL DEFAULT 1,
  last_requested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  provider_transaction_id TEXT NOT NULL UNIQUE,
  provider_capture_id TEXT NOT NULL DEFAULT '',
  sku TEXT NOT NULL,
  amount REAL NOT NULL,
  currency TEXT NOT NULL,
  credits_granted INTEGER NOT NULL,
  terms_version TEXT NOT NULL DEFAULT '',
  refund_policy_version TEXT NOT NULL DEFAULT '',
  consented_at TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT '',
  raw_json TEXT NOT NULL DEFAULT '{}',
  FOREIGN KEY (customer_id) REFERENCES customers(id),
  FOREIGN KEY (sku) REFERENCES sku_packs(sku)
);

CREATE TABLE IF NOT EXISTS credit_ledger (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,
  order_id TEXT,
  entry_type TEXT NOT NULL,
  credits_delta INTEGER NOT NULL,
  balance_after INTEGER NOT NULL,
  reason TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customers(id),
  FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS delivery_records (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,
  action_id TEXT NOT NULL,
  ledger_id TEXT,
  input_json TEXT NOT NULL,
  output_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customers(id),
  FOREIGN KEY (action_id) REFERENCES credit_actions(id),
  FOREIGN KEY (ledger_id) REFERENCES credit_ledger(id)
);

CREATE TABLE IF NOT EXISTS questions (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,
  game TEXT NOT NULL,
  question_type TEXT NOT NULL,
  question_text TEXT NOT NULL DEFAULT '',
  input_json TEXT NOT NULL,
  answer_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL,
  qa_status TEXT NOT NULL DEFAULT 'pending',
  credits_cost INTEGER NOT NULL DEFAULT 0,
  credits_charged INTEGER NOT NULL DEFAULT 0,
  idempotency_key TEXT NOT NULL UNIQUE,
  blocked_reason TEXT NOT NULL DEFAULT '',
  submitted_at TEXT NOT NULL,
  completed_at TEXT,
  FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS question_events (
  id TEXT PRIMARY KEY,
  question_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  label TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS answer_evidence (
  id TEXT PRIMARY KEY,
  question_id TEXT NOT NULL,
  evidence_type TEXT NOT NULL,
  source_title TEXT NOT NULL,
  source_url TEXT NOT NULL,
  claim_supported TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS payment_events (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  provider_event_id TEXT NOT NULL UNIQUE,
  event_type TEXT NOT NULL,
  order_id TEXT,
  payload_json TEXT NOT NULL,
  signature_status TEXT NOT NULL DEFAULT 'unverified',
  processing_status TEXT NOT NULL DEFAULT 'received',
  error TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS owner_notifications (
  notification_key TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  notification_type TEXT NOT NULL,
  status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  sent_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  id TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_signals_game_score
  ON content_signals(game, pain_score DESC, commercial_score DESC);

CREATE INDEX IF NOT EXISTS idx_source_profiles_game_role
  ON content_source_profiles(game_id, source_role, fetch_mode);

CREATE INDEX IF NOT EXISTS idx_demand_backlog_game_score
  ON demand_backlog(game_id, status, opportunity_score DESC, last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_demand_backlog_status_score
  ON demand_backlog(status, opportunity_score DESC, last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_demand_observations_seen
  ON demand_observations(demand_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_snapshots_source_fetched
  ON source_snapshots(source_id, fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_queue_status_priority
  ON publish_queue(status, priority, created_at);

CREATE INDEX IF NOT EXISTS idx_content_automation_status
  ON content_automation_items(status, updated_at);

CREATE INDEX IF NOT EXISTS idx_owner_notifications_status
  ON owner_notifications(status, updated_at);

CREATE INDEX IF NOT EXISTS idx_community_post_drafts_status
  ON community_post_drafts(status, updated_at);

CREATE INDEX IF NOT EXISTS idx_ledger_customer_created
  ON credit_ledger(customer_id, created_at);

CREATE INDEX IF NOT EXISTS idx_sessions_token
  ON sessions(token_hash, expires_at);

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_customer
  ON password_reset_tokens(customer_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_lookup
  ON password_reset_tokens(token_hash, expires_at, used_at);

CREATE INDEX IF NOT EXISTS idx_questions_customer_submitted
  ON questions(customer_id, submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_questions_status_submitted
  ON questions(status, submitted_at);

CREATE INDEX IF NOT EXISTS idx_question_events_question_created
  ON question_events(question_id, created_at);
