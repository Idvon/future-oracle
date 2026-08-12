from datetime import date

from app.collectors import wikipedia_collector
from app.collectors.wikipedia_collector import parse_games, parse_release

FIXTURE_HTML = """
<table>
  <tr><th>Title</th><th>Developer</th><th>Release</th></tr>
  <tr><td><a title="Example Game">Example Game</a></td><td>Studio X</td><td>February 14, 2026</td></tr>
  <tr><td><a title="Quarterly Game">Quarterly Game</a></td><td>Studio Y</td><td>Q3 2026</td></tr>
  <tr><td><a title="Resident Evil (2026 film)">Resident Evil</a></td><td>Studio Z</td><td>March 1, 2026</td></tr>
  <tr><td><a title="The Super Mario Galaxy Movie">The Super Mario Galaxy Movie</a></td><td>Studio M</td><td>March 8, 2026</td></tr>
  <tr><td><a title="Old Game">Old Game</a></td><td>Studio W</td><td>2018</td></tr>
</table>
<table>
  <tr><th>Title</th><th>Platform(s)</th><th>Shutdown date</th></tr>
  <tr><td><a title="NBA Live 19">NBA Live 19</a></td><td>PS4</td><td>January 30, 2026</td></tr>
</table>
"""


def test_parse_release_iso():
    assert parse_release("2026-02-14") == (date(2026, 2, 14), "day")


def test_parse_release_full_date():
    assert parse_release("February 14, 2026") == (date(2026, 2, 14), "day")


def test_parse_release_month_precision():
    assert parse_release("March 2026") == (date(2026, 3, 1), "month")


def test_parse_release_quarter_precision():
    assert parse_release("Q3 2026") == (date(2026, 9, 30), "quarter")


def test_parse_release_year_precision():
    assert parse_release("2026") == (date(2026, 12, 31), "year")


def test_parse_release_unknown_returns_none():
    assert parse_release("TBA") is None


def test_parse_games_filters_films_and_old_games():
    rows = parse_games(FIXTURE_HTML)
    titles = [title for title, _, _ in rows]
    assert "Example Game" in titles
    assert "Quarterly Game" in titles
    assert "Resident Evil (2026 film)" not in titles
    assert "The Super Mario Galaxy Movie" not in titles
    assert "NBA Live 19" not in titles
    assert "Old Game" not in titles
