import json
import urllib.request
from datetime import date, datetime

import httpx
from sqlalchemy.orm import Session

from app.collectors.rss_collector import match_score
from app.config import settings
from app.models import Event, RawRecord, Source

MATCH_THRESHOLD = 0.6
TIMEOUT = 20
SEARCH_LIMIT = 5
USER_AGENT = (
    "FutureOracleTestTask/0.1 (release-prediction prototype; contact: dev@example.com)"
)

EPIC_QUERY = """
query searchStoreQuery($count: Int, $country: String!, $keywords: String, $locale: String, $start: Int){
  Catalog{searchStore(count: $count, country: $country, keywords: $keywords, locale: $locale, start: $start){
    elements{title, productSlug, effectiveDate}
  }}
}
"""

# store.epicgames.com отдаёт 403 для не-браузерных HTTP-клиентов (TLS-фингерпринт),
# поэтому Epic идёт через urllib, а не httpx.
EPIC_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://store.epicgames.com",
    "Referer": "https://store.epicgames.com/",
}

STEAM_DATE_FORMATS = ("%d %b, %Y", "%b %d, %Y", "%Y-%m-%d")


def _epic_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _gog_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y.%m.%d").date()
    except ValueError:
        return None


def _steam_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in STEAM_DATE_FORMATS:
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _search_epic(client: httpx.Client, name: str) -> list[dict]:
    body = json.dumps(
        {
            "operationName": "searchStoreQuery",
            "query": EPIC_QUERY,
            "variables": {
                "count": SEARCH_LIMIT,
                "country": "US",
                "keywords": name,
                "locale": "en-US",
                "start": 0,
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://store.epicgames.com/graphql?operationName=searchStoreQuery",
        data=body,
        headers=EPIC_HEADERS,
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        data = json.loads(response.read().decode("utf-8"))
    elements = data["data"]["Catalog"]["searchStore"]["elements"]
    return [
        {
            "title": element.get("title"),
            "url": (
                f"https://store.epicgames.com/p/{element['productSlug']}"
                if element.get("productSlug")
                else "https://store.epicgames.com"
            ),
            "release_date": _epic_date(element.get("effectiveDate")),
            "coming_soon": None,
        }
        for element in elements
    ]


def _search_gog(client: httpx.Client, name: str) -> list[dict]:
    response = client.get(
        "https://catalog.gog.com/v1/catalog",
        params={"query": name, "limit": SEARCH_LIMIT},
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    products = response.json().get("products", [])
    return [
        {
            "title": product.get("title"),
            "url": (
                f"https://www.gog.com/game/{product['slug']}"
                if product.get("slug")
                else "https://www.gog.com"
            ),
            "release_date": _gog_date(product.get("releaseDate")),
            "coming_soon": None,
        }
        for product in products
    ]


def _steam_details(client: httpx.Client, appid: int) -> dict | None:
    try:
        response = client.get(
            "https://store.steampowered.com/api/appdetails",
            params={"appids": appid, "l": "en"},
        )
        response.raise_for_status()
        payload = response.json().get(str(appid), {})
        if not payload.get("success"):
            return None
        data = payload.get("data") or {}
        release_date = data.get("release_date") or {}
        return {
            "title": data.get("name"),
            "url": f"https://store.steampowered.com/app/{appid}/",
            "release_date": _steam_date(release_date.get("date")),
            "coming_soon": bool(release_date.get("coming_soon")),
        }
    except Exception:
        return None


def _search_steam(client: httpx.Client, name: str) -> list[dict]:
    response = client.get(
        "https://store.steampowered.com/api/storesearch/",
        params={"term": name, "cc": "us", "l": "en"},
    )
    response.raise_for_status()
    results = []
    for item in response.json().get("items", [])[:3]:
        details = _steam_details(client, item.get("id"))
        if details is not None:
            results.append(details)
    return results


SEARCHERS = {
    "epic": _search_epic,
    "gog": _search_gog,
    "steam": _search_steam,
}


def _get_or_create_source(session: Session, store: dict) -> Source:
    source = session.query(Source).filter_by(name=store["name"]).first()
    if source is None:
        source = Source(
            name=store["name"],
            kind=store["kind"],
            url=store["url"],
            reliability=store["reliability"],
        )
        session.add(source)
        session.commit()
        session.refresh(source)
    return source


def collect(session: Session) -> int:
    events = session.query(Event).filter(Event.status == "active").all()
    matched = 0
    with httpx.Client(
        timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    ) as client:
        for store in settings.stores:
            searcher = SEARCHERS.get(store.get("type"))
            if searcher is None:
                continue
            source = _get_or_create_source(session, store)
            for event in events:
                try:
                    results = searcher(client, event.game)
                except Exception:
                    continue
                best_score = 0.0
                best_result = None
                for result in results:
                    score = match_score(result.get("title") or "", event.game)
                    if score > best_score:
                        best_score = score
                        best_result = result
                if best_result is None or best_score < MATCH_THRESHOLD:
                    continue
                release_date = best_result.get("release_date")
                coming_soon = best_result.get("coming_soon")
                content = f"Store listing for {event.game} on {store['name']}"
                if release_date is not None:
                    content += f", release date {release_date.isoformat()}"
                if coming_soon:
                    content += " (coming soon)"
                raw = RawRecord(
                    source_id=source.id,
                    event_id=event.id,
                    title=f"{best_result.get('title') or event.game} — {store['name']} listing",
                    content=content,
                    url=best_result.get("url") or store["url"],
                    payload={
                        "store": store["name"],
                        "product_title": best_result.get("title"),
                        "release_date": (
                            release_date.isoformat() if release_date is not None else None
                        ),
                        "coming_soon": coming_soon,
                    },
                )
                session.add(raw)
                matched += 1
    session.commit()
    return matched
