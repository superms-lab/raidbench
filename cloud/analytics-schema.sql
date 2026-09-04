CREATE TABLE IF NOT EXISTS page_views (
  day TEXT NOT NULL CHECK (length(day) = 10),
  path TEXT NOT NULL,
  referrer_host TEXT NOT NULL DEFAULT 'direct',
  country TEXT NOT NULL DEFAULT 'XX',
  views INTEGER NOT NULL DEFAULT 0 CHECK (views >= 0),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (day, path, referrer_host, country)
);

CREATE INDEX IF NOT EXISTS idx_page_views_day ON page_views(day);
CREATE INDEX IF NOT EXISTS idx_page_views_path ON page_views(path);
CREATE INDEX IF NOT EXISTS idx_page_views_referrer ON page_views(referrer_host);

CREATE TABLE IF NOT EXISTS acquisition_page_views (
  day TEXT NOT NULL CHECK (length(day) = 10),
  path TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'direct',
  medium TEXT NOT NULL DEFAULT 'none',
  campaign TEXT NOT NULL DEFAULT 'none',
  country TEXT NOT NULL DEFAULT 'XX',
  views INTEGER NOT NULL DEFAULT 0 CHECK (views >= 0),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (day, path, source, medium, campaign, country)
);

CREATE INDEX IF NOT EXISTS idx_acquisition_page_views_day ON acquisition_page_views(day);
CREATE INDEX IF NOT EXISTS idx_acquisition_page_views_campaign ON acquisition_page_views(source, campaign);

CREATE TABLE IF NOT EXISTS conversion_events (
  day TEXT NOT NULL CHECK (length(day) = 10),
  event_name TEXT NOT NULL,
  page_path TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'direct',
  medium TEXT NOT NULL DEFAULT 'none',
  campaign TEXT NOT NULL DEFAULT 'none',
  country TEXT NOT NULL DEFAULT 'XX',
  events INTEGER NOT NULL DEFAULT 0 CHECK (events >= 0),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (day, event_name, page_path, source, medium, campaign, country)
);

CREATE INDEX IF NOT EXISTS idx_conversion_events_day ON conversion_events(day);
CREATE INDEX IF NOT EXISTS idx_conversion_events_name ON conversion_events(event_name);
CREATE INDEX IF NOT EXISTS idx_conversion_events_campaign ON conversion_events(source, campaign);
