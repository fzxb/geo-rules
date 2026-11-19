"""Compile and verify binary rule-sets with the official sing-box binary.

Using sing-box itself instead of a hand written SRS encoder is a deliberate
reliability choice: the binary format (magic ``SRS`` + version byte + zlib
payload) is versioned and only the upstream implementation is authoritative.
The same binary is then used to prove that the compiled file still matches the
source after a round-trip.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .ips import canonical
from .util import BuildError, read_json


class SingBox:
    def __init__(self, binary: str) -> None:
        self.binary = binary
        self._version: str | None = None

    def _run(self, args: list[str]) -> str:
        try:
            completed = subprocess.run(
                [self.binary, *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except FileNotFoundError:
            raise BuildError(
                f"sing-box binary not found: {self.binary!r} "
                "(pass --sing-box or install sing-box >= 1.14)"
            ) from None
        except subprocess.TimeoutExpired:
            raise BuildError(f"sing-box {' '.join(args)} timed out") from None
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip().splitlines()
            raise BuildError(
                f"sing-box {' '.join(args)} failed: {detail[-1] if detail else 'unknown error'}"
            )
        # sing-box writes operational output (including `rule-set match`
        # results) to stderr, so both streams have to be inspected.
        return completed.stdout + completed.stderr

    def version(self) -> str:
        if self._version is None:
            output = self._run(["version"])
            for line in output.splitlines():
                if line.startswith("sing-box version"):
                    self._version = line.split()[-1]
                    break
            else:
                raise BuildError(
                    f"cannot parse sing-box version output: {output[:200]!r}"
                )
        return self._version

    def compile(self, source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = self._run(["rule-set", "compile", str(source), "-o", str(target)])
        if not target.exists() or target.stat().st_size == 0:
            raise BuildError(f"sing-box produced no output for {source}")

    def decompile(self, binary: Path) -> dict:
        with tempfile.TemporaryDirectory(prefix="geobuild-") as tmp:
            target = Path(tmp) / "decompiled.json"
            _ = self._run(["rule-set", "decompile", str(binary), "-o", str(target)])
            return load_rule_set(target)

    def matches(self, binary: Path, value: str) -> bool:
        output = self._run(["rule-set", "match", "-f", "binary", str(binary), value])
        return "match rules." in output


def load_rule_set(path: Path) -> dict:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise BuildError(f"{path}: expected a JSON object")
    return payload


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise BuildError(f"unexpected rule-set value: {value!r}")


def flatten(payload: dict) -> tuple[set[tuple[str, str]], list[str]]:
    domains: set[tuple[str, str]] = set()
    prefixes: list[str] = []
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise BuildError("rule-set JSON has no 'rules' list")

    def walk(rule: dict) -> None:
        if rule.get("type") == "logical":
            nested = rule.get("rules")
            if not isinstance(nested, list):
                raise BuildError(f"logical rule without 'rules': {rule!r}")
            for child in nested:
                if not isinstance(child, dict):
                    raise BuildError(f"unexpected logical rule: {child!r}")
                walk(child)
            return
        for key in ("domain", "domain_suffix", "domain_regex", "domain_keyword"):
            for value in _as_list(rule.get(key)):
                domains.add((key, value))
        prefixes.extend(_as_list(rule.get("ip_cidr")))

    for rule in rules:
        if not isinstance(rule, dict):
            raise BuildError(f"unexpected rule entry: {rule!r}")
        walk(rule)
    return domains, prefixes


def _has_logical(payload: dict) -> bool:
    rules = payload.get("rules")
    if not isinstance(rules, list):
        return False

    def walk(rule: dict) -> bool:
        if rule.get("type") == "logical":
            return True
        nested = rule.get("rules")
        if isinstance(nested, list):
            return any(isinstance(child, dict) and walk(child) for child in nested)
        return False

    return any(isinstance(rule, dict) and walk(rule) for rule in rules)


def _rule_structure(rule: dict) -> tuple:
    if rule.get("type") == "logical":
        nested = rule.get("rules")
        if not isinstance(nested, list):
            raise BuildError(f"logical rule without 'rules': {rule!r}")
        return (
            "logical",
            str(rule.get("mode", "")),
            bool(rule.get("invert", False)),
            tuple(_rule_structure(child) for child in nested),
        )
    fields = []
    for key, value in sorted(rule.items()):
        if key in ("type", "invert"):
            continue
        if isinstance(value, list):
            fields.append((key, tuple(sorted(str(item) for item in value))))
        elif isinstance(value, (str, int, bool)):
            fields.append((key, value))
    return ("default", bool(rule.get("invert", False)), tuple(fields))


def _payload_structure(payload: dict) -> tuple:
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise BuildError("rule-set JSON has no 'rules' list")
    return tuple(_rule_structure(rule) for rule in rules)


def verify(source_json: Path, binary: Path, box: SingBox) -> None:
    """Fail the build unless the compiled file is equivalent to the source."""
    source = load_rule_set(source_json)
    compiled = box.decompile(binary)

    source_domains, source_prefixes = flatten(source)
    compiled_domains, compiled_prefixes = flatten(compiled)

    if source_domains != compiled_domains:
        missing = sorted(source_domains - compiled_domains)[:5]
        extra = sorted(compiled_domains - source_domains)[:5]
        raise BuildError(
            f"{source_json.name}: domain round-trip mismatch "
            f"(missing={missing}, extra={extra})"
        )

    if canonical(source_prefixes) != canonical(compiled_prefixes):
        raise BuildError(f"{source_json.name}: ip_cidr round-trip mismatch")

    if _has_logical(source) or _has_logical(compiled):
        if _payload_structure(source) != _payload_structure(compiled):
            raise BuildError(f"{source_json.name}: logical rule round-trip mismatch")
        # Sample matching is intentionally skipped for logical rules: a sample
        # can be inside the inverted exception set and legitimately not match.
        return

    samples: list[str] = []
    for key, value in sorted(source_domains):
        if key == "domain_suffix":
            samples.append(f"probe.{value}")
        elif key in ("domain", "domain_keyword"):
            samples.append(value)
        # domain_regex is a pattern, not a domain: the round-trip comparison
        # above already proves it survived compilation unchanged.
        if len(samples) >= 2:
            break
    for prefix in source_prefixes[:2]:
        samples.append(prefix.split("/")[0])
    for sample in samples:
        if not box.matches(binary, sample):
            raise BuildError(
                f"{source_json.name}: compiled rule-set does not match {sample!r}"
            )
