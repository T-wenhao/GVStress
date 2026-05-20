from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import cast

from pydantic import ValidationInfo, model_validator
from pydantic_core import PydanticCustomError

from gvstress.config.models import StrictModel


class NodeRole(str, Enum):
    STANDALONE = "standalone"
    SENDER = "sender"
    RECEIVER = "receiver"


class NodeHealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class NodeEndpoint(StrictModel):
    id: str
    url: str
    role: NodeRole
    health_status: NodeHealthStatus
    created_at: str
    last_seen_at: str


class TopologyMode(str, Enum):
    SINGLE_NODE = "single_node"
    TWO_NODE = "two_node"


class TestTopology(StrictModel):
    mode: TopologyMode
    sender: NodeEndpoint
    receiver: NodeEndpoint | None

    @model_validator(mode="after")
    def validate_mode_constraints(self) -> TestTopology:
        if self.mode is TopologyMode.SINGLE_NODE:
            if self.receiver is not None and self.receiver != self.sender:
                raise PydanticCustomError(
                    "web.invalid_topology",
                    "receiver must be omitted or equal to sender in single_node mode",
                )
            return self

        if self.receiver is None:
            raise PydanticCustomError(
                "web.invalid_topology",
                "receiver is required in two_node mode",
            )
        if self.sender.id == self.receiver.id:
            raise PydanticCustomError(
                "web.invalid_topology",
                "sender.id must differ from receiver.id in two_node mode",
            )
        return self


class TestJobState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"


class TestJob(StrictModel):
    id: str
    state: TestJobState
    topology: TestTopology
    pktgen_interfaces: list[str]
    created_at: str
    started_at: str | None
    completed_at: str | None
    error_message: str | None

    @model_validator(mode="after")
    def validate_state_transition(self, info: ValidationInfo) -> TestJob:
        raw_previous_state = self._previous_state_from_context(info)
        if raw_previous_state is None:
            return self

        previous_state = self._coerce_previous_state(raw_previous_state)
        if previous_state is self.state:
            return self

        allowed_transitions = {
            TestJobState.PENDING: {TestJobState.RUNNING, TestJobState.FAILED},
            TestJobState.RUNNING: {TestJobState.STOPPING},
            TestJobState.STOPPING: {TestJobState.COMPLETED, TestJobState.FAILED},
        }
        valid_next_states = allowed_transitions.get(previous_state, set())
        if self.state not in valid_next_states:
            raise PydanticCustomError(
                "web.invalid_job_transition",
                "invalid job state transition from '{from_state}' to '{to_state}'",
                {
                    "from_state": previous_state.value,
                    "to_state": self.state.value,
                },
            )
        return self

    @staticmethod
    def _previous_state_from_context(info: ValidationInfo) -> object | None:
        if not isinstance(info.context, Mapping):
            return None
        context = cast(Mapping[str, object], info.context)
        return context.get("previous_state")

    @staticmethod
    def _coerce_previous_state(value: object) -> TestJobState:
        if isinstance(value, TestJobState):
            return value
        try:
            return TestJobState(value)
        except ValueError as exc:
            raise PydanticCustomError(
                "web.invalid_previous_job_state",
                "invalid previous_state '{previous_state}'",
                {"previous_state": value},
            ) from exc


class DeploymentMode(str, Enum):
    NATIVE = "native"
    COMPOSE = "compose"
    HYBRID = "hybrid"
