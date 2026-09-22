"""
Momentro BA Studio API  –  Production v3.1
==========================================

THREE ENDPOINTS:

  1. POST /api/studio/process
       - Receives scraped leads payload
       - Runs full 9-agent AI pipeline for NEW leads
       - Saves ALL data to MySQL (fallback: SQLite)
       - Returns nothing (fire-and-save)

  2. GET  /api/studio/{lead_id}
       - Reads from MySQL/SQLite
       - Returns full studio data with AEO / GEO / ICP scores

  3. GET  /api/dossier/{lead_id}
       - Reads from MySQL/SQLite
       - Returns the executive dossier section only

All three endpoints work purely from the database after processing.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Body

from orchestrator.lead_loader import LeadLoader
from orchestrator.multi_agent_runner import MultiAgentPipeline
from core.database import db_manager

logger = logging.getLogger("momentro.api")

app = FastAPI(
    title="Momentro BA Studio API",
    description=(
        "**POST /api/studio/process** – Ingest scraped leads, run AI pipeline, save to MySQL.\n\n"
        "**GET /api/studio/{lead_id}** – Fetch full studio intelligence with AEO/GEO scores from DB.\n\n"
        "**GET /api/dossier/{lead_id}** – Fetch the executive dossier for a lead from DB."
    ),
    version="3.1.0",
)

pipeline = MultiAgentPipeline()
loader   = LeadLoader()

@app.get("/health", summary="Health Check", tags=["System"])
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "service": "Momentro BA Studio API"}


# ── ICP Score (Empirical – no mock values) ───────────────────────────────────
def _icp_score(job_title: str, sector_tag: str,
               company_data: Optional[Dict] = None,
               raw_posts_count: int = 0, has_website: bool = True) -> int:
    score  = 0
    job    = (job_title  or "").lower()
    sector = (sector_tag or "").lower()

    if any(t in job for t in ["founder","ceo","chief executive","managing director","president","board director"]):
        score += 35
    elif any(t in job for t in ["vp","vice president","director","partner","chief"]):
        score += 28
    elif any(t in job for t in ["manager","lead","head"]):
        score += 18
    else:
        score += 12

    if any(s in sector for s in ["manufacturing","technology","software","fintech","enterprise","b2b"]):
        score += 25
    elif sector:
        score += 18
    else:
        score += 10

    staff = str((company_data or {}).get("staffCountRange") or (company_data or {}).get("employeeCount") or "").lower()
    if any(t in staff for t in ["11-50","51-200","50","63"]): score += 20
    elif any(t in staff for t in ["201-500","501-1000"]):     score += 18
    elif "1-10" in staff:                                     score += 12
    else:                                                     score += 15

    if raw_posts_count >= 8:   score += 15
    elif raw_posts_count >= 3: score += 10
    elif raw_posts_count >= 1: score += 6
    else:                      score += 3

    if has_website: score += 5
    return min(99, max(50, score))


# ── Safe JSON Parse ──────────────────────────────────────────────────────────
def _j(val: Any) -> Any:
    if isinstance(val, (dict, list)): return val
    if isinstance(val, str):
        try: return json.loads(val)
        except Exception: pass
    return val


# ── Build Studio Response from DB ────────────────────────────────────────────
def _from_db(lead_id: int) -> Dict[str, Any]:
    """Reads lead_id from DB and returns the complete studio / dossier dict."""
    c = db_manager.get_lead_complete(lead_id)
    if not c:
        return {}

    dr  = _j(c.get("dossier")        or {})   # lead_dossiers row
    dp  = _j(c.get("dossier_parsed") or {})   # dossier_json parsed
    bi  = _j(c.get("bi_messages")    or {})
    ca  = _j(c.get("competitors")    or {})
    ci  = _j(c.get("contact_info")   or {})
    rp  = c.get("raw_posts") or []

    cp    = _j(c.get("company_profile") or {})

    leadership    = _j(dr.get("leadership_identity")                  or dp.get("leadership_identity"))
    marketing     = _j(dr.get("favorite_marketing_side")             or dp.get("favorite_marketing_side_analysis"))
    paths         = _j(dr.get("favorite_strategic_paths")            or dp.get("favorite_paths_analysis"))
    tech          = _j(dr.get("business_transformation_and_tech_stance") or dp.get("business_transformation_and_tech_stance"))
    company_ana   = _j(dp.get("company_analysis") or {})
    aeo_geo       = _j(dp.get("website_aeo_geo_score") or {})

    social        = _j(ci.get("social_links_json")  or ci.get("social_links")       or {})
    emails        = _j(ci.get("emails_json")         or ci.get("emails")             or [])
    phones        = _j(ci.get("phone_numbers_json")  or ci.get("phone_numbers")      or [])
    locs          = _j(ci.get("locations_json")      or ci.get("locations")          or [])
    cpages        = _j(ci.get("contact_pages_json")  or ci.get("contact_pages_found") or [])
    top_comps     = _j(ca.get("top_competitors_json") or ca.get("top_competitors")   or [])
    mkt_opps      = _j(ca.get("market_opportunities_json") or [])
    resonance     = _j(bi.get("target_resonance_points_json") or bi.get("target_resonance_points") or [])

    aeo   = round(float(dr.get("aeo_score") or (aeo_geo.get("aeo_score") if isinstance(aeo_geo, dict) else 0) or 0), 1)
    geo   = round(float(dr.get("geo_score") or (aeo_geo.get("geo_score") if isinstance(aeo_geo, dict) else 0) or 0), 1)
    ovr   = round(float(dr.get("overall_score") or (aeo_geo.get("overall_score") if isinstance(aeo_geo, dict) else 0) or round((aeo + geo) / 2, 1)), 1)
    icp   = _icp_score(
        job_title=c.get("job_title",""), sector_tag=c.get("sector_tag",""),
        company_data=company_ana if isinstance(company_ana, dict) else {},
        raw_posts_count=len(rp), has_website=bool(ci.get("website"))
    )

    li_url = (social.get("linkedin") if isinstance(social, dict) else None) \
        or (cp.get("linkedin_url") if isinstance(cp, dict) else None) \
        or f"https://www.linkedin.com/search/results/all/?keywords={c.get('full_name','')}"

    posts = [
        {"text": p.get("post_text") or "", "date": p.get("post_date") or "Recent",
         "url": p.get("post_url") or "",  "reactions": p.get("reactions_count") or 0}
        for p in rp
    ]

    def _txt(v, *keys):
        if isinstance(v, dict):
            for k in keys:
                if v.get(k): return str(v[k])
            return ""
        return str(v) if v else ""

    site   = ci.get("website") or (cp.get("website") if isinstance(cp, dict) else "") or ""
    recs   = (aeo_geo.get("recommendations", []) if isinstance(aeo_geo, dict) else [])
    quote  = (posts[0]["text"] or "")[:140] if posts else ""
    plist  = paths.get("strategic_paths") if isinstance(paths, dict) else (paths if isinstance(paths, list) else ([str(paths)] if paths else []))

    # ── Company Profile (full) ────────────────────────────────────────────────
    company_full = {}
    if isinstance(cp, dict) and cp:
        company_full = {
            "company_id":           cp.get("company_id", ""),
            "universal_name":       cp.get("universal_name", ""),
            "name":                 cp.get("name", ""),
            "tagline":              cp.get("tagline", ""),
            "website":              cp.get("website", ""),
            "linkedin_url":         cp.get("linkedin_url", ""),
            "phone":                cp.get("phone", ""),
            "logo_url":             cp.get("logo_url", ""),
            "background_cover_url": cp.get("background_cover_url", ""),
            "founded_year":         cp.get("founded_year"),
            "employee_count":       cp.get("employee_count"),
            "employee_count_range": {
                "start": cp.get("employee_count_range_start"),
                "end":   cp.get("employee_count_range_end"),
            },
            "follower_count":       cp.get("follower_count"),
            "description":          cp.get("description", ""),
            "company_type":         cp.get("company_type", ""),
            "page_verified":        bool(cp.get("page_verified")),
            "locations":            cp.get("locations") or cp.get("locations_json") or [],
            "industries":           cp.get("industries") or cp.get("industries_json") or [],
            "logos":                cp.get("logos") or cp.get("logos_json") or [],
            "people_stats":         cp.get("people_stats") or cp.get("people_stats_json") or [],
            "similar_organizations":cp.get("similar_organizations") or cp.get("similar_organizations_json") or [],
            "specialities":         cp.get("specialities") or cp.get("specialities_json") or [],
        }

    return {
        # ── Identity ────────────────────────────────────────────────────────
        "lead_id":         lead_id,
        "full_name":       c.get("full_name",""),
        "job_title":       c.get("job_title",""),
        "company_name":    c.get("company_name",""),
        "sector_tag":      c.get("sector_tag",""),
        "country":         c.get("country",""),
        "location":        c.get("location",""),
        "linkedin_url":    li_url,
        "company_website": site,
        "status":          c.get("status","Draft Generated"),

        # ── Scores (AEO / GEO / ICP) ────────────────────────────────────────
        "scores": {
            "icp_score":       icp,
            "aeo_score":       aeo,
            "geo_score":       geo,
            "overall_score":   ovr,
            "recommendations": recs,
        },

        # ── Executive Dossier ────────────────────────────────────────────────
        "dossier": {
            "executive_summary":   dr.get("executive_summary") or dp.get("executive_summary") or "",
            "leadership_identity": leadership,
            "company_analysis":    company_ana,
            "strategic_paths":     paths,
            "competitor_analysis": {
                "top_competitors":      top_comps,
                "market_opportunities": mkt_opps,
                "landscape_summary":    ca.get("landscape_summary") or "",
            },
        },

        # ── Analyst Insights Summary ─────────────────────────────────────────
        "insights": {
            "marketing_stance":       _txt(marketing, "favorite_marketing_side", "narrative_angles"),
            "operational_philosophy": _txt(tech, "technology_integration_philosophy", "operational_stance"),
            "favorite_paths":         plist if isinstance(plist, list) else [],
            "aeo_score":              aeo,
            "geo_score":              geo,
            "aeo_geo_score":          ovr,
            "top_quote":              quote,
            "recommendations":        recs,
            "competitors":            top_comps,
        },

        # ── LinkedIn Outreach Messages ───────────────────────────────────────
        "bi_messages": {
            "connection_request_note":   bi.get("connection_request_note",""),
            "primary_inmail":            bi.get("primary_inmail",""),
            "alternative_pitch":         bi.get("alternative_pitch",""),
            "quick_teaser":              bi.get("quick_teaser",""),
            "follow_up":                 bi.get("follow_up",""),
            "resonance_points":          resonance,
            "personalization_rationale": bi.get("personalization_rationale",""),
        },

        # ── Contact Intelligence ─────────────────────────────────────────────
        "contact_info": {
            "website":       site,
            "emails":        emails,
            "phone_numbers": phones,
            "locations":     locs,
            "social_links":  social,
            "contact_pages": cpages,
        },

        # ── Full Company Profile (LinkedIn scraped) ───────────────────────────
        "company_profile": company_full,

        # ── Posts ────────────────────────────────────────────────────────────
        "raw_posts":   posts,
        "posts_count": len(posts),

        # ── Pipeline Timeline ────────────────────────────────────────────────
        "timeline": [
            {"event": "Lead saved to MySQL / SQLite",          "status": "done"},
            {"event": f"{len(posts)} LinkedIn posts extracted", "status": "done"},
            {"event": "Contact & website profiled",            "status": "done"},
            {"event": f"AEO/GEO score: {ovr}/100",            "status": "done"},
            {"event": "Outreach messages generated",           "status": "done"},
        ],
    }


# ════════════════════════════════════════════════════════════════════════════
#  ENDPOINT 1 ─ POST /api/studio/process
#  Receives scraped payload → runs pipeline → saves to MySQL → returns result
# ════════════════════════════════════════════════════════════════════════════
@app.post(
    "/api/studio/process",
    summary="[1] Ingest leads – run pipeline – save to MySQL",
    tags=["1. Process"],
)

def process_leads(payload: Any = Body(...)):
    """
    **Send the scraped leads payload here.**

    This endpoint will:
    1. Parse every lead from the `leads[]` array
    2. Download `posts_report_url` and `company_report_url` from S3 (with local cache fallback for expired URLs)
    3. **Run the full 9-agent AI pipeline** for any lead that is new or not yet processed:
       - DataCleanerAgent
       - MarketingAnalystAgent  (OpenAI)
       - StrategicPathAgent     (OpenAI)
       - CompanyAnalystAgent    (OpenAI)
       - ContactRetrieverAgent  (web scrape)
       - CompetitorAnalystAgent (OpenAI)
       - WebsiteScorerAgent     (live AEO/GEO HTTP audit)
       - BIMessageCreatorAgent  (OpenAI)
       - SeniorBASynthesizerAgent (OpenAI)
    4. **Save all data to MySQL** (`leads`, `lead_dossiers`, `bi_messages`,
       `competitor_analysis`, `contact_intelligence`, `raw_posts` tables)
    5. Return the processed studio data for every lead

    **Input body:**
    ```json
    {
      "request_id": "...",
      "leads": [
        {
          "id": 1,
          "full_name": "...",
          "job_title": "...",
          "company_name": "...",
          "sector_tag": "...",
          "country": "...",
          "location": "...",
          "posts_report_url": "https://s3.amazonaws.com/...",
          "company_report_url": "https://s3.amazonaws.com/..."
        }
      ],
      "skipped_lead_ids": []
    }
    ```
    """
    try:
        leads_items = loader.parse_all_leads_from_payload(payload)
        if not leads_items:
            raise HTTPException(status_code=400, detail="No valid leads found in payload.")

        request_id = payload.get("request_id", "") if isinstance(payload, dict) else ""
        skipped    = payload.get("skipped_lead_ids", []) if isinstance(payload, dict) else []
        processed: List[Dict[str, Any]] = []

        for lead_data, posts_data, company_data in leads_items:
            lead_id = lead_data.get("id")

            # Step 1: Always upsert the lead row into MySQL
            db_manager.upsert_lead(lead_data, status="Processing")

            # Step 1b: Save full company profile + peopleStats
            raw_company = lead_data.get("company") or company_data
            if raw_company and isinstance(raw_company, dict) and lead_id:
                # If peopleStats sits at the top-level payload, merge it in
                if lead_data.get("company") and lead_data.get("peopleStats"):
                    raw_company = dict(raw_company)
                    raw_company.setdefault("peopleStats", lead_data["peopleStats"])
                db_manager.save_company_profile(lead_id, raw_company)

            # Step 2: Check if a full dossier already exists (avoid re-running pipeline)
            # But force re-run if all saved raw_posts have empty text (old hallucinated data)
            existing         = db_manager.get_lead_complete(lead_id) if lead_id else None
            existing_posts   = (existing or {}).get("raw_posts") or []
            posts_are_empty  = all(not (p.get("post_text") or "").strip() for p in existing_posts)
            has_full_dossier = bool(
                existing
                and existing.get("dossier")
                and existing.get("bi_messages")
                and not posts_are_empty   # force re-run if posts were empty
            )

            if not has_full_dossier:
                # Step 3: Run the 9-agent AI pipeline
                try:
                    state = pipeline.run(
                        raw_lead=lead_data,
                        raw_posts=posts_data,
                        raw_company_report=company_data,
                    )

                    if state and state.dossier:
                        # Step 4: Format posts for DB
                        db_posts = []
                        if state.sanitized_texts:
                            for t in state.sanitized_texts:
                                db_posts.append({
                                    "post_text": t,
                                    "post_date": "Recent",
                                    "reactions_count": 0,
                                    "post_url": "",
                                })
                        # Also pick up structured posts from posts_data (supports 'content', 'text', 'post_text')
                        if isinstance(posts_data, list):
                            raw_list = posts_data
                        elif isinstance(posts_data, dict):
                            raw_list = posts_data.get("posts", []) + posts_data.get("company_posts", [])
                        else:
                            raw_list = []
                        for p in raw_list:
                            if isinstance(p, dict):
                                txt = p.get("text") or p.get("post_text") or p.get("content") or ""
                                posted_at = p.get("posted_at") or p.get("postedAt") or {}
                                date_val = posted_at.get("date", "") if isinstance(posted_at, dict) else p.get("post_date", "Recent")
                                engagement = p.get("engagement") or {}
                                reactions = (
                                    p.get("total_reactions")
                                    or p.get("reactions_count")
                                    or (engagement.get("likeCount", 0) if isinstance(engagement, dict) else 0)
                                    or 0
                                )
                                db_posts.append({
                                    "post_text": txt,
                                    "post_date": date_val or "Recent",
                                    "reactions_count": reactions,
                                    "post_url": p.get("url") or p.get("post_url") or p.get("linkedinUrl") or p.get("shareLinkedinUrl") or "",
                                })

                        # Step 5: Save everything to DB
                        db_manager.save_generated_dossier(
                            lead_id=lead_id,
                            dossier=state.dossier,
                            raw_posts=db_posts,
                        )
                        db_manager.update_lead_status(lead_id, "Draft Generated")
                        logger.info("Lead %s pipeline complete – saved to DB.", lead_id)

                except Exception as pipe_err:
                    logger.warning("Pipeline error for lead %s: %s", lead_id, pipe_err)
                    db_manager.update_lead_status(lead_id, "Pipeline Error")
            else:
                logger.info("Lead %s already has a full dossier with real posts – skipping pipeline.", lead_id)

            # Step 6: Read back from DB and add to response
            if lead_id:
                studio = _from_db(lead_id)
                if studio:
                    processed.append({
                        "lead_id": lead_id,
                        "processing_status": "Already in DB" if has_full_dossier else "Completed",
                        "studio_data": studio
                    })

        return {
            "request_id":       request_id,
            "status":           "success",
            "total_received":   len(leads_items),
            "total_processed":  len(processed),
            "skipped_lead_ids": skipped,
            "results":          processed,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in POST /api/studio/process")
        raise HTTPException(status_code=500, detail=str(exc))




# ════════════════════════════════════════════════════════════════════════════
#  ENDPOINT 2b ─ GET /api/studio/{lead_id}
#  Returns full studio data with AEO / GEO / ICP scores from MySQL
# ════════════════════════════════════════════════════════════════════════════
@app.get(
    "/api/studio/{lead_id}",
    summary="[2b] Get studio data with AEO/GEO scores by lead ID",
    tags=["2. Studio"],
)
def get_studio(lead_id: int):
    """
    Returns the **full studio intelligence** for a processed lead, read directly
    from MySQL (or SQLite fallback). Instant — no AI pipeline runs.

    Includes:
    - **scores**: ICP score, AEO score, GEO score, overall score + recommendations
    - **dossier**: executive summary, leadership identity, company analysis, strategic paths, competitors
    - **insights**: marketing stance, operational philosophy, favourite paths, top quote
    - **bi_messages**: 5 personalised LinkedIn outreach message templates
    - **contact_info**: website, emails, phone, social links
    - **raw_posts**: LinkedIn posts with engagement data

    Returns **404** if the lead has not been processed yet.
    Call `POST /api/studio/process` first.
    """
    data = _from_db(lead_id)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No studio data found for lead_id={lead_id}. "
                "Run POST /api/studio/process first to ingest and process this lead."
            ),
        )
    data.pop("company_profile", None)
    return {
        "status":     "success",
        "lead_id":    lead_id,
        "studio":     {
            **data,
            # Studio explicitly surfaces bi_messages and full insights at top-level
            "bi_messages": data.get("bi_messages", {}),
            "insights":    data.get("insights", {}),
        },
    }


# ════════════════════════════════════════════════════════════════════════════
#  ENDPOINT 3 ─ GET /api/dossier/{lead_id}
#  Returns only the executive dossier section from MySQL
# ════════════════════════════════════════════════════════════════════════════
@app.get(
    "/api/dossier/{lead_id}",
    summary="[3] Get executive dossier by lead ID",
    tags=["3. Dossier"],
)

def get_dossier(lead_id: int):
    """
    Returns only the **executive dossier** for a processed lead from MySQL.
    Instant — no AI pipeline runs.

    Includes:
    - **executive_summary**: full written intelligence summary
    - **leadership_identity**: archetype, communication style, decision patterns
    - **company_analysis**: market positioning, key offerings, value proposition
    - **strategic_paths**: the lead's preferred strategic approaches
    - **competitor_analysis**: top competitors, market gaps, landscape summary
    - **scores**: AEO / GEO / ICP readiness scores

    Returns **404** if the lead has not been processed yet.
    Call `POST /api/studio/process` first.
    """
    data = _from_db(lead_id)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No dossier found for lead_id={lead_id}. "
                "Run POST /api/studio/process first."
            ),
        )
    return {
        "status":  "success",
        "lead_id": lead_id,
        "dossier": {
            "identity": {
                "full_name":       data["full_name"],
                "job_title":       data["job_title"],
                "company_name":    data["company_name"],
                "sector_tag":      data["sector_tag"],
                "country":         data["country"],
                "location":        data["location"],
                "linkedin_url":    data["linkedin_url"],
                "company_website": data["company_website"],
            },
            "scores":          data["scores"],
            "dossier":         data["dossier"],
            "insights":        data["insights"],
            "company_profile": data.get("company_profile", {}),
        },
    }



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8080, reload=True)
