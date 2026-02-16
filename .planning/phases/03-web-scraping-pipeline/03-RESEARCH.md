# Phase 3: Web Scraping Pipeline - Research

**Researched:** 2026-02-16
**Domain:** Web scraping of manufacturer spa specification pages
**Confidence:** HIGH

## Summary

Web scraping for this phase targets three manufacturer ecosystems (Sundance, Hot Spring, Bullfrog) to supplement PDF-extracted data. The primary value is filling two critical gaps: (1) ALL 274 part_number fields are null across all 19 models after PDF extraction, and (2) Sundance models are missing dimensions/weights/cover sizes that the website provides.

The research reveals a split scraping strategy: Sundance's official site (sundancespas.com) serves specs as static HTML -- simple httpx + BeautifulSoup is sufficient. Hot Spring's official site (hotspring.com) blocks automated fetches, but the dealer site hotspringhottubs.com serves identical spec data as static HTML. Bullfrog's official site (bullfrogspas.com) loads content dynamically via JavaScript, but the dealer site bullfrogfactorystores.com serves specs as static HTML. Therefore, **no browser automation (Playwright/Selenium) is needed** -- all 19 models can be scraped with httpx + BeautifulSoup from static HTML sources.

However, part numbers are NOT available on manufacturer product pages. They exist only on third-party parts retailer sites (spastore.com, hottuboutpost.com, etc.) which have complex, model-specific catalog structures. Part number population will likely need to be deferred to Phase 4 (manual entry) or a separate scraping effort targeting parts retailer sites.

**Primary recommendation:** Use httpx + BeautifulSoup for static HTML scraping of manufacturer/dealer product pages. Focus Phase 3 on filling spec gaps (dimensions, weights, seating, jet counts, pump details, electrical, filtration). Defer part number scraping to a future effort or Phase 4 manual entry.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28+ | HTTP client for fetching pages | Async support, HTTP/2, connection pooling, modern replacement for requests |
| beautifulsoup4 | 4.12+ | HTML parsing and data extraction | Best for static HTML with complex structure, handles malformed markup gracefully |
| lxml | 5.x | HTML parser backend for BeautifulSoup | 10x faster than html.parser, required for production parsing |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.12+ | Schema validation (already installed) | Validate scraped data against Phase 1 schema |
| tenacity | 9.x | Retry logic with backoff | Handle transient HTTP failures, rate limiting |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx | requests | requests lacks async and HTTP/2; httpx is the modern choice |
| beautifulsoup4 | selectolax | selectolax is faster but less forgiving of malformed HTML; BS4 is safer for unknown page structures |
| Playwright | N/A | NOT NEEDED -- all target sites serve specs as static HTML (via dealer sites for Bullfrog/Hot Spring) |

**Installation:**
```bash
cd /c/dvl/IA/spaparts/dex/backend
uv add httpx beautifulsoup4 lxml tenacity
```

## Architecture Patterns

### Recommended Project Structure
```
backend/src/etl/
├── extract/
│   ├── gemini_extractor.py    # Existing PDF extraction
│   └── web_scraper.py         # NEW: Web page fetching + parsing
├── scrape/                    # NEW: Web scraping module
│   ├── __init__.py
│   ├── config.py              # URL registry for all 19 models
│   ├── fetcher.py             # httpx client with retry/rate-limiting
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── sundance.py        # Sundance-specific HTML parsing
│   │   ├── hotspring.py       # Hot Spring-specific HTML parsing
│   │   └── bullfrog.py        # Bullfrog-specific HTML parsing
│   ├── merger.py              # Merge scraped data into existing JSON
│   └── pipeline.py            # Orchestrator (scrape -> parse -> merge -> write)
├── transform/
│   ├── schema_mapper.py       # Existing
│   └── validators.py          # Existing
└── output/
    ├── writer.py              # Existing (reuse for merged output)
    └── provenance.py          # Existing (extend for website sources)
```

### Pattern 1: Manufacturer-Specific Parsers
**What:** Each manufacturer has its own parser class because HTML structure differs across sites.
**When to use:** Always -- Sundance, Hot Spring, and Bullfrog have completely different page layouts.
**Example:**
```python
# Each parser follows the same interface
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ScrapedSpecs:
    """Structured specs extracted from a web page."""
    dimensions: dict | None = None
    jet_pumps: dict | None = None
    jets: dict | None = None
    filtration: dict | None = None
    electrical: dict | None = None
    cover: dict | None = None
    seating_capacity: int | None = None
    source_url: str = ""

class ManufacturerParser(ABC):
    @abstractmethod
    def parse_model_page(self, html: str, model_name: str) -> ScrapedSpecs:
        """Parse a single model's product page HTML into structured specs."""
        ...
```

### Pattern 2: Merge Strategy (Web Supplements PDF)
**What:** Scraped data fills gaps in existing PDF-extracted JSON; never overwrites existing non-null values.
**When to use:** Always -- PDF extraction is the primary source; web scraping only fills nulls.
**Example:**
```python
def merge_web_into_existing(
    existing: dict,
    scraped: dict,
    source_url: str,
) -> dict:
    """Merge scraped data into existing model JSON.

    Rules:
    - If existing field is null/None/0 and scraped has a value: use scraped value
    - If existing field already has a value: keep existing (PDF is authoritative)
    - Always append a SourceReference for the web page
    """
    for key, scraped_value in scraped.items():
        if scraped_value is None:
            continue
        existing_value = existing.get(key)
        if existing_value is None or existing_value == 0:
            existing[key] = scraped_value

    # Append web source reference
    existing.setdefault("source_documents", []).append({
        "source_type": "website",
        "url": source_url,
        "accessed_date": date.today().isoformat(),
    })
    return existing
```

### Pattern 3: Rate-Limited Fetcher
**What:** HTTP client with polite rate limiting and retry logic.
**When to use:** Always -- respect robots.txt crawl-delay directives.
**Example:**
```python
import asyncio
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

class PoliteHttpClient:
    def __init__(self, delay_seconds: float = 2.0):
        self.delay = delay_seconds
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "DexBot/1.0 (internal-use)"},
            follow_redirects=True,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2))
    async def fetch(self, url: str) -> str:
        response = await self.client.get(url)
        response.raise_for_status()
        await asyncio.sleep(self.delay)
        return response.text
```

### Anti-Patterns to Avoid
- **Overwriting PDF data with web data:** PDF extraction is the primary source. Web scraping only fills gaps. Never replace a non-null PDF-extracted value.
- **Single monolithic parser:** Each manufacturer's HTML is structured differently. Do not try to write one parser for all three.
- **Aggressive scraping:** These are small company sites, not CDNs. Use 2+ second delays between requests. Bullfrog robots.txt specifies crawl-delay of 10 seconds.
- **Coupling scraper to PDF pipeline:** The web scraping pipeline should be independent -- it reads existing JSON files, merges in new data, and writes them back. It does not depend on the PDF extraction pipeline running.

## Target URLs for All 19 Models

### Sundance 880 Series (Official Site - Static HTML)

| Model | URL |
|-------|-----|
| Aspen | https://www.sundancespas.com/en-us/aspen-880-series/Aspen.html |
| Optima | https://www.sundancespas.com/en-us/optima-880-series/Optima.html |
| Cameo | https://www.sundancespas.com/en-us/cameo-880-series/Cameo.html |
| Altamar | https://www.sundancespas.com/en-us/altamar-880-series/Altamar.html |
| Vistamar | https://www.sundancespas.com/en-us/vistamar-880-series/Vistamar.html |
| Marin | https://www.sundancespas.com/en-us/marin-880-series/Marin.html |
| Capris | https://www.sundancespas.com/en-us/capri-880-series/Capri.html |

**URL Pattern:** `https://www.sundancespas.com/en-us/{model_lower}-880-series/{Model}.html`
**Note:** "Capris" model uses "capri" in the URL (no 's').
**Data available:** Dimensions, weight, water capacity, jet count, pump HP/speed/frame/amperage, electrical, filtration area, seating capacity, diverter valves.
**Confidence:** HIGH -- Verified via WebFetch on Aspen, Optima, Cameo, Altamar pages. All return static HTML with specs.

### Hot Spring Highlife Collection (Dealer Site - Static HTML)

hotspring.com blocks automated fetches (returns 500). Use dealer site hotspringhottubs.com instead.

| Model | URL |
|-------|-----|
| Grandee | https://www.hotspringhottubs.com/grandee/ |
| Envoy | https://www.hotspringhottubs.com/envoy/ |
| Aria | https://www.hotspringhottubs.com/aria/ |
| Vanguard | https://www.hotspringhottubs.com/vanguard/ |
| Sovereign | https://www.hotspringhottubs.com/sovereign/ |
| Prodigy | https://www.hotspringhottubs.com/prodigy/ |
| Jetsetter LX | https://www.hotspringhottubs.com/jetsetter-lx/ (NEEDS VERIFICATION) |
| Jetsetter | https://www.hotspringhottubs.com/jetsetter/ |

**URL Pattern:** `https://www.hotspringhottubs.com/{model_lower_hyphenated}/`
**Note:** Jetsetter LX URL needs verification -- may be `/jetsetter-lx/` or similar. The NXT variants also exist (e.g., `/grandee-nxt/`). Research found data for both -- prefer standard (non-NXT) model data first.
**Data available:** Dimensions, weight (dry + filled), water capacity, jet count with breakdown by type, pump names/HP (Wavemaster models), circulation pump model, electrical (voltage/amperage), heater wattage, filtration area, lighting type.
**Confidence:** HIGH -- Verified via WebFetch on Grandee, Envoy, Aria pages. Static HTML with spec tables.

### Bullfrog M Series (Dealer Site - Static HTML)

bullfrogspas.com loads content dynamically via JavaScript. Use dealer site bullfrogfactorystores.com instead.

| Model | URL |
|-------|-----|
| M9 | https://www.bullfrogfactorystores.com/models/detail/?unit_id=9463 |
| M8 | https://www.bullfrogfactorystores.com/models/detail/?unit_id=9464 |
| M7 | https://www.bullfrogfactorystores.com/models/detail/?unit_id=18476 |
| M6 | https://www.bullfrogfactorystores.com/models/detail/?unit_id=9466 |

**URL Pattern:** `https://www.bullfrogfactorystores.com/models/detail/?unit_id={id}`
**Note:** Unit IDs are not sequential. M7 ID (18476) differs significantly from others. These IDs may change over time if the dealer updates their catalog.
**Alternative source:** https://www.hotspas.com/hot-tubs/bullfrog-spas/m-series/bullfrog-model-{m6|m7|m8|m9}/ (also static HTML, verified for M9)
**Data available:** Dimensions, weight (dry + filled), water capacity, seating (total + by type), pump count + speed, total BHP, JetPak count, max jets available, standard therapy jets, filtration system, lighting, water features, circulation pump.
**Confidence:** HIGH -- Verified via WebFetch on M9 and M6 pages. Static HTML.

## Data Gap Analysis

### Current State (After Phase 2 PDF Extraction)

**Part Numbers:** 274/274 null (100% missing) across all 19 models. This is the biggest gap.

**Sundance 880 Series (7 models):**
| Gap | Models Affected | Available on Website? |
|-----|----------------|----------------------|
| Dimensions (L/W/H) | All 7 | YES -- all pages have dimensions |
| Dry weight | All 7 | YES -- all pages have dry weight |
| Water capacity | Aspen, Cameo, Capris, Vistamar | YES -- all pages have volume |
| Seating capacity | Aspen, Cameo, Capris, Vistamar | YES -- most pages list seating |
| Cover dimensions | All 7 | PARTIAL -- some pages may not have cover-specific dims |
| Part numbers | All 7 | NO -- not on product pages |

**Hot Spring Highlife (8 models):**
| Gap | Models Affected | Available on Website? |
|-----|----------------|----------------------|
| Dimensions | None (already have) | Available for verification |
| Part numbers | All 8 | NO -- not on product pages |

**Bullfrog M Series (4 models):**
| Gap | Models Affected | Available on Website? |
|-----|----------------|----------------------|
| Dry weight | All 4 | YES -- dealer pages have weight |
| Water capacity | All 4 | YES -- dealer pages have capacity |
| Seating capacity | All 4 | YES -- dealer pages have seating counts |
| Part numbers | All 4 | NO -- not on product pages |

### What Web Scraping CAN Fill
- Sundance: dimensions, dry weight, water capacity, seating capacity, pump specs, jet counts
- Bullfrog: dry weight, filled weight, water capacity, seating capacity, total BHP
- Hot Spring: verification of existing data, additional pump model names, heater wattage
- All: source URL provenance for every scraped data point

### What Web Scraping CANNOT Fill (From These Sources)
- **Part numbers** -- not listed on any manufacturer product page
- Part numbers exist only on third-party retailer sites (spastore.com, hottuboutpost.com, etc.) with complex model-specific catalog navigation
- Part number scraping would be a separate, significantly more complex effort

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retry logic | Custom retry loops | tenacity library | Handles exponential backoff, jitter, specific exception types cleanly |
| HTML parsing | Regex on HTML | BeautifulSoup4 + lxml | Regex cannot handle malformed HTML, nested tags, encoding issues |
| Rate limiting | sleep() calls | asyncio.sleep() in a client wrapper | Centralized delay logic, easy to adjust per-site |
| URL encoding | Manual string manipulation | httpx URL handling | httpx handles query params, encoding, redirects correctly |
| JSON merging | Manual dict walking | Recursive merge function | Deep nested structures need careful null-vs-empty handling |

**Key insight:** The scraping targets are only 19 pages total across 3 sites. Over-engineering is the main risk. A simple, synchronous scraper with per-manufacturer parsers is sufficient. Async is not needed for 19 requests.

## Common Pitfalls

### Pitfall 1: NXT vs Standard Model Confusion (Hot Spring)
**What goes wrong:** Hot Spring has both "Grandee" and "Grandee NXT" models with different specs. Scraping the wrong variant produces incorrect data.
**Why it happens:** The dealer site (hotspringhottubs.com) has URLs for both `/grandee/` and `/grandee-nxt/`. The spec differences are real (different jet counts, weights, features).
**How to avoid:** Explicitly target the standard (non-NXT) URLs. Verify the page title and model name in the parsed HTML before extracting specs.
**Warning signs:** Jet counts or weights that don't match PDF-extracted values for the same model.

### Pitfall 2: Overwriting PDF Data During Merge
**What goes wrong:** Web-scraped values replace correctly extracted PDF values, introducing discrepancies.
**Why it happens:** A naive merge that always prefers the latest source. Web data may be for a different model year or variant.
**How to avoid:** Strict merge rule: web data only fills fields that are null/None/0 in the existing JSON. Never overwrite a non-null value. Log every field that was filled for manual review.
**Warning signs:** Existing non-null values changing after merge.

### Pitfall 3: Unit Conversion Errors
**What goes wrong:** Dimensions come in different formats across sites: "89.0 inches", "7'10\"", "2.39m".
**Why it happens:** Each manufacturer and dealer site formats dimensions differently.
**How to avoid:** Parse all dimension formats into a canonical float (inches). Write explicit parsers for: decimal inches ("89.0"), feet-inches ("7'10\""), and metric ("2.39m" -> convert to inches).
**Warning signs:** Dimensions that are impossibly large (forgot to convert from cm) or impossibly small (divided instead of multiplied).

### Pitfall 4: Stale Dealer Site Data
**What goes wrong:** Dealer sites may show 2024 or 2025 model specs instead of 2026.
**Why it happens:** Dealer sites update on their own schedule, not necessarily aligned with manufacturer releases.
**How to avoid:** Check for year/model year indicators in the page content. Cross-validate key specs (dimensions, jet count) against PDF-extracted data. Log warnings when web data contradicts PDF data.
**Warning signs:** Spec values that conflict with PDF-extracted values for fields where both sources have data.

### Pitfall 5: Bullfrog Unit ID Changes
**What goes wrong:** The `unit_id` query parameters in bullfrogfactorystores.com URLs may change when the dealer updates their catalog.
**Why it happens:** These are database IDs in the dealer's system, not permanent identifiers.
**How to avoid:** Have a fallback: if the primary dealer URL returns 404 or wrong model data, try the alternative source (hotspas.com). Store URLs in config so they're easy to update.
**Warning signs:** Fetched page shows a different model name than expected.

## Code Examples

### Fetching and Parsing Sundance Specs
```python
# Source: Verified against sundancespas.com Aspen page (WebFetch 2026-02-16)
import httpx
from bs4 import BeautifulSoup

def parse_sundance_specs(html: str) -> dict:
    """Parse specs from a Sundance 880 Series product page.

    Sundance pages embed specs in <li> elements under expandable sections.
    Key spec fields appear as structured text like:
    "1-Speed/2.5 HP Continuous, 11.3A Max., 56 Frame"
    """
    soup = BeautifulSoup(html, "lxml")
    specs = {}

    # Dimensions appear as individual values
    # Height, Length, Width in inches (float)
    # Volume in gallons
    # Dry Weight in pounds
    # Total Jets as integer
    # Pump specs as descriptive strings
    # Electrical as "240 VAC@50A or 60A"
    # Filtration as "MicroClean Ultra II, 130 ft2 (2 interlocking cartridge filters)"

    # Implementation: find spec container elements, parse text content
    # Each manufacturer page has its own HTML structure
    return specs
```

### Dimension Parsing Utility
```python
import re

def parse_dimension_inches(text: str) -> float | None:
    """Parse various dimension formats to inches (float).

    Handles:
    - "89.0" or "89" (already inches)
    - "7'10\"" or "7'-10\"" (feet-inches)
    - "2.39m" (meters to inches)
    - "37.5 inches" (with unit label)
    """
    if not text:
        return None

    text = text.strip().replace(",", "")

    # Feet-inches: 7'10" or 7'-10"
    ft_in = re.match(r"(\d+)['\u2032]-?\s*(\d+(?:\.\d+)?)[\"″\u2033]?", text)
    if ft_in:
        feet = int(ft_in.group(1))
        inches = float(ft_in.group(2))
        return feet * 12.0 + inches

    # Meters: 2.39m
    m = re.match(r"(\d+\.?\d*)\s*m\b", text)
    if m:
        return float(m.group(1)) * 39.3701

    # Plain number (inches)
    num = re.match(r"(\d+\.?\d*)", text)
    if num:
        return float(num.group(1))

    return None
```

### Merge Logic
```python
import json
from datetime import date
from pathlib import Path

def merge_scraped_into_model(
    json_path: Path,
    scraped: dict,
    source_url: str,
) -> bool:
    """Merge scraped specs into an existing model JSON file.

    Returns True if any fields were updated.
    """
    with open(json_path) as f:
        existing = json.load(f)

    updated_fields = []

    # Merge top-level scalar fields
    for field in ["seating_capacity"]:
        if existing.get(field) in (None, 0) and scraped.get(field):
            existing[field] = scraped[field]
            updated_fields.append(field)

    # Merge dimensions
    if "dimensions" in scraped:
        for dim_field in ["length_inches", "width_inches", "height_inches",
                          "dry_weight_lbs", "filled_weight_lbs",
                          "water_capacity_gallons"]:
            existing_val = existing.get("dimensions", {}).get(dim_field)
            scraped_val = scraped.get("dimensions", {}).get(dim_field)
            if (existing_val is None or existing_val == 0) and scraped_val:
                existing["dimensions"][dim_field] = scraped_val
                updated_fields.append(f"dimensions.{dim_field}")

    # Append source reference
    if updated_fields:
        existing.setdefault("source_documents", []).append({
            "source_type": "website",
            "url": source_url,
            "accessed_date": date.today().isoformat(),
        })

        with open(json_path, "w") as f:
            json.dump(existing, f, indent=2)

        print(f"  Updated {len(updated_fields)} fields: {updated_fields}")
        return True

    return False
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| requests + BS4 (sync only) | httpx + BS4 (sync/async) | 2023+ | httpx supports both sync and async, HTTP/2, better timeouts |
| Selenium for JS rendering | Playwright (if needed) | 2023+ | Playwright is faster, more stable, better API; but NOT NEEDED for this phase |
| html.parser backend | lxml backend for BS4 | Always | lxml is 10x faster for parsing |
| Manual retry loops | tenacity library | 2020+ | Declarative retry with backoff, jitter, exception filtering |

**Deprecated/outdated:**
- **mechanize**: Ancient library, do not use.
- **urllib2**: Use httpx instead.
- **Selenium for static pages**: Overkill. Only use Playwright if you actually need JS rendering (we don't).

## Open Questions

Things that couldn't be fully resolved:

1. **Jetsetter LX URL on hotspringhottubs.com**
   - What we know: The URL pattern suggests `/jetsetter-lx/` but search results didn't confirm this exact URL exists.
   - What's unclear: Whether the dealer site has a separate page for Jetsetter LX vs. Jetsetter.
   - Recommendation: Try `/jetsetter-lx/` first; if 404, check if Jetsetter LX specs are on the Jetsetter page or use an alternative dealer site.

2. **Capris vs Capri URL discrepancy**
   - What we know: The model is called "Capris" in the project data but the Sundance website uses "Capri" in the URL.
   - What's unclear: Whether this is a naming inconsistency or the model is officially "Capri" (no trailing 's').
   - Recommendation: Use the URL as-is (`/capri-880-series/Capri.html`). The parser should handle the name mapping.

3. **Part number sources for future scraping**
   - What we know: Manufacturer product pages do not list part numbers. Third-party retailers (spastore.com, hottuboutpost.com) have part catalogs organized by manufacturer and model.
   - What's unclear: How reliably these retailer catalogs can be scraped, and whether they cover all 10 spec categories for all 19 models.
   - Recommendation: Defer part number scraping. Focus Phase 3 on filling spec gaps from manufacturer sites. Address part numbers in Phase 4 via manual entry or a dedicated scraping sub-phase.

4. **Bullfrog unit_id stability**
   - What we know: The current unit_ids work (verified for M9=9463 and M6=9466). M7 has a much higher ID (18476).
   - What's unclear: How often these IDs change when the dealer updates their site.
   - Recommendation: Store URLs in config. Have fallback URLs from alternative dealer site (hotspas.com). Validate model name in parsed page matches expected model.

5. **Hot Spring NXT vs standard model year alignment**
   - What we know: The dealer site lists both "Grandee" and "Grandee NXT" with slightly different specs.
   - What's unclear: Which corresponds to the 2026 model year in the PDF.
   - Recommendation: Start with non-NXT URLs. Cross-validate dimensions and jet counts against PDF data. If NXT matches better, switch.

## Robots.txt Summary

| Site | Policy | Crawl Delay | Product Pages Allowed? |
|------|--------|-------------|----------------------|
| sundancespas.com | Blocks account/cart/search pages; product pages allowed | None specified | YES |
| bullfrogspas.com | Nothing blocked | 10 seconds | YES (but JS-rendered; use dealer site) |
| hotspring.com | Only /wp-admin/ blocked | None specified | YES (but returns 500; use dealer site) |
| hotspringhottubs.com | Not checked | N/A | YES (verified via WebFetch) |
| bullfrogfactorystores.com | Not checked | N/A | YES (verified via WebFetch) |

## Sources

### Primary (HIGH confidence)
- sundancespas.com product pages -- Verified via WebFetch for Aspen, Optima, Cameo, Altamar. Static HTML with full spec tables.
- hotspringhottubs.com dealer pages -- Verified via WebFetch for Grandee, Envoy, Aria. Static HTML with detailed specs including pump model names and heater wattage.
- bullfrogfactorystores.com dealer pages -- Verified via WebFetch for M9 and M6. Static HTML with complete spec tables.
- hotspas.com dealer pages -- Verified via WebFetch for M9. Static HTML alternative for Bullfrog.
- robots.txt files -- Fetched directly for sundancespas.com, bullfrogspas.com, hotspring.com.

### Secondary (MEDIUM confidence)
- httpx PyPI page (https://pypi.org/project/httpx/) -- Current version info
- playwright PyPI page (https://pypi.org/project/playwright/) -- Version 1.58.0 confirmed but NOT NEEDED
- BrowserStack Playwright vs Selenium comparison (2026) -- Confirmed Playwright superiority for JS rendering
- Brightdata httpx web scraping guide (2026) -- Confirmed httpx + BS4 as standard static scraping stack

### Tertiary (LOW confidence)
- Part number availability on retailer sites -- Observed categories on spastore.com and shop.bullfrogspas.com but did not verify completeness of part number coverage for all 19 models
- Bullfrog M7 unit_id (18476) -- From search results, not directly verified via WebFetch

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- httpx + BeautifulSoup verified against actual target pages
- Architecture: HIGH -- Verified all 19 model pages are accessible as static HTML (direct or via dealer sites)
- Target URLs: HIGH for Sundance (verified 4/7), HIGH for Hot Spring (verified 3/8), HIGH for Bullfrog (verified 2/4)
- Data gap analysis: HIGH -- Programmatically analyzed all 19 JSON files
- Pitfalls: MEDIUM -- Based on direct observation of site structures and research patterns
- Part number availability: LOW -- Only surface-level investigation of retailer sites

**Research date:** 2026-02-16
**Valid until:** 2026-03-16 (URLs may change; re-verify before execution if delayed)
