"""The suite must never reach services on the developer's machine or the internet.

A running Ollama would turn every API test into a model call (a small model
can take over a minute), and the network tool would send real requests. These
fail if the guards in conftest.py are ever removed, which no behavioural test
could detect on a machine where those services happen to be offline.
"""

import httpx
import pytest

from app.reasoning import ollama_reasoner
from app.tools import network


def test_tests_cannot_reach_a_real_ollama():
    with pytest.raises(httpx.ConnectError, match="disabled in tests"):
        ollama_reasoner.httpx.post("http://localhost:11434/api/chat")


def test_tests_cannot_reach_the_real_internet_through_the_network_tool():
    with pytest.raises(OSError, match="disabled in tests"):
        network._measure_once("www.msftconnecttest.com", 80, "/connecttest.txt", "x", 1.0)
