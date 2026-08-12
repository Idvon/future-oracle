import re
from datetime import date

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Event, Metric, RawRecord, Source

WIKI_API = "https://en.wikipedia.org/w/api.php"

MONTHS = {
    name: number
    for number, name in enumerate(
        [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ],
        1,
    )
}

QUARTER_END_DAY = {1: 31, 2: 30, 3: 30, 4: 31}

PRECISION_VALUE = {"day": 1.0, "month": 0.85, "quarter": 0.7, "year": 0.5}

SKIP_TITLE_KEYWORDS = (
    "film", "movie", "anime", "tv series", "television series", "animated",
    "season", "episode",
)

SKIP_HEADER_KEYWORDS = (
    "shutdown", "delist", "removed", "cancelled", "cancel", "closed",
)


def _month_number(name: str) -> int | None:
    return MONTHS.get(name.lower())


def _parse_dates(text: str) -> list[tuple[date, str]]:
    text = text.split("[")[0]
    found: list[tuple[date, str]] = []

    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        found.append((date(*map(int, match.groups())), "day"))

    match = re.search(r"([A-Za-z]+) (\d{1,2}),? (\d{4})", text)
    if match and _month_number(match.group(1)):
        found.append((date(int(match.group(3)), _month_number(match.group(1)), int(match.group(2))), "day"))

    match = re.search(r"(\d{1,2}) ([A-Za-z]+) (\d{4})", text)
    if match and _month_number(match.group(2)):
        found.append((date(int(match.group(3)), _month_number(match.group(2)), int(match.group(1))), "day"))

    match = re.search(r"([A-Za-z]+) (\d{4})", text)
    if match and _month_number(match.group(1)):
        found.append((date(int(match.group(2)), _month_number(match.group(1)), 1), "month"))

    match = re.search(r"Q([1-4])[ ]?(\d{4})", text)
    if match:
        quarter = int(match.group(1))
        found.append((date(int(match.group(2)), quarter * 3, QUARTER_END_DAY[quarter]), "quarter"))

    match = re.search(r"^(\d{4})$", text.strip())
    if match:
        found.append((date(int(match.group(1)), 12, 31), "year"))

    return found


def parse_release_date(text: str) -> date | None:
    found = _parse_dates(text)
    return min(found)[0] if found else None


def parse_release(text: str) -> tuple[date, str] | None:
    found = _parse_dates(text)
    return min(found) if found else None


def fetch_year_page_html() -> str:
    response = httpx.get(
        WIKI_API,
        params={
            "action": "parse",
            "page": settings.wikipedia_page,
            "prop": "text",
            "format": "json",
            "formatversion": "2",
        },
        headers={
            "User-Agent": "FutureOracleTestTask/0.1 (release-prediction prototype; contact: dev@example.com)"
        },
        timeout=30,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.json()["parse"]["text"]


def parse_games(html: str) -> list[tuple[str, date, str]]:
    soup = BeautifulSoup(html, "html.parser")
    page_year = int(settings.wikipedia_page.split()[0])
    rows: list[tuple[str, date, str]] = []
    for table in soup.find_all("table"):
        header = table.find("tr")
        if header is None:
            continue
        header_text = header.get_text(" ", strip=True).lower()
        if any(keyword in header_text for keyword in SKIP_HEADER_KEYWORDS):
            continue
        if "title" not in header_text or ("release" not in header_text and "date" not in header_text):
            continue
        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            first = cells[0]
            link = first.find("a")
            title = (link.get("title") or first.get_text(" ", strip=True)) if link else first.get_text(" ", strip=True)
            title = title.strip()
            low = title.lower()
            if not title or len(title) > 120 or any(keyword in low for keyword in SKIP_TITLE_KEYWORDS):
                continue
            date_text = " ".join(cell.get_text(" ", strip=True) for cell in cells[1:])
            release = parse_release(date_text)
            if release and release[0].year == page_year:
                rows.append((title, release[0], release[1]))
    return rows


def _get_or_create_source(session: Session) -> Source:
    source = session.query(Source).filter_by(kind="wikipedia").first()
    if source is None:
        source = Source(
            name="Wikipedia",
            kind="wikipedia",
            url=f"https://en.wikipedia.org/wiki/{settings.wikipedia_page.replace(' ', '_')}",
            reliability=0.8,
        )
        session.add(source)
        session.commit()
        session.refresh(source)
    return source


def collect(session: Session) -> tuple[int, int]:
    html = fetch_year_page_html()
    games = parse_games(html)
    source = _get_or_create_source(session)
    created = 0
    updated = 0

    for game, release_date, precision in games:
        event = (
            session.query(Event)
            .filter(func.lower(Event.game) == game.lower())
            .first()
        )
        if event is None:
            event = Event(game=game, target_date=release_date)
            session.add(event)
            session.flush()
            created += 1
        else:
            event.target_date = release_date
            updated += 1

        raw = RawRecord(
            source_id=source.id,
            event_id=event.id,
            title=f"Wikipedia: {game}",
            content=f"Announced release date: {release_date.isoformat()} ({precision} precision)",
            url=f"https://en.wikipedia.org/wiki/{game.replace(' ', '_')}",
            payload={"release_date": release_date.isoformat(), "precision": precision},
        )
        session.add(raw)
        session.flush()

        metric = Metric(
            event_id=event.id,
            raw_record_id=raw.id,
            signal_type="official_date_confirmed",
            value=PRECISION_VALUE[precision],
            weight=settings.signal_weights["official_date_confirmed"],
            source_reliability=source.reliability,
            note=f"Wikipedia lists {release_date.isoformat()} ({precision} precision)",
        )
        session.add(metric)

    session.commit()
    return created, updated
