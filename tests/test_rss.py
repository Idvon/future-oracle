from app.collectors.rss_collector import match_score


def test_exact_title_containment():
    assert match_score("Elden Ring 2 release date confirmed", "Elden Ring 2") == 1.0


def test_title_is_shorter_than_game_name():
    score = match_score("Elden Ring patch notes", "Elden Ring 2")
    assert score >= 0.6


def test_token_overlap_partial():
    score = match_score("Cyberpunk 2078 delayed again", "Cyberpunk 2078")
    assert score >= 0.8


def test_unrelated_titles_do_not_match():
    assert match_score("GTA 6 players find secret", "Grand Theft Auto VI") < 0.6


def test_empty_title():
    assert match_score("", "Elden Ring 2") == 0.0
