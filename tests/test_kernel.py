import unittest

from agencyos.assurance import Evidence, build_trust_record, content_hash, verify_checks
from agencyos.control import (
    Authority,
    Capability,
    ControlDenied,
    PolicyEngine,
    Request,
)


class KernelTest(unittest.TestCase):
    def test_policy_never_grants_authority_from_request(self):
        engine = PolicyEngine({
            "publish": Capability(
                "publish", side_effect=True, risk="medium",
                requires_approval=True, idempotent=True,
            )
        })
        authority = Authority("agent-1", allowed=frozenset({"publish"}))
        request = Request("agent-1", "publish", "client-1")
        self.assertEqual(engine.evaluate(request, authority)["decision"], "approval_required")
        self.assertEqual(
            engine.evaluate(request, authority, approved=True)["decision"], "allow"
        )

    def test_denied_and_budget_are_deterministic(self):
        engine = PolicyEngine({"billing": Capability("billing", side_effect=True, risk="high")})
        denied = Authority("agent-1", allowed=frozenset(), denied=frozenset({"billing"}))
        with self.assertRaises(ControlDenied):
            engine.evaluate(Request("agent-1", "billing", "client-1"), denied)
        allowed = Authority("agent-1", allowed=frozenset({"billing"}))
        with self.assertRaises(ControlDenied):
            engine.evaluate(
                Request("agent-1", "billing", "client-1", estimated_cost_minor=101),
                allowed,
                max_cost_minor=100,
            )

    def test_evidence_hash_is_stable_and_verification_is_explicit(self):
        value = {"b": 2, "a": 1}
        self.assertEqual(content_hash(value), content_hash({"a": 1, "b": 2}))
        passed = verify_checks({"campaign_exists": True, "budget_matches": True})
        failed = verify_checks({"campaign_exists": True, "budget_matches": False})
        self.assertTrue(passed.passed)
        self.assertFalse(failed.passed)

        record = build_trust_record(
            intent="publish_campaign",
            execution_id="exec-1",
            agent_id="agent-1",
            policy_version="v1",
            evidence=[Evidence("research", "search", {"answer": "x"}, "strong")],
            verification=passed,
            result={"external_id": "cmp-1"},
        )
        self.assertEqual(record["verification"]["status"], "passed")
        self.assertTrue(record["evidence"][0]["fingerprint"].startswith("sha256:"))
        self.assertTrue(record["result_hash"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
