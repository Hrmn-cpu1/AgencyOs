"""Extension boundaries. Implementations are registered explicitly by the orchestrator."""
from dataclasses import dataclass
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class Context:
    actor_id: str
    run_id: str
    input: Mapping[str, Any]


@dataclass(frozen=True)
class Result:
    output: Mapping[str, Any]
    evidence: Mapping[str, Any]


class Tool(Protocol):
    name: str
    def execute(self, context: Context) -> Result: ...


class Skill(Protocol):
    name: str
    def perform(self, context: Context, tools: Mapping[str, Tool]) -> Result: ...


class Worker(Protocol):
    name: str
    def run(self, context: Context, skills: Mapping[str, Skill], tools: Mapping[str, Tool]) -> Result: ...


class Connector(Protocol):
    name: str
    def capabilities(self) -> Mapping[str, bool]: ...
    def ingest(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...
