"""Edge case tests for stream_probe.py - targeting 85%+ coverage.

These tests cover error paths, edge cases, and helper functions
not covered by the main core tests.
"""

import threading

import pytest

from gvstress.dut.stream_probe import (
    DiscoveredDevice,
    StreamProbe,
    StreamPropertySnapshot,
    StreamSample,
    StreamTarget,
    _match_score,
    _next_sleep_seconds,
    _OpenedStream,
    _read_optional_aravis_str,
    _read_required_aravis_str,
    _shutdown_aravis,
)


class TestStreamTargetEdgeCases:
    """Tests for StreamTarget edge cases."""

    def test_from_selector_accepts_valid_format(self) -> None:
        """Test valid selector parsing."""
        target = StreamTarget.from_selector("CAM-001@192.168.1.10")
        assert target.serial_number == "CAM-001"
        assert target.ip_address == "192.168.1.10"

    def test_from_selector_rejects_no_separator(self) -> None:
        """Test missing @ separator."""
        with pytest.raises(ValueError, match="SERIAL@IP format"):
            StreamTarget.from_selector("CAM-001192.168.1.10")

    def test_from_selector_rejects_empty_serial(self) -> None:
        """Test empty serial number."""
        with pytest.raises(ValueError, match="SERIAL@IP format"):
            StreamTarget.from_selector("@192.168.1.10")

    def test_from_selector_rejects_empty_ip(self) -> None:
        """Test empty IP address."""
        with pytest.raises(ValueError, match="SERIAL@IP format"):
            StreamTarget.from_selector("CAM-001@")

    def test_from_selector_trims_whitespace(self) -> None:
        """Test whitespace trimming."""
        target = StreamTarget.from_selector("  CAM-001  @  192.168.1.10  ")
        assert target.serial_number == "CAM-001"
        assert target.ip_address == "192.168.1.10"

    def test_label_format(self) -> None:
        """Test label method."""
        target = StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10")
        assert target.label() == "CAM-001@192.168.1.10"


class TestDiscoveredDeviceToDict:
    """Tests for DiscoveredDevice serialization."""

    def test_to_dict_includes_all_fields(self) -> None:
        """Test all fields are present in dict."""
        device = DiscoveredDevice(
            device_id="dev-a",
            serial_number="CAM-001",
            ip_address="192.168.1.10",
            vendor="Aravis",
            model="FakeCam",
            protocol="GigEVision",
        )
        result = device.to_dict()
        assert result["device_id"] == "dev-a"
        assert result["vendor"] == "Aravis"
        assert result["model"] == "FakeCam"


class TestStreamPropertySnapshotToDict:
    """Tests for StreamPropertySnapshot serialization."""

    def test_to_dict_includes_timestamp_and_target(self) -> None:
        """Test timestamp and target fields."""
        snapshot = StreamPropertySnapshot(
            timestamp=100.0,
            serial_number="CAM-001",
            ip_address="192.168.1.10",
            device_id="dev-a",
            packet_resend=True,
            socket_buffer=True,
            socket_buffer_size=1048576,
            frame_retention=200000,
            initial_packet_timeout=1000,
            packet_timeout=2000,
            packet_request_ratio=0.25,
            receiver_priority=0,
            buffer_count=2,
        )
        result = snapshot.to_dict()
        assert result["timestamp"] == 100.0
        assert result["serial_number"] == "CAM-001"
        assert result["ip_address"] == "192.168.1.10"


class TestMatchScore:
    """Tests for _match_score function."""

    def test_perfect_match_serial_and_ip(self) -> None:
        """Test both serial and IP match."""
        target = StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10")
        device = DiscoveredDevice(
            device_id="dev-a",
            serial_number="CAM-001",
            ip_address="192.168.1.10",
            vendor="Aravis",
            model="FakeCam",
            protocol="GigEVision",
        )
        assert _match_score(target, device) == 3

    def test_serial_only_match(self) -> None:
        """Test serial matches but IP differs."""
        target = StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10")
        device = DiscoveredDevice(
            device_id="dev-a",
            serial_number="CAM-001",
            ip_address="192.168.1.11",
            vendor="Aravis",
            model="FakeCam",
            protocol="GigEVision",
        )
        # Serial matches (+2) and IP doesn't match but serial didn't mismatch first
        # IP mismatch check at line 413-417 triggers because IP differs and is not None
        assert _match_score(target, device) == -1

    def test_ip_only_match(self) -> None:
        """Test IP matches but serial differs."""
        target = StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10")
        device = DiscoveredDevice(
            device_id="dev-a",
            serial_number="CAM-002",
            ip_address="192.168.1.10",
            vendor="Aravis",
            model="FakeCam",
            protocol="GigEVision",
        )
        # IP matches (+1) but serial doesn't match (-1) = 0, returns -1
        assert _match_score(target, device) == -1

    def test_serial_mismatch_returns_minus_one(self) -> None:
        """Test serial mismatch always returns -1."""
        target = StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10")
        device = DiscoveredDevice(
            device_id="dev-a",
            serial_number="CAM-002",
            ip_address="192.168.1.10",
            vendor="Aravis",
            model="FakeCam",
            protocol="GigEVision",
        )
        # Serial mismatch returns -1 immediately
        assert _match_score(target, device) == -1

    def test_no_match_returns_minus_one(self) -> None:
        """Test no matches at all."""
        target = StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10")
        device = DiscoveredDevice(
            device_id="dev-a",
            serial_number="CAM-002",
            ip_address="192.168.1.11",
            vendor="Aravis",
            model="FakeCam",
            protocol="GigEVision",
        )
        assert _match_score(target, device) == -1

    def test_device_without_serial_matches_by_ip(self) -> None:
        """Test device with None serial matches by IP only."""
        target = StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10")
        device = DiscoveredDevice(
            device_id="dev-a",
            serial_number=None,
            ip_address="192.168.1.10",
            vendor="Aravis",
            model="FakeCam",
            protocol="GigEVision",
        )
        score = _match_score(target, device)
        assert score == 1  # Only IP match


class TestNextSleepSeconds:
    """Tests for _next_sleep_seconds function."""

    def test_without_deadline_returns_interval(self) -> None:
        """Test without deadline uses only interval."""
        result = _next_sleep_seconds(now=100.0, next_sample_at=101.0, deadline_at=None)
        assert result == 1.0

    def test_with_deadline_returns_minimum(self) -> None:
        """Test with deadline returns minimum of interval and deadline."""
        # Interval says 1.0s, deadline says 0.5s
        result = _next_sleep_seconds(now=100.0, next_sample_at=101.0, deadline_at=100.5)
        assert result == 0.5

    def test_negative_values_clamped_to_zero(self) -> None:
        """Test negative time differences return 0."""
        result = _next_sleep_seconds(now=100.0, next_sample_at=99.0, deadline_at=None)
        assert result == 0.0


class TestReadOptionalAravisStr:
    """Tests for _read_optional_aravis_str helper."""

    def test_returns_value_when_present(self) -> None:
        """Test returns string value."""

        class FakeAravis:
            def get_serial(self, index: int) -> str:
                return "CAM-001"

        result = _read_optional_aravis_str(FakeAravis(), "get_serial", 0)
        assert result == "CAM-001"

    def test_returns_none_when_reader_missing(self) -> None:
        """Test returns None when getter method doesn't exist."""

        class FakeAravis:
            pass

        result = _read_optional_aravis_str(FakeAravis(), "get_serial", 0)
        assert result is None

    def test_returns_none_when_value_none(self) -> None:
        """Test returns None when getter returns None."""

        class FakeAravis:
            def get_serial(self, index: int) -> None:
                return None

        result = _read_optional_aravis_str(FakeAravis(), "get_serial", 0)
        assert result is None

    def test_strips_whitespace_and_returns_none_if_empty(self) -> None:
        """Test whitespace-only values become None."""

        class FakeAravis:
            def get_serial(self, index: int) -> str:
                return "   "

        result = _read_optional_aravis_str(FakeAravis(), "get_serial", 0)
        assert result is None


class TestReadRequiredAravisStr:
    """Tests for _read_required_aravis_str helper."""

    def test_returns_value_when_present(self) -> None:
        """Test returns value when available."""

        class FakeAravis:
            def get_device_id(self, index: int) -> str:
                return "dev-a"

        result = _read_required_aravis_str(FakeAravis(), "get_device_id", 0)
        assert result == "dev-a"

    def test_raises_when_value_none(self) -> None:
        """Test raises RuntimeError when value is None."""

        class FakeAravis:
            def get_device_id(self, index: int) -> None:
                return None

        with pytest.raises(RuntimeError, match="get_device_id"):
            _read_required_aravis_str(FakeAravis(), "get_device_id", 0)


class TestShutdownAravis:
    """Tests for _shutdown_aravis helper."""

    def test_calls_shutdown_when_present(self) -> None:
        """Test calls shutdown method if available."""
        shutdown_called = False

        class FakeAravis:
            def shutdown(self) -> None:
                nonlocal shutdown_called
                shutdown_called = True

        _shutdown_aravis(FakeAravis())
        assert shutdown_called

    def test_ignores_missing_shutdown(self) -> None:
        """Test no error when shutdown method missing."""

        class FakeAravis:
            pass

        # Should not raise
        _shutdown_aravis(FakeAravis())

    def test_ignores_non_callable_shutdown(self) -> None:
        """Test no error when shutdown exists but not callable."""

        class FakeAravis:
            shutdown = None  # type: ignore

        _shutdown_aravis(FakeAravis())


class TestOpenStreamErrorPaths:
    """Tests for _open_stream error paths using fakes."""

    def test_raises_on_camera_creation_failure(self) -> None:
        """Test RuntimeError when Camera.new returns None."""

        class FakeAravisModule:
            Camera = type("Camera", (), {"new": lambda x: None})

        probe = StreamProbe(
            [StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10")],
            type(
                "Config",
                (),
                {
                    "buffer_count": 2,
                    "property_snapshot": lambda: {
                        "packet_resend": True,
                        "socket_buffer": True,
                        "socket_buffer_size": 1048576,
                        "frame_retention": 200000,
                        "initial_packet_timeout": 1000,
                        "packet_timeout": 2000,
                        "packet_request_ratio": 0.25,
                        "receiver_priority": 0,
                        "buffer_count": 2,
                    },
                    "applied_property_values": lambda self: {},
                },
            )(),
        )

        target = StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10")
        device = DiscoveredDevice(
            device_id="dev-a",
            serial_number="CAM-001",
            ip_address="192.168.1.10",
            vendor="Aravis",
            model="FakeCam",
            protocol="GigEVision",
        )

        with pytest.raises(RuntimeError, match="failed to open.camera"):
            probe._open_stream(FakeAravisModule(), target, device)

    def test_raises_on_stream_creation_failure(self) -> None:
        """Test RuntimeError when create_stream returns None."""

        class FakeStream:
            pass

        class FakeCamera:
            def create_stream(self, a, b):
                return None

            def get_payload(self):
                return 512

        class FakeAravisModule:
            Camera = type(
                "Camera",
                (),
                {"new": lambda x: FakeCamera()},
            )

        probe = StreamProbe(
            [StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10")],
            type(
                "Config",
                (),
                {
                    "buffer_count": 2,
                    "property_snapshot": lambda: {
                        "packet_resend": True,
                        "socket_buffer": True,
                        "socket_buffer_size": 1048576,
                        "frame_retention": 200000,
                        "initial_packet_timeout": 1000,
                        "packet_timeout": 2000,
                        "packet_request_ratio": 0.25,
                        "receiver_priority": 0,
                        "buffer_count": 2,
                    },
                    "applied_property_values": lambda self: {},
                },
            )(),
        )

        target = StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10")
        device = DiscoveredDevice(
            device_id="dev-a",
            serial_number="CAM-001",
            ip_address="192.168.1.10",
            vendor="Aravis",
            model="FakeCam",
            protocol="GigEVision",
        )

        with pytest.raises(RuntimeError, match="failed to create.stream"):
            probe._open_stream(FakeAravisModule(), target, device)

    def test_raises_on_invalid_payload(self) -> None:
        """Test RuntimeError when payload <= 0."""

        class FakeStream:
            def set_property(self, name, value):
                pass

        class FakeCamera:
            def create_stream(self, a, b):
                return FakeStream()

            def get_payload(self):
                return 0

        class FakeAravisModule:
            Camera = type(
                "Camera",
                (),
                {"new": lambda x: FakeCamera()},
            )
            Buffer = type(
                "Buffer",
                (),
                {"new_allocate": lambda x: None},
            )

        probe = StreamProbe(
            [StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10")],
            type(
                "Config",
                (),
                {
                    "buffer_count": 2,
                    "property_snapshot": lambda: {
                        "packet_resend": True,
                        "socket_buffer": True,
                        "socket_buffer_size": 1048576,
                        "frame_retention": 200000,
                        "initial_packet_timeout": 1000,
                        "packet_timeout": 2000,
                        "packet_request_ratio": 0.25,
                        "receiver_priority": 0,
                        "buffer_count": 2,
                    },
                    "applied_property_values": lambda self: {},
                },
            )(),
        )

        target = StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10")
        device = DiscoveredDevice(
            device_id="dev-a",
            serial_number="CAM-001",
            ip_address="192.168.1.10",
            vendor="Aravis",
            model="FakeCam",
            protocol="GigEVision",
        )

        with pytest.raises(RuntimeError, match="invalid payload"):
            probe._open_stream(FakeAravisModule(), target, device)


class TestStopStreamsErrorHandling:
    """Tests for _stop_streams error handling."""

    def test_continues_on_stop_acquisition_error(self) -> None:
        """Test _stop_streams ignores stop_acquisition exceptions."""

        class FakeCamera:
            def stop_acquisition(self):
                raise RuntimeError("already stopped")

            def start_acquisition(self):
                pass

        probe = StreamProbe(
            [StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10")],
            type(
                "Config",
                (),
                {
                    "buffer_count": 2,
                    "property_snapshot": lambda: {},
                },
            )(),
        )

        stop_event = threading.Event()
        opened_stream = _OpenedStream(
            target=StreamTarget(serial_number="CAM-001", ip_address="192.168.1.10"),
            device=DiscoveredDevice(
                device_id="dev-a",
                serial_number="CAM-001",
                ip_address="192.168.1.10",
                vendor="Aravis",
                model="FakeCam",
                protocol="GigEVision",
            ),
            camera=FakeCamera(),
            stream=type("Stream", (), {"push_buffer": lambda s, b: None})(),
            property_snapshot=StreamPropertySnapshot(
                timestamp=1.0,
                serial_number="CAM-001",
                ip_address="192.168.1.10",
                device_id="dev-a",
                packet_resend=True,
                socket_buffer=True,
                socket_buffer_size=1048576,
                frame_retention=200000,
                initial_packet_timeout=1000,
                packet_timeout=2000,
                packet_request_ratio=0.25,
                receiver_priority=0,
                buffer_count=2,
            ),
            stop_event=stop_event,
        )

        # Should not raise despite stop_acquisition error
        probe._stop_streams([opened_stream])
