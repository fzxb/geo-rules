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
from geobuild.emit import write_ruleset
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

    def test_intersect_dependencies_come_first(self):
        rulesets = (
            _ruleset("domain/global", intersect=("domain/a", "domain/b")),
            _ruleset("domain/a"),
            _ruleset("domain/b"),
        )
        self.assertEqual(
            [ruleset.name for ruleset in build_order(rulesets)],
            ["domain/a", "domain/b", "domain/global"],
        )

    def test_strict_subtract_dependencies_come_first(self):
        rulesets = (
            _ruleset("domain/cn", strict_subtract=("domain/gfw",)),
            _ruleset("domain/gfw"),
        )
        self.assertEqual(
            [ruleset.name for ruleset in build_order(rulesets)],
            ["domain/gfw", "domain/cn"],
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


class StrictSubtractBuildTest(unittest.TestCase):
    """Strict subtraction must remove parents that cover a blocked entry."""

    def test_parent_covering_a_blocked_domain_is_removed(self):
        HANDLERS["_strict_cn"] = lambda ctx, src, selector: iter(
            [
                Entry("suffix", "example.com"),
                Entry("suffix", "keep.example.org"),
            ]
        )
        HANDLERS["_strict_gfw"] = lambda ctx, src, selector: iter(
            [Entry("suffix", "blocked.example.com")]
        )
        try:
            config = Config(
                settings={},
                sources={
                    "cn": SourceConfig(name="cn", kind="_strict_cn"),
                    "gfw": SourceConfig(name="gfw", kind="_strict_gfw"),
                },
                rulesets=(
                    RulesetConfig(
                        name="domain/gfw",
                        type="domain",
                        sources=("gfw",),
                        expect_min=1,
                    ),
                    RulesetConfig(
                        name="domain/cn",
                        type="domain",
                        sources=("cn",),
                        strict_subtract=("domain/gfw",),
                        expect_min=1,
                    ),
                ),
            )
            builder = Builder(config, fetcher=None)  # type: ignore[arg-type]
            results = builder.build(list(config.rulesets))
            cn = results["domain/cn"]
            self.assertEqual(cn.rule, {"domain_suffix": ["keep.example.org"]})
            self.assertTrue(
                cn.domain_set is not None
                and results["domain/gfw"].domain_set is not None
                and cn.domain_set.is_disjoint(results["domain/gfw"].domain_set)
            )
            self.assertEqual(builder.checks[0]["count"], 0)
        finally:
            del HANDLERS["_strict_cn"]
            del HANDLERS["_strict_gfw"]


class IntersectBuildTest(unittest.TestCase):
    def test_intersection_uses_the_more_specific_suffix(self):
        HANDLERS["_intersect_a"] = lambda ctx, src, selector: iter(
            [Entry("suffix", "example.com"), Entry("suffix", "keep.a")]
        )
        HANDLERS["_intersect_b"] = lambda ctx, src, selector: iter(
            [Entry("suffix", "sub.example.com"), Entry("suffix", "only.b")]
        )
        try:
            config = Config(
                settings={},
                sources={
                    "a": SourceConfig(name="a", kind="_intersect_a"),
                    "b": SourceConfig(name="b", kind="_intersect_b"),
                },
                rulesets=(
                    RulesetConfig(
                        name="domain/a", type="domain", sources=("a",), expect_min=1
                    ),
                    RulesetConfig(
                        name="domain/b", type="domain", sources=("b",), expect_min=1
                    ),
                    RulesetConfig(
                        name="domain/global",
                        type="domain",
                        intersect=("domain/a", "domain/b"),
                        expect_min=1,
                    ),
                ),
            )
            builder = Builder(config, fetcher=None)  # type: ignore[arg-type]
            results = builder.build(list(config.rulesets))
            self.assertEqual(
                results["domain/global"].rule,
                {"domain_suffix": ["sub.example.com"]},
            )
        finally:
            del HANDLERS["_intersect_a"]
            del HANDLERS["_intersect_b"]

    def test_sources_are_intersected_with_a_target(self):
        HANDLERS["_intersect_a"] = lambda ctx, src, selector: iter(
            [Entry("suffix", "example.com"), Entry("suffix", "keep.a")]
        )
        HANDLERS["_intersect_src"] = lambda ctx, src, selector: iter(
            [Entry("suffix", "sub.example.com"), Entry("suffix", "only.src")]
        )
        try:
            config = Config(
                settings={},
                sources={
                    "a": SourceConfig(name="a", kind="_intersect_a"),
                    "src": SourceConfig(name="src", kind="_intersect_src"),
                },
                rulesets=(
                    RulesetConfig(
                        name="domain/a", type="domain", sources=("a",), expect_min=1
                    ),
                    RulesetConfig(
                        name="domain/global",
                        type="domain",
                        sources=("src",),
                        intersect=("domain/a",),
                        expect_min=1,
                    ),
                ),
            )
            builder = Builder(config, fetcher=None)  # type: ignore[arg-type]
            results = builder.build(list(config.rulesets))
            self.assertEqual(
                results["domain/global"].rule,
                {"domain_suffix": ["sub.example.com"]},
            )
        finally:
            del HANDLERS["_intersect_a"]
            del HANDLERS["_intersect_src"]


class LogicalRuleTest(unittest.TestCase):
    def test_exclude_emits_logical_rule_and_clears_check(self):
        HANDLERS["_logical_cn"] = lambda ctx, src, selector: iter(
            [Entry("suffix", "example.com")]
        )
        HANDLERS["_logical_gfw"] = lambda ctx, src, selector: iter(
            [Entry("suffix", "blocked.example.com")]
        )
        try:
            config = Config(
                settings={},
                sources={
                    "cn": SourceConfig(name="cn", kind="_logical_cn"),
                    "gfw": SourceConfig(name="gfw", kind="_logical_gfw"),
                },
                rulesets=(
                    RulesetConfig(
                        name="domain/gfw",
                        type="domain",
                        sources=("gfw",),
                        expect_min=1,
                    ),
                    RulesetConfig(
                        name="domain/cn",
                        type="domain",
                        sources=("cn",),
                        exclude=("domain/gfw",),
                        expect_min=1,
                    ),
                ),
            )
            builder = Builder(config, fetcher=None)  # type: ignore[arg-type]
            results = builder.build(list(config.rulesets))
            cn = results["domain/cn"]
            self.assertEqual(
                cn.exclusions.suffixes if cn.exclusions else set(),
                {"blocked.example.com"},
            )
            self.assertEqual(builder.checks[0]["count"], 0)
            with tempfile.TemporaryDirectory() as tmp:
                path = write_ruleset(Path(tmp), cn)
                payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["rules"][0]["type"], "logical")
            nested = payload["rules"][0]["rules"]
            self.assertNotIn("invert", nested[0])
            self.assertTrue(nested[1]["invert"])
            self.assertEqual(nested[1]["domain_suffix"], ["blocked.example.com"])
        finally:
            del HANDLERS["_logical_cn"]
            del HANDLERS["_logical_gfw"]


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


class StrictSubtractConfigTest(unittest.TestCase):
    def _load(self, extra: str = "") -> Config:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sources.toml").write_text(
                '[sources.x]\nkind = "static"\nentries = ["example.com"]\n',
                encoding="utf-8",
            )
            (root / "rulesets.toml").write_text(
                "[[ruleset]]\n"
                'name = "domain/gfw"\n'
                'type = "domain"\n'
                'sources = ["x"]\n'
                "\n"
                "[[ruleset]]\n"
                'name = "domain/cn"\n'
                'type = "domain"\n'
                'sources = ["x"]\n'
                + extra,
                encoding="utf-8",
            )
            return load_config(root)

    def test_strict_target_is_parsed(self):
        config = self._load('strict_subtract = ["domain/gfw"]\n')
        cn = config.by_name()["domain/cn"]
        self.assertEqual(cn.strict_subtract, ("domain/gfw",))
        self.assertEqual(
            [ruleset.name for ruleset in build_order(config.rulesets)],
            ["domain/gfw", "domain/cn"],
        )

    def test_duplicate_subtract_and_strict_target_is_rejected(self):
        with self.assertRaises(BuildError):
            self._load(
                'subtract = ["domain/gfw"]\n'
                'strict_subtract = ["domain/gfw"]\n'
            )


class IntersectConfigTest(unittest.TestCase):
    def _load(self, all_body: str, all_type: str = "domain") -> Config:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sources.toml").write_text(
                '[sources.x]\nkind = "static"\nentries = ["example.com"]\n',
                encoding="utf-8",
            )
            (root / "rulesets.toml").write_text(
                "[[ruleset]]\n"
                'name = "domain/a"\n'
                'type = "domain"\n'
                'sources = ["x"]\n'
                "\n"
                "[[ruleset]]\n"
                'name = "domain/b"\n'
                'type = "domain"\n'
                'sources = ["x"]\n'
                "\n"
                "[[ruleset]]\n"
                'name = "domain/all"\n'
                f'type = "{all_type}"\n'
                + all_body,
                encoding="utf-8",
            )
            return load_config(root)

    def test_intersect_is_parsed_and_ordered(self):
        config = self._load('intersect = ["domain/a", "domain/b"]\n')
        all_rule = config.by_name()["domain/all"]
        self.assertEqual(all_rule.intersect, ("domain/a", "domain/b"))
        self.assertEqual(
            [ruleset.name for ruleset in build_order(config.rulesets)],
            ["domain/a", "domain/b", "domain/all"],
        )

    def test_intersect_can_combine_with_sources(self):
        config = self._load(
            'sources = ["x"]\n'
            'intersect = ["domain/a"]\n'
        )
        self.assertEqual(
            config.by_name()["domain/all"].intersect,
            ("domain/a",),
        )

    def test_intersect_needs_two_targets(self):
        with self.assertRaises(BuildError):
            self._load('intersect = ["domain/a"]\n')

    def test_intersect_is_domain_only(self):
        with self.assertRaises(BuildError):
            self._load(
                'intersect = ["domain/a", "domain/b"]\n',
                all_type="ip",
            )


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
