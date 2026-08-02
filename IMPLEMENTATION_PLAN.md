# ProvenPick — Multi-Agent AI Affiliate Review Platform
## Detailed Implementation Plan

---

## What We're Building

An autonomous AI system that:
1. **Monitors** subscribed YouTube channels daily for new product review videos
2. **Classifies** each video — genuine review vs vlog/ad/off-topic
3. **Extracts** transcripts (multi-language: English, Hindi, Telugu, Tamil)
4. **Builds** a knowledge graph from transcript content (LightRAG + Neo4j)
5. **Generates** a full buying guide article with product comparisons
6. **Self-critiques** and rewrites if quality is poor
7. **Enriches** with product images + Amazon affiliate links
8. **Routes** to a staging dashboard where a human editor approves/rejects
9. **Auto-republishes** if rejected — reads editor comments, rewrites, resubmits
10. **Publishes** to a live React frontend with category-based product feeds

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| AI Pipeline | Python 3.12, LangGraph | Multi-agent supervisor pattern, first-class async |
| LLM | Google Gemini 1.5 Flash (via LangChain) | Fast, cheap, multimodal |
| Knowledge Graph | LightRAG + Neo4j | Preserves product relationships (A beats B in battery) |
| Staging API | FastAPI + SQLAlchemy + PostgreSQL | Standard, easy to explain |
| Production API | FastAPI + SQLAlchemy + PostgreSQL | Separate DB — staging never touches prod |
| Task Queue | Redis (lists as queue) | Lightweight, perfect for job queuing |
| Scheduler | APScheduler | Daily channel scan cron |
| Transcript | yt-dlp | Best YouTube transcript extractor |
| Language Detection | langdetect | Detect Hindi/Tamil/Telugu |
| Translation | Gemini (prompt) | Translate to English if needed |
| Frontend | React + Vite + React Router | Standard, you know it |
| Styling | Vanilla CSS (custom design system) | Full control |
| Containerization | Docker + docker-compose | Spin up all services with one command |

---

## System Architecture — Multi-Agent Orchestration

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                           │
│  LangGraph Supervisor — routes jobs, retries failures,          │
│  tracks state across all agents, decides next agent to invoke   │
└────┬──────────┬──────────┬──────────┬──────────┬───────────────┘
     │          │          │          │          │
     ▼          ▼          ▼          ▼          ▼
┌─────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌───────────┐
│  SCOUT  │ │ SCRIBE │ │ CRITIC │ │ENRICHER│ │ PUBLISHER │
│  AGENT  │ │ AGENT  │ │ AGENT  │ │ AGENT  │ │   AGENT   │
└─────────┘ └────────┘ └────────┘ └────────┘ └───────────┘
```

### Agent Responsibilities

#### 🔭 Scout Agent
- Polls YouTube Data API v3 for new videos from subscribed channels
- Compares against `processed_videos` table to find net-new videos
- Calls VideoClassifier LLM: "Is this a genuine product review?"
- Pushes approved video URLs to Redis queue
- Tools: YouTube API, Redis, PostgreSQL

#### ✍️ Scribe Agent
- Pops a video URL from Redis queue
- Fetches transcript via yt-dlp (English/Hindi/Telugu/Tamil)
- Detects language, translates to English if needed
- Builds LightRAG knowledge graph (entities + relationships)
- Queries graph for product context
- Identifies products via LLM (name, brand, price, pros, cons)
- Assigns smart labels (Best Overall, Best Value, etc.)
- Generates full article HTML + mind map
- Tools: yt-dlp, LightRAG, Neo4j, Gemini LLM

#### 🧐 Critic Agent
- Reads Scribe's output
- Runs automated quality checks (word count, no YouTube mentions, product count)
- Runs LLM self-critique ("Is this article authoritative and helpful?")
- If quality score < threshold → sends back to Scribe with comments
- Max 3 retry loops, then forces accept
- Tools: Gemini LLM, quality checker

#### 💎 Enrichment Agent
- Fetches product images (Google Images scraper / SerpAPI)
- Injects Amazon affiliate links for each product
- Attaches tracked commission URLs to each product section
- Tools: SerpAPI / Google Images, Amazon Associates API

#### 📤 Publisher Agent
- Submits completed article to staging DB via Redis queue
- Sends Discord notification to reviewer
- Polls staging API — waits for human approval or rejection
- If **approved**: pushes article to production DB, goes live on frontend
- If **rejected**: reads editor comments, sends back to Scribe with feedback
- Loop continues until approved
- Tools: Redis, FastAPI staging API, FastAPI production API, Discord webhook

---

## Database Schemas

### Database 1 — Workflow DB (`provenpick_workflow`)
> Tracks pipeline state. Owned by the Python pipeline service.

```sql
-- Subscribed YouTube channels
CREATE TABLE channels (
    id              SERIAL PRIMARY KEY,
    channel_id      VARCHAR(64) UNIQUE NOT NULL,  -- YouTube channel ID e.g. "UCxxxxxx"
    channel_name    VARCHAR(255),
    channel_url     VARCHAR(512),
    is_active       BOOLEAN DEFAULT TRUE,
    last_scanned_at TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Videos already seen — prevent re-processing
CREATE TABLE processed_videos (
    id           SERIAL PRIMARY KEY,
    video_id     VARCHAR(64) UNIQUE NOT NULL,  -- YouTube video ID
    channel_id   VARCHAR(64) NOT NULL REFERENCES channels(channel_id),
    video_title  VARCHAR(512),
    video_url    VARCHAR(512),
    is_review    BOOLEAN NOT NULL,             -- True = product review, False = skipped
    skip_reason  TEXT,                         -- Why it was skipped (vlog, ad, etc.)
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Each pipeline run — one per video that passed classification
CREATE TABLE pipeline_jobs (
    id            SERIAL PRIMARY KEY,
    job_uuid      UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    video_id      VARCHAR(64) REFERENCES processed_videos(video_id),
    status        VARCHAR(64) DEFAULT 'queued',
    -- Status flow: queued → transcribing → graphing → writing →
    --              critiquing → enriching → submitted → approved/rejected → published
    current_agent VARCHAR(64),                -- Which agent is currently working
    attempt_count INTEGER DEFAULT 0,          -- How many rewrite attempts
    error_message TEXT,
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Transcript cache — avoid re-fetching the same video twice
CREATE TABLE transcript_cache (
    id                SERIAL PRIMARY KEY,
    video_id          VARCHAR(64) UNIQUE NOT NULL,
    original_language VARCHAR(16),            -- Detected language code (en, hi, te, ta)
    raw_transcript    TEXT NOT NULL,
    translated_text   TEXT,                   -- English translation if non-English
    cached_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

### Database 2 — Staging DB (`provenpick_staging`)
> Human review dashboard. Editor approves/rejects here.

```sql
-- Articles waiting for human review
CREATE TABLE staging_articles (
    id                SERIAL PRIMARY KEY,
    job_uuid          UUID NOT NULL,           -- Links back to pipeline_jobs
    article_uuid      UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    title             VARCHAR(512) NOT NULL,
    introduction      TEXT,
    full_article_html TEXT NOT NULL,
    mindmap_mermaid   TEXT,
    mindmap_image     BYTEA,                   -- Rendered PNG as binary
    bullet_points     JSONB DEFAULT '[]',      -- ["key point 1", "key point 2"]
    l3_category_id    INTEGER NOT NULL,        -- AI-suggested category (editable)
    category_name     VARCHAR(255),
    status            VARCHAR(32) DEFAULT 'pending',
    -- Status: pending → approved / rejected → published
    rejection_count   INTEGER DEFAULT 0,
    editor_comments   TEXT,                    -- Written when rejecting
    submitted_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed_at       TIMESTAMP WITH TIME ZONE,
    reviewed_by       VARCHAR(255)
);

-- Products within each staging article
CREATE TABLE staging_products (
    id                    SERIAL PRIMARY KEY,
    staging_article_id    INTEGER NOT NULL REFERENCES staging_articles(id) ON DELETE CASCADE,
    name                  VARCHAR(512) NOT NULL,
    brand                 VARCHAR(255),
    price_inr             NUMERIC(10, 2),
    pick_label            VARCHAR(128),        -- "Best Overall", "Best Value", etc.
    pick_type             VARCHAR(64),         -- top_pick, value_pick, budget_pick, specialist
    target_persona        TEXT,
    pros                  JSONB DEFAULT '[]',  -- [{"text": "Great battery", "priority": 0}]
    cons                  JSONB DEFAULT '[]',
    specs                 JSONB DEFAULT '{}',  -- {"RAM": "8GB", "Storage": "128GB"}
    best_for              TEXT,
    skip_if               TEXT,
    affiliate_links       JSONB DEFAULT '{}',  -- {"amazon": "https://..."}
    image_urls            JSONB DEFAULT '[]',
    display_order         INTEGER DEFAULT 0,
    created_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Source videos used to generate the article
CREATE TABLE staging_sources (
    id                 SERIAL PRIMARY KEY,
    staging_article_id INTEGER NOT NULL REFERENCES staging_articles(id) ON DELETE CASCADE,
    video_url          VARCHAR(512),
    video_title        VARCHAR(512),
    channel_name       VARCHAR(255)
);
```

---

### Database 3 — Production DB (`provenpick_production`)
> Live site data. Frontend reads from here. Only touched when article is approved.

```sql
-- 3-level category hierarchy
CREATE TABLE l1_categories (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(255) UNIQUE NOT NULL,   -- "Electronics", "Home Appliances"
    slug       VARCHAR(255) UNIQUE NOT NULL,
    icon       VARCHAR(64),
    is_active  BOOLEAN DEFAULT TRUE
);

CREATE TABLE l2_categories (
    id            SERIAL PRIMARY KEY,
    l1_id         INTEGER NOT NULL REFERENCES l1_categories(id),
    name          VARCHAR(255) NOT NULL,       -- "Smartphones", "Kitchen"
    slug          VARCHAR(255) UNIQUE NOT NULL,
    is_active     BOOLEAN DEFAULT TRUE
);

CREATE TABLE l3_categories (
    id            SERIAL PRIMARY KEY,
    l2_id         INTEGER NOT NULL REFERENCES l2_categories(id),
    name          VARCHAR(255) NOT NULL,       -- "Wireless Earbuds Under ₹2000"
    slug          VARCHAR(255) UNIQUE NOT NULL,
    description   TEXT,
    is_active     BOOLEAN DEFAULT TRUE
);

-- Published buying guide articles
CREATE TABLE articles (
    id                SERIAL PRIMARY KEY,
    article_uuid      UUID UNIQUE NOT NULL,    -- Matches staging_articles.article_uuid
    l3_category_id    INTEGER NOT NULL REFERENCES l3_categories(id),
    title             VARCHAR(512) NOT NULL,
    slug              VARCHAR(512) UNIQUE NOT NULL,
    introduction      TEXT,
    full_article_html TEXT NOT NULL,
    mindmap_image_url VARCHAR(1024),           -- S3/CDN URL for the mind map image
    bullet_points     JSONB DEFAULT '[]',
    seo_title         VARCHAR(70),
    seo_description   VARCHAR(160),
    is_published      BOOLEAN DEFAULT TRUE,
    view_count        INTEGER DEFAULT 0,
    published_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Products within each published article
CREATE TABLE products (
    id              SERIAL PRIMARY KEY,
    article_id      INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    name            VARCHAR(512) NOT NULL,
    brand           VARCHAR(255),
    price_inr       NUMERIC(10, 2),
    pick_label      VARCHAR(128),
    pick_type       VARCHAR(64),
    target_persona  TEXT,
    pros            JSONB DEFAULT '[]',
    cons            JSONB DEFAULT '[]',
    specs           JSONB DEFAULT '{}',
    best_for        TEXT,
    skip_if         TEXT,
    image_url       VARCHAR(1024),
    display_order   INTEGER DEFAULT 0
);

-- Tracked affiliate links — one per product per platform
CREATE TABLE affiliate_links (
    id              SERIAL PRIMARY KEY,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    platform        VARCHAR(64) NOT NULL,      -- "amazon", "flipkart"
    raw_url         VARCHAR(2048) NOT NULL,
    tracked_url     VARCHAR(2048) NOT NULL,    -- URL with affiliate tag injected
    affiliate_tag   VARCHAR(128),
    click_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Source YouTube videos credited per article
CREATE TABLE article_sources (
    id          SERIAL PRIMARY KEY,
    article_id  INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    video_url   VARCHAR(512),
    video_title VARCHAR(512),
    channel     VARCHAR(255)
);
```

---

## Folder Structure

```
ProvenPick/
├── docker-compose.yml           ← Spin up all services with one command
├── .env                         ← All secrets (API keys, DB URLs)
├── README.md
│
├── pipeline/                    ← Multi-Agent Python Pipeline
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── main.py                  ← Entry point + APScheduler
│   └── src/
│       ├── orchestrator/
│       │   ├── supervisor.py    ← LangGraph supervisor graph
│       │   └── state.py         ← Shared pipeline state (TypedDict)
│       │
│       ├── agents/
│       │   ├── scout_agent.py   ← Channel monitor + video classifier
│       │   ├── scribe_agent.py  ← Transcript → graph → article
│       │   ├── critic_agent.py  ← Self-critique + rewrite loop
│       │   ├── enricher_agent.py← Images + affiliate links
│       │   └── publisher_agent.py ← Staging submit + rejection handler
│       │
│       ├── services/
│       │   ├── youtube.py       ← yt-dlp transcript fetching
│       │   ├── channel_monitor.py ← YouTube Data API v3 scanning
│       │   ├── video_classifier.py ← LLM: review vs vlog/ad
│       │   ├── lightrag_service.py ← LightRAG + Neo4j
│       │   ├── affiliate.py     ← Amazon affiliate link injection
│       │   ├── product_images.py ← Image fetching
│       │   ├── redis_client.py  ← Queue operations
│       │   └── discord.py       ← Notifications webhook
│       │
│       └── db/
│           ├── models.py        ← SQLAlchemy models (workflow DB)
│           └── session.py       ← DB connection + session factory
│
├── staging-api/                 ← FastAPI — Human Review Backend
│   ├── main.py
│   └── src/
│       ├── routes/
│       │   ├── articles.py      ← GET/PATCH staging articles
│       │   └── auth.py          ← Reviewer JWT login
│       └── db/
│           ├── models.py        ← SQLAlchemy models (staging DB)
│           └── session.py
│
├── production-api/              ← FastAPI — Public Site Backend
│   ├── main.py
│   └── src/
│       ├── routes/
│       │   ├── articles.py      ← Public article endpoints
│       │   ├── categories.py    ← Category tree
│       │   └── search.py        ← Full-text search
│       └── db/
│           ├── models.py        ← SQLAlchemy models (production DB)
│           └── session.py
│
We also have a separate web directory on the Desktop:

```
ProvenPick-web/
├── public-site/                 ← React + Vite (Public Site)
│   └── src/
│       ├── components/
│       │   ├── Navbar.jsx
│       │   ├── CategorySidebar.jsx
│       │   ├── ArticleCard.jsx
│       │   ├── ProductCard.jsx
│       │   └── AffiliateButton.jsx
│       └── pages/
│           ├── Home.jsx         ← Category feed
│           ├── ArticlePage.jsx  ← Full buying guide
│           └── CategoryPage.jsx ← All articles in a category
│
└── editor-dashboard/            ← React + Vite (Editor Dashboard)
    └── src/
        └── pages/
            ├── ReviewQueue.jsx  ← List pending articles
            └── ArticleReview.jsx← Approve / reject with comments
```

---

## API Contracts

### Staging API

```
POST  /api/queue/submit              ← Pipeline submits article (consumed from Redis)
GET   /api/articles                  ← List pending articles for editor
GET   /api/articles/:uuid            ← Full article detail
PATCH /api/articles/:uuid/approve    ← Editor approves → triggers publish to production
PATCH /api/articles/:uuid/reject     ← Editor rejects with comments
GET   /api/articles/by-uuid/:uuid    ← Pipeline polls for status
```

### Production API

```
GET  /api/categories                 ← Full L1 → L2 → L3 tree
GET  /api/articles                   ← Paginated published articles
GET  /api/articles/:slug             ← Full article by slug
GET  /api/categories/:slug/articles  ← Articles in a category
GET  /api/search?q=                  ← Full-text search
POST /api/affiliate/click/:id        ← Track affiliate link click
```

---

## Pipeline Flow (End to End)

```
[APScheduler — daily 6 AM IST]
         │
         ▼
[Scout Agent]
  → YouTube API: fetch latest 10 videos per subscribed channel
  → DB check: filter already-processed video IDs
  → For each new video:
      → VideoClassifier LLM: "genuine product review?"
      → If NO  → mark processed, log skip reason, continue
      → If YES → push {video_url, video_id, channel} to Redis queue
         │
         ▼
[Orchestrator — consumes Redis queue]
         │
         ▼
[Scribe Agent]
  → yt-dlp: fetch transcript
  → langdetect: detect language (en/hi/te/ta/ml)
  → If non-English → Gemini: translate to English
  → LightRAG: build entity-relationship graph in Neo4j
  → LightRAG global query: "What products + key considerations?"
  → Gemini: identify products (name, brand, price, pros, cons)
  → Gemini: assign smart labels (Best Overall, Best Value...)
  → Gemini: generate SEO title (≤60 chars)
  → Gemini: generate mind map (Mermaid) → render PNG
  → Gemini: write full buying guide article HTML
         │
         ▼
[Critic Agent]
  → Quality check: word count, no YouTube mentions, min 2 products
  → Gemini: "Is this authoritative? Any issues?"
  → If score < 0.7 AND attempts < 3 → back to Scribe with comments
  → Else → proceed
         │
         ▼
[Enrichment Agent]
  → Fetch product images (1 per product)
  → Generate Amazon affiliate tracked URLs per product
         │
         ▼
[Auto-Categorize]
  → Load L3 categories from production DB
  → Gemini: pick best matching category for this article
         │
         ▼
[Publisher Agent — Submit]
  → Write to staging_articles + staging_products tables
  → Discord notification to reviewer
  → Poll /api/articles/by-uuid/:uuid every 30s
         │
         ├── [APPROVED]
         │       → Copy to production articles + products tables
         │       → Generate slug, SEO fields
         │       → is_published = TRUE → live on frontend
         │
         └── [REJECTED with comments]
                 → Read editor_comments
                 → Send back to Scribe: "Rewrite fixing: [comments]"
                 → rejection_count++
                 → Loop: Critic → Enricher → Publisher
                 → Max 5 rejections → escalate to Discord
```

---

## 10-Day Build Timeline

| Day | What you build |
|---|---|
| **Day 1** | docker-compose, all 3 PostgreSQL DBs, SQLAlchemy models, Alembic migrations |
| **Day 2** | LangGraph supervisor skeleton + OrchestratorState + Scout Agent (channel monitor + classifier) |
| **Day 3** | Scribe Agent — yt-dlp transcript fetch, langdetect, translation, LightRAG + Neo4j |
| **Day 4** | Scribe Agent — product identification, smart labeling, title generation, article HTML + mindmap |
| **Day 5** | Critic Agent — quality checker + LLM self-critique + retry loop back to Scribe |
| **Day 6** | Enrichment Agent (images + affiliate) + Auto-categorize node |
| **Day 7** | Publisher Agent + Staging FastAPI backend (submit/approve/reject endpoints) |
| **Day 8** | Staging React dashboard (review queue + article review with approve/reject UI) + Production API |
| **Day 9** | Public React frontend (home feed, article page, category sidebar, affiliate buy buttons) |
| **Day 10** | End-to-end test with real YouTube channel, README, architecture diagram, mock interview prep |

---

## Open Questions (Answer Before Day 1)

1. **LLM** — Google Gemini (free tier) or OpenAI GPT-4o-mini?
2. **Amazon Associates** — do you have an account? (We can mock if not)
3. **YouTube Data API Key** — do you have one?
4. **Neo4j** — local Docker or Aura free cloud tier?
5. **Product Images** — SerpAPI trial or build a scraper?
