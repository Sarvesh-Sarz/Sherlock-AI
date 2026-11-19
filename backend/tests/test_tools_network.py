"""The network tool, run for real against a scripted local server.

The server speaks just enough HTTP to behave like a healthy host, a slow
one, a captive portal, a flaky connection, or one that accepts and then
goes silent. No test here touches the internet.
"""

import socket
import socketserver
import threading
import time

import pytest

from app.models.tool_result import ToolStatus
from app.tools import network

OK = b"HTTP/1.1 200 OK\r\nContent-Length: 22\r\nConnection: close\r\n\r\nMicrosoft Connect Test"
PORTAL = b"HTTP/1.1 302 Found\r\nLocation: http://login.example/\r\nConnection: close\r\n\r\n"
FAKE_PAGE = b"HTTP/1.1 200 OK\r\nContent-Length: 18\r\nConnection: close\r\n\r\n<html>Sign in</html>"


class Script:
    """Per-request behaviour. Each entry: ("reply", bytes, delay_s), ("drop",) or ("hang", seconds)."""

    def __init__(self, *steps):
        self.steps = list(steps)
        self.count = 0
        self.lock = threading.Lock()

    def next(self):
        with self.lock:
            step = self.steps[min(self.count, len(self.steps) - 1)]
            self.count += 1
            return step


@pytest.fixture
def serve():
    servers = []

    def start(*steps):
        script = Script(*steps)

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.recv(2048)
                step = script.next()
                if step[0] == "reply":
                    time.sleep(step[2] if len(step) > 2 else 0)
                    self.request.sendall(step[1])
                elif step[0] == "hang":
                    time.sleep(step[1])
                # "drop": close without replying

        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
        servers.append(server)
        return server.server_address[1], script

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def collect(port, **kwargs):
    return network._collect(host="127.0.0.1", port=port, **kwargs)


# ---- A healthy connection ---------------------------------------------------

def test_healthy_host_reports_timings_and_an_expected_response(serve):
    port, script = serve(("reply", OK))
    payload = collect(port)

    assert script.count == 3
    assert payload["attempted"] == 3 and payload["successful"] == 3 and payload["failed_samples"] == 0
    assert payload["response_ok"] is True
    for key in ("dns_ms", "connect_ms", "first_byte_ms"):
        assert isinstance(payload[key], float) and payload[key] >= 0


def test_a_slow_host_shows_up_in_first_byte_time(serve):
    port, _ = serve(("reply", OK, 0.3))
    assert collect(port, samples=2)["first_byte_ms"] >= 250


# ---- The network is not what it claims to be -------------------------------------

@pytest.mark.parametrize("reply", [PORTAL, FAKE_PAGE])
def test_captive_portal_or_intercepting_proxy_is_flagged(serve, reply):
    port, _ = serve(("reply", reply))
    payload = collect(port, samples=1)

    assert payload["response_ok"] is False  # reachable, but not the real page


def test_one_bad_reply_among_good_ones_makes_the_whole_check_not_ok(serve):
    port, _ = serve(("reply", OK), ("reply", PORTAL), ("reply", OK))
    assert collect(port)["response_ok"] is False


# ---- Flaky and failing connections ------------------------------------------------

def test_intermittent_failures_are_counted_not_hidden(serve):
    port, _ = serve(("reply", OK), ("drop",), ("reply", OK))
    payload = collect(port)

    assert payload["attempted"] == 3
    assert payload["successful"] == 2
    assert payload["failed_samples"] == 1


def test_every_attempt_failing_is_an_error_not_a_slow_reading(serve):
    port, _ = serve(("drop",))
    with pytest.raises(RuntimeError, match="closed the connection without replying"):
        collect(port)


def test_connection_refused_is_reported_plainly():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]  # nothing listens here once the socket closes
    with pytest.raises(RuntimeError, match="connection was refused"):
        collect(closed_port, samples=1)


def test_a_server_that_goes_silent_is_cut_off_by_the_timeout(serve):
    port, _ = serve(("hang", 5))
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="timed out"):
        collect(port, samples=1, sample_timeout=0.4)
    assert time.monotonic() - started < 2


def test_total_timeout_bounds_the_whole_check(serve):
    port, _ = serve(("hang", 5))
    started = time.monotonic()
    with pytest.raises(RuntimeError):
        collect(port, samples=3, sample_timeout=5, total_timeout=0.6)
    assert time.monotonic() - started < 3


# ---- DNS ---------------------------------------------------------------------------

def test_dns_failure_is_reported_as_unresolvable(monkeypatch):
    def fail(*args, **kwargs):
        raise socket.gaierror(11001, "getaddrinfo failed")

    monkeypatch.setattr(network.socket, "getaddrinfo", fail)
    with pytest.raises(RuntimeError, match="could not be resolved"):
        network._collect(samples=1)


def test_a_hung_dns_lookup_is_abandoned_at_the_deadline(monkeypatch):
    monkeypatch.setattr(network.socket, "getaddrinfo", lambda *a, **k: time.sleep(3))
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="DNS lookup .* timed out"):
        network._collect(samples=1, sample_timeout=0.3)
    assert time.monotonic() - started < 2


# ---- run() contract ------------------------------------------------------------------

def test_run_never_raises_and_returns_an_error_result(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("no route to host")

    monkeypatch.setattr(network, "_measure_once", boom)
    result = network.run()

    assert result.tool_name == "network"
    assert result.status == ToolStatus.ERROR
    assert "no route to host" in result.payload["error"]


def test_run_success_wraps_the_payload(monkeypatch):
    monkeypatch.setattr(network, "_collect", lambda: {"dns_ms": 1.0})
    result = network.run()

    assert result.status == ToolStatus.SUCCESS
    assert result.payload == {"dns_ms": 1.0}


def test_it_targets_the_public_connectivity_check_file_over_plain_http():
    # Documented in the module: this is the file Windows itself fetches.
    assert network.HOST == "www.msftconnecttest.com"
    assert network.PORT == 80 and network.PATH == "/connecttest.txt"


def test_network_is_registered_and_runs_through_the_tool_manager(monkeypatch, serve):
    from datetime import datetime, timezone

    from app.models.investigation_plan import InvestigationPlan
    from app.tools.tool_manager import ToolManager

    port, _ = serve(("reply", OK))
    monkeypatch.setattr(network, "HOST", "127.0.0.1")
    monkeypatch.setattr(network, "PORT", port)
    # `_collect` binds its defaults at definition time, so aim it explicitly.
    real_collect = network._collect
    monkeypatch.setattr(network, "_collect", lambda: real_collect(host="127.0.0.1", port=port, samples=1))

    plan = InvestigationPlan(
        problem_description="my internet is slow",
        tools_to_execute=["network"],
        matched_keywords=["internet"],
        created_at=datetime.now(timezone.utc),
    )
    # The registry holds a reference to `network.run`, which calls the patched `_collect`.
    (result,) = ToolManager().execute(plan)

    assert result.tool_name == "network"
    assert result.status == ToolStatus.SUCCESS
    assert result.payload["response_ok"] is True


def test_an_error_status_is_not_ok_even_if_the_body_looks_right(serve):
    body = b"Microsoft Connect Test"
    port, _ = serve(("reply", b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\n\r\n" + body))
    assert collect(port, samples=1)["response_ok"] is False
