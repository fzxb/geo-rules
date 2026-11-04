from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from geobuild.build import Builder
from geobuild.cli import (
    assert_safe_output,
    check_baseline,
    parse_github_remote,
    resolve_repository,
)
from geobuild.config import (
    Config,
    RulesetConfig,
    SourceConfig,
    build_order,
    load_config,
    select,
)
from geobuild.origins import HANDLERS, Entry
from geobuild.util import BuildError, month_placeholders


def _manifest(totals: dict[str, int]) -> dict:
    return {
        "rulesets": {
            name: {"type": "domain", "total": total} for name, total in totals.items()
        }
    }


class BaselineTest(unittest.TestCase):
    def _check(
        self, current: dict, previous: dict | None, *, force: bool = False
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            if previous is not None:
                Path(tmp, "manifest.json").write_text(
                    json.dumps(previous), encoding="utf-8"
                )
            check_baseline(current, Path(tmp), force=force)

    def test_missing_baseline_is_allowed(self):
        self._check(_manifest({"domain/cn": 100}), None)

    def test_stable_counts_pass(self):
        self._check(_manifest({"domain/cn": 100}), _manifest({"domain/cn": 110}))

    def test_shrink_is_blocked(self):
        with self.assertRaises(BuildError):
            self._check(_manifest({"domain/cn": 10}), _manifest({"domain/cn": 100}))

    def test_shrink_can_be_forced(self):
        self._check(
            _manifest({"domain/cn": 10}), _manifest({"domain/cn": 100}), force=True
        )

    def test_growth_only_warns(self):
        self._check(_manifest({"domain/cn": 1000}), _manifest({"domain/cn": 100}))


def _ruleset(name: str, **kwargs) -> RulesetConfig:
    return RulesetConfig(name=name, type="domain", **kwargs)


class OrderTest(unittest.TestCase):
    def test_dependencies_come_first(self):
        rulesets = (
            _ruleset("a/proxy", union=("a/gfw", "a/svc")),
            _ruleset("a/gfw"),
            _ruleset("a/svc"),
        )
        self.assertEqual(
            [ruleset.name for ruleset in build_order(rulesets)],
            ["a/gfw", "a/svc", "a/proxy"],
        )

    def test_subtract_dependencies_come_first(self):
        rulesets = (
            _ruleset("domain/cn", union=("domain/svc",), subtract=("domain/gfw",)),
            _ruleset("domain/gfw"),
            _ruleset("domain/svc"),
        )
        self.assertEqual(
            [ruleset.name for ruleset in build_order(rulesets)],
            ["domain/svc", "domain/gfw", "domain/cn"],
        )

    def test_cycle_is_rejected(self):
        rulesets = (_ruleset("a", union=("b",)), _ruleset("b", union=("a",)))
        with self.assertRaises(BuildError):
            build_order(rulesets)

    def test_select_pulls_in_dependencies(self):
        rulesets = (
            _ruleset("a/proxy", union=("a/gfw",)),
            _ruleset("a/gfw"),
            _ruleset("a/unrelated"),
        )
        selected = select(rulesets, {"a/proxy"})
        self.assertEqual([ruleset.name for ruleset in selected], ["a/gfw", "a/proxy"])

    def test_select_rejects_unknown_names(self):
        with self.assertRaises(BuildError):
            select((_ruleset("a"),), {"nope"})


class MonthPlaceholderTest(unittest.TestCase):
    def test_previous_month_wraps_the_year(self):
        from datetime import UTC, datetime

        values = month_placeholders(datetime(2026, 1, 3, tzinfo=UTC))
        self.assertEqual(
            (
                values["year"],
                values["month"],
                values["prev_year"],
                values["prev_month"],
            ),
            ("2026", "01", "2025", "12"),
        )


class RepositoryTest(unittest.TestCase):
    def test_parse_github_remote(self):
        cases = {
            "git@github.com:fzxb/geo.git": "fzxb/geo",
            "git@github.com:fzxb/geo": "fzxb/geo",
            "https://github.com/fzxb/geo": "fzxb/geo",
            "https://github.com/fzxb/geo.git": "fzxb/geo",
            "https://token@github.com/fzxb/geo.git": "fzxb/geo",
            "ssh://git@github.com/fzxb/geo.git": "fzxb/geo",
            "https://github.com/fzxb/geo/": "fzxb/geo",
        }
        for remote, expected in cases.items():
            self.assertEqual(parse_github_remote(remote), expected, remote)

    def test_non_github_or_incomplete_remotes(self):
        for remote in (
            "git@gitlab.com:fzxb/geo.git",
            "https://gitee.com/fzxb/geo",
            "https://github.com/only-owner",
            "",
        ):
            self.assertIsNone(parse_github_remote(remote), remote)

    def test_explicit_values_win(self):
        with (
            mock.patch("geobuild.cli.detect_repository", return_value="detected/repo"),
            mock.patch.dict("os.environ", {}, clear=True),
        ):
            self.assertEqual(resolve_repository("arg/repo", {}), "arg/repo")
            self.assertEqual(
                resolve_repository("", {"repository": "config/repo"}), "config/repo"
            )
            # the placeholder is treated as unset
            self.assertEqual(
                resolve_repository("", {"repository": "OWNER/REPO"}), "detected/repo"
            )
            self.assertEqual(resolve_repository("", {}), "detected/repo")

    def test_environment_is_used(self):
        with mock.patch.dict("os.environ", {"GITHUB_REPOSITORY": "env/repo"}):
            self.assertEqual(resolve_repository("", {}), "env/repo")

    def test_placeholder_when_nothing_can_be_detected(self):
        with (
            mock.patch("geobuild.cli.detect_repository", return_value=None),
            mock.patch.dict("os.environ", {}, clear=True),
        ):
            self.assertEqual(resolve_repository("", {}), "OWNER/REPO")


class AttributeFilterTest(unittest.TestCase):
    """`exclude_attrs` keeps China-localised entries out of service rule-sets."""

    def _build(self, exclude: tuple[str, ...]):
        entries = [
            Entry("suffix", "global.example.com"),
            Entry("suffix", "cn.example.com", attrs=frozenset({"cn"})),
            Entry("suffix", "cn-ads.example.com", attrs=frozenset({"cn", "ads"})),
        ]
        HANDLERS["_test"] = lambda ctx, src, selector: iter(entries)
        try:
            config = Config(
                settings={},
                sources={"t": SourceConfig(name="t", kind="_test")},
                rulesets=(
                    RulesetConfig(
                        name="domain/x",
                        type="domain",
                        sources=("t",),
                        exclude_attrs=exclude,
                        expect_min=1,
                    ),
                ),
            )
            builder = Builder(config, fetcher=None)  # type: ignore[arg-type]
            return builder, builder.build(list(config.rulesets))["domain/x"]
        finally:
            del HANDLERS["_test"]

    def test_without_exclusion_everything_is_kept(self):
        _, result = self._build(())
        self.assertEqual(result.total, 3)

    def test_excluded_attributes_are_dropped_and_counted(self):
        builder, result = self._build(("cn",))
        self.assertEqual(result.rule, {"domain_suffix": ["global.example.com"]})
        self.assertEqual(
            builder.drops["t: excluded @cn"], 2, "both @cn entries must be reported"
        )


class SafeOutputTest(unittest.TestCase):
    """--out is rmtree'd, so it must never point at the repo or its parents."""

    def test_rejects_cwd_and_ancestors(self):
        for path in (".", "..", "./"):
            with self.assertRaises(BuildError, msg=path):
                assert_safe_output(Path(path))

    def test_rejects_a_git_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            with self.assertRaises(BuildError):
                assert_safe_output(root)

    def test_accepts_a_plain_subdirectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert_safe_output(Path(tmp) / "dist")


class NameValidationTest(unittest.TestCase):
    """Ruleset names become output paths, so traversal must be impossible."""

    def _load(self, name: str):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sources.toml").write_text(
                '[sources.x]\nkind = "static"\nentries = ["example.com"]\n',
                encoding="utf-8",
            )
            (root / "rulesets.toml").write_text(
                f'[[ruleset]]\nname = "{name}"\ntype = "domain"\nsources = ["x"]\n',
                encoding="utf-8",
            )
            return load_config(root)

    def test_valid_names_are_accepted(self):
        for name in ("domain/cn", "domain/example-site", "ip/service/telegram", "a"):
            config = self._load(name)
            self.assertEqual(config.rulesets[0].name, name)

    def test_traversal_is_rejected(self):
        for name in ("a/../../evil", "a//b", "../x", "./x", "a/./b"):
            with self.assertRaises(BuildError, msg=name):
                self._load(name)


if __name__ == "__main__":
    unittest.main()
