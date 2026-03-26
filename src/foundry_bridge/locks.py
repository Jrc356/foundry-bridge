import asyncio

# Per-game asyncio locks shared across runtime components; never evicted.
_game_locks: dict[int, asyncio.Lock] = {}


def get_game_lock(game_id: int) -> asyncio.Lock:
    return _game_locks.setdefault(game_id, asyncio.Lock())
