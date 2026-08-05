# Competitor Intelligence Tracker

> Part of the SOHO platform — Zero-cost competitor monitoring for hotel marketing teams.

## What It Does

Tracks competitor hotel websites and estimates their organic search performance — **without requiring any access to their analytics** and **without installing anything on their site**.

The system answers:
1. **Tech Stack** — What CMS, booking engine, CDN, analytics are they running?
2. **Content Activity** — How many pages? How often are they publishing?
3. **Organic Traffic Estimate** — How much estimated organic search traffic are they getting?

> **Important:** All traffic figures are **estimates** derived from SERP rankings + keyword search volumes. They are **not** actual analytics. Accuracy range: ±30–50%.

## Architecture

```
GitHub Actions (weekly cron)
        │
        ▼
Python Collector (6 modules)
        │
        ▼
Supabase PostgreSQL ──▶ FastAPI (Render) ──▶ Next.js Dashboard (Vercel)
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Supabase account (free)
- Google Ads account (free, for keyword volume CSV export)

### Setup

1. **Database** — Run `schema/schema.sql` in your Supabase SQL editor
2. **Environment** — Copy `.env.example` to `.env` and fill in credentials
3. **Collector**
   ```bash
   pip install -r requirements.txt
   python collector/main.py
   ```
4. **API**
   ```bash
   uvicorn api.main:app --reload
   ```
5. **Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Tests
```bash
pytest tests/ -v
```

## Cost
**$0/month** using free tiers of GitHub Actions, Supabase, Render, and Vercel.

## Disclaimer
Traffic data is estimated from search engine rankings and public keyword volume data. It does not represent actual analytics.
