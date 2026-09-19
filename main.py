import argparse
import json
import logging
import sys
from pathlib import Path
from core.config import settings
from core.database import db_manager
from core.llm_client import LLMClient
from orchestrator.lead_loader import LeadLoader
from orchestrator.multi_agent_runner import MultiAgentPipeline

# Setup clean console logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("SeniorBA")

def print_banner():
    banner = r"""
========================================================================
   MOMENTRO - SENIOR BUSINESS ANALYST MULTI-AGENT PLATFORM
   Executive, Marketing Stance, Strategic Paths, Company & Competitors
========================================================================
"""
    print(banner)

def main():
    parser = argparse.ArgumentParser(description="Run the Senior BA Multi-Agent Pipeline")
    parser.add_argument("--sample", action="store_true", help="Run on Rajive Silva sample fixtures")
    parser.add_argument("--scraped", action="store_true", help="Run on scraped_profiles (2).json (fetching report URLs)")
    parser.add_argument("--export-lead-id", type=int, default=None, help="Fetch lead ID from export endpoint (http://52.91.158.106:8000/api/leads/export)")
    parser.add_argument("--model", type=str, default=None, help="LLM model (e.g., gpt-4o-mini, gpt-4o)")
    parser.add_argument("--output", type=str, default="senior_ba_dossier.json", help="Output JSON path")
    parser.add_argument("--markdown", type=str, default="senior_ba_report.md", help="Output Markdown report path")
    args = parser.parse_args()

    print_banner()

    loader = LeadLoader()
    lead_data = None
    posts_data = None
    company_data = None

    if args.export_lead_id is not None:
        logger.info(f"Fetching lead ID #{args.export_lead_id} from export API (http://52.91.158.106:8000/api/leads/export)...")
        export_results = loader.load_export_leads_with_reports(lead_ids=[args.export_lead_id])
        if not export_results:
            logger.error(f"Failed to fetch lead #{args.export_lead_id} from export endpoint.")
            sys.exit(1)
        lead_data, posts_data, company_data = export_results[0]
    elif args.scraped:
        logger.info("Loading lead and fetching report URLs from 'scraped_profiles (2).json'...")
        lead_data, posts_data, company_data = loader.load_lead_with_reports(index=0)
    else:
        # Default: sample fixtures
        logger.info("Loading Rajive Silva sample lead, posts, and company report...")
        lead_data, posts_data, company_data = loader.load_sample_data()

    # Model and LLM client setup
    model_name = args.model or settings.openai_model
    logger.info(f"Using Model: {model_name}")
    logger.info(f"OpenAI API Key detected: {'Yes (valid sk-...)' if settings.validate_api_key() else 'No / Invalid'}")

    llm_client = LLMClient(model=model_name)
    pipeline = MultiAgentPipeline(llm_client=llm_client)

    logger.info("Executing 7-Agent Senior BA Pipeline...")
    state = pipeline.run(
        raw_lead=lead_data,
        raw_posts=posts_data,
        raw_company_report=company_data
    )

    dossier = state.dossier
    if not dossier:
        logger.error("Pipeline finished without generating a dossier.")
        sys.exit(1)

    # Display rich results
    print("\n" + "="*80)
    print(f" SENIOR BUSINESS ANALYST DOSSIER: {dossier.full_name.upper()}")
    print("="*80)
    print(f"Role:       {dossier.job_title}")
    print(f"Company:    {dossier.company_name}")
    print(f"Sector:     {dossier.sector_tag}")
    print(f"Location:   {dossier.location}, {dossier.country}")
    print("-" * 80)
    print("\n[EXECUTIVE SUMMARY]")
    print(dossier.executive_summary)
    print("\n[LEADERSHIP IDENTITY]")
    print(dossier.leadership_identity)
    print("\n[FAVORITE MARKETING SIDE]")
    print(dossier.favorite_marketing_side_analysis)
    print("\n[FAVORITE STRATEGIC PATHS]")
    print(dossier.favorite_paths_analysis)
    print("\n[BUSINESS TRANSFORMATION & TECH STANCE]")
    print(dossier.business_transformation_and_tech_stance)

    if dossier.company_analysis:
        print("\n[CORPORATE POSITIONING & VALUE PROPOSITION]")
        print(f"Market Positioning: {dossier.company_analysis.market_positioning}")
        print(f"Core Value Prop:    {dossier.company_analysis.core_value_proposition}")
        print("Key Offerings:")
        for off in dossier.company_analysis.key_offerings:
            print(f"  • {off}")

    if dossier.competitor_analysis:
        print("\n[COMPETITIVE LANDSCAPE & BENCHMARKING]")
        print(dossier.competitor_analysis.landscape_summary)
        print("Top Benchmarked Competitors:")
        for comp in dossier.competitor_analysis.top_competitors:
            print(f"  • {comp.name}: {comp.differentiation_vs_target}")

    if dossier.website_aeo_geo_score:
        print("\n[WEBSITE AEO & GEO DIGITAL FOOTPRINT]")
        ws = dossier.website_aeo_geo_score
        print(f"Target URL:    {ws.website_url}")
        print(f"Overall Score: {ws.overall_score}/100")
        print(f"AEO Score:     {ws.aeo_score}/100 (Answer Engine Optimization)")
        print(f"GEO Score:     {ws.geo_score}/100 (Generative Engine Optimization)")
        print(f"Status:        {ws.status}")
        print("Key Recommendations:")
        for rec in ws.recommendations[:2]:
            print(f"  • {rec}")

    if dossier.contact_info:
        print("\n[COMPANY CONTACT & LOCATION INTELLIGENCE (SCRAPED)]")
        ci = dossier.contact_info
        print(f"Company:       {ci.company_name or 'N/A'}")
        print(f"Website:       {ci.website}")
        print(f"Emails:        {', '.join(ci.emails) if ci.emails else 'None'}")
        print(f"Phones:        {', '.join(ci.phone_numbers) if ci.phone_numbers else 'None'}")
        print(f"Social Links:  {', '.join(f'{k}: {v}' for k, v in ci.social_links.items()) if ci.social_links else 'None'}")
        if ci.locations:
            print("Locations:")
            for loc in ci.locations:
                print(f"  • {loc.label}: {loc.full_address or (loc.city + ', ' + (loc.country or ''))}")

    print("\n[SENIOR BA ENGAGEMENT RECOMMENDATIONS]")
    for i, rec in enumerate(dossier.senior_ba_engagement_recommendations, 1):
        print(f"  {i}. {rec}")

    if dossier.bi_messages:
        bm = dossier.bi_messages
        print("\n" + "="*80)
        print(" AUTOMATED LINKEDIN BI OUTREACH MESSAGES (MOMENTRO PLATFORM)")
        print("="*80)
        print("\n[1. CONNECTION REQUEST NOTE (<300 Chars)]")
        print(f"({len(bm.connection_request_note)} characters):")
        print(f'"{bm.connection_request_note}"')

        print("\n[2. PRIMARY INMAIL / DIRECT MESSAGE]")
        print(bm.primary_inmail)

        print("\n[3. ALTERNATIVE STRATEGIC PITCH (Venture/Scale Angle)]")
        print(bm.alternative_pitch)

        print("\n[4. QUICK C-LEVEL TEASER]")
        print(bm.quick_teaser)

        print("\n[5. VALUE-ADD FOLLOW-UP (+3-5 Days)]")
        print(bm.follow_up)

        print("\n[PERSONALIZATION TRIGGERS & RATIONALE]")
        for pt in bm.target_resonance_points:
            print(f"  • {pt}")
        print(f"\nRationale: {bm.personalization_rationale}")

    # Save outputs
    out_json = Path(args.output)
    out_json.write_text(json.dumps(dossier.model_dump(), indent=2), encoding="utf-8")
    logger.info(f"Saved JSON dossier to: {out_json.resolve()}")

    out_md = Path(args.markdown)
    out_md.write_text(dossier.full_description, encoding="utf-8")
    logger.info(f"Saved Markdown report to: {out_md.resolve()}")

    # Persist directly into local SQLite database
    raw_posts_list = []
    if isinstance(posts_data, dict):
        raw_posts_list = posts_data.get("posts", [])
    elif isinstance(posts_data, list):
        raw_posts_list = posts_data

    db_manager.upsert_lead(lead_data, status="Draft Generated")
    db_manager.save_generated_dossier(
        lead_id=dossier.lead_id,
        dossier=dossier,
        raw_posts=raw_posts_list
    )
    logger.info(f"Saved Lead #{dossier.lead_id} intelligence to SQLite database: {db_manager.db_path.resolve()}")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
