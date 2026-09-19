// State
let currentResult = null;

// DOM Elements
const form = document.getElementById('extract-form');
const urlInput = document.getElementById('url-input');
const btnSubmit = document.getElementById('btn-submit');
const btnText = btnSubmit.querySelector('.btn-text');
const btnLoader = btnSubmit.querySelector('.btn-loader');
const forcePlaywrightToggle = document.getElementById('force-playwright-toggle');

const pipelineStatus = document.getElementById('pipeline-status');
const pipelineLog = document.getElementById('pipeline-current-log');
const stepConnect = document.getElementById('step-connect');
const stepCrawl = document.getElementById('step-crawl');
const stepCrawlLabel = document.getElementById('step-crawl-label');
const stepParse = document.getElementById('step-parse');
const stepAi = document.getElementById('step-ai');
const line1 = document.getElementById('line-1');
const line2 = document.getElementById('line-2');
const line3 = document.getElementById('line-3');

const errorBanner = document.getElementById('error-banner');
const errorDesc = document.getElementById('error-desc');
const btnErrorClose = document.getElementById('btn-error-close');

const resultsContainer = document.getElementById('results-container');
const fallbackNotice = document.getElementById('fallback-notice');
const fallbackReasonText = document.getElementById('fallback-reason-text');

const toast = document.getElementById('toast');
const toastText = document.getElementById('toast-text');

// Init
document.addEventListener('DOMContentLoaded', () => {
  loadHistory();
  setupQuickChips();
  setupExportButtons();
});

// Quick Example Chips
function setupQuickChips() {
  document.querySelectorAll('.quick-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      urlInput.value = chip.getAttribute('data-url');
      form.dispatchEvent(new Event('submit'));
    });
  });
}

// Error Close
btnErrorClose.addEventListener('click', () => {
  errorBanner.style.display = 'none';
});

// Toast Helper
function showToast(message) {
  toastText.textContent = message;
  toast.classList.add('toast-show');
  setTimeout(() => {
    toast.classList.remove('toast-show');
  }, 2500);
}

// Copy to Clipboard
function copyText(text, label = 'Copied to clipboard!') {
  navigator.clipboard.writeText(text).then(() => {
    showToast(label);
  }).catch(() => {
    const el = document.createElement('textarea');
    el.value = text;
    document.body.appendChild(el);
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
    showToast(label);
  });
}

// Stepper Progress Animation
let stepperTimer = null;
function startStepper(forcePw) {
  pipelineStatus.style.display = 'block';
  stepCrawlLabel.textContent = forcePw ? 'Playwright Browser' : 'Scrapy Crawl';

  // Reset steps
  [stepConnect, stepCrawl, stepParse, stepAi].forEach(s => s.className = 'step');
  [line1, line2, line3].forEach(l => l.className = 'step-line');

  stepConnect.classList.add('step-active');
  pipelineLog.textContent = 'Connecting to host and analyzing DNS...';

  stepperTimer = setTimeout(() => {
    stepConnect.classList.add('step-done');
    line1.classList.add('line-done');
    stepCrawl.classList.add('step-active');
    pipelineLog.textContent = forcePw 
      ? 'Launching headless browser and hydrating dynamic DOM...'
      : 'Running Scrapy spider and discovering contact subpages...';

    stepperTimer = setTimeout(() => {
      stepCrawl.classList.add('step-done');
      line2.classList.add('line-done');
      stepParse.classList.add('step-active');
      pipelineLog.textContent = 'Parsing Schema.org microdata, addresses & tel/mailto links...';

      stepperTimer = setTimeout(() => {
        stepParse.classList.add('step-done');
        line3.classList.add('line-done');
        stepAi.classList.add('step-active');
        pipelineLog.textContent = 'Stage 1: Verifying contact topics with OpenAI...';
        
        setTimeout(() => {
          if (stepAi.classList.contains('step-active')) {
            pipelineLog.textContent = 'Stage 2: Extracting details from verified contact section...';
          }
        }, 2200);
      }, 3000);
    }, 2500);
  }, 1000);
}

function stopStepper(success) {
  clearTimeout(stepperTimer);
  if (success) {
    [stepConnect, stepCrawl, stepParse, stepAi].forEach(s => s.className = 'step step-done');
    [line1, line2, line3].forEach(l => l.className = 'step-line line-done');
    pipelineLog.textContent = 'Extraction complete!';
    setTimeout(() => {
      pipelineStatus.style.display = 'none';
    }, 1200);
  } else {
    pipelineStatus.style.display = 'none';
  }
}

// Form Submit Handler
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const rawUrl = urlInput.value.trim();
  if (!rawUrl) return;

  const forcePlaywright = forcePlaywrightToggle.checked;

  // UI state: loading
  btnSubmit.disabled = true;
  btnText.style.display = 'none';
  btnLoader.style.display = 'inline-flex';
  errorBanner.style.display = 'none';
  resultsContainer.style.display = 'none';

  startStepper(forcePlaywright);

  try {
    const res = await fetch('/api/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: rawUrl,
        force_playwright: forcePlaywright
      })
    });

    const data = await res.json();

    if (!res.ok || !data.success) {
      throw new Error(data.error || data.detail || 'Failed to retrieve website details.');
    }

    currentResult = data;
    stopStepper(true);
    renderResults(data);
    loadHistory();

    // Smooth scroll to results
    resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });

  } catch (err) {
    stopStepper(false);
    errorDesc.textContent = err.message || 'An unexpected error occurred.';
    errorBanner.style.display = 'flex';
  } finally {
    btnSubmit.disabled = false;
    btnText.style.display = 'inline-flex';
    btnLoader.style.display = 'none';
  }
});

// Render Results Dashboard
function renderResults(result) {
  const d = result.data;

  // Company profile
  document.getElementById('res-company-name').textContent = d.company_name || new URL(result.url).hostname;
  document.getElementById('res-company-desc').textContent = d.description || 'No description available for this organization.';
  
  const linkEl = document.getElementById('res-website-link');
  linkEl.href = result.url;
  document.getElementById('res-website-text').textContent = result.url.replace(/^https?:\/\//, '');

  // Audit metrics
  const methodEl = document.getElementById('res-method');
  methodEl.textContent = result.method_used.toUpperCase();
  if (result.method_used.toLowerCase() === 'playwright') {
    methodEl.style.color = 'var(--cyan)';
  } else {
    methodEl.style.color = 'var(--emerald)';
  }

  document.getElementById('res-time').textContent = `${result.execution_time_sec}s`;
  document.getElementById('res-pages-count').textContent = result.pages_crawled.length || 1;
  
  const aiEl = document.getElementById('res-ai-status');
  aiEl.textContent = result.ai_enriched ? 'Verified' : 'Regex Only';
  aiEl.style.color = result.ai_enriched ? 'var(--emerald)' : 'var(--amber)';

  // Fallback Notice
  if (result.fallback_occurred && result.fallback_reason) {
    fallbackNotice.style.display = 'flex';
    fallbackReasonText.textContent = result.fallback_reason;
  } else {
    fallbackNotice.style.display = 'none';
  }

  // Two-Stage Verified Contact Topics Notice
  const topicsNotice = document.getElementById('topics-notice');
  const topicsTags = document.getElementById('verified-topics-tags');
  const identifiedTopics = result.identified_contact_topics || (d && d.identified_contact_topics) || [];
  if (topicsNotice && topicsTags) {
    if (identifiedTopics.length > 0) {
      topicsNotice.style.display = 'flex';
      topicsTags.innerHTML = identifiedTopics.map(t => `<span class="topic-tag"><i class="fa-solid fa-check"></i> ${escapeHtml(t)}</span>`).join('');
    } else {
      topicsNotice.style.display = 'none';
    }
  }

  // 1. Locations
  const locList = document.getElementById('locations-list');
  const countLoc = document.getElementById('count-locations');
  locList.innerHTML = '';
  countLoc.textContent = d.locations.length;

  if (d.locations.length === 0) {
    locList.innerHTML = '<p class="empty-notice">No physical address detected on crawled pages.</p>';
  } else {
    d.locations.forEach(loc => {
      const mapLink = loc.map_url || `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(loc.full_address)}`;
      const card = document.createElement('div');
      card.className = 'location-item';
      card.innerHTML = `
        <div class="location-top">
          <span class="location-label"><i class="fa-solid fa-map-pin"></i> ${escapeHtml(loc.label || 'Office')}</span>
        </div>
        <p class="location-address">${escapeHtml(loc.full_address)}</p>
        <div class="location-actions">
          <a href="${mapLink}" target="_blank" class="btn-map">
            <i class="fa-solid fa-arrow-up-right-from-square"></i> Open in Maps
          </a>
          <button class="btn-map" onclick="copyText('${escapeJs(loc.full_address)}', 'Address copied!')">
            <i class="fa-solid fa-copy"></i> Copy Address
          </button>
        </div>
      `;
      locList.appendChild(card);
    });
  }

  // 2. Emails
  const emailList = document.getElementById('emails-list');
  const countEmails = document.getElementById('count-emails');
  emailList.innerHTML = '';
  countEmails.textContent = d.emails.length;

  if (d.emails.length === 0) {
    emailList.innerHTML = '<p class="empty-notice">No public email found.</p>';
  } else {
    d.emails.forEach(email => {
      const item = document.createElement('div');
      item.className = 'contact-chip';
      item.innerHTML = `
        <a href="mailto:${escapeHtml(email)}" class="chip-link">${escapeHtml(email)}</a>
        <button class="chip-copy" title="Copy email" onclick="copyText('${escapeJs(email)}', 'Email copied!')">
          <i class="fa-solid fa-copy"></i>
        </button>
      `;
      emailList.appendChild(item);
    });
  }

  // 3. Phones
  const phoneList = document.getElementById('phones-list');
  const countPhones = document.getElementById('count-phones');
  phoneList.innerHTML = '';
  countPhones.textContent = d.phone_numbers.length;

  if (d.phone_numbers.length === 0) {
    phoneList.innerHTML = '<p class="empty-notice">No direct telephone numbers found.</p>';
  } else {
    d.phone_numbers.forEach(phone => {
      const cleanTel = phone.replace(/[^\d+]/g, '');
      const item = document.createElement('div');
      item.className = 'contact-chip';
      item.innerHTML = `
        <a href="tel:${cleanTel}" class="chip-link">${escapeHtml(phone)}</a>
        <button class="chip-copy" title="Copy phone" onclick="copyText('${escapeJs(phone)}', 'Phone copied!')">
          <i class="fa-solid fa-copy"></i>
        </button>
      `;
      phoneList.appendChild(item);
    });
  }

  // Operating Hours
  const hoursContainer = document.getElementById('hours-container');
  const hoursText = document.getElementById('res-hours');
  if (d.operating_hours) {
    hoursContainer.style.display = 'block';
    hoursText.textContent = d.operating_hours;
  } else {
    hoursContainer.style.display = 'none';
  }

  // 4. Social Links
  const socialsList = document.getElementById('socials-list');
  const countSocials = document.getElementById('count-socials');
  socialsList.innerHTML = '';
  const socialEntries = Object.entries(d.social_links || {});
  countSocials.textContent = socialEntries.length;

  if (socialEntries.length === 0) {
    socialsList.innerHTML = '<p class="empty-notice">No social profile links found.</p>';
  } else {
    const iconMap = {
      linkedin: 'fa-brands fa-linkedin',
      twitter: 'fa-brands fa-x-twitter',
      facebook: 'fa-brands fa-facebook',
      instagram: 'fa-brands fa-instagram',
      youtube: 'fa-brands fa-youtube',
      github: 'fa-brands fa-github'
    };

    socialEntries.forEach(([network, link]) => {
      const iconClass = iconMap[network.toLowerCase()] || 'fa-solid fa-globe';
      const a = document.createElement('a');
      a.className = 'social-pill';
      a.href = link;
      a.target = '_blank';
      a.innerHTML = `<i class="${iconClass}"></i> ${network}`;
      socialsList.appendChild(a);
    });
  }

  // 5. Crawled Subpages
  const pagesList = document.getElementById('pages-list');
  const countPages = document.getElementById('count-pages');
  pagesList.innerHTML = '';
  const pages = d.contact_pages_found || [];
  countPages.textContent = pages.length;

  if (pages.length === 0) {
    pagesList.innerHTML = '<p class="empty-notice">Scraped directly from primary page.</p>';
  } else {
    pages.forEach(pUrl => {
      const li = document.createElement('li');
      li.innerHTML = `<a href="${pUrl}" target="_blank"><i class="fa-solid fa-arrow-up-right-from-square"></i> ${escapeHtml(pUrl)}</a>`;
      pagesList.appendChild(li);
    });
  }

  resultsContainer.style.display = 'block';
}

// Session History
async function loadHistory() {
  try {
    const res = await fetch('/api/history');
    if (!res.ok) return;
    const items = await res.json();
    const historyGrid = document.getElementById('history-grid');

    if (!items || items.length === 0) {
      historyGrid.innerHTML = '<p class="empty-text">No previous searches in this session yet.</p>';
      return;
    }

    historyGrid.innerHTML = '';
    items.forEach(item => {
      const card = document.createElement('div');
      card.className = 'history-card';
      const name = item.data.company_name || new URL(item.url).hostname;
      card.innerHTML = `
        <div class="history-header">
          <span class="history-name">${escapeHtml(name)}</span>
          <span class="history-badge">${item.method_used}</span>
        </div>
        <div class="history-url">${escapeHtml(item.url)}</div>
        <div class="history-stats">
          <span><i class="fa-solid fa-envelope"></i> ${item.data.emails.length}</span>
          <span><i class="fa-solid fa-phone"></i> ${item.data.phone_numbers.length}</span>
          <span><i class="fa-solid fa-location-dot"></i> ${item.data.locations.length}</span>
        </div>
      `;
      card.addEventListener('click', () => {
        currentResult = item;
        renderResults(item);
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      historyGrid.appendChild(card);
    });
  } catch (err) {
    console.debug('Failed to load history:', err);
  }
}

// Export Setup
function setupExportButtons() {
  document.getElementById('btn-export-json').addEventListener('click', () => {
    if (!currentResult) return;
    const blob = new Blob([JSON.stringify(currentResult, null, 2)], { type: 'application/json' });
    downloadBlob(blob, `contacts_${new URL(currentResult.url).hostname}.json`);
    showToast('Exported to JSON!');
  });

  document.getElementById('btn-export-csv').addEventListener('click', () => {
    if (!currentResult) return;
    const d = currentResult.data;
    const headers = ['Company Name', 'Website', 'Emails', 'Phones', 'Locations', 'Social Links'];
    const row = [
      `"${(d.company_name || '').replace(/"/g, '""')}"`,
      `"${(d.website || '').replace(/"/g, '""')}"`,
      `"${d.emails.join('; ')}"`,
      `"${d.phone_numbers.join('; ')}"`,
      `"${d.locations.map(l => l.full_address).join(' | ').replace(/"/g, '""')}"`,
      `"${Object.entries(d.social_links).map(([k, v]) => `${k}: ${v}`).join('; ')}"`
    ];
    const csvContent = headers.join(',') + '\n' + row.join(',');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    downloadBlob(blob, `contacts_${new URL(currentResult.url).hostname}.csv`);
    showToast('Exported to CSV!');
  });

  document.getElementById('btn-copy-all').addEventListener('click', () => {
    if (!currentResult) return;
    const d = currentResult.data;
    let summary = `COMPANY: ${d.company_name || 'N/A'}\n`;
    summary += `WEBSITE: ${d.website}\n\n`;
    summary += `EMAILS:\n${d.emails.length ? d.emails.join('\n') : 'None found'}\n\n`;
    summary += `PHONES:\n${d.phone_numbers.length ? d.phone_numbers.join('\n') : 'None found'}\n\n`;
    summary += `LOCATIONS:\n${d.locations.length ? d.locations.map(l => `- [${l.label}] ${l.full_address}`).join('\n') : 'None found'}\n\n`;
    if (Object.keys(d.social_links).length) {
      summary += `SOCIAL PROFILES:\n${Object.entries(d.social_links).map(([k, v]) => `- ${k}: ${v}`).join('\n')}\n`;
    }
    copyText(summary, 'Full contact summary copied!');
  });
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Utilities
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeJs(str) {
  if (!str) return '';
  return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}
