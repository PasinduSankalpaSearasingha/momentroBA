# Momentro Senior Business Analyst (Senior BA) Multi-Agent Platform

A scalable, modular multi-agent platform designed to evaluate executive leads, analyze their **favorite marketing side** and **favorite strategic paths**, evaluate their company positioning, conduct competitive intelligence via a **search tool**, and score the company website using an **AEO/GEO Tool API interface**.

---

## Architecture & Specialized Agents

The platform coordinates 7 specialized agents:

1. **`DataCleanerAgent`** (Data Isolation & Privacy):
   - Strictly extracts **ONLY** the 7 mandated profile fields (`id`, `full_name`, `job_title`, `company_name`, `sector_tag`, `country`, `location`) and the raw post `text` array.
   - Completely filters out media URLs, URNs, reaction counts, and metadata noise.

2. **`MarketingAnalystAgent`** (Senior BA Marketing Strategist):
   - Dissects post texts to analyze the executive's **favorite marketing side**: preferred narrative angles, messaging tactics, B2B consultative authority, and target audience focus.

3. **`StrategicPathAgent`** (Senior BA Operations & Growth Analyst):
   - Uncovers the executive's **favorite strategic paths**: operational foundation before AI investment, franchise scaling, continuous transformation (Stanford Seed), and friction reduction.

4. **`CompanyAnalystAgent`** (Corporate & Positioning Specialist):
   - Ingests `company_report_url`.
   - Strictly isolates **`company_name`**, **`description`**, and **`callToActionUrl`** (website URL).
   - Evaluates corporate value proposition, market positioning, and core product offerings.

5. **`CompetitorAnalystAgent`** (Competitive Intelligence with Search Tool):
   - Equipped with `CompetitorSearchTool` to discover, benchmark, and analyze industry rivals.
   - Evaluates competitive overlap, target company differentiation, and market gaps/opportunities.

6. **`WebsiteScorerAgent`** (AEO & GEO Digital Footprint Evaluator):
   - Ingests `callToActionUrl` (e.g. `https://azendtech.com`).
   - Connects to the `AeoGeoTool` to evaluate Answer Engine Optimization (AEO) and Generative Engine Optimization (GEO) readiness scores (0–100).
   - Pre-configured for live API integration via `AEO_GEO_API_URL` / `AEO_GEO_API_KEY`.

7. **`SeniorBASynthesizerAgent`** (Lead Senior BA Dossier Synthesizer):
   - Combines all intelligence layers into a publication-grade Senior BA Executive & Corporate Dossier, complete with strategic engagement recommendations.

---

## Directory Structure

```
momentroBA/
├── .env                              # Stores OPEN_AI_KEY, AEO_GEO_API_URL
├── scraped_profiles (2).json         # Scraped profiles with report URLs
├── main.py                           # CLI execution runner
├── api.py                            # FastAPI endpoints
├── data/
│   ├── sample_lead.json              # Rajive Silva profile fixture
│   ├── sample_posts_report.json      # Rajive Silva 10-post fixture
│   └── sample_company_report.json    # Azend Technologies company fixture
├── core/
│   ├── __init__.py
│   ├── config.py                     # .env loader & settings
│   ├── schemas.py                    # Pydantic models (Lead, Company, Competitors, AEO/GEO)
│   └── llm_client.py                 # Resilient OpenAI client
├── tools/
│   ├── __init__.py
│   ├── competitor_search_tool.py     # Competitor search tool
│   └── aeo_geo_tool.py               # AEO / GEO website scoring tool
├── agents/
│   ├── __init__.py
│   ├── base_agent.py                 # BaseAgent abstract class
│   ├── data_cleaner_agent.py         # Strictly extracts 7 fields + post texts
│   ├── marketing_analyst_agent.py    # Analyzes favorite marketing side
│   ├── strategic_path_agent.py       # Analyzes favorite strategic paths
│   ├── company_analyst_agent.py      # Analyzes company name & description
│   ├── competitor_analyst_agent.py   # Benchmarks competitors with search tool
│   ├── website_scorer_agent.py       # Scores website with AEO/GEO tool
│   └── senior_ba_synthesizer.py      # Synthesizes holistic executive dossier
└── orchestrator/
    ├── __init__.py
    ├── lead_loader.py                # Report URL fetcher & data loader
    └── multi_agent_runner.py         # MultiAgentPipeline orchestrator
```

---

## Quick Start & Usage

### 1. Environment Setup
Ensure your `.env` contains your OpenAI key:
```env
OPEN_AI_KEY = sk-proj-...
# Optional upcoming AEO / GEO Tool API settings:
# AEO_GEO_API_URL = https://your-aeo-geo-api-endpoint.com/score
# AEO_GEO_API_KEY = your_api_key_here
```

### 2. Run with Sample Fixtures
```bash
python main.py --sample
```
Outputs:
- Rich console report
- `senior_ba_dossier.json`: Complete structured JSON output
- `senior_ba_report.md`: Comprehensive Markdown report

### 3. Run with `scraped_profiles (2).json` (Auto-fetching S3 URLs)
```bash
python main.py --scraped
```
*Automatically downloads and parses `posts_report_url` and `company_report_url` from S3.*

### 4. Running the FastAPI Service
```bash
uvicorn api:app --reload --port 8000
```
Key Endpoints:
- `POST /api/analyze/scraped`: Analyzes lead from `scraped_profiles (2).json`.
- `POST /api/analyze/sample`: Analyzes Rajive Silva sample fixtures.
- `POST /api/analyze/lead`: Accepts custom `{ "lead": {...}, "posts": [...], "company_report": {...} }`.
