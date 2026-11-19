"""Internet connectivity check.

The Wi-Fi tool measures the *link* between this PC and the router (signal
strength and link rate). That says nothing about the connection beyond the
router, so a PC can show a 200 Mbps Wi-Fi link while the internet delivers
6 Mbps. This tool measures what the Wi-Fi tool cannot: how the connection
actually behaves end to end.

It makes a few tiny plain-HTTP requests for Microsoft's own connectivity-
check file (http://www.msftconnecttest.com/connecttest.txt, 22 bytes), the
same file Windows itself fetches to decide whether you are online, and times
each step:

    dns_ms         resolving the host name
    connect_ms     opening the TCP connection
    first_byte_ms  waiting for the first byte of the reply

Privacy: the only thing sent is an ordinary HTTP GET for that public file,
so the remote side learns what any website would (your public IP address
and a generic User-Agent). Nothing about this machine is read or sent, and
nothing is written or changed locally.

This is a latency and reachability check, not a speed test. It does not
download large files, so it cannot report throughput in Mbps.

Payload shape on success (medians over the successful attempts):

    {
        "host": "www.msftconnecttest.com",
        "attempted": 3,
        "successful": 3,
        "failed_samples": 0,
        "dns_ms": 24.1,
        "connect_ms": 31.5,
        "first_byte_ms": 58.0,
        "response_ok": True,
    }

`response_ok` is False when the reply was not the expected file, which is
what a captive portal (a sign-in page) or an intercepting proxy produces.

If no attempt completes (no internet, DNS down, a firewall or proxy that
blocks direct HTTP), the tool returns an ERROR rather than a result. A
failure to measure is unknown, never evidence that the internet is "slow".
"""

import logging
import socket
import statistics
import threading
import time
from datetime import datetime, timezone

from app.models.tool_result import ToolResult, ToolStatus

logger = logging.getLogger(__name__)

TOOL_NAME = "network"

HOST = "www.msftconnecttest.com"
PORT = 80
PATH = "/connecttest.txt"
EXPECTED_BODY = "Microsoft Connect Test"

SAMPLES = 3
SAMPLE_TIMEOUT_SECONDS = 5.0
# Hard ceiling for the whole tool, so a dead network cannot stall an investigation.
TOTAL_TIMEOUT_SECONDS = 12.0
MAX_RESPONSE_BYTES = 4096

_USER_AGENT = "SherlockAI-connectivity-check/1.0"


def run() -> ToolResult:
    """Collect internet connectivity timings.

    Never raises: failures are returned as an error ToolResult.
    """
    try:
        payload = _collect()

        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.SUCCESS,
            collected_at=datetime.now(timezone.utc),
            payload=payload,
        )

    except Exception as exc:  # noqa: BLE001
        logger.warning("network tool failed to collect data: %s", exc)

        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.ERROR,
            collected_at=datetime.now(timezone.utc),
            payload={"error": str(exc)},
        )


def _collect(
    host: str = HOST,
    port: int = PORT,
    path: str = PATH,
    expected_body: str = EXPECTED_BODY,
    samples: int = SAMPLES,
    sample_timeout: float = SAMPLE_TIMEOUT_SECONDS,
    total_timeout: float = TOTAL_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Run several timed requests and summarize them."""
    deadline = time.monotonic() + total_timeout
    results: list[dict[str, object]] = []
    failures: list[str] = []
    attempted = 0

    for _ in range(samples):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        attempted += 1
        try:
            results.append(
                _measure_once(host, port, path, expected_body, min(sample_timeout, remaining))
            )
        except OSError as exc:
            failures.append(_describe(exc))

    if not results:
        reason = failures[-1] if failures else "no attempt could be made"
        raise RuntimeError(f"Could not complete the internet check: {reason}")

    return {
        "host": host,
        "attempted": attempted,
        "successful": len(results),
        "failed_samples": len(failures),
        "dns_ms": _median(results, "dns_ms"),
        "connect_ms": _median(results, "connect_ms"),
        "first_byte_ms": _median(results, "first_byte_ms"),
        "response_ok": all(bool(item["response_ok"]) for item in results),
    }


def _measure_once(
    host: str, port: int, path: str, expected_body: str, timeout: float
) -> dict[str, object]:
    """One timed request. All stages share a single deadline of `timeout` seconds."""
    deadline = time.monotonic() + timeout

    started = time.perf_counter()
    family, socktype, proto, _, address = _resolve(host, port, deadline)
    dns_ms = _elapsed_ms(started)

    sock = socket.socket(family, socktype, proto)
    try:
        sock.settimeout(_remaining(deadline, "connecting to " + host))
        started = time.perf_counter()
        sock.connect(address)
        connect_ms = _elapsed_ms(started)

        request = (
            f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: {_USER_AGENT}\r\n"
            "Accept: */*\r\nConnection: close\r\n\r\n"
        )
        sock.settimeout(_remaining(deadline, "sending the request"))
        started = time.perf_counter()
        sock.sendall(request.encode("ascii"))

        sock.settimeout(_remaining(deadline, "waiting for a reply"))
        chunk = sock.recv(MAX_RESPONSE_BYTES)
        if not chunk:
            raise ConnectionError("the server closed the connection without replying")
        first_byte_ms = _elapsed_ms(started)

        data = chunk
        while len(data) < MAX_RESPONSE_BYTES:
            try:
                sock.settimeout(_remaining(deadline, "reading the reply"))
                more = sock.recv(MAX_RESPONSE_BYTES - len(data))
            except TimeoutError:
                break  # the first byte arrived; a slow tail does not invalidate the sample
            if not more:
                break
            data += more
    finally:
        sock.close()

    return {
        "dns_ms": dns_ms,
        "connect_ms": connect_ms,
        "first_byte_ms": first_byte_ms,
        "response_ok": _is_expected_reply(data, expected_body),
    }


def _resolve(host: str, port: int, deadline: float):
    """Resolve `host`, giving up at `deadline`.

    `getaddrinfo` has no timeout parameter and can block for many seconds
    when DNS is down, so it runs in a daemon thread that is abandoned on
    timeout.
    """
    outcome: dict[str, object] = {}

    def lookup() -> None:
        try:
            outcome["infos"] = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            outcome["error"] = exc

    thread = threading.Thread(target=lookup, daemon=True)
    thread.start()
    thread.join(_remaining(deadline, f"looking up {host}"))

    if thread.is_alive():
        raise TimeoutError(f"DNS lookup for {host} timed out")
    if "error" in outcome:
        raise outcome["error"]  # type: ignore[misc]
    infos = outcome.get("infos")
    if not infos:
        raise OSError(f"DNS returned no addresses for {host}")
    return infos[0]  # type: ignore[index]


def _is_expected_reply(data: bytes, expected_body: str) -> bool:
    head, _, body = data.partition(b"\r\n\r\n")
    status_line = head.split(b"\r\n", 1)[0].decode("latin-1", errors="replace")
    parts = status_line.split()
    if len(parts) < 2 or parts[1] != "200":
        return False  # a redirect or error page, e.g. a captive portal
    return expected_body in body.decode("utf-8", errors="replace")


def _remaining(deadline: float, doing: str) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError(f"timed out while {doing}")
    return left


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 1)


def _median(results: list[dict[str, object]], key: str) -> float:
    return round(statistics.median(float(item[key]) for item in results), 1)  # type: ignore[arg-type]


def _describe(exc: OSError) -> str:
    if isinstance(exc, socket.gaierror):
        return f"the host name could not be resolved ({exc.strerror or exc})"
    if isinstance(exc, TimeoutError):
        return str(exc) or "the request timed out"
    if isinstance(exc, ConnectionRefusedError):
        return "the connection was refused"
    return str(exc) or exc.__class__.__name__
