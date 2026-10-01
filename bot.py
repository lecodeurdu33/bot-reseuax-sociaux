#!/usr/bin/env python3
"""Veille quotidienne : cherche sur les réseaux les vidéos publiées aujourd'hui
qui correspondent aux mots-clés (prénom, "aura battle", école...) et produit un
rapport avec les liens à signaler.

Sources automatiques (API officielles, clés gratuites) :
  - YouTube Data API v3
  - Google Programmable Search (couvre TikTok, Instagram, Snapchat, CapCut...
    via des recherches "site:" limitées aux dernières 24 h)
Pour chaque plateforme, le rapport contient aussi des liens de recherche à
ouvrir à la main et le lien du formulaire de signalement.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, quote_plus

import requests
import yaml

TIMEOUT = 20

# Sites interrogés via Google Programmable Search.
SITES = {
    "TikTok": "tiktok.com",
    "Instagram": "instagram.com",
    "Snapchat": "snapchat.com",
    "CapCut": "capcut.com",
    "Facebook": "facebook.com",
    "X/Twitter": "x.com",
}

# Formulaires de signalement (à vérifier de temps en temps : les plateformes les déplacent).
REPORT_LINKS = {
    "YouTube": "https://support.google.com/youtube/answer/142443",
    "TikTok": "https://www.tiktok.com/legal/report/privacy",
    "Instagram": "https://help.instagram.com/contact/504521742987441",
    "Snapchat": "https://help.snapchat.com/hc/fr-fr/requests/new",
    "CapCut": "https://www.capcut.com/clause/report",
    "Facebook": "https://www.facebook.com/help/contact/144059062408922",
    "X/Twitter": "https://help.x.com/forms/safety-and-sensitive-content/private-information",
    "Autorités (France)": "https://www.internet-signalement.gouv.fr",
}


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if not cfg.get("keywords"):
        sys.exit("config : la liste 'keywords' est vide.")
    return cfg


def start_of_today_utc() -> datetime:
    local_midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(timezone.utc)


def search_youtube(query: str, api_key: str, since: datetime, max_results: int) -> list[dict]:
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "part": "snippet",
            "type": "video",
            "q": query,
            "order": "date",
            "maxResults": max_results,
            "publishedAfter": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "key": api_key,
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    out = []
    for item in r.json().get("items", []):
        sn = item["snippet"]
        out.append({
            "platform": "YouTube",
            "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
            "title": sn.get("title", ""),
            "detail": f"{sn.get('channelTitle', '')} — {sn.get('publishedAt', '')}",
            "query": query,
        })
    return out


def search_google(query: str, site: str, platform: str, key: str, cx: str) -> list[dict]:
    r = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={"key": key, "cx": cx, "q": f"site:{site} {query}", "dateRestrict": "d1", "num": 10},
        timeout=TIMEOUT,
    )
    if r.status_code == 429:
        raise RuntimeError("quota Google Programmable Search dépassé (100 requêtes/jour gratuites)")
    r.raise_for_status()
    return [
        {
            "platform": platform,
            "url": it["link"],
            "title": it.get("title", ""),
            "detail": it.get("snippet", "").replace("\n", " "),
            "query": query,
        }
        for it in r.json().get("items", [])
    ]


def manual_links(query: str) -> dict[str, str]:
    q = quote_plus(query)
    links = {
        "YouTube (aujourd'hui)": f"https://www.youtube.com/results?search_query={q}&sp=EgIIAg%3D%3D",
        "TikTok": f"https://www.tiktok.com/search?q={q}",
        "Instagram": f"https://www.instagram.com/explore/search/keyword/?q={q}",
        "Snapchat": f"https://www.snapchat.com/search?q={q}",
    }
    for name, site in SITES.items():
        links[f"Google « {name} » (24 h)"] = (
            f"https://www.google.com/search?q={quote('site:' + site + ' ' + query)}&tbs=qdr:d"
        )
    return links


def run(cfg: dict, state_path: Path) -> tuple[list[dict], list[str]]:
    since = start_of_today_utc()
    yt_key = os.environ.get("YOUTUBE_API_KEY")
    g_key, g_cx = os.environ.get("GOOGLE_API_KEY"), os.environ.get("GOOGLE_CSE_ID")
    seen = set(json.loads(state_path.read_text())) if state_path.exists() else set()
    results, warnings = [], []

    if not yt_key:
        warnings.append("YOUTUBE_API_KEY absente : YouTube n'est pas interrogé automatiquement.")
    if not (g_key and g_cx):
        warnings.append("GOOGLE_API_KEY / GOOGLE_CSE_ID absentes : TikTok, Instagram, Snapchat, CapCut "
                        "ne sont pas interrogés automatiquement (utilisez les liens manuels).")

    for kw in cfg["keywords"]:
        if yt_key:
            try:
                results += search_youtube(kw, yt_key, since, cfg.get("max_results", 10))
            except requests.RequestException as e:
                warnings.append(f"YouTube « {kw} » : {e}")
        if g_key and g_cx:
            for platform, site in SITES.items():
                try:
                    results += search_google(kw, site, platform, g_key, g_cx)
                except (requests.RequestException, RuntimeError) as e:
                    warnings.append(f"{platform} « {kw} » : {e}")
                    if isinstance(e, RuntimeError):
                        break

    new, urls = [], set()
    for r in results:
        if r["url"] in urls:
            continue
        urls.add(r["url"])
        r["new"] = r["url"] not in seen
        new.append(r)
    state_path.write_text(json.dumps(sorted(seen | urls)), encoding="utf-8")
    return new, warnings


def render_html(results: list[dict], warnings: list[str], cfg: dict) -> str:
    e = html.escape
    today = datetime.now().strftime("%d/%m/%Y %H:%M")
    parts = [
        "<!doctype html><meta charset='utf-8'><title>Veille réseaux sociaux</title>",
        "<style>body{font:16px sans-serif;max-width:800px;margin:2em auto;padding:0 1em}"
        "li{margin:.6em 0}.new{background:#fff3cd;padding:2px 6px;border-radius:4px}"
        ".small{color:#555;font-size:.9em}</style>",
        f"<h1>Veille du {today}</h1>",
    ]
    for w in warnings:
        parts.append(f"<p class='small'>⚠️ {e(w)}</p>")
    parts.append(f"<h2>Résultats automatiques ({len(results)})</h2>")
    if not results:
        parts.append("<p>Rien trouvé automatiquement aujourd'hui. Vérifiez aussi les liens manuels ci-dessous.</p>")
    platforms = list(dict.fromkeys(r["platform"] for r in results))
    for p in platforms:
        parts.append(f"<h3>{e(p)} — <a href='{e(REPORT_LINKS.get(p, '#'))}'>signaler</a></h3><ul>")
        for r in (x for x in results if x["platform"] == p):
            badge = "<span class='new'>NOUVEAU</span> " if r["new"] else ""
            parts.append(f"<li>{badge}<a href='{e(r['url'])}'>{e(r['title'] or r['url'])}</a>"
                         f"<br><span class='small'>{e(r['detail'])} (mot-clé : {e(r['query'])})</span></li>")
        parts.append("</ul>")
    parts.append("<h2>Vérification manuelle</h2>")
    for kw in cfg["keywords"]:
        parts.append(f"<h3>« {e(kw)} »</h3><ul>")
        for name, url in manual_links(kw).items():
            parts.append(f"<li><a href='{e(url)}'>{e(name)}</a></li>")
        parts.append("</ul>")
    parts.append("<h2>Formulaires de signalement</h2><ul>")
    for name, url in REPORT_LINKS.items():
        parts.append(f"<li><a href='{e(url)}'>{e(name)}</a></li>")
    parts.append("</ul><p class='small'>Conseil : faites une capture d'écran + copiez l'URL avant de signaler. "
                 "En France : 3018 (e-Enfance) et droit à l'effacement des mineurs (CNIL).</p>")
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--config", default="config.yaml", type=Path)
    ap.add_argument("-o", "--output", default="rapport.html", type=Path)
    ap.add_argument("--state", default=".seen.json", type=Path)
    args = ap.parse_args()
    cfg = load_config(args.config)
    results, warnings = run(cfg, args.state)
    args.output.write_text(render_html(results, warnings, cfg), encoding="utf-8")
    n_new = sum(r["new"] for r in results)
    print(f"{len(results)} résultat(s), dont {n_new} nouveau(x). Rapport : {args.output}")
    for w in warnings:
        print("⚠️ ", w, file=sys.stderr)


if __name__ == "__main__":
    main()
