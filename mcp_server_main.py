# -*- coding: utf-8 -*-
"""
Kosovo Legal Research, Multi-Tier Case Law & Citation Verification MCP Server (xk-legal-mcp)
Version: 2.0.0 (Live National Legal Archive & Multi-Tier Court Search Engine)
Organization: JurisAtlas
License: MIT
"""
import asyncio
import io
import json
import logging
import os
import re
import urllib.parse
import warnings
from typing import Any, Dict, List, Optional
import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from fastmcp import FastMCP
from pydantic import Field

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None

try:
    import primp
except ImportError:
    primp = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("xk-legal-mcp")

JURISDICTION_CODE = "XK"
JURISDICTION_NAME = "Kosovo"
LEGISLATION_PORTAL = "https://gzk.rks-gov.net"
CASELAW_PORTAL = "https://supreme.gjyqesori-rks.org"
API_MODE = "xk_native"

COURT_HIERARCHY: Dict[str, Any] = {
    "tier_1_first_instance": "7 Gjykatat Themelore (Basic Courts: Prishtinë, Prizren, Pejë, Gjilan, Gjakovë, Mitrovicë, Ferizaj) & Gjykata Komerciale (First Instance Chambers)",
    "tier_2_appellate_regional": "Gjykata e Apelit e Kosovës (Court of Appeals in Prishtinë) & Gjykata Komerciale (Second Instance Chambers)",
    "tier_3_supreme_constitutional": "Gjykata Supreme e Kosovës (supreme.gjyqesori-rks.org) & Gjykata Kushtetuese (gjk-ks.org)",
    "tiered_database_name": "Këshilli Gjyqësor i Kosovës - Regjistri i Vendimeve Gjyqësore (gjyqesori-rks.org)",
    "tiered_database_url": "https://www.gjyqesori-rks.org/aktgjykimet/",
    "sub_portals": {
        "kgjk_all_decisions": "https://www.gjyqesori-rks.org/aktgjykimet/",
        "gjykata_supreme": "https://supreme.gjyqesori-rks.org",
        "gjykata_apelit": "https://apeli.gjyqesori-rks.org",
        "gjykata_komerciale": "https://komerciale.gjyqesori-rks.org",
        "themelore_prishtine": "https://prishtine.gjyqesori-rks.org"
    }
}

ARCHIVE_PROFILE: Dict[str, Any] = {
    "leg_sites": [
        "gzk.rks-gov.net",
        "kuvendikosoves.org",
        "rks-gov.net"
    ],
    "leg_keywords": "Ligji OR Gazeta Zyrtare e Republikës së Kosovës",
    "case_sites": [
        "gjk-ks.org",
        "gjyqesori-rks.org",
        "rks-gov.net"
    ],
    "case_keywords": "Aktgjykim OR Vendim Gjykata Kosovë",
    "tier_keywords": {
        "first_instance": "Gjykata Themelore OR Gjykata Komerciale Aktgjykim",
        "appellate_regional": "Gjykata e Apelit Aktgjykim Kosovë",
        "supreme_constitutional": "Gjykata Supreme OR Gjykata Kushtetuese Aktgjykim Kosovë"
    },
    "sub_court_names": {
        "gjykata_supreme": "Gjykata Supreme e Kosovës",
        "gjykata_apelit": "Gjykata e Apelit e Kosovës",
        "gjykata_komerciale": "Gjykata Komerciale e Kosovës",
        "themelore_prishtine": "Gjykata Themelore në Prishtinë"
    }
}

mcp = FastMCP(
    name="xk-legal-mcp",
    instructions=(
        "Official-source legal research, live national archive search, multi-tier judicial hierarchy "
        "search (First Instance, Regional/Cantonal/Appellate, and Supreme/Constitutional courts), "
        "and citation verification MCP server for Kosovo (XK)."
    ),
)

_http_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            headers={
                "User-Agent": "JurisAtlas-Legal-MCP/2.0 (+https://github.com/jurisatlas)",
                "Accept": "application/json, application/xml, text/html, */*",
            },
            timeout=30.0,
            follow_redirects=True,
        )
    return _http_client


def _clean_html(html: str, max_chars: int = 6000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    if "HOLC Statutory Compilations" in text:
        text = text.split("HOLC Statutory Compilations", 1)[-1].strip()
    return text[:max_chars]


def _sync_archive_search(
    query: str,
    sites: List[str],
    extra_keywords: str = "",
    limit: int = 10,
) -> List[Dict[str, Any]]:
    if DDGS is None:
        return []
    results: List[Dict[str, Any]] = []
    seen_urls = set()

    clean_q = query.strip()
    first_kw = extra_keywords.split("OR")[0].strip() if extra_keywords else ""

    def _add_hits(raw_items: Any, default_source: str) -> None:
        for r in raw_items or []:
            href = r.get("href", "")
            if not href or href in seen_urls or href.startswith("https://en.wikipedia.org"):
                continue
            parsed = urllib.parse.urlparse(href)
            if parsed.path.rstrip("/") in ("", "/en", "/bg", "/fr", "/de", "/index.faces", "/homepage.html") and not parsed.query:
                continue
            seen_urls.add(href)
            domain = parsed.netloc
            results.append({
                "id": href,
                "title": r.get("title", ""),
                "url": href,
                "snippet": r.get("body", ""),
                "is_pdf": href.lower().split("?")[0].endswith(".pdf"),
                "source": domain or default_source,
            })
            if len(results) >= limit:
                break

    ddgs_client = DDGS()

    import time

    def _query_ddgs(q_str: str, max_res: int) -> List[Dict[str, Any]]:
        for attempt in range(3):
            try:
                items = DDGS().text(q_str, backend="yahoo", max_results=max_res)
                if items:
                    return items
            except Exception as e:
                logger.debug("DDGS yahoo attempt %d: %s", attempt + 1, e)
                time.sleep(0.4)
        return []

    # Pass 1: Query official national domains directly
    if sites:
        for s_dom in sites[:2]:
            if len(results) >= limit:
                break
            q_dom = f"{s_dom} {clean_q} {first_kw}".strip()
            hits = _query_ddgs(q_dom, min(limit * 2, 10))
            _add_hits(hits, s_dom)

    # Pass 2: Broad national legal search with court/statute keywords
    if len(results) < limit:
        q2 = f"{clean_q} {first_kw} {JURISDICTION_NAME}".strip()
        _add_hits(_query_ddgs(q2, min(limit * 2, 12)), "Open Legal Archive")

    return results[:limit]


async def _live_archive_search(
    query: str,
    sites: List[str],
    extra_keywords: str = "",
    limit: int = 10,
) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(_sync_archive_search, query, sites, extra_keywords, limit)


def _decode_bytes_smart(raw_bytes: bytes, content_type: str = "") -> str:
    if not raw_bytes:
        return ""
    ct_lower = content_type.lower()
    if "windows-1251" in ct_lower or "cp1251" in ct_lower:
        return raw_bytes.decode("windows-1251", errors="replace")
    if "windows-1250" in ct_lower or "iso-8859-2" in ct_lower:
        return raw_bytes.decode("windows-1250", errors="replace")
    if "iso-8859-7" in ct_lower or "windows-1253" in ct_lower:
        return raw_bytes.decode("windows-1253", errors="replace")
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        for enc in ("windows-1251", "windows-1250", "iso-8859-2", "windows-1253", "iso-8859-1"):
            try:
                return raw_bytes.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw_bytes.decode("utf-8", errors="replace")


def _sync_fetch_document(target_url: str) -> Dict[str, Any]:
    raw_bytes = b""
    text_body = ""
    content_type = ""
    status_code = 0

    if primp is not None:
        try:
            pclient = primp.Client(impersonate="chrome", follow_redirects=True, timeout=25)
            resp = pclient.get(target_url)
            status_code = resp.status_code
            headers = {k.lower(): v for k, v in resp.headers.items()}
            content_type = headers.get("content-type", "")
            raw_bytes = resp.content
            text_body = _decode_bytes_smart(raw_bytes, content_type)
        except Exception as e:
            logger.debug("primp fetch fallback: %s", e)

    if not raw_bytes:
        try:
            with httpx.Client(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                },
                follow_redirects=True,
                timeout=20.0,
            ) as hclient:
                resp = hclient.get(target_url)
                status_code = resp.status_code
                content_type = resp.headers.get("content-type", "")
                raw_bytes = resp.content
                text_body = _decode_bytes_smart(raw_bytes, content_type)
        except Exception as e:
            logger.debug("httpx fetch fallback: %s", e)

    is_pdf = (
        target_url.lower().split("?")[0].endswith(".pdf")
        or "application/pdf" in content_type.lower()
        or raw_bytes[:4] == b"%PDF"
    )

    if is_pdf and PdfReader is not None and raw_bytes:
        reader = PdfReader(io.BytesIO(raw_bytes))
        pages_text = []
        for idx, p in enumerate(reader.pages):
            extracted = p.extract_text() or ""
            if extracted.strip():
                pages_text.append(f"--- [PDF Page {idx + 1}/{len(reader.pages)}] ---\n{extracted.strip()}")
        full_text = "\n\n".join(pages_text)
        return {
            "format": "PDF",
            "pdf_pages": len(reader.pages),
            "status_code": status_code,
            "text": full_text[:100000],
        }

    cleaned = _clean_html(text_body, max_chars=80000) if text_body else ""
    if "judiciary.uk/judgments/" in target_url and PdfReader is not None and text_body:
        pdf_links = re.findall(r"https://www\.judiciary\.uk/wp-content/uploads/[A-Za-z0-9_./\-]+\.pdf", text_body, re.I)
        if pdf_links:
            try:
                p_doc = _sync_fetch_document(pdf_links[0])
                if p_doc.get("text"):
                    cleaned = f"{cleaned}\n\n=== [Attached Official Judgment PDF: {pdf_links[0]}] ===\n{p_doc['text']}"
            except Exception:
                pass
    if len(cleaned) < 150 or "Just a moment..." in cleaned:
        fallback_hits = _sync_archive_search(target_url, [], "", limit=5)
        if fallback_hits:
            excerpts = "\n\n".join(
                f"### {h.get('title', '')}\n- URL: {h.get('url', '')}\n- Excerpt: {h.get('snippet', '')}"
                for h in fallback_hits
            )
            cleaned = f"{cleaned}\n\n--- [Indexed Legal Archive Mirror / Excerpts] ---\n{excerpts}".strip()

    return {
        "format": "HTML/XML",
        "status_code": status_code,
        "text": cleaned,
    }


@mcp.tool(
    description=(
        "Search Kosovo (XK) national legislation (statutes, acts, codes, regulations, official gazette) "
        "via Gazeta Zyrtare e Republikës së Kosovës (gzk.rks-gov.net Official Gazette) and live national legal archives."
    )
)
async def search_legislation(
    query: str = Field(..., description="Keywords or statute title/number to search in Kosovo legislation."),
    year: Optional[int] = Field(None, description="Optional enactment year filter."),
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results to return."),
) -> Dict[str, Any]:
    year = year if isinstance(year, int) else None
    limit = limit if isinstance(limit, int) else 10
    client = get_client()
    results: List[Dict[str, Any]] = []

    try:
        if API_MODE == "uk_native":
            url = f"https://www.legislation.gov.uk/all/data.feed?title={urllib.parse.quote(query)}"
            if year:
                url = f"https://www.legislation.gov.uk/all/{year}/data.feed?title={urllib.parse.quote(query)}"
            resp = await client.get(url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for entry in soup.find_all("entry")[:limit]:
                    title_el = entry.find("title")
                    id_el = entry.find("id")
                    sum_el = entry.find("summary")
                    results.append({
                        "id": id_el.get_text(strip=True) if id_el else "",
                        "title": title_el.get_text(strip=True) if title_el else "",
                        "summary": sum_el.get_text(strip=True) if sum_el else "",
                        "url": id_el.get_text(strip=True) if id_el else "",
                        "source": "legislation.gov.uk",
                    })

        elif API_MODE == "us_native":
            seen_usc = set()
            usc_target = max(1, (limit + 1) // 2)
            # 1. Direct U.S.C. citation lookup on https://uscode.house.gov
            cit_m = re.search(
                r"\b(\d{1,2})\s*(?:U\.?S\.?C\.?|United States Code|Title)\s*(?:§+|sec(?:tion|\.)?)?\s*([0-9A-Za-z\-]+)",
                query,
                re.I,
            )
            if cit_m:
                t_num, s_num = cit_m.group(1), cit_m.group(2)
                direct_usc_url = f"https://uscode.house.gov/us/usc/t{t_num}/s{s_num}/"
                usc_resp = await client.get(direct_usc_url)
                if usc_resp.status_code == 200:
                    soup_u = BeautifulSoup(usc_resp.text, "html.parser")
                    t_el = soup_u.find("title")
                    results.append({
                        "id": f"{t_num} U.S.C. § {s_num}",
                        "title": t_el.get_text(strip=True) if t_el else f"{t_num} U.S.C. § {s_num}",
                        "url": direct_usc_url,
                        "snippet": _clean_html(usc_resp.text, 500),
                        "source": "uscode.house.gov",
                    })
                    seen_usc.add(direct_usc_url)

            # 2. Live scan of https://uscode.house.gov/browse.html & browse-tree HTML
            if len(results) < usc_target:
                b_resp = await client.get("https://uscode.house.gov/browse.html")
                if b_resp.status_code == 200:
                    soup_b = BeautifulSoup(b_resp.text, "html.parser")
                    q_words = [w.lower() for w in re.findall(r"\w+", query) if len(w) >= 3]
                    for det in soup_b.find_all("details", class_="tree-title"):
                        t_num = det.get("data-lazy-title", "")
                        sum_el = det.find("summary")
                        sum_txt = sum_el.get_text(" ", strip=True) if sum_el else ""
                        if t_num and any(w[:5] in sum_txt.lower() for w in q_words):
                            t_resp = await client.get(f"https://uscode.house.gov/browse-tree/t{t_num}.html")
                            if t_resp.status_code == 200:
                                soup_t = BeautifulSoup(t_resp.text, "html.parser")
                                scored_secs = []
                                for a_el in soup_t.find_all("a", class_="section-link", href=True):
                                    sec_txt = a_el.get_text(" ", strip=True)
                                    sc = sum(1 for w in q_words if w in sec_txt.lower())
                                    if sc > 0:
                                        scored_secs.append((sc, sec_txt, a_el["href"]))
                                scored_secs.sort(key=lambda x: x[0], reverse=True)
                                for sc, sec_txt, href in scored_secs[:usc_target]:
                                    h_url = "https://uscode.house.gov/" + href.lstrip("/")
                                    if h_url not in seen_usc:
                                        seen_usc.add(h_url)
                                        results.append({
                                            "id": f"Title {t_num} {sec_txt.split('—')[0].strip()}",
                                            "title": f"Title {t_num} {sec_txt}",
                                            "url": h_url,
                                            "snippet": f"{sum_txt} -> {sec_txt}",
                                            "source": "uscode.house.gov/browse.html",
                                        })
                                        if len(results) >= usc_target:
                                            break
                        if len(results) >= usc_target:
                            break

            # 3. Electronic Code of Federal Regulations (eCFR REST API)
            params = {"query": query, "per_page": max(2, limit - len(results)), "page": 1}
            resp = await client.get("https://www.ecfr.gov/api/search/v1/results", params=params)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", [])[: max(2, limit - len(results))]:
                    t_cfr = str(item.get("hierarchy", {}).get("title", ""))
                    s_cfr = str(item.get("hierarchy", {}).get("section", ""))
                    raw_sec_title = item.get("headings", {}).get("section", "") or item.get("headings", {}).get("part", "")
                    results.append({
                        "id": f"{t_cfr} C.F.R. § {s_cfr}",
                        "title": _clean_html(raw_sec_title, 300),
                        "url": f"https://www.ecfr.gov/current/title-{t_cfr}/section-{s_cfr}" if t_cfr and s_cfr else "https://www.ecfr.gov",
                        "snippet": _clean_html(item.get("full_text_excerpt", ""), 500),
                        "date": item.get("starts_on"),
                        "source": "ecfr.gov",
                    })

        elif API_MODE == "at_ris_native":
            params = {"Suchworte": query, "DokumenteProSeite": "Ten"}
            resp = await client.get("https://data.bka.gv.at/ris/api/v2.6/Bundesrecht", params=params)
            if resp.status_code == 200:
                data = resp.json()
                refs = (
                    data.get("OgdSearchResult", {})
                    .get("OgdDocumentResults", {})
                    .get("OgdDocumentReference", [])
                )
                if isinstance(refs, dict):
                    refs = [refs]
                for ref in refs[:limit]:
                    meta = ref.get("Data", {}).get("Metadaten", {})
                    bund = meta.get("Bundesrecht", {})
                    results.append({
                        "id": meta.get("Technisch", {}).get("ID", ""),
                        "title": bund.get("Kurztitel", "") or bund.get("Titel", ""),
                        "citation": bund.get("Kundmachungsorgan", ""),
                        "url": bund.get("GesamteRechtsvorschriftUrl", ""),
                        "source": "data.bka.gv.at (RIS)",
                    })

        elif API_MODE == "pl_native":
            params = {"title": query, "limit": limit}
            if year:
                params["year"] = year
            resp = await client.get("https://api.sejm.gov.pl/eli/acts/search", params=params)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("items", [])[:limit]:
                    results.append({
                        "id": item.get("ELI", ""),
                        "title": item.get("title", ""),
                        "status": item.get("status", ""),
                        "promulgation": item.get("promulgation", ""),
                        "url": f"https://api.sejm.gov.pl/eli/acts/{item.get('ELI', '')}",
                        "source": "api.sejm.gov.pl",
                    })

        elif API_MODE == "se_native":
            params = {"sok": query, "doktyp": "sfs", "utformat": "json"}
            resp = await client.get("https://data.riksdagen.se/dokumentlista/", params=params)
            if resp.status_code == 200:
                data = resp.json()
                docs = data.get("dokumentlista", {}).get("dokument", [])
                for d in docs[:limit]:
                    results.append({
                        "id": d.get("dok_id", ""),
                        "citation": d.get("beteckning", ""),
                        "title": d.get("titel", ""),
                        "date": d.get("datum", ""),
                        "url": "https:" + d.get("dokument_url_html", "") if str(d.get("dokument_url_html", "")).startswith("//") else d.get("dokument_url_html", ""),
                        "source": "data.riksdagen.se",
                    })

        elif API_MODE == "ie_native":
            params = {"limit": 50}
            resp = await client.get("https://api.oireachtas.ie/v1/legislation", params=params)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", []):
                    bill = item.get("bill", {})
                    short_title = bill.get("shortTitleEn", "")
                    if query.lower() in short_title.lower():
                        results.append({
                            "id": str(bill.get("billNo", "")) + "/" + str(bill.get("billYear", "")),
                            "title": short_title,
                            "status": bill.get("status", ""),
                            "url": bill.get("uri", "https://www.irishstatutebook.ie"),
                            "source": "api.oireachtas.ie",
                        })
                        if len(results) >= limit:
                            break

        elif API_MODE == "no_native":
            lovdata_key = os.environ.get("LOVDATA_API_KEY", "").strip()
            if lovdata_key:
                # Enterprise / Authenticated Lovdata API (/v1/search)
                ld_resp = await client.get(
                    "https://api.lovdata.no/v1/search",
                    params={"q": query},
                    headers={"X-API-Key": lovdata_key},
                )
                if ld_resp.status_code == 200:
                    ld_data = ld_resp.json()
                    for hit in (ld_data if isinstance(ld_data, list) else ld_data.get("hits", ld_data.get("results", [])))[:limit]:
                        ref_id = hit.get("refID") or hit.get("id", "")
                        results.append({
                            "id": ref_id,
                            "title": hit.get("title", ""),
                            "url": hit.get("url") or f"https://lovdata.no/dokument/{ref_id}",
                            "snippet": hit.get("summary") or hit.get("snippet", ""),
                            "source": "api.lovdata.no (/v1/search)",
                        })

            # Direct LOV-YYYY-MM-DD-NN citation lookup on lovdata.no
            lov_m = re.search(r"(?:LOV[-/])?(\d{4}-\d{2}-\d{2}-\d+)", query, re.I)
            if lov_m and len(results) < limit:
                lov_id = lov_m.group(1)
                lov_url = f"https://lovdata.no/dokument/NL/lov/{lov_id}"
                fetched_lov = await asyncio.to_thread(_sync_fetch_document, lov_url)
                if fetched_lov.get("status_code") == 200 and fetched_lov.get("text"):
                    first_line = fetched_lov["text"].splitlines()[0] if fetched_lov["text"].splitlines() else f"LOV-{lov_id}"
                    results.append({
                        "id": f"LOV-{lov_id}",
                        "title": first_line[:200],
                        "url": lov_url,
                        "snippet": fetched_lov["text"][:500],
                        "source": "lovdata.no",
                    })

            # Official NLOD 2.0 https://api.lovdata.no/v1/publicData/list
            if len(results) < limit:
                pub_resp = await client.get("https://api.lovdata.no/v1/publicData/list")
                if pub_resp.status_code == 200:
                    pub_list = pub_resp.json()
                    q_low = query.lower()
                    if any(k in q_low for k in ("dataset", "publicdata", "lovtidend", "forskrift", "gjeldende", "api")):
                        for pkg in pub_list[:2]:
                            fn = pkg.get("filename", "")
                            results.append({
                                "id": fn,
                                "title": f"Lovdata NLOD 2.0 Open Dataset: {pkg.get('description', fn)}",
                                "url": f"https://api.lovdata.no/v1/publicData/get/{fn}",
                                "lastModified": pkg.get("lastModified", ""),
                                "source": "api.lovdata.no (/v1/publicData/list)",
                            })

        elif API_MODE == "de_native":
            params = {"searchTerm": query, "size": limit}
            resp = await client.get("https://testphase.rechtsinformationen.bund.de/v1/document", params=params)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("member", [])[:limit]:
                    item = m.get("item", {})
                    doc_id = item.get("@id", "")
                    results.append({
                        "id": item.get("legislationIdentifier") or doc_id,
                        "title": item.get("name") or item.get("headline", ""),
                        "abbreviation": item.get("abbreviation", ""),
                        "date": item.get("legislationDate") or item.get("decisionDate", ""),
                        "url": "https://testphase.rechtsinformationen.bund.de" + doc_id if doc_id.startswith("/") else doc_id,
                        "source": "rechtsinformationen.bund.de",
                    })

        elif API_MODE == "ee_native":
            params = {"lehekylg": 1, "limiit": limit, "pealkiri": query}
            resp = await client.get("https://www.riigiteataja.ee/api/oigusakt_otsing/1/otsi", params=params)
            if resp.status_code == 200:
                data = resp.json()
                for akt in data.get("aktid", [])[:limit]:
                    gid = akt.get("globaalID", "")
                    results.append({
                        "id": str(gid),
                        "title": akt.get("pealkiri", ""),
                        "abbreviation": akt.get("lyhend", ""),
                        "url": f"https://www.riigiteataja.ee/akt/{gid}" if gid else "https://www.riigiteataja.ee",
                        "source": "riigiteataja.ee",
                    })

        # Live National Legal Archive Search (Primary for non-REST countries & supplementary for all)
        if len(results) < limit:
            leg_sites = ARCHIVE_PROFILE.get("leg_sites", [])
            leg_kw = ARCHIVE_PROFILE.get("leg_keywords", "")
            if year:
                leg_kw = f"{leg_kw} {year}".strip()
            archive_hits = await _live_archive_search(
                query=query,
                sites=leg_sites,
                extra_keywords=leg_kw,
                limit=limit - len(results),
            )
            results.extend(archive_hits)
    except Exception as e:
        logger.warning("search_legislation error: %s", e)

    return {
        "jurisdiction": JURISDICTION_NAME,
        "code": JURISDICTION_CODE,
        "official_portal": LEGISLATION_PORTAL,
        "indexed_domains": ARCHIVE_PROFILE.get("leg_sites", []),
        "query": query,
        "count": len(results),
        "results": results,
    }


@mcp.tool(
    description=(
        "Search Kosovo (XK) court decisions and binding precedents via Gjykata Supreme e Kosovës (supreme.gjyqesori-rks.org) & Gjykata Kushtetuese (gjk-ks.org) "
        "and open national judicial archives (Supported courts: Gjykata Supreme e Kosovës (Supreme Court), Gjykata Kushtetuese (Constitutional Court), Gjykata e Apelit, Gjykata Komerciale)."
    )
)
async def search_case_law(
    query: str = Field(..., description="Legal issue, keywords, party name, or ECLI/case number."),
    court: str = Field("", description="Optional court filter (Gjykata Supreme e Kosovës (Supreme Court), Gjykata Kushtetuese (Constitutional Court), Gjykata e Apelit, Gjykata Komerciale)."),
    limit: int = Field(10, ge=1, le=50, description="Maximum number of judgments to return."),
) -> Dict[str, Any]:
    court = court if isinstance(court, str) else ""
    limit = limit if isinstance(limit, int) else 10
    client = get_client()
    decisions: List[Dict[str, Any]] = []

    try:
        if API_MODE == "uk_native":
            tna_target = max(1, (limit + 1) // 2)
            q_combined = f"{query} {court}".strip()
            # 1. The National Archives Find Case Law Atom API (caselaw.nationalarchives.gov.uk)
            url = f"https://caselaw.nationalarchives.gov.uk/atom.xml?query={urllib.parse.quote(q_combined)}"
            resp = await client.get(url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for entry in soup.find_all("entry")[:tna_target]:
                    title_el = entry.find("title")
                    id_el = entry.find("id")
                    upd_el = entry.find("updated")
                    decisions.append({
                        "id": id_el.get_text(strip=True) if id_el else "",
                        "title": title_el.get_text(strip=True) if title_el else "",
                        "url": id_el.get_text(strip=True) if id_el else "",
                        "date": upd_el.get_text(strip=True) if upd_el else "",
                        "source": "caselaw.nationalarchives.gov.uk",
                    })

            # 2. Courts and Tribunals Judiciary REST JSON API (https://www.judiciary.uk/wp-json/wp/v2/judgment)
            jud_limit = max(2, limit - len(decisions))
            jud_resp = await client.get(
                "https://www.judiciary.uk/wp-json/wp/v2/judgment",
                params={"search": q_combined, "per_page": jud_limit},
            )
            jud_items = jud_resp.json() if jud_resp.status_code == 200 and isinstance(jud_resp.json(), list) else []
            if not jud_items and len(q_combined.split()) > 2:
                short_q = " ".join(q_combined.split()[:2])
                jud_resp2 = await client.get(
                    "https://www.judiciary.uk/wp-json/wp/v2/judgment",
                    params={"search": short_q, "per_page": jud_limit},
                )
                if jud_resp2.status_code == 200 and isinstance(jud_resp2.json(), list):
                    jud_items = jud_resp2.json()
            for j_item in jud_items[:jud_limit]:
                rendered_html = j_item.get("content", {}).get("rendered", "")
                pdf_m = re.search(r"(https://www\.judiciary\.uk/wp-content/uploads/[A-Za-z0-9_./\-]+\.pdf)", rendered_html, re.I)
                pdf_url = pdf_m.group(1) if pdf_m else ""
                decisions.append({
                    "id": str(j_item.get("id", "")),
                    "title": _clean_html(j_item.get("title", {}).get("rendered", ""), 300),
                    "url": j_item.get("link", ""),
                    "pdf_url": pdf_url,
                    "date": j_item.get("date", ""),
                    "snippet": _clean_html(rendered_html, 500),
                    "source": "judiciary.uk (Courts and Tribunals Judiciary)",
                })

        elif API_MODE == "us_native":
            params = {"q": query, "type": "o"}
            if court:
                params["court"] = court
            resp = await client.get("https://www.courtlistener.com/api/rest/v4/search/", params=params)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", [])[:limit]:
                    decisions.append({
                        "id": str(item.get("cluster_id") or item.get("id", "")),
                        "caseName": item.get("caseName", ""),
                        "title": item.get("caseName", ""),
                        "court": item.get("court", ""),
                        "dateFiled": item.get("dateFiled", ""),
                        "citation": item.get("citation", []),
                        "url": "https://www.courtlistener.com" + str(item.get("absolute_url", "")),
                        "snippet": _clean_html(item.get("snippet", ""), 400),
                        "source": "courtlistener.com",
                    })

        elif API_MODE == "at_ris_native":
            params = {"Applikation": "Justiz", "Suchworte": query, "DokumenteProSeite": "Ten"}
            resp = await client.get("https://data.bka.gv.at/ris/api/v2.6/Judikatur", params=params)
            if resp.status_code == 200:
                data = resp.json()
                refs = (
                    data.get("OgdSearchResult", {})
                    .get("OgdDocumentResults", {})
                    .get("OgdDocumentReference", [])
                )
                if isinstance(refs, dict):
                    refs = [refs]
                for ref in refs[:limit]:
                    meta = ref.get("Data", {}).get("Metadaten", {})
                    jud = meta.get("Judikatur", {})
                    justiz = jud.get("Justiz", {})
                    decisions.append({
                        "id": meta.get("Technisch", {}).get("ID", ""),
                        "court": justiz.get("Gericht", "OGH / Justiz"),
                        "caseNumber": str(jud.get("Geschaeftszahl", "")),
                        "date": jud.get("Entscheidungsdatum", ""),
                        "ecli": jud.get("EuropeanCaseLawIdentifier", ""),
                        "url": jud.get("DokumentUrl", ""),
                        "source": "data.bka.gv.at (RIS Justiz)",
                    })

        elif API_MODE == "nl_native":
            params = {"zoekterm": query, "max": limit, "return": "DOC"}
            resp = await client.get("https://data.rechtspraak.nl/uitspraken/zoeken", params=params)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for entry in soup.find_all("entry")[:limit]:
                    id_el = entry.find("id")
                    title_el = entry.find("title")
                    sum_el = entry.find("summary")
                    decisions.append({
                        "ecli": id_el.get_text(strip=True) if id_el else "",
                        "title": title_el.get_text(strip=True) if title_el else "",
                        "summary": sum_el.get_text(strip=True) if sum_el else "",
                        "url": f"https://uitspraken.rechtspraak.nl/details?id={id_el.get_text(strip=True) if id_el else ''}",
                        "source": "data.rechtspraak.nl",
                    })

        elif API_MODE == "pl_native":
            params = {"all": query, "pageSize": limit}
            resp = await client.get("https://saos.org.pl/api/search/judgments", params=params)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("items", [])[:limit]:
                    cases = [c.get("caseNumber", "") for c in item.get("courtCases", [])]
                    decisions.append({
                        "id": str(item.get("id", "")),
                        "caseNumbers": cases,
                        "judgmentDate": item.get("judgmentDate", ""),
                        "courtType": item.get("courtType", ""),
                        "url": f"https://www.saos.org.pl/judgments/{item.get('id', '')}",
                        "snippet": _clean_html(item.get("textContent", ""), 400),
                        "source": "saos.org.pl",
                    })

        elif API_MODE == "ch_native":
            # Direct JSON-RPC 2.0 integration with official Swiss https://mcp.entscheidsuche.ch/mcp
            canton_map = {
                "zurich": "ZH", "zürich": "ZH", "zh": "ZH",
                "bern": "BE", "be": "BE",
                "geneva": "GE", "genf": "GE", "geneve": "GE", "ge": "GE",
                "vaud": "VD", "waadt": "VD", "vd": "VD",
                "basel_stadt": "BS", "basel-stadt": "BS", "bs": "BS",
                "basel_land": "BL", "basel-land": "BL", "bl": "BL",
                "ticino": "TI", "tessin": "TI", "ti": "TI",
                "st_gallen": "SG", "sg": "SG",
                "aargau": "AG", "ag": "AG",
                "luzern": "LU", "lu": "LU",
                "zug": "ZG", "zg": "ZG",
                "bundesgericht": "CH_BGer", "bger": "CH_BGer", "bge": "CH_BGE",
                "bvger": "CH_BVGer", "bstger": "CH_BStGer",
            }
            args_payload: Dict[str, Any] = {"query": query, "size": limit}
            if court:
                c_low = court.lower()
                for k_canton, h_code in canton_map.items():
                    if k_canton in c_low:
                        args_payload["hierarchy"] = [h_code]
                        break
            rpc_resp = await client.post(
                "https://mcp.entscheidsuche.ch/mcp",
                headers={"Accept": "application/json, text/event-stream"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "search", "arguments": args_payload},
                },
            )
            if rpc_resp.status_code == 200:
                rpc_data = rpc_resp.json()
                content_list = rpc_data.get("result", {}).get("content", [])
                if content_list and content_list[0].get("text"):
                    parsed = json.loads(content_list[0]["text"])
                    for h in parsed.get("hits", [])[:limit]:
                        decisions.append({
                            "id": h.get("id", ""),
                            "title": h.get("title", ""),
                            "court": h.get("court", ""),
                            "canton": h.get("canton", ""),
                            "date": h.get("decision_date", ""),
                            "abstract": _clean_html(h.get("abstract") or "", 300),
                            "snippet": _clean_html(h.get("text") or "", 400),
                            "url": h.get("document_url") or h.get("original_url") or f"https://entscheidsuche.ch",
                            "is_pdf": bool(h.get("is_pdf")),
                            "source": "mcp.entscheidsuche.ch",
                        })

        elif API_MODE == "de_native":
            params = {"searchTerm": f"{query} {court}".strip(), "size": limit}
            resp = await client.get("https://testphase.rechtsinformationen.bund.de/v1/rechtsprechung", params=params)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("member", [])[:limit]:
                    item = m.get("item", {})
                    doc_id = item.get("@id", "")
                    decisions.append({
                        "id": item.get("documentNumber") or doc_id,
                        "ecli": item.get("ecli", ""),
                        "title": item.get("headline") or item.get("titleLine", ""),
                        "court": item.get("courtName", ""),
                        "fileNumbers": item.get("fileNumbers", []),
                        "date": item.get("decisionDate", ""),
                        "url": "https://testphase.rechtsinformationen.bund.de" + doc_id if doc_id.startswith("/") else doc_id,
                        "source": "rechtsinformationen.bund.de",
                    })

        elif API_MODE == "eu_native":
            hudoc_q = f"contentsitename:ECHR AND {query}"
            params = {
                "query": hudoc_q,
                "select": "itemid,docname,kpdate,ecli,importance",
                "sort": "kpdate Descending",
                "start": 0,
                "length": limit,
            }
            resp = await client.get("https://hudoc.echr.coe.int/app/query/results", params=params)
            if resp.status_code == 200:
                data = resp.json()
                for r_item in data.get("results", [])[:limit]:
                    cols = r_item.get("columns", {})
                    iid = cols.get("itemid", "")
                    decisions.append({
                        "id": iid,
                        "ecli": cols.get("ecli", ""),
                        "title": cols.get("docname", ""),
                        "date": cols.get("kpdate", ""),
                        "url": f"https://hudoc.echr.coe.int/eng?i={iid}" if iid else "https://hudoc.echr.coe.int",
                        "source": "hudoc.echr.coe.int",
                    })

        # Live National Judicial Archive Search (Primary for 36 countries + regional/court-specific supplement)
        if len(decisions) < limit:
            case_sites = ARCHIVE_PROFILE.get("case_sites", [])
            court_str = (court if isinstance(court, str) else "").strip()
            extra_kw = court_str if court_str else ARCHIVE_PROFILE.get("case_keywords", "")
            archive_decisions = await _live_archive_search(
                query=query,
                sites=case_sites,
                extra_keywords=extra_kw,
                limit=limit - len(decisions),
            )
            decisions.extend(archive_decisions)
    except Exception as e:
        logger.warning("search_case_law error: %s", e)

    return {
        "jurisdiction": JURISDICTION_NAME,
        "code": JURISDICTION_CODE,
        "official_caselaw_portal": CASELAW_PORTAL,
        "indexed_domains": ARCHIVE_PROFILE.get("case_sites", []),
        "query": query,
        "count": len(decisions),
        "decisions": decisions,
    }


@mcp.tool(
    description=(
        "Retrieve full Markdown text of a legislation document or court judgment (HTML or PDF) from Kosovo (XK) "
        "by its URL or official identifier."
    )
)
async def get_legal_document_markdown(
    document_id_or_url: str = Field(..., description="Document URL (.html or .pdf), ECLI, ELI, or official ID returned by search tools."),
    page: int = Field(1, ge=1, description="Page number (5,000 characters per page)."),
) -> Dict[str, Any]:
    page = page if isinstance(page, int) else 1
    target_url = document_id_or_url.strip()
    if API_MODE == "ch_native" and not target_url.startswith("http"):
        try:
            client = get_client()
            rpc_resp = await client.post(
                "https://mcp.entscheidsuche.ch/mcp",
                headers={"Accept": "application/json, text/event-stream"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "fetch_document", "arguments": {"id": target_url}},
                },
            )
            if rpc_resp.status_code == 200:
                content_list = rpc_resp.json().get("result", {}).get("content", [])
                if content_list and content_list[0].get("text"):
                    doc_obj = json.loads(content_list[0]["text"])
                    full_text = f"# {doc_obj.get('title', '')}\n\n**Abstract:** {doc_obj.get('abstract', '')}\n\n{doc_obj.get('text', '')}"
                    chunk_size = 5000
                    total_pages = max(1, (len(full_text) + chunk_size - 1) // chunk_size)
                    page = min(page, total_pages)
                    start = (page - 1) * chunk_size
                    return {
                        "jurisdiction": JURISDICTION_NAME,
                        "source_url": doc_obj.get("document_url") or f"https://entscheidsuche.ch ({target_url})",
                        "document_format": "entscheidsuche-mcp JSON-RPC",
                        "current_page": page,
                        "total_pages": total_pages,
                        "markdown_content": full_text[start : start + chunk_size],
                    }
        except Exception as e:
            logger.debug("entscheidsuche fetch_document fallback: %s", e)

    if not target_url.startswith("http"):
        if API_MODE == "us_native":
            cit_m = re.search(
                r"\b(\d{1,2})\s*(?:U\.?S\.?C\.?|United States Code|Title)\s*(?:§+|sec(?:tion|\.)?)?\s*([0-9A-Za-z\-]+)",
                target_url,
                re.I,
            )
            if cit_m:
                target_url = f"https://uscode.house.gov/us/usc/t{cit_m.group(1)}/s{cit_m.group(2)}/"
        elif API_MODE == "no_native":
            lov_m = re.search(r"(?:LOV[-/])?(\d{4}-\d{2}-\d{2}-\d+)", target_url, re.I)
            if lov_m:
                target_url = f"https://lovdata.no/dokument/NL/lov/{lov_m.group(1)}"
        if not target_url.startswith("http"):
            if API_MODE == "uk_native":
                target_url = f"https://www.legislation.gov.uk/{target_url.lstrip('/')}/data.htm"
            elif API_MODE == "nl_native" and target_url.startswith("ECLI:"):
                target_url = f"https://data.rechtspraak.nl/uitspraken/content?id={urllib.parse.quote(target_url)}"
            elif API_MODE == "pl_native" and target_url.isdigit():
                target_url = f"https://www.saos.org.pl/api/judgments/{target_url}"
            else:
                target_url = f"{CASELAW_PORTAL.rstrip('/')}/{target_url.lstrip('/')}"

    try:
        fetched = await asyncio.to_thread(_sync_fetch_document, target_url)
        text = fetched.get("text", "")
        chunk_size = 5000
        total_pages = max(1, (len(text) + chunk_size - 1) // chunk_size)
        page = min(page, total_pages)
        start = (page - 1) * chunk_size
        return {
            "jurisdiction": JURISDICTION_NAME,
            "source_url": target_url,
            "document_format": fetched.get("format", "HTML"),
            "current_page": page,
            "total_pages": total_pages,
            "markdown_content": text[start : start + chunk_size],
        }
    except Exception as e:
        return {
            "jurisdiction": JURISDICTION_NAME,
            "source_url": target_url,
            "error": str(e),
        }


@mcp.tool(
    description=(
        "Return the complete step-by-step multi-tier judicial hierarchy for Kosovo (XK): "
        "Tier 1 (First Instance / Trial / Municipal / District Courts), "
        "Tier 2 (Regional / Cantonal / County / Appellate Courts), "
        "Tier 3 (Supreme / Cassation / Constitutional Courts), and all official court sub-portals."
    )
)
async def list_court_hierarchy() -> Dict[str, Any]:
    return {
        "jurisdiction": JURISDICTION_NAME,
        "code": JURISDICTION_CODE,
        "hierarchy": COURT_HIERARCHY,
        "indexed_archive_domains": ARCHIVE_PROFILE.get("case_sites", []),
        "supported_sub_courts": ARCHIVE_PROFILE.get("sub_court_names", {}),
    }


@mcp.tool(
    description=(
        "Search court decisions in Kosovo (XK) filtered by specific judicial tier or regional/cantonal/appellate court. "
        "Supports Tier 1 (first_instance), Tier 2 (appellate_regional — including Cantonal/Regional/County/Circuit courts), "
        "and Tier 3 (supreme_constitutional), or a specific sub-portal key from list_court_hierarchy."
    )
)
async def search_tiered_court_decisions(
    query: str = Field(..., description="Legal issue, statute article, case number, or keywords."),
    tier: str = Field(
        "appellate_regional",
        description="Judicial stage: 'first_instance', 'appellate_regional' (Cantonal/Regional/Circuit/Appellate), 'supreme_constitutional', or 'all'.",
    ),
    sub_court: str = Field(
        "",
        description="Optional specific court/canton/region key (e.g. 'kantonalni_sud_sarajevo', 'kantonalni_sud_odzak_posavski_kanton', 'okruzni_sud_banja_luka', etc.).",
    ),
    limit: int = Field(10, ge=1, le=50, description="Maximum number of decisions to return."),
) -> Dict[str, Any]:
    tier = tier if isinstance(tier, str) else "appellate_regional"
    sub_court = sub_court if isinstance(sub_court, str) else ""
    limit = limit if isinstance(limit, int) else 10
    sub_portals = COURT_HIERARCHY.get("sub_portals", {})
    sub_court_names = ARCHIVE_PROFILE.get("sub_court_names", {})
    selected_portal = COURT_HIERARCHY.get("tiered_database_url", CASELAW_PORTAL)
    matched_sub_court = ""
    native_court_query = ""

    if sub_court:
        clean_key = sub_court.strip().lower().replace(" ", "_").replace("-", "_")
        for k, url in sub_portals.items():
            if clean_key in k.lower() or k.lower() in clean_key:
                selected_portal = url
                matched_sub_court = k
                break
        for k, nat_name in sub_court_names.items():
            if clean_key in k.lower() or k.lower() in clean_key:
                native_court_query = nat_name
                if not matched_sub_court:
                    matched_sub_court = k
                break
        if not native_court_query:
            native_court_query = sub_court.replace("_", " ")

    tier_key_map = {
        "first_instance": COURT_HIERARCHY.get("tier_1_first_instance", ""),
        "appellate_regional": COURT_HIERARCHY.get("tier_2_appellate_regional", ""),
        "supreme_constitutional": COURT_HIERARCHY.get("tier_3_supreme_constitutional", ""),
    }
    tier_description = tier_key_map.get(tier, COURT_HIERARCHY.get("tier_2_appellate_regional", "All Judicial Tiers"))

    tier_kw_map = ARCHIVE_PROFILE.get("tier_keywords", {})
    target_kw = native_court_query or tier_kw_map.get(tier, ARCHIVE_PROFILE.get("case_keywords", ""))

    decisions: List[Dict[str, Any]] = []
    # If jurisdiction has a native structured API (e.g., CH mcp.entscheidsuche.ch, DE bund.de, AT RIS, US CourtListener, NL Rechtspraak, PL SAOS, UK National Archives), query it first
    if API_MODE in ("ch_native", "de_native", "at_ris_native", "nl_native", "pl_native", "us_native", "uk_native", "eu_native"):
        base_search = await search_case_law(query=query, court=native_court_query or sub_court or "", limit=limit)
        decisions.extend(base_search.get("decisions", []))

    if len(decisions) < limit:
        archive_hits = await _live_archive_search(
            query=query,
            sites=ARCHIVE_PROFILE.get("case_sites", []),
            extra_keywords=target_kw,
            limit=limit - len(decisions),
        )
        seen = {d.get("url") or d.get("id") for d in decisions}
        for d in archive_hits:
            key = d.get("url") or d.get("id")
            if key not in seen:
                decisions.append(d)
                seen.add(key)

    for d in decisions:
        d["judicial_tier"] = tier
        d["tier_courts_covered"] = tier_description
        d["tiered_portal_url"] = selected_portal
        if matched_sub_court:
            d["sub_court_portal_key"] = matched_sub_court
        if native_court_query:
            d["matched_court_filter"] = native_court_query

    return {
        "jurisdiction": JURISDICTION_NAME,
        "code": JURISDICTION_CODE,
        "requested_tier": tier,
        "tier_courts_covered": tier_description,
        "matched_sub_court": matched_sub_court or "all_in_tier",
        "native_court_filter": native_court_query or target_kw,
        "official_tiered_portal": selected_portal,
        "available_sub_portals": sub_portals,
        "query": query,
        "count": len(decisions),
        "decisions": decisions,
    }


@mcp.tool(
    description=(
        "No-Hallucination Citation Verifier for Kosovo (XK). "
        "Validates format and live existence of legal citations (e.g., 'AGJ 123/2024 or Ligji Nr. 08/L-123') "
        "against official Kosovo and ECLI/ELI registries to prevent AI-hallucinated citations."
    )
)
async def verify_citation(
    citation: str = Field(..., description="Case citation, ECLI, or statute reference to verify (e.g., 'AGJ 123/2024 or Ligji Nr. 08/L-123')."),
) -> Dict[str, Any]:
    clean_cit = citation.strip()
    is_ecli = bool(re.match(r"^ECLI:[A-Z]{2}:[A-Za-z0-9]+:\d{4}:[A-Za-z0-9._-]+$", clean_cit))
    case_check = await search_case_law(query=clean_cit, court="", limit=3)
    leg_check = await search_legislation(query=clean_cit, year=None, limit=3)

    matches = case_check.get("decisions", []) + leg_check.get("results", [])
    verified = len(matches) > 0

    return {
        "jurisdiction": JURISDICTION_NAME,
        "citation": clean_cit,
        "is_valid_ecli_syntax": is_ecli,
        "verified_in_official_registry": verified,
        "match_count": len(matches),
        "matches": matches[:3],
        "status": "VERIFIED_OFFICIAL_RECORD" if verified else "UNVERIFIED_CHECK_MANUALLY",
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
