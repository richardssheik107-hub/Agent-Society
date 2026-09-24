#!/usr/bin/env python3
"""只读仓库审计：旧32项原文可恢复，业务保护不放宽，中文导航单独检查。"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_entries(data: dict) -> list[dict]:
    pairs = list(data["archive_files"])
    for group in data["archive_directories"]:
        names = git("ls-tree", "-r", "--name-only", group["ref"], group["source"]).decode().splitlines()
        for source in names:
            relative = Path(source).relative_to(group["source"])
            pairs.append({"ref": group["ref"], "source": source,
                          "archive": str(Path(group["archive"]) / relative)})
    return pairs


def audit() -> dict:
    errors, modules, checked = [], {}, []
    files: list[str] = []
    try:
        files = git("ls-files").decode().splitlines()
        data = json.loads((ROOT / "docs/current/cleanup_manifest.json").read_text(encoding="utf-8"))
        policy = data.get("document_retirement", {})
        if policy.get("policy") != "PINNED_GIT_HISTORY_FOR_DOCS_ONLY":
            raise ValueError("explicit document retirement policy required")
        mapping_path = ROOT / policy["mapping"]
        if mapping_path.resolve() != (ROOT / "docs/reference/cleanup_map.json").resolve():
            raise ValueError("unexpected retirement mapping")
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        for entry in archive_entries(data):
            original = git("show", entry["ref"] + ":" + entry["source"])
            expected = sha(original)
            blob = git("rev-parse", entry["ref"] + ":" + entry["source"]).decode().strip()
            actual_blob = hashlib.sha1(b"blob " + str(len(original)).encode() + b"\0" + original).hexdigest()
            if actual_blob != blob:
                errors.append("GIT_CONTENT_CORRUPTION:" + entry["source"])
            path = ROOT / entry["archive"]
            if entry["archive"].startswith("docs/archive/"):
                replacement = mapping["by_basename"].get(path.name)
                if not replacement or not (ROOT / replacement).is_file():
                    errors.append("归档缺少中文替代:" + entry["archive"])
                if path.exists():
                    errors.append("已退役文档重新出现:" + entry["archive"])
                storage = "PINNED_GIT_HISTORY"
            else:
                if not path.is_file() or sha(path.read_bytes()) != expected:
                    errors.append("归档工具原文变化:" + entry["archive"])
                storage = "WORKTREE_BYTE_IDENTICAL"
            checked.append({**entry, "sha256": expected, "git_blob": blob, "storage": storage})
        if len(checked) != 32:
            errors.append("原32项档案登记数量改变")
        originals = git("ls-tree", "-r", "--name-only", data["research_base"]).decode().splitlines()
        for source in originals:
            if source in data["allowed_legacy_changes"]:
                continue
            if not any(source.startswith(prefix) for prefix in data["protected_base_prefixes"]):
                continue
            path = ROOT / source
            expected = sha(git("show", data["research_base"] + ":" + source))
            if not path.is_file() or sha(path.read_bytes()) != expected:
                errors.append("历史代码变化:" + source)
        for source in data["protected_main_files"]:
            path = ROOT / source
            expected = sha(git("show", data["main_base"] + ":" + source))
            if not path.is_file() or sha(path.read_bytes()) != expected:
                errors.append("其他成员数据变化:" + source)
        actual = git("rev-parse", "HEAD:third_party/AgentSociety").decode().strip()
        if actual != data["upstream_gitlink"]:
            errors.append("上游子模块版本改变")
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        errors.append("HISTORY_AUDIT_INCOMPLETE:" + type(error).__name__)
    for name in files:
        path = ROOT / name
        if not path.is_file() or not name.endswith(".py"):
            continue
        if name.startswith(("src/", "scripts/", "tests/", "smoke/")):
            try:
                ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                errors.append("Python语法错误:" + name)
        if name.startswith("src/social_sim/"):
            module = name.split("/")[2]
            modules[module] = modules.get(module, 0) + 1
    try:
        from audit_documentation import audit as audit_docs
        docs = audit_docs(ROOT)
        errors.extend(docs["errors"])
    except (ImportError, OSError, ValueError) as error:
        errors.append("DOCUMENT_AUDIT_INCOMPLETE:" + type(error).__name__)
    return {"tracked_files": len(files), "modules": modules,
            "archived_count": len(checked), "archived": checked,
            "errors": sorted(set(errors)), "status": "PASS" if not errors else "FAIL",
            "read_only": True, "provider_requests": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = audit()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.check and report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
