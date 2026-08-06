# AGENTS.md — Competitor Intelligence Tracker

## Project Overview
SOHO Competitor Intelligence Tracker monitors hotel competitor websites and estimates their organic search traffic using public SERP data. All traffic numbers are **estimates** — never actual analytics.

## Architecture
```
GitHub Actions (cron)          SQLite (local file)        FastAPI               Next.js 14
Python Collector ──────────▶   data/tracker.db   ◀──────  REST API  ◀─────────  Dashboard UI
```

## Repository Structure
```
/
├── AGENTS.md                     # This file — agent/AI guidance
├── README.md
├── requirements.txt              # Python deps (collector + API)
├── .env.example
├── .github/
│   └── workflows/
│       └── scrape.yml            # Weekly GitHub Actions cron
├── collector/                    # Python data collection pipeline
│   ├── main.py                   # Orchestrator — runs all 6 modules
│   ├── modules/
│   │   ├── sitemap.py            # Module A: advertools sitemap parser
│   │   ├── tech_stack.py         # Module B: python-Wappalyzer
│   │   ├── serp_checker.py       # Module C: SERP rank checker
│   │   ├── traffic_estimator.py  # Module D: CTR curve × volume
│   │   ├── brand_interest.py     # Module E: pytrends
│   │   └── dom_monitor.py        # Module F: BeautifulSoup + MD5
│   └── db/
│       └── client.py             # SQLite client (all data stored locally in data/tracker.db)
├── api/                          # FastAPI backend
│   ├── main.py
│   ├── routers/
│   │   ├── domains.py
│   │   ├── traffic.py
│   │   ├── tech.py
│   │   ├── sitemap.py
│   │   ├── changes.py
│   │   ├── keywords.py
│   │   └── scan.py
│   └── models/
│       └── schemas.py
├── schema/
│   └── schema.sql                # Full DDL — applied automatically by setup_schema.py
├── tests/                        # pytest unit tests
│   ├── test_traffic_estimator.py
│   ├── test_sitemap.py
│   ├── test_dom_monitor.py
│   └── test_serp_checker.py
└── frontend/                     # Next.js 14 dashboard
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx               # Competitor Overview (View 1)
    │   ├── comparison/page.tsx    # Traffic Comparison (View 2)
    │   ├── keywords/page.tsx      # Keyword Breakdown (View 3)
    │   ├── tech/page.tsx          # Tech Stack Diff (View 4)
    │   └── changes/page.tsx       # Change Log (View 5)
    ├── components/
    │   ├── OverviewCard.tsx
    │   ├── TrafficComparison.tsx
    │   ├── KeywordTable.tsx
    │   ├── TechStackDiff.tsx
    │   ├── ChangeLog.tsx
    │   └── EstimatedBadge.tsx     # Reusable "Estimated" label
    └── lib/
        └── api.ts                 # API client
```

## Critical Rules for AI Agents

### 1. Traffic is ALWAYS an estimate
- Every traffic number must be labeled with `~` prefix OR `(est.)` suffix
- Charts must use Y-axis label: `Estimated Monthly Organic Visits`
- Every page must have a footer disclaimer
- Never display a bare traffic number without an "Estimated" indicator

### 2. Rate Limiting is Non-Negotiable
| Module | Delay | Max/Cycle | Backoff |
|---|---|---|---|
| SERP Checker | 2–5s random | 200 keywords | 10s → 30s → 90s → skip |
| pytrends | 10s between groups | 50 groups | Retry once after 30s |
| Wappalyzer | 1s | No limit | Retry once, log 'blocked' |
| DOM Hash | 1s | No limit | Timeout 10s/URL |

### 3. Error Handling Contract
Every module must return a structured error object — never throw unhandled exceptions:
```json
{
  "status": "error",
  "module": "serp_checker",
  "domain": "competitor.com",
  "error_type": "rate_limited | timeout | blocked | unknown",
  "message": "...",
  "timestamp": "ISO8601"
}
```

### 4. CTR Curve (Source of Truth)
```
#1=27.6%  #2=15.8%  #3=11.0%  #4=6.6%  #5=3.7%
#6=2.6%   #7=1.8%   #8=1.3%   #9=1.0%  #10=0.7%
#11–20=0.3%   >20 or not found=0%
```

### 5. Out of Scope (Do NOT implement)
- Paid ads / social / direct / referral traffic estimation
- Real-time data (weekly cadence only)
- Competitor booking data or pricing
- Any snippet/pixel on client or competitor sites

## Environment Variables
```
NEXT_PUBLIC_API_URL=http://localhost:8000   # or your deployed API URL
```

All collected data is stored locally in `data/tracker.db` (SQLite). No external database credentials needed.

## Deployment
| Service | Platform | Tier | Cost |
|---|---|---|---|
| Collector | GitHub Actions | Free (2,000 min/mo) | $0 |
| Database | SQLite file (`data/tracker.db`) | Local | $0 |
| API | Render | Free | $0 |
| Frontend | Vercel | Free | $0 |

## Running Locally
```bash
# Collector
pip install -r requirements.txt
cp .env.example .env
python3.10 setup_schema.py    # creates DB + seeds keywords/domains
python collector/main.py

# API
uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

## Running Tests
```bash
pytest tests/ -v
```
