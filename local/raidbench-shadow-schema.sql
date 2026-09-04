PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS shadow_runs (
  id TEXT PRIMARY KEY,
  suite_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT NOT NULL DEFAULT '',
  summary_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS shadow_benchmark_results (
  benchmark_key TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  game_id TEXT NOT NULL,
  category TEXT NOT NULL,
  expected_disposition TEXT NOT NULL,
  actual_disposition TEXT NOT NULL,
  expected_reason_code TEXT NOT NULL DEFAULT '',
  actual_reason_code TEXT NOT NULL DEFAULT '',
  author_status TEXT NOT NULL DEFAULT 'not_run',
  reviewer_decision TEXT NOT NULL DEFAULT 'not_run',
  peer_reviewer_decision TEXT NOT NULL DEFAULT 'not_run',
  reviewer_agreement INTEGER NOT NULL DEFAULT 0,
  deterministic_status TEXT NOT NULL,
  critical_failure INTEGER NOT NULL DEFAULT 0,
  evidence_fingerprint TEXT NOT NULL DEFAULT '',
  evidence_oldest_at TEXT NOT NULL DEFAULT '',
  answer_fingerprint TEXT NOT NULL DEFAULT '',
  credits_charged INTEGER NOT NULL DEFAULT 0 CHECK (credits_charged = 0),
  attempts INTEGER NOT NULL DEFAULT 1,
  latest_run_id TEXT NOT NULL,
  artifact_dir TEXT NOT NULL DEFAULT '',
  error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (latest_run_id) REFERENCES shadow_runs(id)
);

CREATE TABLE IF NOT EXISTS shadow_benchmark_attempts (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  benchmark_key TEXT NOT NULL,
  case_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  expected_disposition TEXT NOT NULL,
  actual_disposition TEXT NOT NULL,
  deterministic_status TEXT NOT NULL,
  reviewer_decision TEXT NOT NULL DEFAULT 'not_run',
  peer_reviewer_decision TEXT NOT NULL DEFAULT 'not_run',
  reviewer_agreement INTEGER NOT NULL DEFAULT 0,
  credits_charged INTEGER NOT NULL DEFAULT 0 CHECK (credits_charged = 0),
  artifact_dir TEXT NOT NULL DEFAULT '',
  error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES shadow_runs(id),
  FOREIGN KEY (benchmark_key) REFERENCES shadow_benchmark_results(benchmark_key)
);

CREATE TABLE IF NOT EXISTS product_qa_readiness (
  product_id TEXT PRIMARY KEY,
  decision TEXT NOT NULL,
  shadow_cases INTEGER NOT NULL DEFAULT 0,
  supported_cases INTEGER NOT NULL DEFAULT 0,
  supported_qa_passed INTEGER NOT NULL DEFAULT 0,
  no_charge_cases INTEGER NOT NULL DEFAULT 0,
  no_charge_correct INTEGER NOT NULL DEFAULT 0,
  critical_failures INTEGER NOT NULL DEFAULT 0,
  reviewer_case_count INTEGER NOT NULL DEFAULT 0,
  reviewer_agreement_rate REAL,
  idempotency_passed INTEGER NOT NULL DEFAULT 0,
  in_account_delivery_passed INTEGER NOT NULL DEFAULT 0,
  gate_results_json TEXT NOT NULL DEFAULT '[]',
  evaluated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS delivery_gate_results (
  product_id TEXT PRIMARY KEY,
  benchmark_key TEXT NOT NULL,
  answer_fingerprint TEXT NOT NULL,
  delivery_code_fingerprint TEXT NOT NULL,
  idempotency_passed INTEGER NOT NULL DEFAULT 0,
  in_account_delivery_passed INTEGER NOT NULL DEFAULT 0,
  first_balance INTEGER NOT NULL DEFAULT 0,
  balance_after_first INTEGER NOT NULL DEFAULT 0,
  balance_after_replay INTEGER NOT NULL DEFAULT 0,
  question_count INTEGER NOT NULL DEFAULT 0,
  verified_at TEXT NOT NULL,
  details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_shadow_results_product
  ON shadow_benchmark_results(product_id, deterministic_status, updated_at);

CREATE INDEX IF NOT EXISTS idx_shadow_attempts_run
  ON shadow_benchmark_attempts(run_id, created_at);
