#!/usr/bin/env python3
"""Vendor public Eggs, normalize their exchange format and build the panel feed.

Only this maintenance tool reads upstream repositories. The panel reads the
versioned catalog/index.json and bundles from eggs-for-soneyko exclusively.
No downloaded installation script is executed by this tool.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMATS = {"PTDL_v1", "PTDL_v2", "PLCN_v1", "PLCN_v2", "PLCN_v3"}
CATEGORIES = {"minecraft", "games", "sites", "applications", "bots", "data", "instances"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def slug(value: str, limit=64) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:limit] or "egg"


def normalize(raw: dict) -> list[dict]:
    """Keep executable settings intact; adapt only documented format differences."""
    if raw.get("meta", {}).get("version") not in FORMATS:
        raise ValueError("unsupported export format")
    egg = copy.deepcopy(raw)
    images = egg.get("docker_images")
    if not images and isinstance(egg.get("docker_image"), str):
        images = {"Default": egg["docker_image"]}
    if not isinstance(images, dict) or not images or not all(isinstance(v, str) and v for v in images.values()):
        raise ValueError("missing Docker images")
    egg["docker_images"] = {label: value.strip() for label, value in images.items()}
    egg["meta"] = {"version": "PTDL_v2", "update_url": None}
    egg.setdefault("file_denylist", [])
    egg.setdefault("features", [])
    egg.setdefault("config", {})
    egg.setdefault("variables", [])
    if isinstance(egg["variables"], dict):
        egg["variables"] = list(egg["variables"].values())
    seen = set()
    for variable in egg["variables"]:
        name = variable.get("env_variable", "")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or name in seen:
            raise ValueError(f"invalid or duplicate variable: {name}")
        seen.add(name)
        rules = variable.get("rules") or ""
        if isinstance(rules, list):
            rules = "|".join(rules)
        if not isinstance(rules, str):
            raise ValueError("invalid variable rules")
        variable["rules"] = rules
        default = variable.get("default_value")
        variable["default_value"] = "" if default is None else str(default).lower() if isinstance(default, bool) else str(default)
        for key in ("user_viewable", "user_editable"):
            variable[key] = bool(variable.get(key, True))
    for key in ("files", "startup", "logs"):
        value = egg["config"].get(key, "{}")
        parsed = json.loads(value) if isinstance(value, str) and value else value or {}
        # Pterodactyl expects these export fields to contain JSON strings.
        egg["config"][key] = json.dumps(parsed, ensure_ascii=False)
    commands = egg.pop("startup_commands", None)
    if not commands:
        commands = {"Default": egg.get("startup")}
    if not isinstance(commands, dict) or not commands:
        raise ValueError("missing startup command")
    variants = []
    for label, command in commands.items():
        if not isinstance(command, str) or not command.strip():
            raise ValueError("empty startup command")
        variant = copy.deepcopy(egg)
        variant["startup"] = command
        if len(commands) > 1:
            variant["name"] = f"{egg['name']} — {label}"
        variants.append(variant)
    return variants


def category_for(source: dict, path: str, egg: dict) -> str:
    text = f"{path} {egg.get('name', '')}".lower()
    if "minecraft" in text or source["category"] == "minecraft":
        return "minecraft"
    if any(word in text for word in ("discord", "telegram", "chatbot", "chat_bot", "chat-bot")):
        return "bots"
    if any(word in text for word in ("postgres", "mysql", "mariadb", "redis", "mongodb", "database", "rabbitmq", "memcached")):
        return "data"
    if source["category"] == "games" or "game_eggs/" in text or "steamcmd" in text:
        return "games"
    if any(word in text for word in ("nginx", "wordpress", "static_site", "static-site", "nextjs", "next.js")):
        return "sites"
    return source["category"]


def resources_for(category: str) -> dict:
    return {"cpu": 100, "memory_mb": 2048 if category in ("minecraft", "games") else 512,
            "disk_mb": 10240 if category in ("minecraft", "games", "instances") else 5120}


def executable_fingerprint(egg: dict) -> str:
    # Export timestamps, UUIDs and Docker display labels do not create a variant.
    value = {key: egg.get(key) for key in ("name", "startup", "scripts", "config", "variables", "features", "file_denylist", "force_outgoing_ip")}
    value["images"] = sorted(set(egg["docker_images"].values()))
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def get_checkout(source: dict, offline: bool) -> tuple[Path, str]:
    repo = source["repository"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("invalid source repository")
    checkout = ROOT / ".cache" / "upstreams" / repo.replace("/", "--")
    if not (checkout / ".git").exists():
        if offline:
            raise ValueError(f"missing local checkout: {repo}")
        checkout.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", "--branch", source["branch"], f"https://github.com/{repo}.git", str(checkout)], check=True)
    elif not offline:
        subprocess.run(["git", "-C", str(checkout), "fetch", "--depth", "1", "origin", source["branch"]], check=True)
        subprocess.run(["git", "-C", str(checkout), "checkout", "--detach", "FETCH_HEAD"], check=True)
    revision = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    return checkout, revision


def build(offline=False):
    entries, records, skipped, duplicates, sources_lock = [], [], [], [], []
    fingerprints = {}
    written = set()
    sources = read_json(ROOT / "sources.json")
    for source in sources:
        checkout, revision = get_checkout(source, offline)
        repo = source["repository"]
        source_id = repo.replace("/", "--")
        licenses = [p for p in checkout.iterdir() if p.is_file() and p.name.lower().startswith(("license", "copying"))]
        if not licenses:
            raise ValueError(f"source has no root license: {repo}")
        for license_path in licenses:
            target = ROOT / "licenses" / source_id / license_path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(license_path.read_bytes())
        sources_lock.append({**source, "commit": revision, "licenses": [f"licenses/{source_id}/{p.name}" for p in licenses]})
        count = 0
        for path in sorted(checkout.rglob("*.json")):
            if ".git" in path.parts:
                continue
            relative = path.relative_to(checkout).as_posix()
            try:
                raw = read_json(path)
                if not isinstance(raw, dict) or not isinstance(raw.get("meta"), dict) or "version" not in raw["meta"]:
                    continue
                count += 1
                variants = normalize(raw)
            except (ValueError, TypeError, KeyError) as error:
                skipped.append({"repository": repo, "path": relative, "reason": str(error)})
                continue
            for index, egg in enumerate(variants):
                fingerprint = executable_fingerprint(egg)
                origin = {"repository": repo, "commit": revision, "path": relative, "format": raw["meta"]["version"]}
                if fingerprint in fingerprints:
                    fingerprints[fingerprint]["upstream_aliases"].append(origin)
                    duplicates.append({**origin, "canonical_id": fingerprints[fingerprint]["id"]})
                    continue
                category = category_for(source, relative, egg)
                suffix = sha(f"{repo}:{relative}:{index}".encode())[:12]
                key = f"{slug(egg['name'], 40)}-{suffix}"
                egg_path = f"eggs/{category}/{key}.json"
                # Preserve every original export, including Pelican-only metadata.
                original_path = f"originals/{source_id}/{suffix}.json"
                write_json(ROOT / original_path, raw)
                write_json(ROOT / egg_path, egg)
                written.update((egg_path, original_path))
                entry = {"id": key, "name": egg["name"], "description": str(egg.get("description") or "")[:12000],
                         "category": category, "kind": "preset", "path": egg_path, "sha256": sha(encoded(egg)),
                         "resources": resources_for(category), "upstream": origin, "upstream_aliases": [],
                         "original_path": original_path, "runtime_tested": False}
                fingerprints[fingerprint] = entry
                entries.append(entry)
                records.append({"entry": entry, "egg": egg})
        print(f"{repo}: {count} source Eggs", flush=True)
    # First-party entries are normal PTDL_v2 Eggs, with optional panel hints.
    for path in sorted((ROOT / "custom").glob("*.json")):
        raw = read_json(path)
        metadata = raw.pop("_soneyko", {})
        egg = normalize(raw)[0]
        key = metadata.get("id", path.stem)
        category = metadata.get("category", "applications")
        if category not in CATEGORIES or not re.fullmatch(r"[a-z0-9-]+", key):
            raise ValueError(f"invalid custom metadata: {path}")
        egg_path = f"eggs/{category}/{key}.json"
        write_json(ROOT / egg_path, egg)
        written.add(egg_path)
        entry = {"id": key, "name": egg["name"], "description": egg.get("description", ""), "category": category,
                 "kind": metadata.get("kind", "preset"), "path": egg_path, "sha256": sha(encoded(egg)),
                 "resources": metadata.get("resources", resources_for(category)), "upstream": None,
                 "upstream_aliases": [], "runtime_tested": False, **metadata}
        entries.append(entry)
        records.append({"entry": entry, "egg": egg})
    records.sort(key=lambda record: (record["entry"]["kind"] != "instance", record["entry"]["category"], record["entry"]["name"].lower(), record["entry"]["id"]))
    bundles = []
    for offset in range(0, len(records), 10):
        path = f"catalog/bundles/{offset // 10:04d}.json"
        value = {"schema_version": 1, "items": records[offset:offset + 10]}
        write_json(ROOT / path, value)
        written.add(path)
        bundles.append({"path": path, "sha256": sha(encoded(value)), "count": len(value["items"])})
    index = {"schema_version": 1, "repository": "trusted-technologies/eggs-for-soneyko", "count": len(records),
             "bundles": bundles, "entries": [record["entry"] for record in records]}
    write_json(ROOT / "catalog/index.json", index)
    write_json(ROOT / "catalog/sources.lock.json", sources_lock)
    write_json(ROOT / "catalog/import-report.json", {"imported": len(records), "duplicates": duplicates, "skipped": skipped})
    # Only delete generated files under these explicitly bounded directories.
    for directory in (ROOT / "eggs", ROOT / "originals", ROOT / "catalog" / "bundles"):
        if directory.exists():
            for path in directory.rglob("*.json"):
                if path.relative_to(ROOT).as_posix() not in written:
                    path.unlink()
    print(f"Catalog: {len(records)} entries, {len(duplicates)} identical duplicates, {len(skipped)} skipped", flush=True)
    return index


def validate():
    index = read_json(ROOT / "catalog/index.json")
    seen = set()
    loaded = []
    for bundle in index["bundles"]:
        path = ROOT / bundle["path"]
        assert sha(path.read_bytes()) == bundle["sha256"], f"bundle checksum: {path}"
        items = read_json(path)["items"]
        assert len(items) == bundle["count"]
        for record in items:
            entry, egg = record["entry"], record["egg"]
            assert entry["id"] not in seen, f"duplicate id: {entry['id']}"
            seen.add(entry["id"])
            assert entry["category"] in CATEGORIES
            assert entry["kind"] in ("preset", "instance")
            assert sha((ROOT / entry["path"]).read_bytes()) == entry["sha256"]
            assert encoded(egg) == (ROOT / entry["path"]).read_bytes()
            normalize(egg)
            loaded.append(entry)
    assert loaded == index["entries"] and len(loaded) == index["count"]
    print(f"Validated {len(loaded)} catalog entries and {len(index['bundles'])} bundles")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="use existing pinned upstream checkouts")
    parser.add_argument("--check", action="store_true", help="validate generated catalog without downloading")
    args = parser.parse_args()
    if args.check:
        validate()
    else:
        build(args.offline)
        validate()
