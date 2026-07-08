import time


def check_rate_limit(session_state, max_calls: int = 5, window_seconds: int = 60):
    """
    Returns (allowed: bool, seconds_until_next_slot: float).
    Tracks call timestamps in the caller's st.session_state so it resets per
    browser session (not shared across users).
    """
    now = time.time()
    timestamps = session_state.get("_ratelimit_calls", [])
    timestamps = [t for t in timestamps if now - t < window_seconds]

    if len(timestamps) >= max_calls:
        oldest = min(timestamps)
        wait = window_seconds - (now - oldest)
        session_state["_ratelimit_calls"] = timestamps
        return False, max(wait, 0)

    timestamps.append(now)
    session_state["_ratelimit_calls"] = timestamps
    return True, 0.0
