from mcqgenrator import cache, ratelimit, social


def test_cache_miss_then_hit():
    key = cache.make_key(text="abc", number=5, subject="Math")
    assert cache.get(key) is None
    cache.set(key, quiz_json='{"1":{}}', review="good")
    hit = cache.get(key)
    assert hit is not None
    assert hit["quiz"] == '{"1":{}}'
    assert hit["review"] == "good"


def test_cache_key_deterministic_and_order_independent():
    k1 = cache.make_key(a=1, b=2, c="x")
    k2 = cache.make_key(c="x", b=2, a=1)
    assert k1 == k2


def test_cache_key_changes_with_input():
    k1 = cache.make_key(text="abc")
    k2 = cache.make_key(text="xyz")
    assert k1 != k2


def test_cache_stats_and_clear():
    cache.set(cache.make_key(text="t1"), "{}", "r")
    cache.set(cache.make_key(text="t2"), "{}", "r")
    stats = cache.stats()
    assert stats["entries"] == 2
    cache.clear()
    assert cache.stats()["entries"] == 0


def test_ratelimit_allows_up_to_max():
    state = {}
    for _ in range(5):
        allowed, wait = ratelimit.check_rate_limit(state, max_calls=5, window_seconds=60)
        assert allowed is True
    allowed, wait = ratelimit.check_rate_limit(state, max_calls=5, window_seconds=60)
    assert allowed is False
    assert wait > 0


def test_ratelimit_independent_sessions():
    state_a, state_b = {}, {}
    for _ in range(5):
        ratelimit.check_rate_limit(state_a, max_calls=5, window_seconds=60)
    allowed_a, _ = ratelimit.check_rate_limit(state_a, max_calls=5, window_seconds=60)
    allowed_b, _ = ratelimit.check_rate_limit(state_b, max_calls=5, window_seconds=60)
    assert allowed_a is False
    assert allowed_b is True


def test_social_share_roundtrip():
    code = social.create_share("Math", "Simple", "Multiple Choice", '{"1":{}}', "review")
    assert len(code) == 6
    rec = social.get_share(code)
    assert rec["subject"] == "Math"
    assert social.get_share("NOTREAL") is None


def test_social_leaderboard_ordering():
    code = social.create_share("Sci", "Simple", "Multiple Choice", "{}", "")
    social.submit_score(code, "Alice", 3, 5, 30.0)
    social.submit_score(code, "Bob", 5, 5, 20.0)
    social.submit_score(code, "Carol", 5, 5, 10.0)
    lb = social.get_leaderboard(code)
    assert list(lb["player_name"]) == ["Carol", "Bob", "Alice"]


def test_social_hardest_questions():
    social.log_attempt("Q1", True, subject="Math")
    social.log_attempt("Q1", False, subject="Math")
    social.log_attempt("Q2", True, subject="Math")
    hard = social.hardest_questions()
    assert hard.iloc[0]["question_text"] == "Q1"
    assert hard.iloc[0]["accuracy"] == 50.0
