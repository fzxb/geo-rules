"""Write the published artefacts: JSON, SRS, manifest and the branch README."""

from __future__ import annotations

from pathlib import Path

from .build import BuildResult
from .util import human_bytes, human_int, sha256_file, utc_now, write_json

#: sing-box source format version. Version 3 is understood by every release
#: from 1.11 onwards, while everything we emit (domain, domain_suffix,
#: ip_cidr) has been stable since version 1.
SOURCE_VERSION = 3

DEFAULT_BRANCH = "rule-set"


def write_ruleset(out_dir: Path, result: BuildResult) -> Path:
    path = out_dir / f"{result.config.name}.json"
    write_json(path, {"version": SOURCE_VERSION, "rules": [result.rule]})
    return path


def file_entry(path: Path, root: Path) -> dict:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def build_manifest(
    results: dict[str, BuildResult],
    source_stats: dict[str, dict],
    out_dir: Path,
    *,
    builder_version: str,
    sing_box_version: str,
    notes: list[str],
    drops: dict[str, int],
    checks: list[dict] | None = None,
) -> dict:
    rulesets: dict[str, dict] = {}
    total_bytes = 0
    total_domains = 0
    total_prefixes = 0

    for name, result in results.items():
        files: dict[str, dict] = {}
        json_path = out_dir / f"{name}.json"
        if json_path.exists():
            entry = file_entry(json_path, out_dir)
            files["json"] = entry
            total_bytes += entry["bytes"]
        srs_path = out_dir / f"{name}.srs"
        if srs_path.exists():
            entry = file_entry(srs_path, out_dir)
            files["srs"] = entry
            total_bytes += entry["bytes"]

        total_domains += result.counts.get("domain", 0) + result.counts.get(
            "domain_suffix", 0
        )
        total_prefixes += result.counts.get("ip_cidr", 0)
        rulesets[name] = {
            "type": result.config.type,
            "description": result.config.description,
            "total": result.total,
            "entries": result.counts,
            "rejects": dict(sorted(result.rejects.items())),
            "subtracted": result.subtracted,
            "sources": result.sources,
            "files": files,
        }

    sources = [
        {
            "name": stats["source"],
            "kind": stats["kind"],
            "url": url,
            "revision": stats["revision"],
            "sha256": stats["sha256"],
            "bytes": stats["bytes"],
            "fetched_at": stats["fetched_at"],
        }
        for url, stats in sorted(
            source_stats.items(), key=lambda item: (item[1]["source"], item[0])
        )
    ]

    return {
        "schema": 2,
        "generated_at": utc_now(),
        "builder": {
            "name": "geobuild",
            "version": builder_version,
            "sing_box": sing_box_version,
            "source_version": SOURCE_VERSION,
        },
        "stats": {
            "rulesets": len(rulesets),
            "bytes": total_bytes,
            "domains": total_domains,
            "ip_cidrs": total_prefixes,
        },
        "notes": notes,
        "checks": checks or [],
        "drops": dict(sorted(drops.items())),
        "sources": sources,
        "rulesets": rulesets,
    }


def render_readme(manifest: dict, repository: str, branch: str = DEFAULT_BRANCH) -> str:
    base = f"https://raw.githubusercontent.com/{repository}/{branch}"
    stats = manifest["stats"]
    builder = manifest["builder"]
    lines = [
        "# rule-set",
        "",
        (
            "> Generated from the "
            f"[`main`](https://github.com/{repository}/tree/main) branch by GitHub "
            "Actions. Do not edit."
        ),
        "",
        (
            f"`{manifest['generated_at']}` · sing-box `{builder['sing_box']}` · "
            f"source format v{builder['source_version']} · "
            f"{stats['rulesets']} rule-sets · {human_int(stats['domains'])} domains · "
            f"{human_int(stats['ip_cidrs'])} prefixes · {human_bytes(stats['bytes'])}"
        ),
        "",
        "Counts are per rule-set; service and collection layers overlap.",
        "",
        "## Usage",
        "",
        "```jsonc",
        "{",
        '  "route": {',
        '    "rule_set": [',
        "      {",
        '        "type": "remote",',
        '        "tag": "cn-domain",',
        '        "format": "binary",',
        f'        "url": "{base}/domain/cn.srs",',
        '        "http_client": "proxy",',
        '        "update_interval": "1d"',
        "      }",
        "    ],",
        '    "rules": [',
        '      { "rule_set": ["cn-domain"], "outbound": "direct" }',
        "    ],",
        '    "final": "proxy"',
        "  }",
        "}",
        "```",
        "",
        (
            "`http_client` is required since sing-box 1.14; `format` may be omitted. "
            "Match `gfw` before `cn` (~0.6% overlap via the bare `cn` TLD)."
        ),
        "",
        "## Rule-sets",
        "",
        "| Rule-set | Type | Entries | JSON | SRS |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for name, entry in manifest["rulesets"].items():
        files = entry["files"]
        json_size = human_bytes(files["json"]["bytes"]) if "json" in files else "-"
        srs_size = human_bytes(files["srs"]["bytes"]) if "srs" in files else "-"
        lines.append(
            f"| `{name}` | {entry['type']} | {human_int(entry['total'])} "
            f"| [{json_size}]({base}/{name}.json) | [{srs_size}]({base}/{name}.srs) |"
        )

    lines += [
        "",
        "## Verification",
        "",
        "Every file's SHA-256 is recorded in [`manifest.json`](manifest.json):",
        "",
        "```bash",
        f"curl -sL {base}/manifest.json | jq -r '.rulesets[].files.srs.sha256'",
        "```",
        "",
        "## Sources",
        "",
        "| Source | Kind | Revision |",
        "| --- | --- | --- |",
    ]
    seen: set[str] = set()
    for source in manifest["sources"]:
        if source["name"] in seen:
            continue
        seen.add(source["name"])
        revision = source["revision"] or "-"
        if len(revision) > 20:
            revision = revision[:12]
        lines.append(f"| `{source['name']}` | {source['kind']} | `{revision}` |")
    lines.append("")
    return "\n".join(lines)
