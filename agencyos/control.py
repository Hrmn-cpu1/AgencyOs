"""Deterministic control-plane primitives: capabilities, policy gates and scoped authority.

LLMs may request actions, but this module is the non-LLM boundary that decides
whether a requested capability is allowed in the current context.
"""
from dataclasses import dataclass
from typing import Any, Mapping


class ControlDenied(Exception):
    """Raised when policy does not authorize a capability request."""


@dataclass(frozen=True)
class Capability:
    name: str
    side_effect: bool = False
    risk: str = "low"
    requires_approval: bool = False
    idempotent: bool = True
    verification_required: bool = True
    reversible: bool = True


@dataclass(frozen=True)
class Authority:
    agent_id: str
    allowed: frozenset[str] = frozenset()
    approval_required: frozenset[str] = frozenset()
    denied: frozenset[str] = frozenset()

    def decide(self, capability: Capability, approved: bool = False) -> str:
        if capability.name in self.denied or capability.name not in self.allowed:
            return "deny"
        if capability.name in self.approval_required or capability.requires_approval:
            return "allow" if approved else "approval_required"
        return "allow"


@dataclass(frozen=True)
class Request:
    agent_id: str
    capability: str
    scope: str
    estimated_cost_minor: int = 0


class PolicyEngine:
    """Small deterministic policy engine; deliberately independent of an LLM."""

    def __init__(self, capabilities: Mapping[str, Capability]):
        self.capabilities = dict(capabilities)

    def evaluate(
        self,
        request: Request,
        authority: Authority,
        *,
        approved: bool = False,
        max_cost_minor: int | None = None,
    ) -> dict[str, Any]:
        capability = self.capabilities.get(request.capability)
        if not capability:
            raise ControlDenied("capability not registered")
        if request.estimated_cost_minor < 0:
            raise ControlDenied("negative estimated cost")
        if max_cost_minor is not None and request.estimated_cost_minor > max_cost_minor:
            raise ControlDenied("cost limit exceeded")

        decision = authority.decide(capability, approved=approved)
        if decision == "deny":
            raise ControlDenied("capability not authorized")
        return {
            "decision": decision,
            "agent_id": request.agent_id,
            "capability": capability.name,
            "scope": request.scope,
            "risk": capability.risk,
            "side_effect": capability.side_effect,
            "verification_required": capability.verification_required,
        }
