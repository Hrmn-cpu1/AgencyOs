"""Evidence and verification primitives for the AgencyOS trust chain."""
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Evidence:
    kind: str
    source: str
    data: Mapping[str, Any]
    strength: str = "unknown"

    def fingerprint(self) -> str:
        return content_hash({
            "kind": self.kind,
            "source": self.source,
            "data": self.data,
            "strength": self.strength,
        })


@dataclass(frozen=True)
class Verification:
    status: str
    checks: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.status == "passed"


def verify_checks(checks: Mapping[str, bool]) -> Verification:
    failed = tuple(name for name, ok in checks.items() if not ok)
    return Verification("failed" if failed else "passed", tuple(checks.keys()) if not failed else failed)


def build_trust_record(
    *,
    intent: str,
    execution_id: str,
    agent_id: str,
    policy_version: str,
    evidence: list[Evidence],
    verification: Verification,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "execution_id": execution_id,
        "intent": intent,
        "agent_id": agent_id,
        "authorization": {"policy_version": policy_version},
        "evidence": [
            {"kind": item.kind, "source": item.source, "fingerprint": item.fingerprint()}
            for item in evidence
        ],
        "result_hash": content_hash(result),
        "verification": {
            "status": verification.status,
            "checks": list(verification.checks),
        },
    }
