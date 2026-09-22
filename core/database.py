import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import pymysql
import pymysql.cursors

from core.schemas import SeniorBAExecutiveDossier

logger = logging.getLogger("DatabaseManager")

# MySQL Configuration defaults (matching XAMPP localhost)
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DATABASE", "momentoba")

class DatabaseManager:
    """Enterprise Database Manager using MySQL exclusively."""

    def __init__(self):
        # Test MySQL connection on boot, will fail fast if unavailable
        conn = self.get_mysql_connection()
        conn.close()
        logger.info(f"Connected successfully to MySQL database '{MYSQL_DB}' at {MYSQL_HOST}:{MYSQL_PORT}")
        self.init_db()

    def get_mysql_connection(self):
        return pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )

    def init_db(self) -> None:
        """Initializes tables in MySQL."""
        conn = self.get_mysql_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id INT PRIMARY KEY,
                    full_name VARCHAR(255) NOT NULL,
                    job_title VARCHAR(255),
                    company_name VARCHAR(255),
                    sector_tag VARCHAR(255),
                    country VARCHAR(100),
                    location VARCHAR(255),
                    posts_report_url TEXT,
                    company_report_url TEXT,
                    status VARCHAR(50) DEFAULT 'Draft Generated',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS lead_dossiers (
                    lead_id INT PRIMARY KEY,
                    executive_summary LONGTEXT,
                    leadership_identity LONGTEXT,
                    favorite_marketing_side LONGTEXT,
                    favorite_strategic_paths LONGTEXT,
                    business_transformation_and_tech_stance LONGTEXT,
                    market_positioning LONGTEXT,
                    core_value_proposition LONGTEXT,
                    aeo_score DOUBLE DEFAULT 0,
                    geo_score DOUBLE DEFAULT 0,
                    overall_score DOUBLE DEFAULT 0,
                    full_description LONGTEXT,
                    dossier_json LONGTEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS bi_messages (
                    lead_id INT PRIMARY KEY,
                    connection_request_note TEXT,
                    primary_inmail LONGTEXT,
                    alternative_pitch LONGTEXT,
                    quick_teaser LONGTEXT,
                    follow_up LONGTEXT,
                    target_resonance_points_json LONGTEXT,
                    personalization_rationale LONGTEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS competitor_analysis (
                    lead_id INT PRIMARY KEY,
                    target_company VARCHAR(255),
                    landscape_summary LONGTEXT,
                    top_competitors_json LONGTEXT,
                    market_opportunities_json LONGTEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS contact_intelligence (
                    lead_id INT PRIMARY KEY,
                    company_name VARCHAR(255),
                    website VARCHAR(500),
                    emails_json LONGTEXT,
                    phone_numbers_json LONGTEXT,
                    locations_json LONGTEXT,
                    social_links_json LONGTEXT,
                    contact_pages_json LONGTEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS raw_posts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    lead_id INT,
                    post_text LONGTEXT,
                    post_date VARCHAR(100),
                    reactions_count INT DEFAULT 0,
                    post_url VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS company_profile (
                    lead_id INT PRIMARY KEY,
                    company_id VARCHAR(64),
                    universal_name VARCHAR(255),
                    name VARCHAR(255),
                    tagline TEXT,
                    website VARCHAR(500),
                    linkedin_url VARCHAR(500),
                    phone VARCHAR(100),
                    logo_url VARCHAR(1000),
                    background_cover_url VARCHAR(1000),
                    founded_year INT,
                    employee_count INT,
                    employee_count_range_start INT,
                    employee_count_range_end INT,
                    follower_count INT,
                    description LONGTEXT,
                    company_type VARCHAR(100),
                    page_verified TINYINT(1) DEFAULT 0,
                    locations_json LONGTEXT,
                    industries_json LONGTEXT,
                    logos_json LONGTEXT,
                    people_stats_json LONGTEXT,
                    similar_organizations_json LONGTEXT,
                    specialities_json LONGTEXT,
                    raw_company_json LONGTEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
        finally:
            conn.close()

    def upsert_lead(self, lead_data: Dict[str, Any], status: str = "Draft Generated") -> int:
        lead_id = lead_data.get("id")
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        conn = self.get_mysql_connection()
        try:
            with conn.cursor() as cur:
                sql = """
                INSERT INTO leads (
                    id, full_name, job_title, company_name, sector_tag, country, location,
                    posts_report_url, company_report_url, status, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    full_name=VALUES(full_name),
                    job_title=VALUES(job_title),
                    company_name=VALUES(company_name),
                    sector_tag=VALUES(sector_tag),
                    country=VALUES(country),
                    location=VALUES(location),
                    posts_report_url=VALUES(posts_report_url),
                    company_report_url=VALUES(company_report_url),
                    status=VALUES(status),
                    updated_at=VALUES(updated_at);
                """
                cur.execute(sql, (
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
                return cur.lastrowid or lead_id
        finally:
            conn.close()

    def save_company_profile(self, lead_id: int, company_data: Dict[str, Any]) -> None:
        if not company_data or not isinstance(company_data, dict):
            return
        co = company_data
        if "company" in co and isinstance(co["company"], dict):
            co = co["company"]
        phone_raw = co.get("phone") or {}
        phone_str = phone_raw.get("number", "") if isinstance(phone_raw, dict) else str(phone_raw)
        logos = co.get("logos") or []
        logo_url = logos[0].get("url", "") if logos and isinstance(logos, list) and isinstance(logos[0], dict) else co.get("logo", "")
        bg_covers = co.get("backgroundCovers") or []
        bg_url = bg_covers[0].get("url", "") if bg_covers and isinstance(bg_covers, list) and isinstance(bg_covers[0], dict) else co.get("backgroundCover", "")
        founded = co.get("foundedOn") or {}
        founded_year = founded.get("year") if isinstance(founded, dict) else None
        emp_range = co.get("employeeCountRange") or {}
        emp_start = emp_range.get("start") if isinstance(emp_range, dict) else None
        emp_end   = emp_range.get("end")   if isinstance(emp_range, dict) else None
        li_url = co.get("linkedinUrl", "") or company_data.get("company_linkedin_url", "")
        def _j(v): return json.dumps(v) if v else "[]"
        params = (
            lead_id,
            str(co.get("id", "") or ""),
            co.get("universalName", "") or "",
            co.get("name", "") or "",
            co.get("tagline", "") or "",
            co.get("website", "") or co.get("callToActionUrl", "") or "",
            li_url,
            phone_str,
            logo_url,
            bg_url,
            founded_year,
            co.get("employeeCount"),
            emp_start,
            emp_end,
            co.get("followerCount"),
            co.get("description", "") or "",
            co.get("companyType", "") or "",
            1 if co.get("pageVerified") else 0,
            _j(co.get("locations")),
            _j(co.get("industries")),
            _j(co.get("logos")),
            _j(co.get("peopleStats") or company_data.get("peopleStats")),
            _j(co.get("similarOrganizations")),
            _j(co.get("specialities")),
            json.dumps(co),
        )
        conn = self.get_mysql_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO company_profile (
                        lead_id, company_id, universal_name, name, tagline, website, linkedin_url,
                        phone, logo_url, background_cover_url, founded_year, employee_count,
                        employee_count_range_start, employee_count_range_end, follower_count,
                        description, company_type, page_verified, locations_json, industries_json,
                        logos_json, people_stats_json, similar_organizations_json, specialities_json,
                        raw_company_json
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                        company_id=VALUES(company_id), universal_name=VALUES(universal_name),
                        name=VALUES(name), tagline=VALUES(tagline), website=VALUES(website),
                        linkedin_url=VALUES(linkedin_url), phone=VALUES(phone),
                        logo_url=VALUES(logo_url), background_cover_url=VALUES(background_cover_url),
                        founded_year=VALUES(founded_year), employee_count=VALUES(employee_count),
                        employee_count_range_start=VALUES(employee_count_range_start),
                        employee_count_range_end=VALUES(employee_count_range_end),
                        follower_count=VALUES(follower_count), description=VALUES(description),
                        company_type=VALUES(company_type), page_verified=VALUES(page_verified),
                        locations_json=VALUES(locations_json), industries_json=VALUES(industries_json),
                        logos_json=VALUES(logos_json), people_stats_json=VALUES(people_stats_json),
                        similar_organizations_json=VALUES(similar_organizations_json),
                        specialities_json=VALUES(specialities_json),
                        raw_company_json=VALUES(raw_company_json);
                """, params)
        finally:
            conn.close()

    def update_lead_status(self, lead_id: int, status: str) -> bool:
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        conn = self.get_mysql_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE leads SET status = %s, updated_at = %s WHERE id = %s", (status, now, lead_id))
                return cur.rowcount > 0
        finally:
            conn.close()

    def save_generated_dossier(self, lead_id: int, dossier: SeniorBAExecutiveDossier, raw_posts: Optional[List[Dict[str, Any]]] = None) -> None:
        def to_text(val: Any) -> str:
            return json.dumps(val, indent=2) if isinstance(val, (dict, list)) else str(val or "")
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
        dossier_json = json.dumps(dossier.model_dump(), indent=2)
        bm, ca, ci = dossier.bi_messages, dossier.competitor_analysis, dossier.contact_info

        conn = self.get_mysql_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO lead_dossiers (
                        lead_id, executive_summary, leadership_identity, favorite_marketing_side,
                        favorite_strategic_paths, business_transformation_and_tech_stance,
                        market_positioning, core_value_proposition, aeo_score, geo_score, overall_score,
                        full_description, dossier_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        executive_summary=VALUES(executive_summary), leadership_identity=VALUES(leadership_identity),
                        favorite_marketing_side=VALUES(favorite_marketing_side), favorite_strategic_paths=VALUES(favorite_strategic_paths),
                        business_transformation_and_tech_stance=VALUES(business_transformation_and_tech_stance),
                        market_positioning=VALUES(market_positioning), core_value_proposition=VALUES(core_value_proposition),
                        aeo_score=VALUES(aeo_score), geo_score=VALUES(geo_score), overall_score=VALUES(overall_score),
                        full_description=VALUES(full_description), dossier_json=VALUES(dossier_json);
                """, (lead_id, exec_summary, leadership_id, marketing_side, strategic_paths, tech_stance, market_pos, core_val, aeo, geo, overall, dossier.full_description, dossier_json))

                if bm:
                    cur.execute("""
                        INSERT INTO bi_messages (
                            lead_id, connection_request_note, primary_inmail, alternative_pitch,
                            quick_teaser, follow_up, target_resonance_points_json, personalization_rationale
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            connection_request_note=VALUES(connection_request_note), primary_inmail=VALUES(primary_inmail),
                            alternative_pitch=VALUES(alternative_pitch), quick_teaser=VALUES(quick_teaser),
                            follow_up=VALUES(follow_up), target_resonance_points_json=VALUES(target_resonance_points_json),
                            personalization_rationale=VALUES(personalization_rationale);
                    """, (lead_id, bm.connection_request_note, bm.primary_inmail, bm.alternative_pitch, bm.quick_teaser, bm.follow_up, json.dumps(bm.target_resonance_points), to_text(bm.personalization_rationale)))

                if ca:
                    top_comps = [c.model_dump() for c in ca.top_competitors]
                    cur.execute("""
                        INSERT INTO competitor_analysis (lead_id, target_company, landscape_summary, top_competitors_json, market_opportunities_json)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            target_company=VALUES(target_company), landscape_summary=VALUES(landscape_summary),
                            top_competitors_json=VALUES(top_competitors_json), market_opportunities_json=VALUES(market_opportunities_json);
                    """, (lead_id, ca.target_company, to_text(ca.landscape_summary), json.dumps(top_comps), json.dumps(ca.market_opportunities_and_gaps)))

                if ci:
                    locs = [l.model_dump() for l in ci.locations]
                    cur.execute("""
                        INSERT INTO contact_intelligence (
                            lead_id, company_name, website, emails_json, phone_numbers_json,
                            locations_json, social_links_json, contact_pages_json
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            company_name=VALUES(company_name), website=VALUES(website), emails_json=VALUES(emails_json),
                            phone_numbers_json=VALUES(phone_numbers_json), locations_json=VALUES(locations_json),
                            social_links_json=VALUES(social_links_json), contact_pages_json=VALUES(contact_pages_json);
                    """, (lead_id, ci.company_name or dossier.company_name, ci.website, json.dumps(ci.emails), json.dumps(ci.phone_numbers), json.dumps(locs), json.dumps(ci.social_links), json.dumps(ci.contact_pages_found)))

                if raw_posts:
                    cur.execute("DELETE FROM raw_posts WHERE lead_id = %s;", (lead_id,))
                    for p in raw_posts:
                        text = p.get("text") if isinstance(p, dict) else str(p)
                        date_val = p.get("posted_at", {}).get("date", "Recent") if isinstance(p, dict) and isinstance(p.get("posted_at"), dict) else (p.get("date", "Recent") if isinstance(p, dict) else "Recent")
                        reactions = p.get("total_reactions", 0) if isinstance(p, dict) else 0
                        p_url = p.get("url", "") if isinstance(p, dict) else ""
                        cur.execute("INSERT INTO raw_posts (lead_id, post_text, post_date, reactions_count, post_url) VALUES (%s, %s, %s, %s, %s);", (lead_id, text, str(date_val), reactions, p_url))
        finally:
            conn.close()

    def get_all_leads(self) -> List[Dict[str, Any]]:
        conn = self.get_mysql_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT l.*, d.overall_score, d.aeo_score, d.geo_score FROM leads l LEFT JOIN lead_dossiers d ON l.id = d.lead_id ORDER BY l.id ASC;")
                return cur.fetchall()
        finally:
            conn.close()

    def get_lead_complete(self, lead_id: int) -> Optional[Dict[str, Any]]:
        conn = self.get_mysql_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM leads WHERE id = %s;", (lead_id,))
                lead_row = cur.fetchone()
                if not lead_row: return None
                result = dict(lead_row)

                cur.execute("SELECT * FROM lead_dossiers WHERE lead_id = %s;", (lead_id,))
                dossier_row = cur.fetchone()
                if dossier_row:
                    result["dossier"] = dict(dossier_row)
                    if dossier_row.get("dossier_json"):
                        try: result["dossier_parsed"] = json.loads(dossier_row["dossier_json"])
                        except Exception: pass

                cur.execute("SELECT * FROM bi_messages WHERE lead_id = %s;", (lead_id,))
                bm_row = cur.fetchone()
                if bm_row:
                    result["bi_messages"] = dict(bm_row)
                    if bm_row.get("target_resonance_points_json"):
                        try: result["bi_messages"]["target_resonance_points"] = json.loads(bm_row["target_resonance_points_json"])
                        except Exception: pass

                cur.execute("SELECT * FROM competitor_analysis WHERE lead_id = %s;", (lead_id,))
                comp_row = cur.fetchone()
                if comp_row:
                    result["competitors"] = dict(comp_row)
                    if comp_row.get("top_competitors_json"):
                        try: result["competitors"]["top_competitors"] = json.loads(comp_row["top_competitors_json"])
                        except Exception: pass

                cur.execute("SELECT * FROM contact_intelligence WHERE lead_id = %s;", (lead_id,))
                contact_row = cur.fetchone()
                if contact_row:
                    result["contact_info"] = dict(contact_row)
                    for fld in ["emails_json", "phone_numbers_json", "locations_json", "social_links_json", "contact_pages_json"]:
                        if contact_row.get(fld):
                            try: result["contact_info"][fld.replace("_json", "")] = json.loads(contact_row[fld])
                            except Exception: pass

                cur.execute("SELECT * FROM raw_posts WHERE lead_id = %s ORDER BY id ASC;", (lead_id,))
                result["raw_posts"] = [dict(p) for p in cur.fetchall()]

                cur.execute("SELECT * FROM company_profile WHERE lead_id = %s;", (lead_id,))
                cp_row = cur.fetchone()
                if cp_row:
                    cp = dict(cp_row)
                    for jfld in ["locations_json", "industries_json", "logos_json", "people_stats_json", "similar_organizations_json", "specialities_json", "raw_company_json"]:
                        if cp.get(jfld):
                            try: cp[jfld.replace("_json", "")] = json.loads(cp[jfld])
                            except Exception: pass
                    result["company_profile"] = cp

                return result
        finally:
            conn.close()

db_manager = DatabaseManager()
