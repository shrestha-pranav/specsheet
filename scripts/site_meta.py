#!/usr/bin/env python3
"""Site shell + discovery files, generated from docs/site.json (the single brand/domain/contact setting).

Writes into docs/ (not docs/api): llms.txt, sitemap.xml, robots.txt, sources.json, and re-stamps the brand, footer
addresses and the schema.org Dataset JSON-LD inside docs/index.html. Called by build.py; also runnable alone:
  python3 -I scripts/site_meta.py
sources.json is generated from data/decisions/policies.yaml (the source-policy file): every source id an accepted
policy draws on, with a display credit and a public-domain flag. No secret or personal value is read or written.
"""
import json, re, sys
from html import escape
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
POLICIES = ROOT / "data" / "decisions" / "policies.yaml"

# Display credit per source id (or id prefix). Anything not listed gets "<Brand> (manufacturer specification pages)".
CREDITS = {
    "energystar": ("U.S. EPA ENERGY STAR certified product data", True),
    "carb": ("California Air Resources Board certified air cleaner list", False),
    "displayhdr": ("VESA DisplayHDR certified products list", False),
    "csa-dcl": ("CSA Distributed Compliance Ledger (Matter)", False),
    "lenovo-psref": ("Lenovo PSREF (Product Specifications Reference)", False),
}


def load_site():
    return json.loads((DOCS / "site.json").read_text())


def credit_for(source_id):
    for prefix, (label, public) in CREDITS.items():
        if source_id == prefix or source_id.startswith(prefix + "-"):
            return label, public
    brand = re.split(r"-us\b|-", source_id)[0]
    names = {"tplink": "TP-Link", "tripplite": "Tripp Lite", "cyberpower": "CyberPower", "ecoflow": "EcoFlow", "irobot": "iRobot",
             "goalzero": "Goal Zero", "ankersolix": "Anker SOLIX", "lg": "LG", "tcl": "TCL", "asus": "ASUS", "ugreen": "UGREEN",
             "iniu": "INIU", "cuktech": "CUKTECH", "kuxiu": "KUXIU", "teamgroup": "TeamGroup", "mophie": "mophie"}
    return f"{names.get(brand, brand.title())} official specification pages", False


def sources():
    policies = yaml.safe_load(POLICIES.read_text())
    ids = {}
    for policy in policies.get("claim_policies", []):
        for sid in policy.get("match", {}).get("source_ids", []):
            ids.setdefault(sid, set()).add(policy["id"])
    out = []
    for sid in sorted(ids):
        label, public = credit_for(sid)
        out.append({"id": sid, "credit": label, "public_domain": public})
    return {"generated_from": "data/decisions/policies.yaml", "sources": out}


def wordmark(brand):
    for suffix in ("sheet", "spec"):
        if brand.endswith(suffix) and len(brand) > len(suffix):
            return brand[:-len(suffix)], suffix
    return brand, ""


def email(site, role):
    if not site.get('email_enabled'):
        return f"a GitHub issue (https://github.com/{site['repo']}/issues)"
    return f"{site['contacts'][role]}@{site['domain']}"


def categories():
    path = DOCS / "api" / "v1" / "categories.json"
    if not path.exists():
        return []
    return [c for c in json.loads(path.read_text()) if not c.get("demo")]


def llms_txt(site):
    base, brand = site["site_url"].rstrip("/"), site["brand"]
    lines = [f"# {brand}", "",
             f"> Cross-brand product specifications with provenance: every value links to the source that states it, and "
             f"\"unknown\" never means \"no\". Free, open dataset (ODbL 1.0). A paid tier is coming later.", "",
             "## Free dataset (static JSON)", "",
             f"- [Manifest]({base}/api/v1/manifest.json): categories, schema versions, index shards, release id",
             f"- [Categories]({base}/api/v1/categories.json): category list with counts",
             f"- [Identifier lookup]({base}/api/v1/lookup/identifiers.json): GTIN / model number to product id",
             f"- Per category: `{base}/api/v1/<category>/index-N.json` (rows), `facets.json`, `schema.json`, `products/<id>.json` (full record with per-value sources)",
             f"- [Data contract]({base}/api/v1/README.md)", ""]
    cats = categories()
    if cats:
        lines += ["## Categories", ""] + [f"- {c['id']}: {c['name']} ({c['count']} products)" for c in cats] + [""]
    lines += ["## API and MCP (preview)", "",
              "- Preview: a read-only HTTP API and an MCP endpoint may be offered later; limits and paths can change without notice.",
              "- Until announced here, use the static dataset above.", "",
              "## Rules", "",
              f"- Licence: ODbL 1.0; produced works include: \"Data: {brand} (ODbL), sources linked per value\". See {base}/#/terms and {base}/#/sources.",
              "- Spec values come from the sources named per value, not independent testing. Check the source before a purchase.",
              f"- Corrections: {email(site, 'corrections')}. Takedowns: {email(site, 'legal')}.", ""]
    return "\n".join(lines)


def sitemap(site):
    base = site["site_url"].rstrip("/")
    urls = [f"{base}/", f"{base}/#/about", f"{base}/#/terms", f"{base}/#/privacy", f"{base}/#/sources"]
    urls += [f"{base}/#/category/{c['id']}" for c in categories()]
    body = "\n".join(f"  <url><loc>{escape(u)}</loc></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n'


def robots(site):
    base = site["site_url"].rstrip("/")
    return f"User-agent: *\nAllow: /\nDisallow: /v1/query\nDisallow: /v1/match\nDisallow: /mcp\n\nSitemap: {base}/sitemap.xml\n"


def jsonld(site):
    base, brand = site["site_url"].rstrip("/"), site["brand"]
    data = {"@context": "https://schema.org", "@type": "Dataset", "name": f"{brand} product specifications",
            "description": "Cross-brand product specifications, each value linked to its source.",
            "url": f"{base}/", "license": "https://opendatacommons.org/licenses/odbl/1-0/",
            "isAccessibleForFree": True,
            "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{base}/api/v1/manifest.json"}]}
    return json.dumps(data, indent=2).replace("</", "<\\/")


def stamp_index(site):
    path = DOCS / "index.html"
    html = path.read_text()
    brand, tag = site["brand"], site["tagline"]
    strong, light = wordmark(brand)
    html = re.sub(r"<title>.*?</title>", f"<title>{escape(brand)} — factual product comparison</title>", html, count=1)
    html = re.sub(r'(<a class="wordmark"[^>]*?aria-label=")[^"]*(">).*?(</a>)',
                  lambda m: f'{m.group(1)}{escape(brand)} home{m.group(2)}{escape(strong)}<span>{escape(light)}</span><i aria-hidden="true"></i>{m.group(3)}', html, count=1, flags=re.S)
    html = re.sub(r"(<span data-brand-line>).*?(</span>)", lambda m: f"{m.group(1)}{escape(brand)} · {escape(tag)}{m.group(2)}", html, count=1)
    corr = email(site, "corrections")
    html = re.sub(r'(<a href="mailto:)[^"]*(" data-email="corrections">).*?(</a>)', lambda m: f"{m.group(1)}{corr}{m.group(2)}{corr}{m.group(3)}", html)
    repo = site["repo"]
    html = re.sub(r'(<a href="https://github\.com/)[^"]*(" data-repo>)', lambda m: f"{m.group(1)}{repo}{m.group(2)}", html)
    html = re.sub(r'(<a href="https://github\.com/)[^"?]*(/issues/new\?title=Correction%3A%20" data-repo-issue>)', lambda m: f"{m.group(1)}{repo}{m.group(2)}", html)
    block = f'<!--site:jsonld--><script type="application/ld+json">\n{jsonld(site)}\n</script><!--/site:jsonld-->'
    html = re.sub(r"<!--site:jsonld-->.*?<!--/site:jsonld-->", lambda m: block, html, count=1, flags=re.S)
    path.write_text(html)


def generate():
    site = load_site()
    (DOCS / "llms.txt").write_text(llms_txt(site))
    (DOCS / "sitemap.xml").write_text(sitemap(site))
    (DOCS / "robots.txt").write_text(robots(site))
    (DOCS / "sources.json").write_text(json.dumps(sources(), indent=1, ensure_ascii=False) + "\n")
    stamp_index(site)


if __name__ == "__main__":
    generate()
    print("site meta written")
