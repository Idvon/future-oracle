import re

import feedparser
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Event, RawRecord, Source

MATCH_THRESHOLD = 0.6


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower())


def match_score(title: str, game: str) -> float:
    title_tokens = set(_norm(title).split())
    game_tokens = set(_norm(game).split())
    if not game_tokens or not title_tokens:
        return 0.0
    if game_tokens <= title_tokens:
        return 1.0
    overlap = len(title_tokens & game_tokens)
    return overlap / min(len(title_tokens), len(game_tokens))


def _get_or_create_source(session: Session) -> Source:
    source = session.query(Source).filter_by(kind="rss").first()
    if source is None:
        source = Source(
            name="Gaming news RSS",
            kind="rss",
            url=", ".join(settings.rss_feeds),
            reliability=0.6,
        )
        session.add(source)
        session.commit()
        session.refresh(source)
    return source


def collect(session: Session) -> int:
    events = session.query(Event).filter(Event.status == "active").all()
    names = {event.game.lower(): event for event in events}
    source = _get_or_create_source(session)
    matched = 0

    for feed_url in settings.rss_feeds:
        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            continue
        for entry in feed.entries[:50]:
            title = entry.get("title", "")
            best_score = 0.0
            best_event: Event | None = None
            for name, event in names.items():
                score = match_score(title, name)
                if score > best_score:
                    best_score = score
                    best_event = event
            if best_event is None or best_score < MATCH_THRESHOLD:
                continue
            payload = {"feed": feed_url}
            published = entry.get("published_parsed")
            if published is not None:
                payload["published"] = f"{published[0]:04d}-{published[1]:02d}-{published[2]:02d}"
            raw = RawRecord(
                source_id=source.id,
                event_id=best_event.id,
                title=title,
                content=entry.get("summary", ""),
                url=entry.get("link", ""),
                payload=payload,
            )
            session.add(raw)
            matched += 1

    session.commit()
    return matched
