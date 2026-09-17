"""Create the one-time A2-Final JSON answer from completed local artifacts."""

from __future__ import annotations

import json

from a2_final_stage_a_real import BASELINE, OUTPUT_ROOT, START_MARKER, protected_hashes
from social_sim.a2_final.micro import micro_arms, summarize_micro
from social_sim.a2_final.synthesis import synthesize_final_answer


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    marker = read_json(START_MARKER)
    output = OUTPUT_ROOT / marker["experiment_id"]
    stage_a, stage_b = output / "stage_a", output / "stage_b"
    target = output / "final_answer.json"
    if target.exists():
        raise RuntimeError("FINAL_ANSWER_ALREADY_WRITTEN")
    config = read_json(stage_a / "experiment_config.json")
    if config["git_baseline_commit"] != BASELINE or protected_hashes() != config["production_protected_before"]:
        raise RuntimeError("FROZEN_BASELINE_OR_CONFIG_CHANGED")
    selection = read_json(stage_a / "engineering_selection.json")
    panel_rows = [json.loads(line) for line in (stage_a / "decision_rows.jsonl").read_text(
        encoding="utf-8").splitlines()]
    split = read_json(stage_a / "train_eval_split.json")
    retrieval = read_json(stage_a / "retrieval_metrics.json")
    micro_rows = [json.loads(line) for line in (stage_b / "episode_rows.jsonl").read_text(
        encoding="utf-8").splitlines()]
    arms = micro_arms(selection["selected_corpus"], selection["selected_prior"])
    micro = summarize_micro(micro_rows, arms)
    if micro["by_arm"] != read_json(stage_b / "condition_metrics.json"):
        raise RuntimeError("STAGE_B_SUMMARY_MISMATCH")
    answer = synthesize_final_answer(selection, panel_rows, micro, split, retrieval, BASELINE)
    with target.open("x", encoding="utf-8") as file:
        json.dump(answer, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write("\n")
    print(f"A2_FINAL_SYNTHESIS_COMPLETE status={answer['status']} output={target}", flush=True)


if __name__ == "__main__":
    main()
