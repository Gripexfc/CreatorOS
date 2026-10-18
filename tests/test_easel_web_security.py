"""Regression tests for the local-only write guard used by model settings."""

import io
import json
import urllib.error

from fastapi.testclient import TestClient

from creatoros.api.easel_bridge import _module as upstream


def test_loopback_origin_allows_vite_fallback_port():
    assert upstream._loopback_origin("http://127.0.0.1:5175") is True
    assert upstream._loopback_origin("http://localhost:5174") is True
    assert upstream._loopback_origin("http://[::1]:4173") is True


def test_loopback_origin_rejects_external_origin():
    assert upstream._loopback_origin("https://example.com") is False
    assert upstream._loopback_origin("http://192.168.1.12:5175") is False
    assert upstream._loopback_origin("not-an-origin") is False


def test_model_write_from_vite_fallback_origin_is_not_blocked(monkeypatch, tmp_path):
    monkeypatch.setattr(upstream, "_read_env", lambda: {})
    monkeypatch.setattr(upstream, "PROJECT_ROOT", tmp_path)
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/api/settings/models/selftest",
            json={"channel": "chat"},
            headers={"Origin": "http://127.0.0.1:5175"},
        )
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_model_write_from_external_origin_is_blocked(monkeypatch, tmp_path):
    monkeypatch.setattr(upstream, "_read_env", lambda: {})
    monkeypatch.setattr(upstream, "PROJECT_ROOT", tmp_path)
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/api/settings/models/selftest",
            json={"channel": "chat"},
            headers={"Origin": "https://example.com"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "仅允许从本机工作台操作。"


def test_media_selftest_is_an_honest_preflight_not_a_chat_probe(monkeypatch):
    monkeypatch.setattr(upstream, "_model_channels", lambda: {
        "channels": {
            "image": {"rows": [{"slot": "openai", "baseUrl": "https://img.example/v1", "result": "已配置"}]},
            "video": {"rows": []},
        },
        "primary": "",
    })
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.post("/api/settings/models/selftest", json={"channel": "image"},
                               headers={"Origin": "http://127.0.0.1:5173"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["channel"] == "image"
    assert payload["results"][0]["ok"] is True
    assert "真实生图/生视频" not in payload["results"][0]["detail"]


def test_image_save_requires_its_own_model_and_endpoint(monkeypatch, tmp_path):
    monkeypatch.setattr(upstream, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(upstream, "_read_env", lambda: {})
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/api/settings/models/save",
            json={"channel": "image", "rows": [{"slot": "openai", "key": "test-key"}]},
            headers={"Origin": "http://127.0.0.1:5173"},
        )
    assert response.status_code == 400
    assert "生图必须填写图片模型 ID" in response.json()["detail"]


def test_model_status_restores_last_selftest_without_credentials(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    model_file = runtime / "openclaw" / "model-selftest.json"
    model_file.parent.mkdir(parents=True)
    monkeypatch.setattr(upstream, "PROJECT_ROOT", runtime)
    monkeypatch.setattr(upstream, "MODEL_SELFTEST_FILE", model_file)
    monkeypatch.setattr(upstream, "_read_env", lambda: {"OPENAI_API_KEY": "server-only-key"})
    fingerprint = upstream._chat_model_config_fingerprint()
    model_file.write_text(json.dumps({
        "testedAt": 1234567890,
        "configFingerprint": fingerprint,
        "results": [{
            "baseUrl": "https://api.example.com/v1",
            "ok": True,
            "ms": 42,
            "detail": "ok",
            "apiKey": "must-not-be-returned",
        }],
    }))
    monkeypatch.setattr(upstream, "check_gateway", lambda: True)
    monkeypatch.setattr(upstream, "gateway_base_url", lambda _profile: "http://127.0.0.1:1234")
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.get("/api/settings/models/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["lastSelftest"] == {
        "testedAt": 1234567890,
        "results": [{"baseUrl": "https://api.example.com/v1", "ok": True, "ms": 42, "detail": "ok"}],
    }
    assert "server-only-key" not in response.text
    assert "must-not-be-returned" not in response.text


def test_model_status_recognizes_custom_openclaw_provider(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    config_path = runtime / "openclaw" / "openclaw.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps({
        "agents": {"defaults": {"model": {"primary": "custom/MiniMax"}}},
        "models": {"providers": {
            "custom": {"baseUrl": "https://api.example.com/v1", "apiKey": "secret", "models": [{"id": "MiniMax"}]},
        }},
    }))
    monkeypatch.setattr(upstream, "PROJECT_ROOT", runtime)
    monkeypatch.setattr(upstream, "MODEL_SELFTEST_FILE", runtime / "openclaw" / "model-selftest.json")
    monkeypatch.setattr(upstream, "_read_env", lambda: {})
    monkeypatch.setattr(upstream, "check_gateway", lambda: True)
    monkeypatch.setattr(upstream, "gateway_base_url", lambda _profile: "http://127.0.0.1:1234")
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.get("/api/settings/models/status")
    assert response.status_code == 200
    assert response.json()["configured"] is True


def test_model_start_reports_missing_config_without_spawning(monkeypatch, tmp_path):
    monkeypatch.setattr(upstream, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(upstream, "gateway_base_url", lambda _profile: "http://127.0.0.1:1234")
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/api/settings/models/start",
            json={},
            headers={"Origin": "http://127.0.0.1:5173"},
        )
    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "started": False,
        "gatewayOnline": False,
        "gatewayUrl": "http://127.0.0.1:1234",
        "note": "尚未保存模型配置，请先到模型设置保存并测试。",
    }


def test_model_selftest_persistence_strips_credentials(monkeypatch, tmp_path):
    model_file = tmp_path / "openclaw" / "model-selftest.json"
    monkeypatch.setattr(upstream, "MODEL_SELFTEST_FILE", model_file)
    monkeypatch.setattr(upstream, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(upstream, "_read_env", lambda: {})
    upstream._write_model_selftest([{
        "baseUrl": "https://api.example.com/v1",
        "ok": True,
        "ms": 7,
        "detail": "ok",
        "key": "must-not-be-written",
    }], tested_at=123, config_fingerprint="test-fingerprint")
    raw = model_file.read_text()
    assert "must-not-be-written" not in raw
    assert json.loads(raw) == {
        "testedAt": 123,
        "configFingerprint": "test-fingerprint",
        "results": [{"baseUrl": "https://api.example.com/v1", "ok": True, "ms": 7, "detail": "ok"}],
    }


def test_model_status_ignores_corrupted_snapshot(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    model_file = runtime / "openclaw" / "model-selftest.json"
    model_file.parent.mkdir(parents=True)
    model_file.write_text("[]")
    monkeypatch.setattr(upstream, "PROJECT_ROOT", runtime)
    monkeypatch.setattr(upstream, "MODEL_SELFTEST_FILE", model_file)
    monkeypatch.setattr(upstream, "_read_env", lambda: {})
    monkeypatch.setattr(upstream, "check_gateway", lambda: False)
    monkeypatch.setattr(upstream, "gateway_base_url", lambda _profile: "http://127.0.0.1:1234")
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.get("/api/settings/models/status")
    assert response.status_code == 200
    assert response.json()["lastSelftest"] is None


def test_model_status_ignores_snapshot_after_chat_config_changes(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    model_file = runtime / "openclaw" / "model-selftest.json"
    model_file.parent.mkdir(parents=True)
    env_state = {"OPENAI_API_KEY": "first-server-key"}
    monkeypatch.setattr(upstream, "PROJECT_ROOT", runtime)
    monkeypatch.setattr(upstream, "MODEL_SELFTEST_FILE", model_file)
    monkeypatch.setattr(upstream, "_read_env", lambda: env_state)
    old_fingerprint = upstream._chat_model_config_fingerprint()
    model_file.write_text(json.dumps({
        "testedAt": 123,
        "configFingerprint": old_fingerprint,
        "results": [{"baseUrl": "https://api.example.com/v1", "ok": True, "ms": 1}],
    }))
    env_state["OPENAI_API_KEY"] = "second-server-key"
    assert upstream._read_model_selftest() is None


def test_clear_model_selftest_ignores_delete_failure(monkeypatch):
    class UnlinkFailure:
        def unlink(self, *, missing_ok=False):
            raise OSError("read-only runtime")

    monkeypatch.setattr(upstream, "MODEL_SELFTEST_FILE", UnlinkFailure())
    upstream._clear_model_selftest()


def test_model_save_failure_does_not_clear_existing_probe(monkeypatch, tmp_path):
    clear_calls = []
    monkeypatch.setattr(upstream, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(upstream, "_read_env", lambda: {})
    monkeypatch.setattr(upstream, "_openclaw_provider_creds", lambda: {})
    monkeypatch.setattr(upstream, "_write_env_direct", lambda _updates: None)
    monkeypatch.setattr(upstream, "_sync_openclaw_chat",
                        lambda *_args: "模型信息已保存，但本地创作服务初始化失败；请重试保存并测试。")
    monkeypatch.setattr(upstream, "_model_channels", lambda: {"channels": {"chat": {"rows": []}}, "primary": ""})
    monkeypatch.setattr(upstream, "_clear_model_selftest", lambda: clear_calls.append(True))
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/api/settings/models/save",
            json={"channel": "chat", "rows": [{
                "slot": "openai", "model": "test-model", "baseUrl": "https://api.example.com/v1",
                "key": "test-key", "primary": True,
            }]},
            headers={"Origin": "http://127.0.0.1:5173"},
        )
    assert response.status_code == 200
    assert clear_calls == []


def test_model_save_merges_custom_provider_instead_of_pruning_other_rows(monkeypatch, tmp_path):
    config_dir = tmp_path / "openclaw"
    config_dir.mkdir()
    config_path = config_dir / "openclaw.json"
    config_path.write_text(json.dumps({
        "models": {"providers": {
            "alpha": {"baseUrl": "https://alpha.example/v1", "apiKey": "alpha-key", "models": [{"id": "alpha-model"}]},
        }},
        "agents": {"defaults": {"model": {"primary": "alpha/alpha-model"}}},
    }))
    monkeypatch.setattr(upstream, "PROJECT_ROOT", tmp_path)
    note = upstream._sync_openclaw_chat(
        {"beta": {"base": "https://beta.example/v1", "key": "beta-key", "model": "beta-model"}},
        {"beta"},
        "beta/beta-model",
    )
    assert "失败" not in note
    saved = json.loads(config_path.read_text())
    assert set(saved["models"]["providers"]) == {"alpha", "beta"}
    assert saved["agents"]["defaults"]["model"]["primary"] == "beta/beta-model"


def test_model_save_bootstraps_config_when_openclaw_cli_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(upstream, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(upstream, "openclaw_base_cmd", lambda: (_ for _ in ()).throw(FileNotFoundError()))
    note = upstream._sync_openclaw_chat(
        {"minimax": {"base": "https://api.example.com/v1", "key": "test-key", "model": "MiniMax-M3.1-Flash"}},
        {"minimax"},
        "minimax/MiniMax-M3.1-Flash",
    )
    assert "未找到 OpenClaw CLI" in note
    saved = json.loads((tmp_path / "openclaw" / "openclaw.json").read_text())
    provider = saved["models"]["providers"]["minimax"]
    assert provider["baseUrl"] == "https://api.example.com/v1"
    assert provider["apiKey"] == "test-key"
    assert provider["models"][0]["id"] == "MiniMax-M3.1-Flash"


def test_model_selftest_uses_generation_probe_and_classifies_billing(monkeypatch):
    class BillingOpener:
        def open(self, request, timeout):
            assert request.full_url == "https://api.deepseek.com/chat/completions"
            payload = json.loads(request.data.decode("utf-8"))
            assert payload["model"] == "deepseek-v4-pro"
            assert payload["max_tokens"] == 1
            raise urllib.error.HTTPError(
                request.full_url, 402, "billing", {}, io.BytesIO(b"provider detail"))

    monkeypatch.setattr(upstream, "_read_env", lambda: {
        "OPENAI_BASE_URL": "https://api.deepseek.com",
        "OPENAI_API_KEY": "test-key",
        "OPENAI_MODEL": "deepseek-v4-pro",
    })
    monkeypatch.setattr(upstream, "_ssrf_safe", lambda _url: True)
    monkeypatch.setattr(upstream.urllib.request, "build_opener", lambda _handler: BillingOpener())
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.post("/api/settings/models/selftest", json={"channel": "chat"},
                               headers={"Origin": "http://127.0.0.1:5173"})
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["ok"] is False
    assert result["detail"] == "模型账户余额或额度不足"


def test_model_selftest_classifies_aliyun_arrearage_body(monkeypatch):
    class ArrearageOpener:
        def open(self, request, timeout):
            raise urllib.error.HTTPError(
                request.full_url, 400, "bad request", {},
                io.BytesIO(b'{"code":"Arrearage","message":"Access denied, account overdue-payment"}'))

    monkeypatch.setattr(upstream, "_read_env", lambda: {
        "OPENAI_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "OPENAI_API_KEY": "test-key",
        "OPENAI_MODEL": "qwen3.8-flash",
    })
    monkeypatch.setattr(upstream, "_ssrf_safe", lambda _url: True)
    monkeypatch.setattr(upstream.urllib.request, "build_opener", lambda _handler: ArrearageOpener())
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.post("/api/settings/models/selftest", json={"channel": "chat"},
                               headers={"Origin": "http://127.0.0.1:5173"})
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["ok"] is False
    assert result["detail"] == "模型账户欠费或账户状态异常，请到服务商控制台处理欠费并开启可用额度"


def test_model_selftest_includes_selected_custom_primary_provider(monkeypatch, tmp_path):
    class SuccessResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class SuccessOpener:
        def open(self, request, timeout):
            assert request.full_url == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
            payload = json.loads(request.data.decode("utf-8"))
            assert payload["model"] == "qwen3.8-flash"
            assert request.headers["Authorization"] == "Bearer custom-test-key"
            return SuccessResponse()

    config_dir = tmp_path / "openclaw"
    config_dir.mkdir()
    (config_dir / "openclaw.json").write_text(json.dumps({
        "agents": {"defaults": {"model": {"primary": "aliyun/qwen3.8-flash"}}},
        "models": {"providers": {"aliyun": {
            "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "apiKey": "custom-test-key",
            "models": [{"id": "qwen3.8-flash", "api": "openai-completions"}],
        }}},
    }))
    monkeypatch.setattr(upstream, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(upstream, "_read_env", lambda: {})
    monkeypatch.setattr(upstream, "_ssrf_safe", lambda _url: True)
    monkeypatch.setattr(upstream.urllib.request, "build_opener", lambda _handler: SuccessOpener())
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.post("/api/settings/models/selftest", json={"channel": "chat"},
                               headers={"Origin": "http://127.0.0.1:5173"})
    assert response.status_code == 200
    assert response.json()["results"] == [{
        "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "ok": True,
        "ms": response.json()["results"][0]["ms"],
    }]


class _DiscoveryResponse:
    status = 200

    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, *_args):
        return self.payload


def test_model_discovery_fetches_and_deduplicates_remote_models(monkeypatch):
    requests = []

    class DiscoveryOpener:
        def open(self, request, timeout):
            requests.append((request, timeout))
            return _DiscoveryResponse(json.dumps({
                "data": [
                    {"id": "model-b"},
                    {"id": "model-a"},
                    {"id": "model-b"},
                    {"object": "model"},
                ],
            }).encode())

    monkeypatch.setattr(upstream, "_saved_model_discovery_target",
                        lambda _slot, _name: ("https://api.example.com/v1", "secret-model-key"))
    monkeypatch.setattr(upstream, "_ssrf_safe", lambda _url: True)
    monkeypatch.setattr(upstream.urllib.request, "build_opener", lambda *_args, **_kwargs: DiscoveryOpener())
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/api/settings/models/discover",
            json={"slot": "custom", "name": "snode", "baseUrl": "https://api.example.com/v1"},
            headers={"Origin": "http://127.0.0.1:5173"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["models"] == ["model-b", "model-a"]
    assert response.json()["source"] == "remote"
    assert "secret-model-key" not in response.text
    assert len(requests) == 1
    request, timeout = requests[0]
    assert request.full_url == "https://api.example.com/v1/models"
    assert request.headers["Authorization"] == "Bearer secret-model-key"
    assert timeout == 15


def test_model_discovery_blocks_private_target_before_request(monkeypatch):
    attempted = []

    class ShouldNotOpen:
        def open(self, *_args, **_kwargs):
            attempted.append(True)
            raise AssertionError("private model target must not be requested")

    monkeypatch.setattr(upstream, "_saved_model_discovery_target",
                        lambda _slot, _name: ("http://169.254.169.254/latest", "secret-model-key"))
    monkeypatch.setattr(upstream, "_ssrf_safe", lambda _url: False)
    monkeypatch.setattr(upstream.urllib.request, "build_opener", lambda *_args, **_kwargs: ShouldNotOpen())
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/api/settings/models/discover",
            json={"slot": "custom", "name": "snode", "baseUrl": "http://169.254.169.254/latest"},
            headers={"Origin": "http://127.0.0.1:5173"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["models"] == []
    assert body["available"] is False
    assert body["source"] == "none"
    assert "secret-model-key" not in response.text
    assert not attempted


def test_model_discovery_returns_non_secret_failure_for_provider_error(monkeypatch):
    class FailingOpener:
        def open(self, request, timeout):
            raise urllib.error.HTTPError(
                request.full_url, 401, "unauthorized", {}, io.BytesIO(b"secret-model-key"))

    monkeypatch.setattr(upstream, "_saved_model_discovery_target",
                        lambda _slot, _name: ("https://api.example.com/v1", "secret-model-key"))
    monkeypatch.setattr(upstream, "_ssrf_safe", lambda _url: True)
    monkeypatch.setattr(upstream.urllib.request, "build_opener", lambda *_args, **_kwargs: FailingOpener())
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/api/settings/models/discover",
            json={"slot": "custom", "name": "snode", "baseUrl": "https://api.example.com/v1"},
            headers={"Origin": "http://127.0.0.1:5173"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["models"] == []
    assert body["available"] is False
    assert body["source"] == "none"
    assert "HTTP 401" in body["detail"]
    assert "secret-model-key" not in response.text


def test_model_discovery_does_not_send_stored_key_to_different_endpoint(monkeypatch):
    attempted = []

    class ShouldNotOpen:
        def open(self, *_args, **_kwargs):
            attempted.append(True)
            raise AssertionError("a draft endpoint must not receive the stored provider key")

    monkeypatch.setattr(upstream, "_saved_model_discovery_target",
                        lambda _slot, _name: ("https://saved.example.com/v1", "secret-model-key"))
    monkeypatch.setattr(upstream.urllib.request, "build_opener", lambda *_args, **_kwargs: ShouldNotOpen())
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/api/settings/models/discover",
            json={"slot": "custom", "name": "snode", "baseUrl": "https://other.example.com/v1"},
            headers={"Origin": "http://127.0.0.1:5173"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["models"] == []
    assert body["available"] is False
    assert body["source"] == "none"
    assert "当前服务地址对应的 API Key" in body["detail"]
    assert "secret-model-key" not in response.text
    assert not attempted


def test_model_discovery_uses_draft_key_for_new_endpoint_without_persisting_it(monkeypatch):
    requests = []

    class DiscoveryOpener:
        def open(self, request, timeout):
            requests.append(request)
            return _DiscoveryResponse(json.dumps({"models": [{"id": "draft-model"}]}).encode())

    monkeypatch.setattr(upstream, "_saved_model_discovery_target",
                        lambda _slot, _name: ("https://saved.example.com/v1", "stored-key"))
    monkeypatch.setattr(upstream, "_ssrf_safe", lambda _url: True)
    monkeypatch.setattr(upstream.urllib.request, "build_opener", lambda *_args, **_kwargs: DiscoveryOpener())
    with TestClient(upstream.app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/api/settings/models/discover",
            json={
                "slot": "custom",
                "name": "snode",
                "baseUrl": "https://draft.example.com/v1",
                "key": "draft-key",
            },
            headers={"Origin": "http://127.0.0.1:5173"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["models"] == ["draft-model"]
    assert requests[0].full_url == "https://draft.example.com/v1/models"
    assert requests[0].headers["Authorization"] == "Bearer draft-key"
    assert "draft-key" not in response.text
