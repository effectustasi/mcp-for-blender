"""A client that half-closes after sending must still get its response.

The addon answers from Blender's main thread (_drain_command_queue), not from
the client's handler thread. _handle_client used to close the socket as soon as
recv() returned b"" (client shutdown(SHUT_WR)), before the queued command had
been answered, so the response went to a dead socket and the client hung.
"""

from __future__ import annotations

import json
import socket

from test_server_threading import _make_server, _pump


def _read_json(sock):
    buf = b""
    while True:
        chunk = sock.recv(8192)
        if not chunk:
            raise AssertionError(f"connection closed before a full reply: {buf!r}")
        buf += chunk
        try:
            return json.loads(buf.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue


def test_response_is_delivered_after_client_half_close():
    server = _make_server()
    server.start()
    try:
        with socket.create_connection(("localhost", server.port), timeout=5) as c:
            c.sendall(json.dumps({"type": "ping", "params": {}}).encode())
            c.shutdown(socket.SHUT_WR)
            _pump(server, deadline=0.5)
            reply = _read_json(c)
        assert reply["result"] == {"echo": "ping"}
    finally:
        server.stop()


def test_half_closed_connection_is_closed_after_the_reply():
    server = _make_server()
    server.start()
    try:
        with socket.create_connection(("localhost", server.port), timeout=5) as c:
            c.sendall(json.dumps({"type": "ping", "params": {}}).encode())
            c.shutdown(socket.SHUT_WR)
            _pump(server, deadline=0.5)
            _read_json(c)
            assert c.recv(8192) == b""  # server closed its end afterwards
        assert not server._clients
    finally:
        server.stop()
