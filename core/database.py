import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from core.schemas import SeniorBAExecutiveDossier, BIMessageSet

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "leads_intelligence.db"

class DatabaseManager:
    """Manages local SQLite database operations for storing leads and generated Senior BA intelligence."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self) -> None:
        """Initializes relational tables for leads, dossiers, BI messages, competitors, contacts, and posts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Leads table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                job_title TEXT,
                company_name TEXT,
                sector_tag TEXT,
                country TEXT,
                location TEXT,
                posts_report_url TEXT,
                company_report_url TEXT,
                status TEXT DEFAULT 'Draft Generated',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 2. Dossiers table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS lead_dossiers (
                lead_id INTEGER PRIMARY KEY,
                executive_summary TEXT,
                leadership_identity TEXT,
                favorite_marketing_side TEXT,
                favorite_strategic_paths TEXT,
                business_transformation_and_tech_stance TEXT,
                market_positioning TEXT,
                core_value_proposition TEXT,
                aeo_score REAL,
                geo_score REAL,
                overall_score REAL,
                full_description TEXT,
                dossier_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
            );
            """)

            # 3. BI Outreach Messages table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS bi_messages (
                lead_id INTEGER PRIMARY KEY,
                connection_request_note TEXT,
                primary_inmail TEXT,
                alternative_pitch TEXT,
                quick_teaser TEXT,
                follow_up TEXT,
                target_resonance_points_json TEXT,
                personalization_rationale TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
            );
            """)

            # 4. Competitor Analysis table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS competitor_analysis (
                lead_id INTEGER PRIMARY KEY,
                target_company TEXT,
                landscape_summary TEXT,
                top_competitors_json TEXT,
                market_opportunities_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
            );
            """)

            # 5. Company Contact & Location Intelligence table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS contact_intelligence (
                lead_id INTEGER PRIMARY KEY,
                company_name TEXT,
                website TEXT,
                emails_json TEXT,
                phone_numbers_json TEXT,
                locations_json TEXT,
                social_links_json TEXT,
                contact_pages_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
            );
            """)

            # 6. Raw Posts table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                post_text TEXT,
                post_date TEXT,
                reactions_count INTEGER DEFAULT 0,
                post_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
            );
            """)

            conn.commit()

    def upsert_lead(self, lead_data: Dict[str, Any], status: str = "Draft Generated") -> int:
        """Inserts or updates a lead record."""
        lead_id = lead_data.get("id")
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO leads (
                    id, full_name, job_title, company_name, sector_tag, country, location,
                    posts_report_url, company_report_url, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    full_name=excluded.full_name,
                    job_title=excluded.job_title,
                    company_name=excluded.company_name,
                    sector_tag=excluded.sector_tag,
                    country=excluded.country,
                    location=excluded.location,
                    posts_report_url=excluded.posts_report_url,
                    company_report_url=excluded.company_report_url,
                    status=excluded.status,
                    updated_at=excluded.updated_at;
            """, (
                lead_id,
                lead_data.get("full_name", ""),
                lead_data.get("job_title", ""),
                lead_data.get("company_name", ""),
                lead_data.get("sector_tag", ""),
                lead_data.get("country", ""),
                lead_data.get("location", ""),
                lead_data.get("posts_report_url", ""),
                lead_data.get("company_report_url", ""),
                status,
                now
            ))
            conn.commit()
            return cursor.lastrowid or lead_id

    def save_generated_dossier(
        self,
        lead_id: int,
        dossier: SeniorBAExecutiveDossier,
        raw_posts: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Stores the synthesized dossier and all generated intelligence across respective tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Format fields for storage
            def to_text(val: Any) -> str:
                if isinstance(val, (dict, list)):
                    return json.dumps(val, indent=2)
                return str(val or "")

            exec_summary = to_text(dossier.executive_summary)
            leadership_id = to_text(dossier.leadership_identity)
            marketing_side = to_text(dossier.favorite_marketing_side_analysis)
            strategic_paths = to_text(dossier.favorite_paths_analysis)
            tech_stance = to_text(dossier.business_transformation_and_tech_stance)

            market_pos = to_text(dossier.company_analysis.market_positioning) if dossier.company_analysis else ""
            core_val = to_text(dossier.company_analysis.core_value_proposition) if dossier.company_analysis else ""

            aeo = dossier.website_aeo_geo_score.aeo_score if dossier.website_aeo_geo_score else 0.0
            geo = dossier.website_aeo_geo_score.geo_score if dossier.website_aeo_geo_score else 0.0
            overall = dossier.website_aeo_geo_score.overall_score if dossier.website_aeo_geo_score else 0.0

            dossier_dict = dossier.model_dump()
            dossier_json = json.dumps(dossier_dict, indent=2)

            # 1. Lead Dossiers
            cursor.execute("""
                INSERT INTO lead_dossiers (
                    lead_id, executive_summary, leadership_identity, favorite_marketing_side,
                    favorite_strategic_paths, business_transformation_and_tech_stance,
                    market_positioning, core_value_proposition, aeo_score, geo_score, overall_score,
                    full_description, dossier_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lead_id) DO UPDATE SET
                    executive_summary=excluded.executive_summary,
                    leadership_identity=excluded.leadership_identity,
                    favorite_marketing_side=excluded.favorite_marketing_side,
                    favorite_strategic_paths=excluded.favorite_strategic_paths,
                    business_transformation_and_tech_stance=excluded.business_transformation_and_tech_stance,
                    market_positioning=excluded.market_positioning,
                    core_value_proposition=excluded.core_value_proposition,
                    aeo_score=excluded.aeo_score,
                    geo_score=excluded.geo_score,
                    overall_score=excluded.overall_score,
                    full_description=excluded.full_description,
                    dossier_json=excluded.dossier_json;
            """, (
                lead_id, exec_summary, leadership_id, marketing_side,
                strategic_paths, tech_stance, market_pos, core_val,
                aeo, geo, overall, dossier.full_description, dossier_json
            ))

            # 2. BI Messages
            if dossier.bi_messages:
                bm = dossier.bi_messages
                cursor.execute("""
                    INSERT INTO bi_messages (
                        lead_id, connection_request_note, primary_inmail, alternative_pitch,
                        quick_teaser, follow_up, target_resonance_points_json, personalization_rationale
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(lead_id) DO UPDATE SET
                        connection_request_note=excluded.connection_request_note,
                        primary_inmail=excluded.primary_inmail,
                        alternative_pitch=excluded.alternative_pitch,
                        quick_teaser=excluded.quick_teaser,
                        follow_up=excluded.follow_up,
                        target_resonance_points_json=excluded.target_resonance_points_json,
                        personalization_rationale=excluded.personalization_rationale;
                """, (
                    lead_id,
                    bm.connection_request_note,
                    bm.primary_inmail,
                    bm.alternative_pitch,
                    bm.quick_teaser,
                    bm.follow_up,
                    json.dumps(bm.target_resonance_points),
                    to_text(bm.personalization_rationale)
                ))

            # 3. Competitor Analysis
            if dossier.competitor_analysis:
                ca = dossier.competitor_analysis
                top_comps = [c.model_dump() for c in ca.top_competitors]
                cursor.execute("""
                    INSERT INTO competitor_analysis (
                        lead_id, target_company, landscape_summary, top_competitors_json, market_opportunities_json
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(lead_id) DO UPDATE SET
                        target_company=excluded.target_company,
                        landscape_summary=excluded.landscape_summary,
                        top_competitors_json=excluded.top_competitors_json,
                        market_opportunities_json=excluded.market_opportunities_json;
                """, (
                    lead_id,
                    ca.target_company,
                    to_text(ca.landscape_summary),
                    json.dumps(top_comps),
                    json.dumps(ca.market_opportunities_and_gaps)
                ))

            # 4. Contact & Location Intelligence
            if dossier.contact_info:
                ci = dossier.contact_info
                locs = [l.model_dump() for l in ci.locations]
                cursor.execute("""
                    INSERT INTO contact_intelligence (
                        lead_id, company_name, website, emails_json, phone_numbers_json,
                        locations_json, social_links_json, contact_pages_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(lead_id) DO UPDATE SET
                        company_name=excluded.company_name,
                        website=excluded.website,
                        emails_json=excluded.emails_json,
                        phone_numbers_json=excluded.phone_numbers_json,
                        locations_json=excluded.locations_json,
                        social_links_json=excluded.social_links_json,
                        contact_pages_json=excluded.contact_pages_json;
                """, (
                    lead_id,
                    ci.company_name or dossier.company_name,
                    ci.website,
                    json.dumps(ci.emails),
                    json.dumps(ci.phone_numbers),
                    json.dumps(locs),
                    json.dumps(ci.social_links),
                    json.dumps(ci.contact_pages_found)
                ))

            # 5. Raw Posts
            if raw_posts:
                cursor.execute("DELETE FROM raw_posts WHERE lead_id = ?;", (lead_id,))
                for p in raw_posts:
                    text = p.get("text") if isinstance(p, dict) else str(p)
                    date_val = p.get("posted_at", {}).get("date", "Recent") if isinstance(p, dict) else "Recent"
                    reactions = p.get("total_reactions", 0) if isinstance(p, dict) else 0
                    p_url = p.get("url", "") if isinstance(p, dict) else ""
                    cursor.execute("""
                        INSERT INTO raw_posts (lead_id, post_text, post_date, reactions_count, post_url)
                        VALUES (?, ?, ?, ?, ?);
                    """, (lead_id, text, str(date_val), reactions, p_url))

            conn.commit()

    def get_all_leads(self) -> List[Dict[str, Any]]:
        """Fetches all leads with summary metrics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.*, d.overall_score, d.aeo_score, d.geo_score
                FROM leads l
                LEFT JOIN lead_dossiers d ON l.id = d.lead_id
                ORDER BY l.id ASC;
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_lead_complete(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """Fetches complete consolidated intelligence for a given lead."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM leads WHERE id = ?;", (lead_id,))
            lead_row = cursor.fetchone()
            if not lead_row:
                return None
            result = dict(lead_row)

            # Dossier
            cursor.execute("SELECT * FROM lead_dossiers WHERE lead_id = ?;", (lead_id,))
            dossier_row = cursor.fetchone()
            if dossier_row:
                result["dossier"] = dict(dossier_row)
                if dossier_row["dossier_json"]:
                    try:
                        result["dossier_parsed"] = json.loads(dossier_row["dossier_json"])
                    except Exception:
                        pass

            # BI Messages
            cursor.execute("SELECT * FROM bi_messages WHERE lead_id = ?;", (lead_id,))
            bm_row = cursor.fetchone()
            if bm_row:
                result["bi_messages"] = dict(bm_row)
                if bm_row["target_resonance_points_json"]:
                    try:
                        result["bi_messages"]["target_resonance_points"] = json.loads(bm_row["target_resonance_points_json"])
                    except Exception:
                        pass

            # Competitors
            cursor.execute("SELECT * FROM competitor_analysis WHERE lead_id = ?;", (lead_id,))
            comp_row = cursor.fetchone()
            if comp_row:
                result["competitors"] = dict(comp_row)
                if comp_row["top_competitors_json"]:
                    try:
                        result["competitors"]["top_competitors"] = json.loads(comp_row["top_competitors_json"])
                    except Exception:
                        pass

            # Contact
            cursor.execute("SELECT * FROM contact_intelligence WHERE lead_id = ?;", (lead_id,))
            contact_row = cursor.fetchone()
            if contact_row:
                result["contact_info"] = dict(contact_row)
                for fld in ["emails_json", "phone_numbers_json", "locations_json", "social_links_json", "contact_pages_json"]:
                    if contact_row[fld]:
                        try:
                            clean_name = fld.replace("_json", "")
                            result["contact_info"][clean_name] = json.loads(contact_row[fld])
                        except Exception:
                            pass

            # Posts
            cursor.execute("SELECT * FROM raw_posts WHERE lead_id = ? ORDER BY id ASC;", (lead_id,))
            posts_rows = cursor.fetchall()
            result["raw_posts"] = [dict(p) for p in posts_rows]

            return result

db_manager = DatabaseManager()
