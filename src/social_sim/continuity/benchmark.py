"""7/30 天可重复的工程场景。脚本控制，不代表模型能自主正常生活。"""
from __future__ import annotations

from pathlib import Path

from .context import observe
from .engine import ContinuityWorld
from .models import ObjectDefinition, initial_actor
from .validation import validate_world


def seed_demo(world: ContinuityWorld, *, actors: int = 1) -> None:
    world.seed([initial_actor(i + 1, money_cents=300_000) for i in range(actors)], [
        (ObjectDefinition("food_bread", "测试面包", "FOOD", ("edible", "purchasable"),
                          1200, 320, 350, 30, aliases=("bread",)), 1000),
        (ObjectDefinition("food_meal", "测试餐食", "FOOD", ("edible", "purchasable"),
                          2000, 650, 600, 30, aliases=("meal",)), 1000),
        (ObjectDefinition("game_a", "测试游戏", "GAME", ("playable", "purchasable"),
                          price_cents=3000, duration_min=45, seller="home"), 100),
        (ObjectDefinition("series_a", "测试连续剧", "SERIES", ("watchable",),
                          duration_min=30, episodes=120, aliases=("测试剧",)), 0),
    ])


def run_days(path: str | Path, days: int, *, restart: bool = False,
             duplicate_commands: bool = False) -> dict:
    if days not in (1, 7, 30):
        raise ValueError("days must be 1, 7 or 30")
    if Path(path).exists():
        raise FileExistsError("benchmark must use a new world path")
    world = ContinuityWorld(path)
    seed_demo(world)
    calls, duplicates, restarts, max_context = 0, 0, 0, 0

    def check_result(result: dict):
        if not result["accepted"]:
            raise AssertionError(result)

    def after():
        nonlocal world, restarts, max_context
        from .models import canonical_json
        max_context = max(max_context, len(canonical_json(observe(world, 1))))
        if restart:
            world.close()
            world = ContinuityWorld(path)
            seed_demo(world)
            restarts += 1

    def advance(label: str, until: int):
        nonlocal duplicates
        result = world.advance(label, until)
        check_result(result)
        if duplicate_commands:
            replay = world.advance(label, until)
            assert replay["replayed"]
            duplicates += 1
        after()

    def activity(label: str, kind: str, target: str | None = None):
        nonlocal calls, duplicates
        result = world.start(label, 1, kind, target)
        check_result(result)
        calls += 1
        if duplicate_commands:
            assert world.start(label, 1, kind, target)["replayed"]
            duplicates += 1
        after()
        while c := world.store.commitment(1):
            until = world.minute + min(15, c["remaining_min"])
            advance(f"{label}:t{until}", until)
        status = world.store.get_commitment(label)["status"]
        if status != "COMPLETED":
            raise AssertionError(f"commitment unexpectedly ended with {status}")

    try:
        check_result(world.act("own_game", 1, "BUY", "game_a"))
        after()
        for day in range(days):
            base = day * 1440
            prefix = f"day{day}"
            activity(prefix + ":sleep", "SLEEP")
            activity(prefix + ":breakfast", "MEAL", "food_bread")
            activity(prefix + ":home1", "TRAVEL", "home")
            activity(prefix + ":care", "PERSONAL_CARE")
            activity(prefix + ":office", "TRAVEL", "office")
            advance(prefix + ":nine", base + 540)
            activity(prefix + ":work", "WORK")
            activity(prefix + ":lunch", "MEAL", "food_meal")
            activity(prefix + ":home2", "TRAVEL", "home")
            activity(prefix + ":chores", "CHORES")
            activity(prefix + ":play", "PLAY", "game_a")
            activity(prefix + ":dinner", "MEAL", "food_meal")
            activity(prefix + ":home3", "TRAVEL", "home")
            advance(prefix + ":evening", base + 1200)
            check_result(world.start(prefix + ":watch", 1, "WATCH", "测试剧"))
            calls += 1
            advance(prefix + ":watch10", world.minute + 10)
            check_result(world.control(prefix + ":pause", 1, "PAUSE"))
            advance(prefix + ":break", world.minute + 20)
            check_result(world.control(prefix + ":resume", 1, "RESUME"))
            advance(prefix + ":watch20", world.minute + 20)
            advance(prefix + ":end", base + 1440)
            assert world.store.link(1, "series_a")["watched"] == list(range(1, day + 2))
            validate_world(world)
            print(f"day={day+1}/{days} invariants=PASS next_episode={day+2}", flush=True)
        validation = validate_world(world)
        return {"mode": "SCRIPTED_CONTRACT_TEST", "days": days,
                "completed_days": days, "high_level_decisions": calls,
                "duplicate_commands_checked": duplicates, "restarts": restarts,
                "max_observation_chars": max_context,
                "provider_requests": 0, "llm_calls": 0,
                "autonomous_human_likeness_proven": False,
                "final_observation": observe(world, 1), **validation}
    finally:
        world.close()
