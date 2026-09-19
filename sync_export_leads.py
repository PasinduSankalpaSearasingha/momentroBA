import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List

from core.config import settings
from core.database import db_manager
from core.llm_client import LLMClient
from orchestrator.lead_loader import LeadLoader
from orchestrator.multi_agent_runner import MultiAgentPipeline

# Setup console logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ExportSync")

def print_banner():
    banner = r"""
========================================================================
   MOMENTRO - EXPORT API INGESTION & LOCAL DATABASE PIPELINE
   Connecting: http://52.91.158.106:8000/api/leads/export
   Storage: SQLite Local Database (data/leads_intelligence.db)
========================================================================
"""
    print(banner)

def process_exported_leads(
    lead_ids: List[int],
    endpoint_url: str = "http://52.91.158.106:8000/api/leads/export",
    model: str = None
):
    loader = LeadLoader()
    llm_client = LLMClient(model=model or settings.openai_model)
    pipeline = MultiAgentPipeline(llm_client=llm_client)

    logger.info(f"Connecting to export endpoint: {endpoint_url}")
    logger.info(f"Requesting Lead IDs: {lead_ids}")

    leads_items = loader.load_export_leads_with_reports(
        endpoint_url=endpoint_url,
        lead_ids=lead_ids
    )

    if not leads_items:
        logger.error("No leads returned from the export endpoint.")
        return []

    processed = []

    for lead_data, posts_data, company_data in leads_items:
        lead_id = lead_data.get("id")
        full_name = lead_data.get("full_name", "Unknown Lead")
        company_name = lead_data.get("company_name", "Unknown Company")

        print("\n" + "="*80)
        print(f" PROCESSING LEAD #{lead_id}: {full_name.upper()} ({company_name})")
        print("="*80)

        # 1. Upsert initial lead record in local DB
        db_manager.upsert_lead(lead_data, status="Processing Pipeline")
        logger.info(f"Lead #{lead_id} initialized in local SQLite database.")

        # Extract raw posts list for database storage
        raw_posts_list = []
        if isinstance(posts_data, dict):
            raw_posts_list = posts_data.get("posts", [])
        elif isinstance(posts_data, list):
            raw_posts_list = posts_data

        # 2. Execute Multi-Agent Intelligence Pipeline
        logger.info(f"Running Senior BA Multi-Agent Pipeline for {full_name}...")
        state = pipeline.run(
            raw_lead=lead_data,
            raw_posts=posts_data,
            raw_company_report=company_data
        )

        dossier = state.dossier
        if not dossier:
            logger.error(f"Failed to generate dossier for lead #{lead_id}.")
            continue

        # 3. Store all generated intelligence into the local database
        db_manager.save_generated_dossier(
            lead_id=lead_id,
            dossier=dossier,
            raw_posts=raw_posts_list
        )
        db_manager.upsert_lead(lead_data, status="Draft Generated")
        logger.info(f"Successfully saved all generated intelligence for Lead #{lead_id} into SQLite database!")

        # 4. Display rich summary
        print("\n[EXECUTIVE SUMMARY]")
        print(dossier.executive_summary)

        print("\n[LEADERSHIP IDENTITY]")
        print(dossier.leadership_identity)

        print("\n[FAVORITE MARKETING SIDE]")
        print(dossier.favorite_marketing_side_analysis)

        print("\n[FAVORITE STRATEGIC PATHS]")
        print(dossier.favorite_paths_analysis)

        print("\n[BUSINESS & TECH STANCE]")
        print(dossier.business_transformation_and_tech_stance)

        if dossier.website_aeo_geo_score:
            ws = dossier.website_aeo_geo_score
            print(f"\n[AEO/GEO SCORE]: Overall: {ws.overall_score}/100 | AEO: {ws.aeo_score}/100 | GEO: {ws.geo_score}/100")

        if dossier.bi_messages:
            bm = dossier.bi_messages
            print("\n" + "-"*80)
            print(" GENERATED LINKEDIN BI OUTREACH MESSAGES (STORED IN DB)")
            print("-"*80)
            print(f"\n1. Connection Request Note ({len(bm.connection_request_note)} chars):")
            print(f'   "{bm.connection_request_note}"')
            print("\n2. Primary InMail:")
            print(bm.primary_inmail)
            print("\n3. Alternative Strategic Pitch:")
            print(bm.alternative_pitch)
            print("\n4. Quick C-Level Teaser:")
            print(bm.quick_teaser)
            print("\n5. Value-Add Follow-up:")
            print(bm.follow_up)

        processed.append(lead_id)

    print("\n" + "="*80)
    print(f" COMPLETED PROCESSING {len(processed)} LEAD(S).")
    print(f" All data safely stored in: {db_manager.db_path.resolve()}")
    print("="*80 + "\n")
    return processed

def main():
    parser = argparse.ArgumentParser(description="Fetch leads from export API and store generating data in local database")
    parser.add_argument("--lead-ids", nargs="+", type=int, default=[2], help="Lead IDs to export and process (default: 2)")
    parser.add_argument("--endpoint", type=str, default="http://52.91.158.106:8000/api/leads/export", help="Export API endpoint URL")
    parser.add_argument("--model", type=str, default=None, help="LLM model (e.g. gpt-4o-mini)")
    args = parser.parse_args()

    print_banner()
    process_exported_leads(
        lead_ids=args.lead_ids,
        endpoint_url=args.endpoint,
        model=args.model
    )

if __name__ == "__main__":
    main()
