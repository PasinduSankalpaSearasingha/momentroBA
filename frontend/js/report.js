/**
 * MOMENTRO INTELLIGENCE - EXECUTIVE & COMPANY INTELLIGENCE ENGINE
 * Fully API-driven: all company content comes from data, zero hardcoded company specifics.
 */

document.addEventListener('DOMContentLoaded', async () => {
  let globalCompanyData = null;
  let globalPostsData = null;
  let allPosts = [];
  let rawMergedDossier = {};
  let globalLeadData = null;

  // DOM Elements
  const heroCover = document.getElementById('hero-cover');
  const companyLogo = document.getElementById('company-logo');
  const companyName = document.getElementById('company-name');
  const companyTagline = document.getElementById('company-tagline');
  const companyType = document.getElementById('company-type');
  const companyFounded = document.getElementById('company-founded');
  const companyIndustry = document.getElementById('company-industry');
  const companyDescription = document.getElementById('company-description');
  const linkWebsite = document.getElementById('link-website');
  const labelWebsite = document.getElementById('label-website');
  const linkLinkedin = document.getElementById('link-linkedin');
  const specialitiesContainer = document.getElementById('specialities-container');
  const peersContainer = document.getElementById('peers-container');

  // Lead Card Elements
  const execName = document.getElementById('exec-name');
  const execTitle = document.getElementById('exec-title');
  const execAvatar = document.getElementById('exec-avatar');
  const execQuals = document.getElementById('exec-quals');
  const execSector = document.getElementById('exec-sector');

  // KPI Elements
  const kpiEmployees = document.getElementById('kpi-employees');
  const kpiFollowers = document.getElementById('kpi-followers');
  const kpiLocations = document.getElementById('kpi-locations');
  const kpiTechShare = document.getElementById('kpi-tech-share');
  const kpiPostsCount = document.getElementById('kpi-posts-count');
  const postsTabCounter = document.getElementById('posts-tab-counter');

  // Posts Feed Elements
  const postsContainer = document.getElementById('posts-container');
  const postSearchInput = document.getElementById('post-search-input');
  const postSortSelect = document.getElementById('post-sort-select');
  const postMediaFilter = document.getElementById('post-media-filter');
  const postsShowingCount = document.getElementById('posts-showing-count');

  // Modal Elements
  const postModal = document.getElementById('post-modal');
  const btnCloseModal = document.getElementById('btn-close-modal');
  const modalAuthorLogo = document.getElementById('modal-author-logo');
  const modalAuthorName = document.getElementById('modal-author-name');
  const modalPostTime = document.getElementById('modal-post-time');
  const modalImageWrapper = document.getElementById('modal-image-wrapper');
  const modalPostImage = document.getElementById('modal-post-image');
  const modalPostText = document.getElementById('modal-post-text');
  const modalReactions = document.getElementById('modal-reactions');
  const modalLinkedinBtn = document.getElementById('modal-linkedin-btn');

  // Raw JSON Modal Elements
  const rawModal = document.getElementById('raw-modal');
  const btnViewRaw = document.getElementById('btn-view-raw');
  const btnCloseRawModal = document.getElementById('btn-close-raw-modal');
  const btnDismissRaw = document.getElementById('btn-dismiss-raw');
  const rawJsonCode = document.getElementById('raw-json-code');
  const btnCopyRaw = document.getElementById('btn-copy-raw');
  const btnExportJson = document.getElementById('btn-export-json');
  const btnPrint = document.getElementById('btn-print');

  /* ===================================================================
     1. ROBUST DATA INGESTION ENGINE (Auto-detection + Offline Fallback)
     =================================================================== */
  async function loadIntelligenceData() {
    let companyRaw = null;
    let postsRaw = null;
    let leadMeta = null;

    // ── STEP 0: Check for ?lead_id=X in URL — load from API if present ──
    const urlParams = new URLSearchParams(window.location.search);
    const leadIdParam = urlParams.get('lead_id');

    // Robust API Base resolution (same-origin when on 8080, http://127.0.0.1:8080 when on file:// or other port)
    const isHttp = window.location.protocol === 'http:' || window.location.protocol === 'https:';
    const apiBase = isHttp
      ? (window.location.port === '8080' ? '' : `${window.location.protocol}//${window.location.hostname || '127.0.0.1'}:8080`)
      : 'http://127.0.0.1:8080';

    const resolveReportUrl = (url) => {
      if (!url) return url;
      if (url.startsWith('/')) {
        return apiBase ? `${apiBase}${url}` : url;
      }
      return url;
    };

    const fetchWithTimeout = (url, ms = 7000) => {
      const finalUrl = resolveReportUrl(url);
      return Promise.race([
        fetch(finalUrl),
        new Promise((_, r) => setTimeout(() => r(new Error('timeout')), ms))
      ]);
    };

    if (leadIdParam) {
      try {
        const metaRes = await fetch(`${apiBase}/api/leads/${leadIdParam}/report-urls`);
        if (metaRes.ok) {
          const meta = await metaRes.json();
          leadMeta = {
            id: meta.lead_id,
            full_name: meta.full_name || null,
            job_title: meta.job_title || null,
            company_name: meta.company_name || null,
            company_report_url: meta.company_report_url || null,
            posts_report_url: meta.posts_report_url || null,
            linkedin_url: null
          };

          // Fetch company report (handles relative endpoints, S3 URLs, and local fallback)
          if (meta.company_report_url) {
            try {
              let r = await fetchWithTimeout(meta.company_report_url);
              if (!r.ok) {
                r = await fetchWithTimeout(`${apiBase}/api/leads/${leadIdParam}/company-report`);
              }
              if (r && r.ok) companyRaw = await r.json();
            } catch (e) {
              try {
                const r2 = await fetchWithTimeout(`${apiBase}/api/leads/${leadIdParam}/company-report`);
                if (r2.ok) companyRaw = await r2.json();
              } catch (e2) {
                console.warn('Company fetch failed:', e2);
              }
            }
          }

          // Fetch posts report
          if (meta.posts_report_url) {
            try {
              let r = await fetchWithTimeout(meta.posts_report_url);
              if (!r.ok) {
                r = await fetchWithTimeout(`${apiBase}/api/leads/${leadIdParam}/posts-report`);
              }
              if (r && r.ok) postsRaw = await r.json();
            } catch (e) {
              try {
                const r2 = await fetchWithTimeout(`${apiBase}/api/leads/${leadIdParam}/posts-report`);
                if (r2.ok) postsRaw = await r2.json();
              } catch (e2) {
                console.warn('Posts fetch failed:', e2);
              }
            }
          }
        }
      } catch (apiErr) {
        console.warn('API lead lookup failed, falling back to scraped_profiles:', apiErr);
      }

      // Direct fallback if meta didn't supply valid company data
      if (!companyRaw) {
        try {
          const r = await fetchWithTimeout(`${apiBase}/api/leads/${leadIdParam}/company-report`);
          if (r.ok) companyRaw = await r.json();
        } catch (e) {}
      }
      if (!postsRaw) {
        try {
          const r = await fetchWithTimeout(`${apiBase}/api/leads/${leadIdParam}/posts-report`);
          if (r.ok) postsRaw = await r.json();
        } catch (e) {}
      }
    }

    // ── STEP A: scraped_profiles JSON (used when no lead_id in URL) ──
    if (!companyRaw && !leadIdParam) {
      try {
        let profiles = null;
        try {
          const pRes = await fetch('../scraped_profiles (2).json');
          if (pRes.ok) profiles = await pRes.json();
        } catch (e) {
          try {
            const pRes2 = await fetch('./scraped_profiles (2).json');
            if (pRes2.ok) profiles = await pRes2.json();
          } catch (e2) {}
        }

        if (profiles && profiles.leads && profiles.leads.length > 0) {
          leadMeta = profiles.leads[0];
          const url1 = leadMeta.company_report_url;
          const url2 = leadMeta.posts_report_url;

          const fetchWithTimeout = (url, timeoutMs = 6000) => {
            return Promise.race([
              fetch(url),
              new Promise((_, reject) => setTimeout(() => reject(new Error('Fetch timeout')), timeoutMs))
            ]);
          };

          try {
            const [res1, res2] = await Promise.all([
              fetchWithTimeout(url1),
              fetchWithTimeout(url2)
            ]);
            const d1 = await res1.json();
            const d2 = await res2.json();

            if (d1.company || d1.universalName) {
              companyRaw = d1; postsRaw = d2;
            } else if (d2.company || d2.universalName) {
              companyRaw = d2; postsRaw = d1;
            } else {
              companyRaw = d1; postsRaw = d2;
            }
          } catch (s3Err) {
            console.warn('S3 fetch unavailable, switching to local cached fallback:', s3Err);
          }
        }
      } catch (rootErr) {
        console.warn('Failed querying initial config, falling back to local dataset:', rootErr);
      }
    }

    // Step B: Offline/Local Fallbacks if S3 data is not loaded
    if (!companyRaw) {
      try {
        const cRes = await fetch('./data/company_report.json');
        if (cRes.ok) {
          companyRaw = await cRes.json();
        } else {
          const sRes = await fetch('./data/sample_company.json');
          companyRaw = await sRes.json();
        }
      } catch (err) {
        const sRes = await fetch('./data/sample_company.json');
        companyRaw = await sRes.json();
      }
    }

    if (!postsRaw) {
      try {
        const pRes = await fetch('./data/posts_report.json');
        if (pRes.ok) {
          postsRaw = await pRes.json();
        }
      } catch (err) {
        console.warn('Using embedded post dataset fallback');
      }
    }

    // Unify Lead & Company references
    const company = companyRaw.company || companyRaw;
    
    // Extract posts array
    let postsList = [];
    if (postsRaw && postsRaw.posts && Array.isArray(postsRaw.posts)) {
      postsList = postsRaw.posts;
    } else if (companyRaw.company_posts && Array.isArray(companyRaw.company_posts)) {
      postsList = companyRaw.company_posts;
    } else if (companyRaw.posts && Array.isArray(companyRaw.posts)) {
      postsList = companyRaw.posts;
    }

    // Build lead meta from scraped_profiles OR from the company data itself — no hardcoded name
    if (!leadMeta) {
      leadMeta = {
        full_name: companyRaw.full_name || null,
        job_title: companyRaw.job_title || null,
        sector_tag: companyRaw.sector_tag || null,
        location: companyRaw.location || null,
        linkedin_url: companyRaw.lead_linkedin_url || company.linkedinUrl || null
      };
    }

    return { company, posts: postsList, lead: leadMeta, rawCompany: companyRaw, rawPosts: postsRaw };
  }

  /* ===================================================================
     2. RENDER HERO, KPIS, & METADATA — fully from data, no hardcoded strings
     =================================================================== */
  function renderProfile(company, lead) {
    const name = company.name || 'Unknown Company';
    const universalId = company.universalName || '';

    // Page title & breadcrumb
    document.title = `Momentro Intelligence | ${name}`;
    const breadcrumbEl = document.getElementById('breadcrumb-company');
    if (breadcrumbEl) breadcrumbEl.textContent = name;

    companyName.textContent = name;
    companyTagline.textContent = company.tagline || company.slogan || '';
    companyType.textContent = company.companyType || '';

    if (company.foundedOn?.year) {
      companyFounded.textContent = `Est. ${company.foundedOn.year}`;
    } else {
      companyFounded.style.display = 'none';
    }

    if (company.industries && company.industries.length > 0) {
      companyIndustry.textContent = company.industries[0].name || company.industries[0].title || '';
    }

    // Logo — try logo field, then logos array
    const logoUrl = company.logo || (company.logos && company.logos[0]?.url) || null;
    if (logoUrl) {
      companyLogo.src = logoUrl;
      companyLogo.alt = name;
    } else {
      companyLogo.style.display = 'none';
    }

    // Background cover
    if (company.backgroundCover) {
      heroCover.style.backgroundImage = `url("${company.backgroundCover}")`;
    } else if (company.backgroundCovers && company.backgroundCovers.length > 0) {
      heroCover.style.backgroundImage = `url("${company.backgroundCovers[0].url}")`;
    }

    // Website link
    const websiteUrl = company.website || company.callToActionUrl || null;
    if (websiteUrl) {
      linkWebsite.href = websiteUrl;
      try {
        const urlObj = new URL(websiteUrl);
        labelWebsite.textContent = urlObj.hostname.replace('www.', '');
      } catch (e) {
        labelWebsite.textContent = websiteUrl;
      }
    } else {
      linkWebsite.style.display = 'none';
    }

    // LinkedIn link
    const linkedinUrl = company.linkedinUrl || null;
    if (linkedinUrl) {
      linkLinkedin.href = linkedinUrl;
    } else {
      linkLinkedin.style.display = 'none';
    }

    // Primary location in hero meta strip
    const companyLocationEl = document.getElementById('company-primary-location');
    if (companyLocationEl && company.locations && company.locations.length > 0) {
      const primaryLoc = company.locations.find(l => l.headquarter) || company.locations[0];
      const parsed = primaryLoc.parsed;
      if (parsed) {
        companyLocationEl.textContent = parsed.text || [parsed.city || primaryLoc.city || '', parsed.country || primaryLoc.country || ''].filter(Boolean).join(', ');
      } else {
        companyLocationEl.textContent = [primaryLoc.city || '', primaryLoc.country || ''].filter(Boolean).join(', ');
      }
    } else if (companyLocationEl) {
      companyLocationEl.style.display = 'none';
    }

    // Lead / Executive Card
    renderExecCard(lead, company);

    // Company description & taxonomy
    companyDescription.textContent = company.description || '';

    const specLegalName = document.getElementById('spec-legal-name');
    const specUniversalId = document.getElementById('spec-universal-id');
    const specStructure = document.getElementById('spec-structure');
    const specFounded = document.getElementById('spec-founded');
    const specIndustry = document.getElementById('spec-industry');
    const specHierarchy = document.getElementById('spec-hierarchy');

    if (specLegalName) specLegalName.textContent = name;
    if (specUniversalId) specUniversalId.textContent = universalId;
    if (specStructure) specStructure.textContent = company.companyType || '\u2014';
    if (specFounded) specFounded.textContent = company.foundedOn?.year || '\u2014';

    if (company.industries && company.industries[0]) {
      if (specIndustry) specIndustry.textContent = company.industries[0].name || company.industries[0].title || '';
      if (specHierarchy) specHierarchy.textContent = company.industries[0].hierarchy || '';
    }

    // Dynamically render Operating Offices spec-row
    const specOfficesRow = document.getElementById('spec-offices-row');
    if (specOfficesRow && company.locations) {
      const locationCount = company.locations.length;
      const countryList = [...new Set(company.locations.map(l => l.parsed?.country || l.country).filter(Boolean))].join(' & ');
      specOfficesRow.textContent = locationCount > 0 ? `${locationCount} (${countryList})` : '\u2014';
    }

    // Dynamically render Official Website spec-row
    const specWebsiteLink = document.getElementById('spec-website-link');
    if (specWebsiteLink && websiteUrl) {
      specWebsiteLink.href = websiteUrl;
      specWebsiteLink.textContent = websiteUrl;
    }

    // Strategic highlight card from data
    renderStrategicCard(company);

    // Specialities Tags
    if (company.specialities && Array.isArray(company.specialities)) {
      specialitiesContainer.innerHTML = '';
      company.specialities.forEach(spec => {
        const tag = document.createElement('span');
        tag.className = 'spec-tag';
        tag.textContent = spec;
        specialitiesContainer.appendChild(tag);
      });
    }

    // Similar Organizations / Peers
    if (company.similarOrganizations && Array.isArray(company.similarOrganizations)) {
      peersContainer.innerHTML = '';
      const peerIntro = document.getElementById('peers-intro-text');
      if (peerIntro && company.industries && company.industries[0]) {
        peerIntro.textContent = `The following organizations operate in adjacent ${company.industries[0].name || 'industry'} verticals.`;
      }
      company.similarOrganizations.forEach(org => {
        const card = document.createElement('div');
        card.className = 'peer-card';
        const initials = (org.name || 'Org').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
        const orgIndustry = (org.industries && org.industries[0]) ? (org.industries[0].name || org.industries[0].title) : 'Technology';
        card.innerHTML = `
          <div class="peer-avatar">${initials}</div>
          <div class="peer-info">
            <div class="peer-name" title="${escapeHtml(org.name || '')}">${escapeHtml(org.name || '')}</div>
            <div class="peer-tag">${escapeHtml(orgIndustry)}</div>
          </div>
        `;
        peersContainer.appendChild(card);
      });
    }

    // KPIs
    kpiEmployees.textContent = company.employeeCount != null ? company.employeeCount.toLocaleString() : '\u2014';
    kpiFollowers.textContent = company.followerCount != null ? company.followerCount.toLocaleString() : '\u2014';
    kpiLocations.textContent = company.locations ? company.locations.length : '\u2014';

    // KPI subtext: employee range
    const kpiEmployeeSubtext = document.getElementById('kpi-employee-subtext');
    if (kpiEmployeeSubtext && company.employeeCountRange) {
      const r = company.employeeCountRange;
      kpiEmployeeSubtext.textContent = `Range: ${r.start}\u2013${r.end}`;
    }

    // KPI subtext: HQ location
    const kpiLocationSubtext = document.getElementById('kpi-location-subtext');
    if (kpiLocationSubtext && company.locations && company.locations.length > 0) {
      const hq = company.locations.find(l => l.headquarter);
      if (hq) {
        kpiLocationSubtext.textContent = `HQ: ${hq.parsed?.text || hq.city || hq.country || ''}`;
      }
    }

    // Footer
    const footerMeta = document.getElementById('footer-meta');
    if (footerMeta) {
      const dossierId = universalId || name.toLowerCase().replace(/\s+/g, '-');
      footerMeta.textContent = `Dossier: ${dossierId} \u2022 Confidential \u2022 Generated for Enterprise Analysis`;
    }
  }

  /* -------------------------------------------------------------------
     Render the Executive Lead Card from lead data
     ------------------------------------------------------------------- */
  function renderExecCard(lead, company) {
    const execCardEl = document.getElementById('executive-card');
    if (!lead || (!lead.full_name && !lead.name)) {
      if (execCardEl) execCardEl.style.display = 'none';
      return;
    }

    const rawName = lead.full_name || lead.name || '';
    const cleanName = rawName.split('(')[0].trim();
    const qualsMatch = rawName.match(/\((.*?)\)/);

    if (execName) execName.textContent = cleanName;
    if (qualsMatch && qualsMatch[1]) {
      if (execQuals) execQuals.textContent = qualsMatch[1];
    } else {
      const execQualsRow = document.getElementById('exec-quals-row');
      if (execQualsRow) execQualsRow.style.display = 'none';
    }

    if (execTitle) execTitle.textContent = lead.job_title || lead.title || '';
    if (execSector) {
      if (lead.sector_tag) {
        execSector.textContent = lead.sector_tag;
      } else {
        const execSectorRow = document.getElementById('exec-sector-row');
        if (execSectorRow) execSectorRow.style.display = 'none';
      }
    }

    if (execAvatar) {
      const initials = cleanName.split(' ').map(w => w[0]).filter(Boolean).slice(0, 2).join('').toUpperCase();
      execAvatar.textContent = initials || '?';
    }

    const execLinkedinBtn = document.getElementById('exec-linkedin-btn');
    const linkedinUrl = lead.linkedin_url || lead.linkedinUrl || null;
    if (execLinkedinBtn) {
      if (linkedinUrl) {
        execLinkedinBtn.href = linkedinUrl;
      } else {
        execLinkedinBtn.style.display = 'none';
      }
    }
  }

  /* -------------------------------------------------------------------
     Render Strategic Highlight Card from company data
     ------------------------------------------------------------------- */
  function renderStrategicCard(company) {
    const stratCard = document.getElementById('strategic-highlight-card');
    if (!stratCard) return;

    const tagline = company.tagline || company.slogan;
    const industryVal = company.industries && company.industries[0] ? company.industries[0].name : null;
    const specialitiesList = company.specialities || [];

    let title = tagline || (industryVal ? `${industryVal} Organization` : 'Company Profile');
    let bodyText = '';

    if (company.description) {
      const firstSentence = company.description.split(/[.!?]/)[0].trim();
      bodyText = firstSentence + (firstSentence ? '.' : '');
    } else if (specialitiesList.length > 0) {
      bodyText = `Core specializations include: ${specialitiesList.slice(0, 4).join(', ')}.`;
    }

    const stratTitle = document.getElementById('strat-card-title');
    const stratText = document.getElementById('strat-card-text');
    if (stratTitle) stratTitle.textContent = title;
    if (stratText) stratText.textContent = bodyText;
    if (!title && !bodyText) stratCard.style.display = 'none';
  }

  /* ===================================================================
     3. RENDER TALENT & WORKFORCE ANALYTICS
     =================================================================== */
  function renderTalentAnalytics(company) {
    // Update workforce header badge dynamically
    const workforceBadge = document.getElementById('workforce-badge');
    if (workforceBadge) {
      if (company.employeeCount) {
        workforceBadge.textContent = `${company.employeeCount.toLocaleString()} Employees`;
      } else if (company.employeeCountRange) {
        const r = company.employeeCountRange;
        workforceBadge.textContent = `${r.start}\u2013${r.end} Employees`;
      }
    }

    if (!company.peopleStats || !Array.isArray(company.peopleStats)) return;

    // A. Department Function
    const funcStat = company.peopleStats.find(s => s.statTitle === 'Current Function');
    const deptContainer = document.getElementById('dept-distribution');
    if (funcStat && funcStat.values && deptContainer) {
      deptContainer.innerHTML = '';
      const totalDeptStaff = funcStat.values.reduce((sum, v) => sum + v.count, 0) || 1;

      // Update engineering share KPI
      const engEntry = funcStat.values.find(v => v.title === 'Engineering');
      if (engEntry) {
        const engShare = Math.round((engEntry.count / totalDeptStaff) * 100);
        kpiTechShare.textContent = `${engShare}%`;
        const kpiTechSubtext = document.getElementById('kpi-tech-subtext');
        if (kpiTechSubtext) kpiTechSubtext.textContent = `${engEntry.count} Engineers`;
      } else {
        kpiTechShare.textContent = '\u2014';
      }

      funcStat.values.slice(0, 8).forEach(item => {
        const pct = Math.round((item.count / totalDeptStaff) * 100);
        const barItem = document.createElement('div');
        barItem.className = 'bar-item';
        barItem.innerHTML = `
          <div class="bar-label-row">
            <span class="bar-dept">${escapeHtml(item.title)}</span>
            <span class="bar-count">${item.count} team members (${pct}%)</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width: ${pct}%"></div>
          </div>
        `;
        deptContainer.appendChild(barItem);
      });
    }

    // B. Top Engineering Skills
    const skillStat = company.peopleStats.find(s => s.statTitle === 'Skill Explicit');
    const skillsContainer = document.getElementById('skills-distribution');
    if (skillStat && skillStat.values && skillsContainer) {
      skillsContainer.innerHTML = '';
      skillStat.values.slice(0, 14).forEach(sk => {
        const pill = document.createElement('span');
        pill.className = 'skill-pill';
        pill.innerHTML = `
          <span class="skill-name">${escapeHtml(sk.title)}</span>
          <span class="skill-count">${sk.count}</span>
        `;
        skillsContainer.appendChild(pill);
      });
    }

    // C. Academic Pipelines
    const schoolStat = company.peopleStats.find(s => s.statTitle === 'School');
    const schoolContainer = document.getElementById('academic-pipeline');
    if (schoolStat && schoolStat.values && schoolContainer) {
      schoolContainer.innerHTML = '';
      schoolStat.values.slice(0, 6).forEach(sch => {
        const item = document.createElement('div');
        item.className = 'pipeline-item';
        item.innerHTML = `
          <span class="pipeline-name">${escapeHtml(sch.title)}</span>
          <span class="pipeline-count">${sch.count} Alumni</span>
        `;
        schoolContainer.appendChild(item);
      });
    }
  }

  /* ===================================================================
     4. RENDER GLOBAL MAP — fully dynamic from company.locations data
     =================================================================== */
  // Country coordinate lookup (lat, lng) for equirectangular projection
  const COUNTRY_COORDS = {
    'US': { lat: 39.5, lng: -98.35 }, 'GB': { lat: 51.5, lng: -0.12 },
    'LK': { lat: 7.87, lng: 80.77 }, 'IN': { lat: 20.59, lng: 78.96 },
    'AU': { lat: -25.27, lng: 133.77 }, 'CA': { lat: 56.13, lng: -106.35 },
    'DE': { lat: 51.17, lng: 10.45 }, 'FR': { lat: 46.23, lng: 2.21 },
    'SG': { lat: 1.35, lng: 103.82 }, 'AE': { lat: 23.42, lng: 53.85 },
    'JP': { lat: 36.2, lng: 138.25 }, 'CN': { lat: 35.86, lng: 104.19 },
    'BR': { lat: -14.24, lng: -51.93 }, 'ZA': { lat: -30.56, lng: 22.94 },
    'NG': { lat: 9.08, lng: 8.68 }, 'NL': { lat: 52.13, lng: 5.29 },
    'SE': { lat: 60.13, lng: 18.64 }, 'NO': { lat: 60.47, lng: 8.47 },
    'CH': { lat: 46.82, lng: 8.23 }, 'PK': { lat: 30.38, lng: 69.35 },
    'BD': { lat: 23.68, lng: 90.36 }, 'PH': { lat: 12.88, lng: 121.77 },
    'ID': { lat: -0.79, lng: 113.92 }, 'MY': { lat: 4.21, lng: 101.98 },
    'NZ': { lat: -40.90, lng: 174.89 }, 'MX': { lat: 23.63, lng: -102.55 },
    'AR': { lat: -38.42, lng: -63.62 }, 'KE': { lat: -0.02, lng: 37.91 },
    'EG': { lat: 26.82, lng: 30.80 }, 'IT': { lat: 41.87, lng: 12.57 },
    'ES': { lat: 40.46, lng: -3.75 }, 'PT': { lat: 39.40, lng: -8.22 },
    'PL': { lat: 51.92, lng: 19.15 }, 'RU': { lat: 61.52, lng: 105.32 },
    'KR': { lat: 35.91, lng: 127.77 }, 'TH': { lat: 15.87, lng: 100.99 },
    'VN': { lat: 14.06, lng: 108.28 }, 'GH': { lat: 7.95, lng: -1.02 },
  };

  // City coordinate lookup (lat, lng) for common cities
  const CITY_COORDS = {
    'wyoming': { lat: 43.08, lng: -107.29 }, 'new york': { lat: 40.71, lng: -74.01 },
    'san francisco': { lat: 37.77, lng: -122.42 }, 'los angeles': { lat: 34.05, lng: -118.24 },
    'chicago': { lat: 41.88, lng: -87.63 }, 'houston': { lat: 29.76, lng: -95.37 },
    'austin': { lat: 30.27, lng: -97.74 }, 'seattle': { lat: 47.61, lng: -122.33 },
    'boston': { lat: 42.36, lng: -71.06 }, 'london': { lat: 51.51, lng: -0.13 },
    'paris': { lat: 48.86, lng: 2.35 }, 'berlin': { lat: 52.52, lng: 13.40 },
    'amsterdam': { lat: 52.37, lng: 4.90 }, 'stockholm': { lat: 59.33, lng: 18.07 },
    'zurich': { lat: 47.38, lng: 8.54 }, 'toronto': { lat: 43.65, lng: -79.38 },
    'vancouver': { lat: 49.28, lng: -123.12 }, 'sydney': { lat: -33.87, lng: 151.21 },
    'melbourne': { lat: -37.81, lng: 144.96 }, 'singapore': { lat: 1.35, lng: 103.82 },
    'dubai': { lat: 25.20, lng: 55.27 }, 'abu dhabi': { lat: 24.47, lng: 54.37 },
    'tokyo': { lat: 35.69, lng: 139.69 }, 'mumbai': { lat: 19.08, lng: 72.88 },
    'bangalore': { lat: 12.97, lng: 77.59 }, 'delhi': { lat: 28.61, lng: 77.21 },
    'hyderabad': { lat: 17.39, lng: 78.49 }, 'pune': { lat: 18.52, lng: 73.86 },
    'chennai': { lat: 13.08, lng: 80.27 }, 'colombo': { lat: 6.93, lng: 79.86 },
    'nairobi': { lat: -1.29, lng: 36.82 }, 'cape town': { lat: -33.93, lng: 18.42 },
    'johannesburg': { lat: -26.20, lng: 28.04 }, 'lagos': { lat: 6.52, lng: 3.38 },
    'cairo': { lat: 30.06, lng: 31.25 }, 'accra': { lat: 5.56, lng: -0.20 },
    'karachi': { lat: 24.86, lng: 67.01 }, 'dhaka': { lat: 23.81, lng: 90.41 },
    'manila': { lat: 14.60, lng: 120.98 }, 'jakarta': { lat: -6.21, lng: 106.85 },
    'kuala lumpur': { lat: 3.14, lng: 101.69 }, 'beijing': { lat: 39.91, lng: 116.39 },
    'shanghai': { lat: 31.23, lng: 121.47 }, 'seoul': { lat: 37.57, lng: 126.98 },
    'mexico city': { lat: 19.43, lng: -99.13 }, 'sao paulo': { lat: -23.55, lng: -46.63 },
  };

  function getLocationCoords(loc) {
    const city = (loc.city || loc.parsed?.city || '').toLowerCase().trim();
    const country = (loc.country || loc.parsed?.countryCode || '').toUpperCase().trim();
    if (city && CITY_COORDS[city]) return CITY_COORDS[city];
    for (const [knownCity, coords] of Object.entries(CITY_COORDS)) {
      if (city && (city.includes(knownCity) || knownCity.includes(city))) return coords;
    }
    if (country && COUNTRY_COORDS[country]) return COUNTRY_COORDS[country];
    return null;
  }

  async function initWorldMap(company) {
    const mapContainer = document.getElementById('map-svg-container');
    if (!mapContainer) return;

    const locations = (company && company.locations) ? company.locations : [];

    try {
      const res = await fetch('./images/world_map.svg');
      if (!res.ok) throw new Error('Could not fetch world_map.svg');
      const svgText = await res.text();
      mapContainer.innerHTML = svgText;

      const svg = mapContainer.querySelector('svg');
      if (!svg) return;

      const pinsLayer = svg.querySelector('#map-pins-layer') || svg;

      function project(lat, lng) {
        return {
          x: Math.round(((lng + 180) * (1000 / 360)) * 10) / 10,
          y: Math.round(((90 - lat) * (500 / 180)) * 10) / 10
        };
      }

      // Render dynamic map zoom buttons
      renderMapControls(svg, locations, project);

      function createPin(coords, label, sublabel, cardId, isHq = false) {
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', 'map-pin-group');
        g.setAttribute('id', `pin-${cardId}`);
        g.style.cursor = 'pointer';

        const pulse = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        pulse.setAttribute('cx', coords.x); pulse.setAttribute('cy', coords.y);
        pulse.setAttribute('r', '8'); pulse.setAttribute('fill', 'none');
        pulse.setAttribute('stroke', isHq ? '#3b82f6' : '#0ea5e9');
        pulse.setAttribute('stroke-width', '1.5');
        pulse.setAttribute('class', 'map-pin-pulse');
        g.appendChild(pulse);

        const core = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        core.setAttribute('cx', coords.x); core.setAttribute('cy', coords.y);
        core.setAttribute('r', '5'); core.setAttribute('class', 'map-pin-core');
        g.appendChild(core);

        const textTitle = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        textTitle.setAttribute('x', coords.x + 10); textTitle.setAttribute('y', coords.y - 4);
        textTitle.setAttribute('class', 'map-pin-label'); textTitle.textContent = label;
        g.appendChild(textTitle);

        const textSub = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        textSub.setAttribute('x', coords.x + 10); textSub.setAttribute('y', coords.y + 10);
        textSub.setAttribute('class', 'map-pin-sublabel'); textSub.textContent = sublabel;
        g.appendChild(textSub);

        g.addEventListener('click', () => {
          const card = document.getElementById(cardId);
          if (card) {
            card.scrollIntoView({ behavior: 'smooth', block: 'center' });
            card.style.borderColor = '#3b82f6';
            card.style.boxShadow = '0 0 20px rgba(59, 130, 246, 0.4)';
            setTimeout(() => { card.style.borderColor = ''; card.style.boxShadow = ''; }, 2500);
          }
        });
        return g;
      }

      // Place a pin for each company location
      locations.forEach((loc, idx) => {
        const coords = getLocationCoords(loc);
        if (!coords) return;
        const projected = project(coords.lat, coords.lng);
        const isHq = loc.headquarter === true;
        const city = loc.city || loc.parsed?.city || loc.country || 'Office';
        const countryCode = loc.country || loc.parsed?.countryCode || '';
        const label = [city, countryCode].filter(Boolean).join(', ');
        const sublabel = isHq ? 'Corporate HQ' : (loc.description || 'Regional Office');
        const cardId = `office-card-${idx}`;
        pinsLayer.appendChild(createPin(projected, label, sublabel, cardId, isHq));
      });

      // Update active hubs badge
      const hubsBadge = document.querySelector('.map-overlay-badge');
      if (hubsBadge) {
        const pinCount = locations.length;
        hubsBadge.innerHTML = `<span class="status-dot"></span> ${pinCount} Active Global ${pinCount === 1 ? 'Hub' : 'Hubs'}`;
      }

    } catch (err) {
      console.warn('Map initialization note:', err);
    }
  }

  function renderMapControls(svg, locations, project) {
    const mapControlsContainer = document.getElementById('map-controls-dynamic');
    const btnZoomReset = document.getElementById('map-zoom-reset');

    if (mapControlsContainer) {
      mapControlsContainer.innerHTML = '';
      locations.forEach((loc, idx) => {
        const coords = getLocationCoords(loc);
        if (!coords) return;
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-outline btn-xs';
        btn.id = `map-zoom-loc-${idx}`;
        const city = loc.city || loc.parsed?.city || '';
        const countryCode = loc.country || loc.parsed?.countryCode || '';
        btn.textContent = [city, countryCode].filter(Boolean).join(', ') || 'Location';
        btn.addEventListener('click', () => {
          const projected = project(coords.lat, coords.lng);
          const vbX = Math.max(0, projected.x - 150);
          const vbY = Math.max(0, projected.y - 100);
          svg.setAttribute('viewBox', `${vbX} ${vbY} 300 200`);
        });
        mapControlsContainer.appendChild(btn);
      });
    }

    if (btnZoomReset) {
      btnZoomReset.addEventListener('click', () => {
        svg.setAttribute('viewBox', '0 0 1000 500');
      });
    }
  }

  /* -------------------------------------------------------------------
     Render dynamic office/location cards in the Global Footprint tab
     ------------------------------------------------------------------- */
  function renderLocationCards(company) {
    const locationsGrid = document.getElementById('locations-cards-grid');
    if (!locationsGrid) return;

    const locations = company.locations || [];
    if (locations.length === 0) { locationsGrid.style.display = 'none'; return; }

    locationsGrid.innerHTML = '';
    locations.forEach((loc, idx) => {
      const isHq = loc.headquarter === true;
      const countryCode = loc.country || loc.parsed?.countryCode || '??';
      const city = loc.city || loc.parsed?.city || '';
      const country = loc.parsed?.countryFull || loc.parsed?.country || loc.country || '';
      const cityCountry = [city, country].filter(Boolean).join(', ');
      const description = loc.description || (isHq ? 'Headquarters' : 'Regional Office');
      const postalCode = loc.postalCode || '';
      const state = loc.parsed?.state || loc.geographicArea || '';

      const card = document.createElement('div');
      card.className = 'office-card';
      card.id = `office-card-${idx}`;

      const badgeClass = isHq ? 'badge-primary' : 'badge-neutral';
      const badgeLabel = isHq ? 'Corporate Headquarters' : 'Regional Office';

      card.innerHTML = `
        <div class="office-header">
          <div class="office-flag-box">
            <span class="country-code">${escapeHtml(countryCode)}</span>
          </div>
          <div class="office-identity">
            <span class="badge ${badgeClass}">${badgeLabel}</span>
            <h3 class="office-city">${escapeHtml(cityCountry || countryCode)}</h3>
            <p class="office-role">${escapeHtml(description)}</p>
          </div>
        </div>
        <div class="office-specs">
          ${state ? `<div class="spec-row"><span class="spec-name">Region / State</span><span class="spec-data">${escapeHtml(state)}</span></div>` : ''}
          ${postalCode ? `<div class="spec-row"><span class="spec-name">Postal Code</span><span class="spec-data">${escapeHtml(postalCode)}</span></div>` : ''}
          ${countryCode ? `<div class="spec-row"><span class="spec-name">Country Code</span><span class="spec-data">${escapeHtml(countryCode)}</span></div>` : ''}
        </div>
      `;
      locationsGrid.appendChild(card);
    });
  }

  /* ===================================================================
     5. RENDER POSTS FEED (Strictly Monochrome Icons - Zero Colored Emojis)
     =================================================================== */
  function renderPostsFeed(posts, company) {
    allPosts = posts || [];
    kpiPostsCount.textContent = allPosts.length;
    postsTabCounter.textContent = allPosts.length;
    applyPostFilters(company);
  }

  function applyPostFilters(company) {
    const searchTerm = (postSearchInput?.value || '').toLowerCase().trim();
    const sortMode = postSortSelect?.value || 'recent';
    const mediaMode = postMediaFilter?.value || 'all';

    let filtered = allPosts.filter(p => {
      const text = (p.text || p.content || '').toLowerCase();
      if (searchTerm && !text.includes(searchTerm)) return false;
      const hasImage = Boolean(p.image_url || (p.media && p.media.images && p.media.images.length > 0));
      if (mediaMode === 'image' && !hasImage) return false;
      return true;
    });

    if (sortMode === 'reactions') {
      filtered.sort((a, b) => {
        const rA = a.stats?.total_reactions ?? a.total_reactions ?? 0;
        const rB = b.stats?.total_reactions ?? b.total_reactions ?? 0;
        return rB - rA;
      });
    }

    if (postsShowingCount) {
      postsShowingCount.textContent = `Showing ${filtered.length} of ${allPosts.length} verified publications`;
    }

    postsContainer.innerHTML = '';
    if (filtered.length === 0) {
      postsContainer.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 3rem; text-align: center; color: var(--text-muted);">
          <svg class="icon-lg" style="margin-bottom: 0.5rem; stroke: var(--text-muted);"><use href="#icon-search"></use></svg>
          <p>No publications matched your search criteria.</p>
        </div>
      `;
      return;
    }

    // Use company data for fallback author info — no hardcoded names
    const companyDisplayName = company?.name || '';
    const companyLogoUrl = company?.logo || (company?.logos && company.logos[0]?.url) || null;

    filtered.forEach((post) => {
      const card = document.createElement('div');
      card.className = 'post-card';
      card.tabIndex = 0;

      const postText = post.text || post.content || '';
      const timeStr = post.posted_at?.relative || post.posted_at?.text
        || post.postedAt?.postedAgoShort || post.postedAt?.postedAgoText
        || post.date || 'Recent';

      const totalReactions = post.stats?.total_reactions ?? post.total_reactions ?? 0;
      const likesCount = post.stats?.like ?? totalReactions;
      const repostsCount = post.stats?.reposts ?? post.reposts ?? 0;

      // Image resolution
      let imgUrl = null;
      if (post.media && post.media.images && post.media.images.length > 0) {
        imgUrl = post.media.images[0].url;
      } else if (post.image_url) {
        imgUrl = post.image_url;
      }

      // Author info from post data, fall back to company info
      const authorImg = post.author?.profile_picture || post.author?.avatar?.url || companyLogoUrl || '';
      const authorName = post.author
        ? (post.author.name || `${post.author.first_name || ''} ${post.author.last_name || ''}`.trim() || companyDisplayName)
        : companyDisplayName;

      let mediaHtml = '';
      if (imgUrl) {
        mediaHtml = `
          <div class="post-media-container">
            <img class="post-media-img" src="${imgUrl}" alt="Publication visual" loading="lazy" />
          </div>
        `;
      }

      card.innerHTML = `
        <div class="post-card-author">
          <div class="author-left">
            ${authorImg ? `<img class="post-author-img" src="${authorImg}" alt="Author" />` : `<div class="post-author-initials">${escapeHtml(authorName.slice(0,2).toUpperCase())}</div>`}
            <div>
              <div class="post-author-name">${escapeHtml(authorName)}</div>
              <div class="post-author-meta">Verified Enterprise Broadcast</div>
            </div>
          </div>
          <span class="post-time-badge">${escapeHtml(timeStr)}</span>
        </div>

        ${mediaHtml}

        <div class="post-text-snippet">${escapeHtml(postText)}</div>

        <div class="post-footer-row">
          <div class="reactions-breakdown">
            <span class="reaction-item" title="Likes">
              <svg class="icon-sm"><use href="#icon-thumbs-up"></use></svg>
              <span>${likesCount}</span>
            </span>
            <span class="reaction-item" title="Reposts">
              <svg class="icon-sm"><use href="#icon-repeat"></use></svg>
              <span>${repostsCount}</span>
            </span>
            <span class="reaction-item" title="Total Reactions">
              <span><strong>${totalReactions}</strong> total</span>
            </span>
          </div>
          <span class="view-post-link">
            <span>Inspect</span>
            <svg class="icon-sm"><use href="#icon-external-link"></use></svg>
          </span>
        </div>
      `;

      card.addEventListener('click', () => {
        openPostModal(post, imgUrl, authorName, authorImg, timeStr, likesCount, repostsCount, totalReactions);
      });

      postsContainer.appendChild(card);
    });
  }

  function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function openPostModal(post, imgUrl, authorName, authorImg, timeStr, likes, reposts, total) {
    modalAuthorName.textContent = authorName;
    modalAuthorLogo.src = authorImg;
    modalPostTime.textContent = timeStr;
    modalPostText.textContent = post.text || post.content || '';

    if (imgUrl) {
      modalImageWrapper.classList.remove('hidden');
      modalPostImage.src = imgUrl;
    } else {
      modalImageWrapper.classList.add('hidden');
    }

    modalReactions.innerHTML = `
      <span class="reaction-item"><svg class="icon-sm"><use href="#icon-thumbs-up"></use></svg> ${likes} Likes</span>
      <span class="reaction-item"><svg class="icon-sm"><use href="#icon-repeat"></use></svg> ${reposts} Reposts</span>
      <span class="reaction-item"><strong>${total}</strong> Total Reactions</span>
    `;

    const postUrl = post.url || post.linkedinUrl || globalCompanyData?.linkedinUrl || '#';
    modalLinkedinBtn.href = postUrl;

    postModal.classList.remove('hidden');
  }

  /* ===================================================================
     6. TAB NAVIGATION & MODAL CONTROLS
     =================================================================== */
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabPanels = document.querySelectorAll('.tab-panel');

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-tab');
      tabButtons.forEach(b => b.classList.remove('active'));
      tabPanels.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) {
        targetPanel.classList.add('active');
      }
    });
  });

  // Post Modal Close
  btnCloseModal?.addEventListener('click', () => {
    postModal.classList.add('hidden');
  });

  postModal?.addEventListener('click', (e) => {
    if (e.target === postModal) postModal.classList.add('hidden');
  });

  // Raw JSON Modal Controls
  btnViewRaw?.addEventListener('click', () => {
    rawJsonCode.textContent = JSON.stringify(rawMergedDossier, null, 2);
    rawModal.classList.remove('hidden');
  });

  btnCloseRawModal?.addEventListener('click', () => rawModal.classList.add('hidden'));
  btnDismissRaw?.addEventListener('click', () => rawModal.classList.add('hidden'));
  rawModal?.addEventListener('click', (e) => {
    if (e.target === rawModal) rawModal.classList.add('hidden');
  });

  btnCopyRaw?.addEventListener('click', () => {
    navigator.clipboard.writeText(rawJsonCode.textContent).then(() => {
      btnCopyRaw.textContent = 'Copied!';
      setTimeout(() => btnCopyRaw.textContent = 'Copy JSON', 2000);
    });
  });

  // Export JSON Download — filename derived dynamically from company data
  btnExportJson?.addEventListener('click', () => {
    const companySlug = (globalCompanyData?.universalName || globalCompanyData?.name || 'company')
      .toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(rawMergedDossier, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `${companySlug}_dossier.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  });

  // Print Report
  btnPrint?.addEventListener('click', () => {
    window.print();
  });

  // Filter Event Listeners
  postSearchInput?.addEventListener('input', () => applyPostFilters(globalCompanyData));
  postSortSelect?.addEventListener('change', () => applyPostFilters(globalCompanyData));
  postMediaFilter?.addEventListener('change', () => applyPostFilters(globalCompanyData));

  // Deep Linking Tab Support (e.g. ?tab=map, ?tab=talent, ?tab=posts)
  const urlParams = new URLSearchParams(window.location.search);
  const requestedTab = urlParams.get('tab');
  if (requestedTab) {
    const targetBtn = document.querySelector(`.tab-btn[data-tab="tab-${requestedTab}"]`);
    if (targetBtn) {
      setTimeout(() => targetBtn.click(), 100);
    }
  }

  /* ===================================================================
     7. INITIALIZATION BOOTSTRAP
     =================================================================== */
  try {
    const data = await loadIntelligenceData();
    globalCompanyData = data.company;
    globalPostsData = data.posts;
    globalLeadData = data.lead;
    rawMergedDossier = {
      lead: data.lead,
      company: data.company,
      posts_count: data.posts.length,
      posts: data.posts
    };

    renderProfile(data.company, data.lead);
    renderTalentAnalytics(data.company);
    renderLocationCards(data.company);
    await initWorldMap(data.company);
    renderPostsFeed(data.posts, data.company);

    // Update footer timestamp from scraped_at or today's date
    const tsEl = document.getElementById('footer-timestamp');
    if (tsEl) {
      const scrapedAt = data.rawCompany?.scraped_at;
      if (scrapedAt) {
        const dateStr = new Date(scrapedAt).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
        tsEl.textContent = `Intelligence Record: ${dateStr} \u2022 Verified \u2022 Active Production Status`;
      } else {
        const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
        tsEl.textContent = `Intelligence Record: ${today} \u2022 Verified \u2022 Active Production Status`;
      }
    }

  } catch (fatalErr) {
    console.error('Fatal initialization error:', fatalErr);
    if (companyName) companyName.textContent = 'Intelligence Platform';
    if (companyTagline) companyTagline.textContent = 'Data loading failed. Please refresh.';
  }
});
