"""Command line interface: ``python -m geobuild build``."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from .build import Builder
from .config import Config, build_order, load_config, select
from .emit import build_manifest, render_readme, write_ruleset
from .fetch import Fetcher
from .util import BuildError, human_bytes, human_int, log, read_json, write_json
from .verify import SingBox, verify

SHRINK_FLOOR = 0.6
GROWTH_CEILING = 2.5
PLACEHOLDER_REPOSITORY = "OWNER/REPO"

# git@github.com:o/r.git | https://github.com/o/r | https://user@github.com/o/r
_GITHUB_REMOTE = re.compile(
    r"^(?:git@|https?://(?:[^@/]+@)?|ssh://(?:[^@/]+@)?)github\.com[:/]"
    r"(?P<owner>[A-Za-z0-9._-]+)/(?P<repo>[A-Za-z0-9._-]+?)(?:\.git)?/?$"
)


def as_int(value: object, label: str, default: int | None = None) -> int:
    if value is None and default is not None:
        return default
    try:
        return int(str(value))
    except (TypeError, ValueError):
        raise BuildError(f"{label}: expected an integer, got {value!r}") from None


def parse_github_remote(url: str) -> str | None:
    """``git@github.com:owner/repo.git`` -> ``owner/repo`` (GitHub only)."""
    match = _GITHUB_REMOTE.match(url.strip())
    return f"{match['owner']}/{match['repo']}" if match else None


def detect_repository() -> str | None:
    """Best effort guess from the local ``origin`` remote."""
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return parse_github_remote(completed.stdout)


def resolve_repository(argument: str, settings: dict) -> str:
    """--repository > $GITHUB_REPOSITORY > config > git remote > placeholder."""
    for candidate in (
        argument,
        os.environ.get("GITHUB_REPOSITORY"),
        settings.get("repository"),
    ):
        text = str(candidate or "").strip()
        if text and text != PLACEHOLDER_REPOSITORY:
            return text
    detected = detect_repository()
    if detected:
        log(f"repository: {detected} (detected from git remote)")
        return detected
    log(
        "repository: cannot detect owner/repo, links will use "
        + PLACEHOLDER_REPOSITORY,
        "warn",
    )
    return PLACEHOLDER_REPOSITORY


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geobuild",
        description="Build sing-box rule-sets from authoritative upstream data.",
    )
    _ = parser.add_argument(
        "--version", action="version", version=f"geobuild {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build all configured rule-sets")
    _ = build.add_argument(
        "--config-dir", default="config", help="directory with *.toml configs"
    )
    _ = build.add_argument(
        "--out", default="dist", help="output directory (default: dist)"
    )
    _ = build.add_argument("--cache", default=".cache", help="download cache directory")
    _ = build.add_argument(
        "--sing-box",
        default=os.environ.get("SING_BOX", "sing-box"),
        help="sing-box binary used to compile and verify SRS (default: $SING_BOX)",
    )
    _ = build.add_argument("--only", default="", help="comma separated ruleset names")
    _ = build.add_argument("--baseline", default="", help="previously published tree")
    _ = build.add_argument(
        "--repository",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
        help=(
            "owner/repo used in generated links "
            "(default: $GITHUB_REPOSITORY, then the git origin remote)"
        ),
    )
    _ = build.add_argument(
        "--no-srs", action="store_true", help="skip .srs compilation"
    )
    _ = build.add_argument("--offline", action="store_true", help="use the cache only")
    _ = build.add_argument(
        "--force", action="store_true", help="ignore the shrink guard"
    )
    _ = build.add_argument(
        "--no-readme", action="store_true", help="do not write README.md"
    )

    listing = subparsers.add_parser("list", help="list configured rule-sets")
    _ = listing.add_argument("--config-dir", default="config")

    return parser


def _load(config_dir: str) -> Config:
    return load_config(Path(config_dir))


def list_rulesets(args: argparse.Namespace) -> int:
    config = _load(args.config_dir)
    for ruleset in build_order(config.rulesets):
        inputs = ", ".join(
            [*ruleset.sources, *(f"union:{name}" for name in ruleset.union)]
        )
        print(f"{ruleset.name:32s} {ruleset.type:6s} {inputs}")
    return 0


def check_baseline(manifest: dict, baseline: Path, *, force: bool) -> None:
    """Refuse to publish a ruleset that suddenly lost most of its entries."""
    previous_path = baseline / "manifest.json"
    if not previous_path.exists():
        log("no baseline manifest, skipping regression guard")
        return
    previous = read_json(previous_path)
    if not isinstance(previous, dict):
        log(f"baseline manifest at {previous_path} is not an object, skipping", "warn")
        return
    previous_rulesets = previous.get("rulesets") or {}
    problems: list[str] = []
    for name, entry in manifest["rulesets"].items():
        old = previous_rulesets.get(name)
        if not isinstance(old, dict):
            continue
        old_total = as_int(old.get("total"), f"baseline {name}.total", default=0)
        new_total = as_int(entry.get("total"), f"{name}.total")
        if old_total <= 0:
            continue
        if new_total < old_total * SHRINK_FLOOR:
            problems.append(f"{name}: {old_total} -> {new_total}")
        elif new_total > old_total * GROWTH_CEILING:
            log(f"baseline: {name} grew {old_total} -> {new_total} entries", "warn")
    if not problems:
        log("baseline check passed")
        return
    message = "shrink guard tripped (" + "; ".join(problems) + ")"
    if force:
        log(message + " -- ignored because of --force", "warn")
        return
    raise BuildError(message + " -- rerun with --force if this is expected")


def assert_safe_output(out_dir: Path) -> None:
    """Refuse to wipe a directory that holds the repo (or the cwd)."""
    resolved = out_dir.resolve()
    cwd = Path.cwd().resolve()
    if resolved == cwd or cwd.is_relative_to(resolved):
        raise BuildError(
            f"refusing to use {out_dir} as --out: it contains the working directory"
        )
    if (resolved / ".git").exists():
        raise BuildError(f"refusing to use {out_dir} as --out: it is a git repository")


def run_build(args: argparse.Namespace) -> int:
    config = _load(args.config_dir)
    repository = resolve_repository(args.repository, config.settings)

    user_agent = str(
        config.settings.get(
            "user_agent",
            f"geobuild/{__version__} (+https://github.com/{repository})",
        )
    ).replace("OWNER/REPO", repository)

    fetcher = Fetcher(
        Path(args.cache),
        user_agent,
        ttl=as_int(config.settings.get("cache_ttl"), "settings.cache_ttl", 6 * 3600),
        offline=bool(args.offline),
    )
    builder = Builder(config, fetcher, repository=repository, version=__version__)

    if args.only:
        only = {name.strip() for name in str(args.only).split(",") if name.strip()}
        rulesets = select(config.rulesets, only)
    else:
        rulesets = build_order(config.rulesets)

    log(
        f"building {len(rulesets)} rule-set(s) from {len(config.sources)} source endpoint(s)"
    )
    results = builder.build(rulesets)

    sing_box_version = "skipped"
    box: SingBox | None = None
    if args.no_srs:
        log("--no-srs: binary rule-sets are disabled", "warn")
    else:
        box = SingBox(str(args.sing_box))
        sing_box_version = box.version()
        log(f"using sing-box {sing_box_version}")

    out_dir = Path(args.out)
    assert_safe_output(out_dir)
    if out_dir.exists():
        try:
            shutil.rmtree(out_dir)
        except OSError as exc:
            raise BuildError(f"cannot clear {out_dir}: {exc}") from None
    out_dir.mkdir(parents=True)

    for result in results.values():
        json_path = write_ruleset(out_dir, result)
        if box is not None:
            srs_path = json_path.with_suffix(".srs")
            box.compile(json_path, srs_path)
            verify(json_path, srs_path, box)

    manifest = build_manifest(
        results,
        builder.source_stats,
        out_dir,
        builder_version=__version__,
        sing_box_version=sing_box_version,
        notes=builder.notes,
        drops=dict(builder.drops),
        checks=builder.checks,
    )
    write_json(out_dir / "manifest.json", manifest)

    if not args.no_readme:
        readme = render_readme(manifest, repository)
        _ = (out_dir / "README.md").write_text(readme, encoding="utf-8")

    if args.baseline:
        check_baseline(manifest, Path(args.baseline), force=bool(args.force))

    _print_summary(manifest)
    return 0


def _print_summary(manifest: dict) -> None:
    width = (
        max(len(name) for name in manifest["rulesets"]) if manifest["rulesets"] else 10
    )
    for name, entry in manifest["rulesets"].items():
        files = entry["files"]
        json_size = files.get("json", {}).get("bytes", 0)
        srs_size = files.get("srs", {}).get("bytes", 0)
        counts = " ".join(f"{key}={value}" for key, value in entry["entries"].items())
        log(
            f"{name:<{width}}  {human_int(entry['total']):>8}  "
            f"{human_bytes(json_size):>9} / {human_bytes(srs_size):>9}  {counts}"
        )
    stats = manifest["stats"]
    log(
        f"total: {stats['rulesets']} rule-sets, {human_int(stats['domains'])} domains, "
        f"{human_int(stats['ip_cidrs'])} prefixes, {human_bytes(stats['bytes'])}"
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "list":
            return list_rulesets(args)
        return run_build(args)
    except BuildError as exc:
        log(str(exc), "error")
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
