CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    source_url TEXT,
    article_text TEXT NOT NULL,
    article_domain VARCHAR(50) NOT NULL DEFAULT 'general',
    overall_verdict VARCHAR(50) NOT NULL DEFAULT 'insufficient evidence',
    report_summary TEXT NOT NULL DEFAULT '',
    elapsed_ms INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE articles ADD COLUMN IF NOT EXISTS article_domain VARCHAR(50) NOT NULL DEFAULT 'general';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS overall_verdict VARCHAR(50) NOT NULL DEFAULT 'insufficient evidence';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS report_summary TEXT NOT NULL DEFAULT '';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS elapsed_ms INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS claims (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    sentence_index INTEGER NOT NULL,
    claim_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL DEFAULT '',
    claim_type VARCHAR(50) NOT NULL,
    checkability_score NUMERIC(5,1) NOT NULL,
    domain VARCHAR(50) NOT NULL,
    key_terms TEXT[] NOT NULL DEFAULT '{}',
    hedged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE claims ADD COLUMN IF NOT EXISTS normalized_text TEXT NOT NULL DEFAULT '';
ALTER TABLE claims ADD COLUMN IF NOT EXISTS key_terms TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE claims ADD COLUMN IF NOT EXISTS hedged BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS sources (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(120) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    organization VARCHAR(255) NOT NULL,
    domain VARCHAR(50) NOT NULL,
    source_type VARCHAR(50) NOT NULL DEFAULT 'report',
    snippet TEXT NOT NULL,
    tags TEXT[] NOT NULL DEFAULT '{}',
    authority_score NUMERIC(4,2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE sources ADD COLUMN IF NOT EXISTS source_type VARCHAR(50) NOT NULL DEFAULT 'report';

CREATE TABLE IF NOT EXISTS claim_evaluations (
    id SERIAL PRIMARY KEY,
    claim_id INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    verdict VARCHAR(50) NOT NULL,
    credibility_score NUMERIC(5,1) NOT NULL,
    confidence_score NUMERIC(5,1) NOT NULL,
    explanation TEXT NOT NULL,
    reviewer_note TEXT NOT NULL DEFAULT '',
    evidence_count INTEGER NOT NULL DEFAULT 0,
    top_source_slugs TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE claim_evaluations ADD COLUMN IF NOT EXISTS reviewer_note TEXT NOT NULL DEFAULT '';
ALTER TABLE claim_evaluations ADD COLUMN IF NOT EXISTS evidence_count INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS evaluation_evidence (
    id SERIAL PRIMARY KEY,
    evaluation_id INTEGER NOT NULL REFERENCES claim_evaluations(id) ON DELETE CASCADE,
    source_slug VARCHAR(120) NOT NULL,
    evidence_rank INTEGER NOT NULL,
    match_score NUMERIC(6,1) NOT NULL,
    relevance_score NUMERIC(6,1) NOT NULL DEFAULT 0,
    coverage_score NUMERIC(6,1) NOT NULL DEFAULT 0,
    authority_component NUMERIC(6,1) NOT NULL DEFAULT 0,
    signal_summary TEXT NOT NULL,
    keyword_hits TEXT[] NOT NULL DEFAULT '{}',
    tag_hits TEXT[] NOT NULL DEFAULT '{}',
    phrase_hits TEXT[] NOT NULL DEFAULT '{}',
    matched_numbers TEXT[] NOT NULL DEFAULT '{}',
    evidence_snapshot JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE evaluation_evidence ADD COLUMN IF NOT EXISTS relevance_score NUMERIC(6,1) NOT NULL DEFAULT 0;
ALTER TABLE evaluation_evidence ADD COLUMN IF NOT EXISTS coverage_score NUMERIC(6,1) NOT NULL DEFAULT 0;
ALTER TABLE evaluation_evidence ADD COLUMN IF NOT EXISTS authority_component NUMERIC(6,1) NOT NULL DEFAULT 0;
ALTER TABLE evaluation_evidence ADD COLUMN IF NOT EXISTS phrase_hits TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE evaluation_evidence ADD COLUMN IF NOT EXISTS matched_numbers TEXT[] NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_claims_article_id ON claims(article_id);
CREATE INDEX IF NOT EXISTS idx_claim_evaluations_claim_id ON claim_evaluations(claim_id);
CREATE INDEX IF NOT EXISTS idx_evaluation_evidence_evaluation_id ON evaluation_evidence(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_sources_slug ON sources(slug);
CREATE INDEX IF NOT EXISTS idx_articles_domain ON articles(article_domain);
