import pytest
from pydantic import ValidationError

from gvstress.web import domain as web_domain


def build_node(
    *, node_id: str, role: web_domain.NodeRole, url: str
) -> web_domain.NodeEndpoint:
    return web_domain.NodeEndpoint(
        id=node_id,
        url=url,
        role=role,
        health_status=web_domain.NodeHealthStatus.OK,
        created_at="2026-05-20T10:00:00Z",
        last_seen_at="2026-05-20T10:05:00Z",
    )


def test_valid_single_node_topology_loads() -> None:
    sender = build_node(
        node_id="node-a",
        role=web_domain.NodeRole.STANDALONE,
        url="http://node-a.local",
    )

    topology = web_domain.TestTopology(
        mode=web_domain.TopologyMode.SINGLE_NODE,
        sender=sender,
        receiver=None,
    )

    assert topology.mode is web_domain.TopologyMode.SINGLE_NODE
    assert topology.receiver is None


def test_valid_two_node_topology_loads() -> None:
    topology = web_domain.TestTopology(
        mode=web_domain.TopologyMode.TWO_NODE,
        sender=build_node(
            node_id="sender-1",
            role=web_domain.NodeRole.SENDER,
            url="http://sender.local",
        ),
        receiver=build_node(
            node_id="receiver-1",
            role=web_domain.NodeRole.RECEIVER,
            url="http://receiver.local",
        ),
    )

    assert topology.mode is web_domain.TopologyMode.TWO_NODE
    assert topology.sender.id == "sender-1"
    assert topology.receiver is not None
    assert topology.receiver.id == "receiver-1"


def test_invalid_two_node_topology_with_same_ids_raises() -> None:
    with pytest.raises(ValidationError, match="sender.id must differ from receiver.id"):
        _ = web_domain.TestTopology(
            mode=web_domain.TopologyMode.TWO_NODE,
            sender=build_node(
                node_id="shared-node",
                role=web_domain.NodeRole.SENDER,
                url="http://sender.local",
            ),
            receiver=build_node(
                node_id="shared-node",
                role=web_domain.NodeRole.RECEIVER,
                url="http://receiver.local",
            ),
        )


def test_valid_job_state_transition() -> None:
    job = web_domain.TestJob.model_validate(
        {
            "id": "job-001",
            "state": "running",
            "topology": {
                "mode": "single_node",
                "sender": {
                    "id": "node-a",
                    "url": "http://node-a.local",
                    "role": "standalone",
                    "health_status": "ok",
                    "created_at": "2026-05-20T10:00:00Z",
                    "last_seen_at": "2026-05-20T10:05:00Z",
                },
                "receiver": None,
            },
            "pktgen_interfaces": ["iface-a"],
            "created_at": "2026-05-20T10:00:00Z",
            "started_at": "2026-05-20T10:01:00Z",
            "completed_at": None,
            "error_message": None,
        },
        context={"previous_state": web_domain.TestJobState.PENDING},
    )

    assert job.state is web_domain.TestJobState.RUNNING


def test_invalid_job_state_transition_raises() -> None:
    with pytest.raises(ValidationError, match="invalid job state transition"):
        _ = web_domain.TestJob.model_validate(
            {
                "id": "job-002",
                "state": "completed",
                "topology": {
                    "mode": "single_node",
                    "sender": {
                        "id": "node-a",
                        "url": "http://node-a.local",
                        "role": "standalone",
                        "health_status": "ok",
                        "created_at": "2026-05-20T10:00:00Z",
                        "last_seen_at": "2026-05-20T10:05:00Z",
                    },
                    "receiver": None,
                },
                "pktgen_interfaces": ["iface-a"],
                "created_at": "2026-05-20T10:00:00Z",
                "started_at": "2026-05-20T10:01:00Z",
                "completed_at": "2026-05-20T10:02:00Z",
                "error_message": None,
            },
            context={"previous_state": web_domain.TestJobState.PENDING},
        )
