"""Hunyuan3D local-site image URLs must not reach internal-network hosts."""
import socket
import types

import pytest

from test_hunyuan_import_security import _load_addon


class _Resp:
    def __init__(self, status=200, content=b"img", headers=None):
        self.status_code = status
        self.content = content
        self.headers = headers or {}

    def raise_for_status(self):
        return None


def _server(monkeypatch):
    addon, bpy = _load_addon(monkeypatch)
    bpy.context.scene.blendermcp_hunyuan3d_octree_resolution = 256
    bpy.context.scene.blendermcp_hunyuan3d_num_inference_steps = 5
    bpy.context.scene.blendermcp_hunyuan3d_guidance_scale = 5.0
    bpy.context.scene.blendermcp_hunyuan3d_texture = False
    server = addon.BlenderMCPServer()
    monkeypatch.setattr(server, "_get_hunyuan3d_api_url", lambda: "http://localhost:8081")
    return addon, server


def _resolve(monkeypatch, mapping):
    def fake(host, port, **_kw):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (mapping[host], port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.1"])
def test_internal_image_url_is_not_fetched(monkeypatch, ip):
    addon, server = _server(monkeypatch)
    _resolve(monkeypatch, {"internal.test": ip})
    calls = []
    monkeypatch.setattr(addon.requests, "get", lambda *a, **k: calls.append(a) or _Resp(), raising=False)
    result = server.create_hunyuan_job_local_site(image="http://internal.test/x.png")
    assert "error" in result
    assert calls == []


def test_redirect_to_internal_host_is_blocked(monkeypatch):
    addon, server = _server(monkeypatch)
    _resolve(monkeypatch, {"public.test": "93.184.216.34", "internal.test": "127.0.0.1"})
    urls = []

    def get(url, **_kw):
        urls.append(url)
        return _Resp(302, headers={"Location": "http://internal.test/secret"})

    monkeypatch.setattr(addon.requests, "get", get, raising=False)
    result = server.create_hunyuan_job_local_site(image="http://public.test/x.png")
    assert "error" in result
    assert urls == ["http://public.test/x.png"]


def test_public_image_url_still_downloads(monkeypatch):
    addon, _server_ = _server(monkeypatch)
    _resolve(monkeypatch, {"public.test": "93.184.216.34"})
    monkeypatch.setattr(addon.requests, "get", lambda *a, **k: _Resp(content=b"PNG"), raising=False)
    assert addon._download_public_image("https://public.test/a.png") == b"PNG"
