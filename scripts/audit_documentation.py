#!/usr/bin/env python3
"""只读检查中文导航、链接、阶段/问题覆盖与逐文件删除映射。"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r"[\u3400-\u9fff]")
LINK = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)")


def without_fences(text: str) -> tuple[str, bool]:
    lines, fence = [], None
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return "\n".join(lines), fence is None


def anchors(text: str) -> set[str]:
    found = set(re.findall(r'<a\s+id="([^"]+)"', text))
    counts: Counter[str] = Counter()
    for heading in re.findall(r"^#{1,6}\s+(.+)$", text, flags=re.MULTILINE):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        suffix = "" if counts[slug] == 0 else f"-{counts[slug]}"
        found.add(slug + suffix)
        counts[slug] += 1
    return found


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def check_document_set(root: Path, index: dict) -> tuple[list[str], dict, dict]:
    errors: list[str] = []
    declared = [name for group in index["groups"].values() for name in group]
    actual = {p.relative_to(root).as_posix() for p in (root / "docs").rglob("*.md")}
    if len(set(declared)) != len(declared):
        errors.append("DUPLICATE_NAVIGATION_ENTRY")
    for name in sorted(actual - set(declared)):
        errors.append("UNINDEXED_DOCUMENT:" + name)
    for name in sorted(set(declared) - actual):
        errors.append("MISSING_DOCUMENT:" + name)
    contents, graph = {}, {}
    extras = ["README.md", "smoke/README.md", "archive/legacy_tools/README.md"]
    for name in sorted(actual | {n for n in extras if (root / n).is_file()}):
        path = root / name
        if path.is_symlink():
            errors.append("SYMLINK_DOCUMENT:" + name)
            continue
        text, balanced = without_fences(path.read_text(encoding="utf-8"))
        contents[name] = text
        graph[name] = set()
        if not balanced:
            errors.append("UNCLOSED_CODE_FENCE:" + name)
        title = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
        if title is None or not CJK.search(title.group(1)):
            errors.append("NON_CHINESE_TITLE:" + name)
    for name, text in contents.items():
        for match in LINK.finditer(text):
            url = match.group(1).strip()
            parts = urlsplit(url)
            if parts.scheme or parts.netloc:
                if parts.path.lower().endswith((".md", ".rst", ".pdf", ".docx")):
                    errors.append("EXTERNAL_READING_DOCUMENT:" + name)
                continue
            target = ((root / name).parent / unquote(parts.path)).resolve() if parts.path else (root / name).resolve()
            try:
                target_name = target.relative_to(root.resolve()).as_posix()
            except ValueError:
                errors.append("LINK_OUTSIDE_REPOSITORY:" + name)
                continue
            if not target.exists():
                errors.append(f"BROKEN_LINK:{name}->{target_name}")
                continue
            if target.suffix == ".md":
                target_text = contents.get(target_name)
                if target_text is None:
                    errors.append(f"LINK_TO_UNINDEXED_DOCUMENT:{name}->{target_name}")
                    continue
                graph[name].add(target_name)
                if parts.fragment and unquote(parts.fragment) not in anchors(target_text):
                    errors.append(f"BROKEN_ANCHOR:{name}->{target_name}#{parts.fragment}")
    visited, pending = set(), [index["root"]]
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        pending.extend(graph.get(name, set()) - visited)
    for name in sorted(actual - visited):
        errors.append("UNREACHABLE_DOCUMENT:" + name)
    review = contents.get("docs/review/decisions.md", "")
    for key in index["review_ids"]:
        if key not in anchors(review):
            errors.append("MISSING_REVIEW_ITEM:" + key)
    return errors, contents, graph


def migration_inventory(root: Path, mapping: dict, actual: set[str]) -> tuple[list[dict], list[str]]:
    errors, inventory = [], []
    ref = mapping["baseline_commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise ValueError("baseline must be a frozen commit")
    raw = subprocess.check_output(
        ["git", "ls-tree", "-r", ref, "--", "docs"], cwd=root,
        stderr=subprocess.DEVNULL, text=True,
    )
    for line in raw.splitlines():
        metadata, name = line.split("\t", 1)
        if not name.endswith(".md"):
            continue
        original_blob = metadata.split()[2]
        if name in actual:
            target, action = name, "RETAINED_AND_REWRITTEN"
        else:
            target = mapping["by_basename"].get(Path(name).name)
            action = "REMOVED_CONSOLIDATED_IN_CHINESE"
            if target not in actual:
                errors.append("UNMAPPED_REMOVAL:" + name)
        inventory.append({"old_path": name, "original_commit": ref,
                          "original_blob": original_blob, "action": action,
                          "chinese_replacement": target})
    if len(inventory) != mapping["baseline_markdown_count"]:
        errors.append("BASELINE_DOCUMENT_COUNT_MISMATCH")
    removed = sum(row["action"].startswith("REMOVED") for row in inventory)
    if removed != mapping["expected_removed_count"]:
        errors.append("REMOVAL_COUNT_MISMATCH")
    for prefix in mapping["retired_prefixes"]:
        if any(name.startswith(prefix) for name in actual):
            errors.append("RETIRED_DOCUMENT_TREE_REINTRODUCED:" + prefix)
    return inventory, errors


def audit(root: Path = ROOT, *, include_history: bool = True) -> dict:
    root = root.resolve()
    errors, inventory, contents = [], [], {}
    try:
        index = read_json(root / "docs/reference/navigation.json")
        mapping = read_json(root / "docs/reference/cleanup_map.json")
        found, contents, _ = check_document_set(root, index)
        errors.extend(found)
        actual = {name for name in contents if name.startswith("docs/")}
        for replacement in mapping["by_basename"].values():
            if replacement not in actual:
                errors.append("MISSING_REPLACEMENT:" + replacement)
        if include_history:
            inventory, found = migration_inventory(root, mapping, actual)
            errors.extend(found)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        errors.append("AUDIT_INCOMPLETE:" + type(error).__name__)
    return {
        "status": "PASS" if not errors else "FAIL", "read_only": True,
        "provider_requests": 0, "history_checked": include_history,
        "current_markdown_count": sum(name.startswith("docs/") for name in contents),
        "old_markdown_count": len(inventory),
        "removed_count": sum(row["action"].startswith("REMOVED") for row in inventory),
        "inventory": inventory, "errors": sorted(set(errors)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = audit()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.check and report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
