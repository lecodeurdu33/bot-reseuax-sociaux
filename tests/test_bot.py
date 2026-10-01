import json
from pathlib import Path

import bot


def test_manual_links_cover_platforms():
    links = bot.manual_links('"aura battle" Léo')
    assert any("tiktok.com/search" in u for u in links.values())
    assert any("tbs=qdr%3Ad" in u or "tbs=qdr:d" in u for u in links.values())


def test_dedup_and_new_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "x")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    fake = [{"platform": "YouTube", "url": "u1", "title": "t", "detail": "", "query": "q"}] * 2
    monkeypatch.setattr(bot, "search_youtube", lambda *a, **k: [dict(f) for f in fake])
    state = tmp_path / "s.json"
    res, _ = bot.run({"keywords": ["q"]}, state)
    assert len(res) == 1 and res[0]["new"]
    res, _ = bot.run({"keywords": ["q"]}, state)
    assert not res[0]["new"] and json.loads(state.read_text()) == ["u1"]


def test_render_escapes(tmp_path):
    r = [{"platform": "YouTube", "url": "http://a/?x=<b>", "title": "<script>", "detail": "", "query": "q", "new": True}]
    out = bot.render_html(r, [], {"keywords": ["q"]})
    assert "<script>" not in out
