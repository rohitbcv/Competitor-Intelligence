"""
Module B: Tech Stack Detection

Strategy (in order):
  1. Fetch homepage with a realistic Chrome browser UA + headers.
  2. Parse response *headers* for CDN / WAF / infrastructure signatures
     (works even on 403 responses from Akamai / Cloudflare).
  3. Parse response HTML (if any was returned) for JS framework, analytics,
     consent, monitoring and CMS fingerprints.
  4. Retry on 429 with a 20-second back-off.
  5. If homepage is fully blocked, fall back to /robots.txt — its headers
     often still leak CDN and server info.
"""

import re
import time
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_CHROME_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
}

# ── Header fingerprints ────────────────────────────────────────────────────────
# Each entry: (response-header-name, substring-to-match, technology-label)
_HEADER_SIGS: list[tuple[str, str, str]] = [
    # CDN / Infrastructure
    ("server",              "akamaighost",       "Akamai CDN"),
    ("server",              "akamaineistorage",  "Akamai CDN"),
    ("server",              "akamai",            "Akamai CDN"),
    ("server",              "cloudflare",        "Cloudflare"),
    ("server",              "cloudfront",        "AWS CloudFront"),
    ("server",              "nginx",             "Nginx"),
    ("server",              "apache",            "Apache"),
    ("server",              "fastly",            "Fastly CDN"),
    ("via",                 "1.1 google",        "Google Cloud CDN"),
    ("via",                 "cloudfront",        "AWS CloudFront"),
    ("x-served-by",         "cache-",            "Fastly CDN"),
    ("x-amz-cf-id",         "",                  "AWS CloudFront"),
    ("cf-ray",              "",                  "Cloudflare"),
    ("akamai-grn",          "",                  "Akamai CDN"),
    ("x-akamai-edgescape",  "",                  "Akamai CDN"),
    # WAF signals
    ("server",              "imperva",           "Imperva WAF"),
    ("x-iinfo",             "",                  "Imperva WAF"),
    # Strict-Transport / Security headers that hint at specific stacks
    ("x-powered-by",        "express",           "Express.js"),
    ("x-powered-by",        "next.js",           "Next.js"),
    ("x-powered-by",        "php",               "PHP"),
    ("x-powered-by",        "asp.net",           "ASP.NET"),
]

# ── HTML fingerprints ─────────────────────────────────────────────────────────
# Each entry: (regex-pattern, technology-label)
# Patterns applied to *lowercased* HTML.
_HTML_SIGS: list[tuple[str, str]] = [
    # JS Frameworks / Runtime
    (r"react(?:[-_.]dom|root|\.js|/react\.)",   "React"),
    (r"__next_data__|/_next/static/",            "Next.js"),
    (r"ng-version=|angularjs|angular\.min\.js",  "Angular"),
    (r'__vue_|vue\.(?:min\.)?js|vue\.runtime',   "Vue.js"),
    (r"backbone\.js|backbone\.min",              "Backbone.js"),
    (r"ember\.js|ember\.min",                    "Ember.js"),
    (r"jquery(?:[-.](?:\d|min)|\.js)",           "jQuery"),
    # Analytics
    (r"gtag\(|google(?:tag|analytics)\.js|g-[a-z0-9]{6,}", "Google Analytics"),
    (r"gtm\.js\?|googletagmanager\.com",         "Google Tag Manager"),
    (r"omniture|s_gi\s*\(|adobe\.com/id",        "Adobe Analytics"),
    (r"_satellite\.|adobe\.com/experience",      "Adobe Launch"),
    (r"adobedtm\.com|adobe\.com/audiencemanager","Adobe Audience Manager"),
    # A/B Testing / Personalization
    (r"optimizely",                              "Optimizely"),
    (r"adobe\.target|mboxCreate|mbox2Session",   "Adobe Target"),
    (r"vwo\.com|vwo_async",                      "VWO"),
    (r"qualtrics",                               "Qualtrics"),
    # Monitoring / RUM
    (r"dynatrace|ruxitagent|dtrum\.",            "Dynatrace"),
    (r"newrelic|nr-data\.net|window\.newrelic",  "New Relic"),
    (r"datadog-rum|datadoghq\.com",              "Datadog RUM"),
    (r"bugsnag",                                 "Bugsnag"),
    # CDN / Performance
    (r"akam-sw|akstat|akamai\.",                 "Akamai"),
    (r"cloudflare\.com|cf-beacon",               "Cloudflare"),
    # CMP / Consent
    (r"onetrust|optanon(?:wrapper|consent)",     "OneTrust"),
    (r"osano(?:-cm|-cookie|\.com)",              "Osano"),
    (r"utag\.js|tealium(?:iq)?",                 "Tealium"),
    (r"didomi",                                  "Didomi CMP"),
    (r"cookiebot",                               "Cookiebot"),
    (r"usercentrics",                            "Usercentrics"),
    # CMS / Platforms
    (r'content="wordpress|wp-content/|wp-json/', "WordPress"),
    (r"drupal\.settings|drupal\.js",             "Drupal"),
    (r"jcr:|aem\.js|cq\.analytics",             "Adobe Experience Manager"),
    (r"sitecore",                                "Sitecore"),
    (r"contentful",                              "Contentful"),
    # Social / Tracking pixels
    (r"fbq\(|facebook\.net/en_us/fbevents",      "Facebook Pixel"),
    (r"ttq\.|tiktok\.com/i18n/pixel",            "TikTok Pixel"),
    (r"linkedin\.com/px",                        "LinkedIn Insight"),
    (r"hotjar",                                  "Hotjar"),
    # E-commerce / booking
    (r"salesforce\.com|sfmc\.js|pardot",         "Salesforce Marketing"),
    (r"stripe\.js|stripe\.com/v3",               "Stripe"),
    (r"bazaarvoice",                             "BazaarVoice"),
    # Cloud / Hosting hints
    (r'src="https://s3\.amazonaws\.com',         "AWS S3"),
    (r"vercel\.live|_vercel",                    "Vercel"),
]


def _fetch(url: str, retries: int = 2) -> requests.Response | None:
    """Fetch a URL with Chrome headers; retry once on 429 with a short back-off."""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=_CHROME_HEADERS, timeout=12,
                             verify=False, allow_redirects=True)
            if r.status_code == 429 and attempt < retries - 1:
                time.sleep(8)
                continue
            return r
        except Exception:
            return None
    return None


def _fingerprint_headers(headers: dict) -> list[str]:
    detected = []
    lower_headers = {k.lower(): v.lower() for k, v in headers.items()}
    for header_name, substring, label in _HEADER_SIGS:
        val = lower_headers.get(header_name, "")
        if val and (not substring or substring in val):
            if label not in detected:
                detected.append(label)
    return detected


def _fingerprint_html(html: str) -> list[str]:
    detected = []
    lower = html.lower()
    for pattern, label in _HTML_SIGS:
        if re.search(pattern, lower) and label not in detected:
            detected.append(label)
    return detected


def detect_tech_stack(domain: str) -> dict:
    """
    Detect technologies used on a domain.

    Returns:
        {
            "technologies": list[str],
            "scan_status": "success" | "partial" | "blocked" | "error"
        }
    """
    time.sleep(1)

    tech: list[str] = []
    got_html = False

    # ── Try two URL variants: bare domain then www. prefix ───────────────────
    urls_to_try = [f"https://{domain}"]
    if not domain.startswith("www."):
        urls_to_try.append(f"https://www.{domain}")

    r = None
    for url in urls_to_try:
        r = _fetch(url)
        if r is not None:
            tech_from_headers = _fingerprint_headers(r.headers)
            tech += [t for t in tech_from_headers if t not in tech]

            if r.status_code < 400 or (r.status_code in (403, 429) and len(r.text) > 5000):
                html_tech = _fingerprint_html(r.text)
                tech += [t for t in html_tech if t not in tech]
                got_html = bool(html_tech)

            if tech:
                break   # got useful signal from this URL — no need to try www.

    # ── Fallback fetch: /robots.txt for header-only signal ────────────────────
    if not tech:
        r2 = _fetch(f"https://{domain}/robots.txt")
        if r2 is not None:
            hdr_tech = _fingerprint_headers(r2.headers)
            tech += [t for t in hdr_tech if t not in tech]

    # ── Wappalyzer pass on homepage HTML (bonus detections) ──────────────────
    if r is not None and r.status_code == 200:
        try:
            from Wappalyzer import Wappalyzer, WebPage
            wappalyzer = Wappalyzer.latest()
            webpage = WebPage(f"https://{domain}", r.text, r.headers)
            for t in wappalyzer.analyze(webpage):
                if t not in tech:
                    tech.append(t)
        except Exception:
            pass

    # ── Determine status ──────────────────────────────────────────────────────
    if tech:
        scan_status = "success" if (got_html or (r is not None and r.status_code == 200)) else "partial"
    elif r is not None and r.status_code in (403, 429, 503):
        scan_status = "blocked"
    else:
        scan_status = "error"

    return {
        "technologies": sorted(set(tech)),
        "scan_status": scan_status,
    }
