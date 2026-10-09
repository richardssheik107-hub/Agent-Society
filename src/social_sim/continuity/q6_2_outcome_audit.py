"""M1.5: pure, descriptive post-hoc consequences, not a new success score.

No provider, world execution, credentials, raw completions or network imports.
Only whitelisted facts survive. Missing consequences never become zero.
"""
from __future__ import annotations

import math
import random
import re
from collections import Counter, defaultdict
from statistics import mean, median

EVALUATION_TYPE = "EXPLORATORY_POST_HOC"
CONDITIONS = ("A_RAW", "B_FEASIBLE")
FAMILIES = ("OWNERSHIP", "POST_MEAL_NEED", "MEDIA_PROGRESS", "ACTIVITY_LOCATION",
            "MEAL_PAYMENT", "MEAL_SUPPLY")
ACTIVITIES = frozenset({"TRAVEL", "MEAL", "WATCH", "PLAY", "WORK", "SLEEP",
                        "LEISURE", "PERSONAL_CARE", "CHORES"})
OBJECTS = ("food_bread", "food_meal", "game_a", "series_a")
LOCATIONS = ("home", "restaurant", "office", "park")
METRICS = ("hunger_relief", "energy_change", "money_delta", "minutes_elapsed",
           "work_minutes_change")
LABELS = {"hunger_relief": "净饥饿降低(milli)", "energy_change": "精力变化(milli)",
          "money_delta": "金钱变化(cents)", "minutes_elapsed": "模拟分钟",
          "work_minutes_change": "工作分钟变化"}


def _number(value, *, integer=False, low=None, high=None):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or (isinstance(value, float) and not math.isfinite(value))
            or (integer and not isinstance(value, int))
            or (low is not None and value < low) or (high is not None and value > high)):
        return None
    return value


def _id(value, kind):
    pattern = {"cell": r"c\d{3}", "pair": r"p\d{3}", "scenario": r"s\d{2}"}[kind]
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError("INVALID_OUTCOME_ID")
    return value


def _counts(value, keys):
    if not isinstance(value, dict):
        return None
    return {key: _number(value[key], integer=True, low=0) for key in keys if key in value}


def _media(value):
    if not isinstance(value, dict) or not isinstance(value.get("series_a"), dict):
        return None
    item = value["series_a"]
    watched = item.get("watched")
    if (not isinstance(watched, list)
            or any(_number(v, integer=True, low=1, high=100_000) is None for v in watched)):
        watched = None
    maps = {}
    for field in ("offsets", "view_counts"):
        raw = item.get(field)
        maps[field] = ({key: _number(val, integer=True, low=0)
                        for key, val in raw.items()
                        if isinstance(key, str) and re.fullmatch(r"[1-9]\d{0,5}", key)}
                       if isinstance(raw, dict) else None)
    return {"series_a": {"watched": sorted(watched) if watched is not None else None,
                         **maps, "next_episode": _number(item.get("next_episode"),
                                                       integer=True, low=1),
                         "total_episodes": _number(item.get("total_episodes"),
                                                  integer=True, low=1)}}


def _state(value):
    if not isinstance(value, dict):
        return None
    out = {field: _number(value.get(field), integer=True, low=0,
                         high=1000 if field in {"hunger_milli", "energy_milli"} else None)
           for field in ("minute", "money_cents", "hunger_milli", "energy_milli",
                         "work_minutes")}
    out["location"] = value.get("location") if value.get("location") in LOCATIONS else None
    out["inventory"] = _counts(value.get("inventory"), OBJECTS)
    out["play_minutes"] = _counts(value.get("play_minutes"), ("game_a",))
    out["media_progress"] = _media(value.get("media_progress"))
    return out


def _difference(after, before):
    return after - before if after is not None and before is not None else None


def _mapping_delta(before, after):
    if before is None or after is None:
        return None
    return {key: _difference(after.get(key), before.get(key))
            for key in sorted(set(before) | set(after))}


def cell_delta(row: dict) -> dict:
    """Net changes after the observed decision; incomplete calls have no effects."""
    metadata = {key: _id(row.get(key), kind) for key, kind in
                (("cell_id", "cell"), ("pair_id", "pair"), ("scenario_id", "scenario"))}
    if (row.get("condition") not in CONDITIONS or row.get("family") not in FAMILIES
            or type(row.get("repeat")) is not int or row["repeat"] not in {1, 2}):
        raise ValueError("INVALID_OUTCOME_METADATA")
    valid = row.get("strict_json_valid") is True and row.get("catalog_valid") is True
    observed = (valid and row.get("rule_checked") is True
                and row.get("effects_observed", True) is True
                and row.get("status") in {"DECISION_ACCEPTED", "RULE_REJECTED",
                                          "COMMITMENT_FAILED"})
    before = _state(row.get("before_state"))
    after = _state(row.get("after_state")) if observed else None
    activity = row.get("proposal_activity")
    activity = activity if valid and isinstance(activity, str) and activity in ACTIVITIES else None
    target = row.get("proposal_target")
    target = target if valid and target in (*OBJECTS, *LOCATIONS) else None
    status = row.get("status")
    status = status if status in {"DECISION_ACCEPTED", "RULE_REJECTED", "COMMITMENT_FAILED",
                                  "PROVIDER_TIMEOUT", "NOT_RUN", "UNKNOWN"} else "UNKNOWN"
    out = {**metadata, "condition": row["condition"], "family": row["family"],
           "repeat": row["repeat"], "status": status,
           "proposal_activity": activity, "proposal_target": target,
           "valid_proposal": valid, "effects_observed": observed,
           "start_accepted": row.get("start_accepted") if valid and
                             type(row.get("start_accepted")) is bool else None,
           "activity_completed": row.get("activity_completed") if valid and
                                 type(row.get("activity_completed")) is bool else None,
           "before_state": before, "after_state": after,
           "effect_status": "OBSERVED" if observed else "UNKNOWN",
           "backend": "glm-5.3" if row.get("provider_model") == "glm-5.3" else None}
    for prefix, field in (("hunger", "hunger_milli"), ("energy", "energy_milli"),
                          ("money", "money_cents"), ("minutes", "minute")):
        out[prefix + "_before"] = before.get(field) if before else None
        out[prefix + "_after"] = after.get(field) if after else None
    out["hunger_relief"] = _difference(out["hunger_before"], out["hunger_after"])
    out["energy_change"] = _difference(out["energy_after"], out["energy_before"])
    out["money_delta"] = _difference(out["money_after"], out["money_before"])
    out["minutes_elapsed"] = _difference(out["minutes_after"], out["minutes_before"])
    out["money_spent"] = max(-out["money_delta"], 0) if out["money_delta"] is not None else None
    out["money_income"] = max(out["money_delta"], 0) if out["money_delta"] is not None else None
    out["location_before"] = before.get("location") if before else None
    out["location_after"] = after.get("location") if after else None
    out["location_changed"] = (out["location_before"] != out["location_after"]
                               if out["location_before"] and out["location_after"] else None)
    for section, field, keys in (("inventory", "inventory", OBJECTS),
                                 ("play", "play_minutes", ("game_a",))):
        old = before.get(field) if before else None
        new = after.get(field) if after else None
        delta = _mapping_delta(old, new)
        known = (delta is not None and set(old) == set(new) == set(keys)
                 and all(v is not None for v in delta.values()))
        flag = "UNKNOWN" if not known else (
            "NOT_EXERCISED" if section == "play" and activity != "PLAY" else "OBSERVED")
        out[section] = {"status": flag, "before": old, "after": new, "delta": delta}
    old = before.get("media_progress") if before else None
    new = after.get("media_progress") if after else None
    watched = None
    offsets = None
    if old and new:
        a, b = old["series_a"], new["series_a"]
        if a["watched"] is not None and b["watched"] is not None:
            watched = sorted(set(b["watched"]) - set(a["watched"]))
        # Absent offset keys are not invented as zero: explicit absence is kept.
        offsets = _mapping_delta(a["offsets"], b["offsets"])
    media_known = (watched is not None and offsets is not None
                   and all(value is not None for value in offsets.values()))
    out["media"] = {"status": "UNKNOWN" if not media_known else (
        "OBSERVED" if activity == "WATCH" else "NOT_EXERCISED"),
        "before": old, "after": new, "newly_watched": watched, "offset_changes": offsets}
    facts = row.get("domain_facts") if isinstance(row.get("domain_facts"), dict) else {}
    work_before = _number(facts.get("work_minutes_before"), integer=True, low=0)
    work_after = _number(facts.get("work_minutes_after"), integer=True, low=0) if observed else None
    if work_before is None and before:
        work_before = before.get("work_minutes")
    if work_after is None and after:
        work_after = after.get("work_minutes")
    work_delta = _difference(work_after, work_before)
    out["work_minutes_change"] = work_delta
    out["work"] = {"status": "UNKNOWN" if work_delta is None else (
        "OBSERVED" if activity == "WORK" else "NOT_EXERCISED"),
        "before": work_before, "after": work_after, "delta": work_delta}
    purchases = _counts(facts.get("purchased_quantities"), OBJECTS) if observed else None
    consumption = _counts(facts.get("consumed_quantities"), OBJECTS) if observed else None
    out["resource_transactions"] = {
        "status": "OBSERVED" if purchases is not None and consumption is not None
                  and all(v is not None for v in [*purchases.values(), *consumption.values()]) else "UNKNOWN",
        "purchased_quantities": purchases, "consumed_quantities": consumption,
        "meaning": "VERIFIED_DOMAIN_LEDGER_AND_INVENTORY_NOT_EVENT_PRESENCE_ALONE"}
    for field in ("input_tokens", "output_tokens", "reasoning_tokens", "simulation_minutes"):
        out[field] = _number(row.get(field), integer=True, low=0)
    out["latency_seconds"] = _number(row.get("latency_seconds"), low=0)
    # A net inventory of zero does not prove there was no purchase/consumption.
    out["inventory_interpretation"] = "NET_QUANTITY_NOT_GROSS_ACQUISITION_OR_CONSUMPTION"
    resources = row.get("initial_resources")
    out["initial_resources"] = None
    if isinstance(resources, list):
        out["initial_resources"] = [{
            "object_id": item["id"],
            "owned_quantity": _number(item.get("qty"), integer=True, low=0),
            "price_cents": _number(item.get("price_cents"), integer=True, low=0),
            "duration_minutes": _number(item.get("minutes"), integer=True, low=0),
            "available": item.get("available") if type(item.get("available")) is bool else None,
            "in_stock": item.get("in_stock") if type(item.get("in_stock")) is bool else None,
        } for item in resources if isinstance(item, dict) and item.get("id") in OBJECTS]
    return out


def statistics(values, *, eligible=None):
    """Signed descriptive statistics with an explicit missing denominator."""
    values = list(values)
    known = [v for v in values if _number(v) is not None]
    eligible = len(values) if eligible is None else eligible
    if eligible < len(known):
        raise ValueError("INVALID_OUTCOME_DENOMINATOR")
    return {"mean": mean(known) if known else None, "median": median(known) if known else None,
            "min": min(known) if known else None, "max": max(known) if known else None,
            "positive": sum(v > 0 for v in known), "negative": sum(v < 0 for v in known),
            "zero": sum(v == 0 for v in known), "known": len(known),
            "missing": eligible - len(known), "eligible": eligible,
            "coverage": {"numerator": len(known), "denominator": eligible,
                         "value": len(known) / eligible if eligible else None}}


def _summaries(cells, pairs):
    return {"A": {metric: statistics([c[metric] for c in cells if c["condition"] == CONDITIONS[0]])
                  for metric in METRICS},
            "B": {metric: statistics([c[metric] for c in cells if c["condition"] == CONDITIONS[1]])
                  for metric in METRICS},
            "B_minus_A": {metric: statistics([p["B_minus_A"][metric] for p in pairs])
                          for metric in METRICS}}


def paired_effects(rows: list[dict]) -> dict:
    cells = [cell_delta(row) for row in rows]
    if len({c["cell_id"] for c in cells}) != len(cells):
        raise ValueError("DUPLICATE_OUTCOME_CELL")
    grouped = defaultdict(list)
    for cell in cells:
        grouped[cell["pair_id"]].append(cell)
    pairs = []
    for pair_id, arms in sorted(grouped.items()):
        if (len(arms) != 2 or {a["condition"] for a in arms} != set(CONDITIONS)
                or any(len({a[field] for a in arms}) != 1
                       for field in ("scenario_id", "family", "repeat"))):
            raise ValueError("OUTCOME_PAIR_METADATA_MISMATCH")
        a = next(c for c in arms if c["condition"] == CONDITIONS[0])
        b = next(c for c in arms if c["condition"] == CONDITIONS[1])
        if a["before_state"] != b["before_state"]:
            raise ValueError("OUTCOME_PAIR_INITIAL_STATE_MISMATCH")
        complete = a["effects_observed"] and b["effects_observed"]
        backend = ("BACKEND_UNKNOWN" if a["backend"] is None or b["backend"] is None else
                   "BACKEND_MATCH" if a["backend"] == b["backend"] else "BACKEND_DIFFERENT")
        pairs.append({"pair_id": pair_id, "scenario_id": a["scenario_id"], "family": a["family"],
                      "repeat": a["repeat"], "A": a, "B": b, "complete": complete,
                      "backend_comparison": backend,
                      "B_minus_A": {metric: _difference(b[metric], a[metric])
                                    if complete else None for metric in METRICS},
                      "missing_reason": None if complete else " / ".join(
                          f"{label}_{cell['status']}" for label, cell in (("A", a), ("B", b))
                          if not cell["effects_observed"]),
                      "supports": "OBSERVED_SINGLE_DECISION_NET_CONSEQUENCES" if complete
                                  else "OBSERVED_ONE_SIDE_ONLY",
                      "cannot_support": "CAUSAL_MECHANISM_OR_NEXT_MODEL_ACTION_OR_HUMAN_OPTIMALITY"})
    complete_cells = [c for p in pairs if p["complete"] for c in (p["A"], p["B"])]
    return {"pairs": pairs, "aggregates": _summaries(cells, pairs),
            "complete_pair_arms": _summaries(complete_cells, pairs),
            "complete_pairs": sum(p["complete"] for p in pairs),
            "planned_pairs": len(pairs),
            "by_family": {family: _summaries(
                [c for c in cells if c["family"] == family],
                [p for p in pairs if p["family"] == family]) for family in FAMILIES},
            "by_scenario": {scenario: _summaries(
                [c for c in cells if c["scenario_id"] == scenario],
                [p for p in pairs if p["scenario_id"] == scenario])
                for scenario in sorted({c["scenario_id"] for c in cells})}}


def build_outcome_audit(rows: list[dict], prompt_audit=None) -> dict:
    cells = [cell_delta(row) for row in rows]
    pairs = paired_effects(rows)
    actions = {label: dict(sorted(Counter(
        (c["proposal_activity"] + "/" + (c["proposal_target"] or "null"))
        for c in cells if c["condition"] == condition and c["valid_proposal"]
        and c["proposal_activity"] is not None).items()))
        for label, condition in zip(("A", "B"), CONDITIONS, strict=True)}
    matched = [p for p in pairs["pairs"] if p["complete"]
               and p["backend_comparison"] == "BACKEND_MATCH"]
    cost = {}
    for field in ("input_tokens", "latency_seconds"):
        usable = [p for p in matched if p["A"][field] is not None and p["B"][field] is not None]
        a = mean([p["A"][field] for p in usable]) if usable else None
        b = mean([p["B"][field] for p in usable]) if usable else None
        cost[field] = {"A_mean": a, "B_mean": b, "B_minus_A_mean": _difference(b, a),
                       "increase_percent": (b - a) / a * 100 if a else None,
                       "known_pairs": len(usable), "planned_pairs": len(pairs["pairs"])}
    return {"schema": "Q62_OUTCOME_AUDIT_V1", "evaluation_type": EVALUATION_TYPE,
            "cells": cells, "paired_effects": pairs, "actions": actions, "costs": cost,
            "layer_contract": {"L1": "FACTUAL_INVARIANTS_NOT_BEHAVIORAL_SUCCESS",
                               "L2": "OBSERVED_MULTI_DIMENSIONAL_NET_CHANGES",
                               "L3": "HUMAN_APPROPRIATENESS_UNRESOLVED"},
            "markers": {"EVALUATION_TYPE": EVALUATION_TYPE, "NEW_REAL_PROVIDER_REQUESTS": 0,
                        "ORIGINAL_Q62_CONCLUSION": "NO_CLEAR_DIFFERENCE",
                        "HUMAN_NEED_SATISFACTION_CONCLUSION": "UNRESOLVED",
                        "HUMAN_REVIEW_COMPLETED": "NO", "HUMAN_REVIEW_PACKET": "READY",
                        "LONG_TERM_HUMAN_LIKENESS": "NOT_TESTED",
                        "SHORT_HORIZON_STATE_CONTINUITY": "INSUFFICIENT_EVIDENCE"}}


def safe_delivery_summary(audit, prompt_audit, integrity, provenance):
    """Small public evidence table; no databases, text, prompts or blind key."""
    fields = ("cell_id", "pair_id", "scenario_id", "family", "repeat", "condition", "status",
              "proposal_activity", "proposal_target", "activity_completed", "effects_observed",
              "hunger_before", "hunger_after", "hunger_relief", "energy_before", "energy_after",
              "energy_change", "money_before", "money_after", "money_delta", "money_spent",
              "money_income", "minutes_before", "minutes_after", "minutes_elapsed",
              "location_before", "location_after", "work_minutes_change", "input_tokens",
              "output_tokens", "reasoning_tokens", "latency_seconds", "backend",
              "inventory", "resource_transactions", "initial_resources", "play", "work")
    cells = []
    for cell in audit["cells"]:
        item = {key: cell[key] for key in fields}
        media = cell["media"]
        item["media"] = {"status": media["status"], "newly_watched": media["newly_watched"],
                         "offset_changes": media["offset_changes"]}
        for label in ("before", "after"):
            value = media[label]["series_a"] if media[label] else None
            item["media"][label] = ({"watched_count": len(value["watched"])
                                     if value["watched"] is not None else None,
                                     "next_episode": value["next_episode"],
                                     "total_episodes": value["total_episodes"]} if value else None)
        cells.append(item)
    pairs = [{key: value for key, value in pair.items() if key not in {"A", "B"}}
             for pair in audit["paired_effects"]["pairs"]]
    return {"schema": "Q62_OUTCOME_SAFE_DELIVERY_V1", "markers": audit["markers"],
            "source": {key: provenance[key] for key in
                       ("session_id", "protocol_version", "protocol_hash", "execution_commit")},
            "source_integrity": {"file_count": integrity["file_count"],
                                 "listing_digest": integrity["listing_digest"],
                                 "all_sha256_unchanged": True,
                                 "world_databases_verified": 48,
                                 "source_file_hashes": integrity["before"]},
            "cells": cells, "pairs": pairs,
            "aggregates": {key: value for key, value in audit["paired_effects"].items()
                           if key != "pairs"},
            "actions": audit["actions"], "costs": audit["costs"],
            "prompt_intervention": {key: value for key, value in prompt_audit.items()
                                    if key != "cells"},
            "human_review_completed": False, "human_review_key_published": False,
            "future_experiment_approved": False}


def _display(value):
    if value is None:
        return "UNKNOWN"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _proposal(cell):
    return (cell["proposal_activity"] + "/" + (cell["proposal_target"] or "null")
            if cell["proposal_activity"] else "UNKNOWN")


def _effects(cell):
    return "; ".join(f"{LABELS[key]}={_display(cell[key])}" for key in METRICS)


def render_report(audit: dict, prompt_audit=None, integrity=None) -> str:
    """All pairs, all families, all missing outcomes; no global welfare score."""
    lines = ["# Q6.2 真实行为后果与提示干预审计", "",
             "评价类型：EXPLORATORY_POST_HOC。仅使用既有真实证据；新增真实请求0。",
             "原预注册拒绝/完成主结论保持NO_CLEAR_DIFFERENCE；本轮不能事后宣布B胜利。",
             "行为适当性UNRESOLVED；人工审核尚未完成；长期真人相似性NOT_TESTED。", "",
             "## 分层与单位", "",
             "L1是事实约束，L2是客观状态净变化，L3需要独立偏好、任务与人工标准。",
             "hunger_relief=before−after（正值净降低，负值不裁剪）；energy_change=after−before；",
             "money_delta=after−before；净支出/收入不代表错误/优劣；minutes_elapsed=after−before。",
             "饥饿/精力均为合成milli参数（范围0..1000），金钱为cents，非真实生理测量。",
             "模拟分钟、API延迟秒、整轮墙钟秒分别记录，不相加；缺失为UNKNOWN/null，不补0。",
             "库存是净持有变化，不能据净零断言未购买/未进食；媒体/游戏/工作未触发时NOT_EXERCISED。", "",
             "## 单次决策与宏活动粒度", "",
             "TRAVEL完成表示已到目的地；MEAL可以包括旅行、购买、进食，粒度不同。",
             "去餐厅是可能的准备动作而不是自动失败；MEAL不是人类标准答案。",
             "不观测也不推断A下一步会吃饭或永不吃饭；本轮未运行假想续步。", "",
             "## 全部分配单元与24对", "",
             "每对保留同scenario/repeat的两侧；两个超时侧无有效提案，后果未知。",
             "主要B−A描述来自完整配对；两个重复是相同冻结状态，不是独立真人样本。", "",
             "|配对/状态/家族/重复|A提案/执行|B提案/执行|A/B饥饿前→后|A状态后果|B状态后果|A/B位置|A/B库存、媒体、游戏、工作|B−A|完整/后端/缺失|支持与边界|",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for pair in audit["paired_effects"]["pairs"]:
        a, b = pair["A"], pair["B"]
        hunger = " / ".join(f"{_display(c['hunger_before'])}→{_display(c['hunger_after'])}"
                            for c in (a, b))
        location = " / ".join(f"{_display(c['location_before'])}→{_display(c['location_after'])}"
                              for c in (a, b))
        objects = " / ".join(
            f"库存:{c['inventory']['status']}:{_display(c['inventory']['delta'])}; "
            f"媒体:{c['media']['status']}:新增集={_display(c['media']['newly_watched'])},"
            f"播放位变化={_display(c['media']['offset_changes'])}; "
            f"游戏:{c['play']['status']}:{_display(c['play']['delta'])}; "
            f"工作:{c['work']['status']}:{_display(c['work']['delta'])}; "
            f"已核购买/消费:{_display(c['resource_transactions']['purchased_quantities'])}/"
            f"{_display(c['resource_transactions']['consumed_quantities'])}" for c in (a, b))
        delta = "; ".join(f"{LABELS[k]}:{_display(pair['B_minus_A'][k])}" for k in METRICS)
        lines.append(f"|{pair['pair_id']}/{pair['scenario_id']}/{pair['family']}/{pair['repeat']}"
                     f"|{_proposal(a)}/{a['status']}/完成={_display(a['activity_completed'])}"
                     f"|{_proposal(b)}/{b['status']}/完成={_display(b['activity_completed'])}"
                     f"|{hunger}|{_effects(a)}|{_effects(b)}|{location}|{objects}|{delta}"
                     f"|{pair['complete']}/{pair['backend_comparison']}/{pair['missing_reason'] or '无'}"
                     "|已观测单决策净后果；不支持未来动作/因果机制/人类最优|")
    lines.extend(["", "## 描述性统计（全部配对分母保留）", "",
                  "|范围|指标|mean|median|min|max|正/负/平|已知/计划|缺失|",
                  "|---|---|---:|---:|---:|---:|---|---|---:|"])
    groups = [("整体各臂23个已知/24分配", audit["paired_effects"]["aggregates"]),
              ("完整22对各臂（B−A仍保留24对分母）", audit["paired_effects"]["complete_pair_arms"])] + list(
        audit["paired_effects"]["by_family"].items())
    for group, arms in groups:
        for arm, metrics in arms.items():
            for metric, stats in metrics.items():
                lines.append(f"|{group}/{arm}|{LABELS[metric]}|{_display(stats['mean'])}"
                             f"|{_display(stats['median'])}|{_display(stats['min'])}"
                             f"|{_display(stats['max'])}|{stats['positive']}/{stats['negative']}/{stats['zero']}"
                             f"|{stats['known']}/{stats['eligible']}|{stats['missing']}|")
    lines.extend(["", "## 成本与覆盖", ""])
    for field, stats in audit["costs"].items():
        lines.append(f"- {field}：A均值{_display(stats['A_mean'])}，B均值{_display(stats['B_mean'])}；"
                     f"B−A={_display(stats['B_minus_A_mean'])}；"
                     f"增幅{_display(stats['increase_percent'])}%；"
                     f"完整同后端已知配对{stats['known_pairs']}/{stats['planned_pairs']}。")
    if prompt_audit:
        lines.extend(["", "## 冻结提示干预审计", "",
                      "12场景/48单元state、observation、candidate和提示hash/字符/UTF-8字节核对PASS。",
                      "B system保持A完整字节前缀，追加116字符选择指令；用户事实与目的地相同，新增executable_options。",
                      "规范JSON键重排使A用户消息不是B字节前缀（共同前缀55字符）；不是只追加数据的单因子干预。",
                      "候选按(activity,target)字典序，null目标作空字符串排序，不是偏好排序。", "",
                      "|状态|候选数|活动出现次数|MEAL在全部TRAVEL前|提示字符A/B|提示字节A/B|",
                      "|---|---:|---|---|---|---|"])
        for scenario in prompt_audit["scenarios"]:
            lines.append(f"|{scenario['scenario_id']}|{scenario['candidate_count']}"
                         f"|{scenario['candidate_activity_counts']}|{scenario['meal_before_all_travel']}"
                         f"|{scenario['prompt_chars']['A_RAW']}/{scenario['prompt_chars']['B_FEASIBLE']}"
                         f"|{scenario['prompt_bytes']['A_RAW']}/{scenario['prompt_bytes']['B_FEASIBLE']}|")
        lines.extend(["", f"24个B分配的候选曝光：{prompt_audit['candidate_exposure_b_allocations']}。",
                      "TRAVEL曝光次数比MEAL多，数量本身不能解释B偏向MEAL；12/12场景MEAL排序在TRAVEL前。",
                      "候选列表未展开MEAL的准备→购买→进食宏步骤。",
                      "混杂：候选信息、明确选择指令、上下文长度、排列、活动名称重复、宏活动粒度。",
                      "不能分离因果机制；不读取completion/隐藏思考，不改提示后请求模型。"])
    lines.extend(["", "缺失token不补0，input/output/reasoning不相加，不推算人民币账单。",
                  "提示信息、额外选择指令、长度、候选顺序和活动曝光同时改变；没有分离因果机制。",
                  "真实有reasoning tokens，未证明关闭思考或小模型模拟。", "",
                  "## 七个研究问题", "",
                  "1. 零拒绝：两臂实际均选合法动作，合法选项较多且完成指标出现天花板；不证明提示等价。",
                  "2. A常出行：原提示显式列出TRAVEL和目的地，出行本身合法；这是可观察上下文，不是隐藏推理。",
                  "3. B常进食：候选数据、额外选择指令、曝光与排序可能共同影响；只提出机制假设。",
                  "4. 后果差异：见全部逐对delta及六家族统计；不得选择性报告。",
                  "5. 成本是否值得：输入与延迟增加已知；是否值得取决于尚未批准的需求、时间、资源目标。",
                  "6. 是否更符合需求：可比较净饥饿、精力、钱、时间，不等于整体生活最优，人工标准仍待审。",
                  "7. 下一阶段：先盲审任务目标与准备动作标准，再决定是否预注册独立提示分解实验，不自动执行。", "",
                  "## 人工审核与未来备选（未执行）", "",
                  "人工包隐藏条件标签并随机展示同态双案例；未伪造合理性分数或评审一致性。",
                  "待审：只保留原指标；多维需求而不合成总分；带目标并区分准备/终点；独立拆分提示干预。",
                  "未来候选臂：原RAW、仅候选数据、仅选择指令、紧凑候选、受控顺序/相近token预算。",
                  "以上没有实现或验证；新真实实验必须另立协议和授权。", "",
                  "## 完成标记", "", "```text"])
    lines.extend(f"{key} = {value}" for key, value in audit["markers"].items())
    lines.extend(["```", ""])
    return "\n".join(lines)


def build_human_review_packet(rows: list[dict], seed=20261008):
    """Neutral IDs and shuffled within-pair order; unblinding key is separate."""
    pairs = paired_effects(rows)["pairs"]
    rng = random.Random(seed)
    rng.shuffle(pairs)
    lines = ["# 同态双案例人工审核包", "",
             "请独立评价实际事实；未提供标准答案，也不要求每对必须选优胜者。",
             "顺序已随机化，条件标签及解盲键不在此包中；如果事先看过结果报告，不再保证盲审。",
             "未作人工标注：HUMAN_REVIEW_COMPLETED=NO。缺失后果不可补零或猜测未来。", "",
             "单位与方向：饥饿/精力是0..1000的合成milli状态，不是真人生理测量。",
             "净饥饿降低=开始−结束，正数降低、负数增加；精力变化=结束−开始。",
             "金钱单位cents，负向变化是支出但不自动错误；模拟分钟不是API延迟或墙钟秒。",
             "TRAVEL的完成表示到达目的地；MEAL可按原规则包含旅行、购买、进食，粒度不同。",
             "准备步骤不自动失败，最终进食不自动最优；未观测未来，不猜下一步。",
             "初始资源来自同态冻结观测核对，不展示条件候选列表；供应与持有量分开。",
             "购买/消费数来自只读账本与实际库存交叉核验，净库存0不代表没有消费。", ""]
    key = {}
    for index, pair in enumerate(pairs, 1):
        review_id = f"r{index:03d}"
        cases = [pair["A"], pair["B"]]
        rng.shuffle(cases)
        lines.extend([f"## 双案例 {review_id}", ""])
        key[review_id] = {"pair_id": pair["pair_id"], "cases": {}}
        for position, cell in enumerate(cases, 1):
            key[review_id]["cases"][str(position)] = {"condition": cell["condition"],
                                                     "cell_id": cell["cell_id"]}
            before = cell["before_state"] or {}
            lines.extend([f"### 案例 {position}", "",
                          f"初始模拟分钟：{_display(before.get('minute'))}；"
                          f"位置：{_display(before.get('location'))}；"
                          f"钱(cents)：{_display(before.get('money_cents'))}；"
                          f"饥饿/精力(milli)：{_display(before.get('hunger_milli'))}/"
                          f"{_display(before.get('energy_milli'))}。",
                          f"初始库存：{_display(before.get('inventory'))}；"
                          f"媒体进度：{_display(before.get('media_progress'))}；"
                          f"游戏分钟：{_display(before.get('play_minutes'))}。",
                          f"初始资源（拥有量/价格cents/可用/供应/时长）：{_display(cell['initial_resources'])}。",
                          f"活动/对象：{_proposal(cell)}；实际完成：{_display(cell['activity_completed'])}。",
                          f"实际状态净变化：{_effects(cell)}。",
                          f"实际净支出/收入(cents)：{_display(cell['money_spent'])}/"
                          f"{_display(cell['money_income'])}；"
                          f"位置：{_display(cell['location_before'])}→{_display(cell['location_after'])}。",
                          f"库存净变化：{_display(cell['inventory']['delta'])}；"
                          f"媒体覆盖：{cell['media']['status']}；游戏覆盖：{cell['play']['status']}；"
                          f"工作覆盖：{cell['work']['status']}。", "",
                          f"核实购买量：{_display(cell['resource_transactions']['purchased_quantities'])}；"
                          f"核实消费量：{_display(cell['resource_transactions']['consumed_quantities'])}。", "",
                          "判断：□行为合理 □不合理 □信息不足",
                          "判断理由：________；依赖的具体状态事实：________",
                          "是否视为准备步骤：________；判断是否依赖未来行为：________",
                          "不确定性与缺少的偏好/目标：________", ""])
    return "\n".join(lines), key
