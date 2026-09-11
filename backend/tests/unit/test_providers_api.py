#!/usr/bin/env python3
"""Unit tests for AI Provider CRUD API endpoints.

Tests cover:
- list_providers empty and with data
- create_provider validation (name, URL, max_turns) and duplicate-name 409
- delete_provider 404 when missing and 409 when last provider
- set_default_provider 404 when missing
"""

import os
import sys
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies.auth import require_admin_user, require_authenticated_user
from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    id=1,
    name="test-provider",
    base_url="http://localhost:11434/v1",
    api_key=None,
    model="claude-sonnet-4-20250514",
    max_turns=20,
    system_prompt=None,
    is_default=False,
    is_disabled=False,
):
    """Build a mock AIProvider ORM object."""
    from app.models import AIProvider

    p = AIProvider(
        name=name,
        base_url=base_url,
        api_key=api_key,
        model=model,
        max_turns=max_turns,
        system_prompt=system_prompt,
        is_default=is_default,
        is_disabled=is_disabled,
    )
    p.id = id
    p.created_at = datetime(2026, 1, 1)
    p.updated_at = datetime(2026, 1, 1)
    return p


# ---------------------------------------------------------------------------
# List providers
# ---------------------------------------------------------------------------


class ProviderListTests(unittest.TestCase):
    """Tests for GET /api/providers."""

    def setUp(self):
        self._original_key = os.environ.get("CONFIG_ENCRYPTION_KEY")
        os.environ["CONFIG_ENCRYPTION_KEY"] = "unit-test-config-key"

        self.mock_db = MagicMock()
        self.mock_db.execute = AsyncMock()
        self.mock_db.get = AsyncMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.flush = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.refresh = AsyncMock()
        self.mock_db.delete = AsyncMock()

        app.dependency_overrides[get_db] = lambda: self.mock_db
        app.dependency_overrides[require_authenticated_user] = lambda: MagicMock()
        app.dependency_overrides[require_admin_user] = lambda: MagicMock()

        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        if self._original_key is None:
            os.environ.pop("CONFIG_ENCRYPTION_KEY", None)
        else:
            os.environ["CONFIG_ENCRYPTION_KEY"] = self._original_key

    def test_list_providers_empty(self):
        """GET /api/providers with no providers returns 200 and an empty list."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        self.mock_db.execute = AsyncMock(return_value=mock_result)

        response = self.client.get("/api/providers")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_list_providers_returns_serialized(self):
        """GET /api/providers returns serialized provider with api_key_configured flag."""
        provider = _make_provider(
            id=5,
            name="my-llm",
            base_url="https://api.openai.com/v1",
            api_key="enc:secret-key",
            model="gpt-4o",
            max_turns=30,
            system_prompt="You are helpful.",
            is_default=True,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [provider]
        self.mock_db.execute = AsyncMock(return_value=mock_result)

        response = self.client.get("/api/providers")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)

        item = data[0]
        self.assertEqual(item["id"], 5)
        self.assertEqual(item["name"], "my-llm")
        self.assertEqual(item["base_url"], "https://api.openai.com/v1")
        self.assertTrue(item["api_key_configured"])
        self.assertEqual(item["model"], "gpt-4o")
        self.assertEqual(item["max_turns"], 30)
        self.assertEqual(item["system_prompt"], "You are helpful.")
        self.assertTrue(item["is_default"])
        self.assertFalse(item["is_disabled"])
        self.assertEqual(item["created_at"], "2026-01-01T00:00:00")
        self.assertEqual(item["updated_at"], "2026-01-01T00:00:00")

        # Raw api_key must NEVER leak into the response
        self.assertNotIn("api_key", item)


# ---------------------------------------------------------------------------
# Create provider — validation
# ---------------------------------------------------------------------------


class ProviderCreateTests(unittest.TestCase):
    """Tests for POST /api/providers validation."""

    def setUp(self):
        self._original_key = os.environ.get("CONFIG_ENCRYPTION_KEY")
        os.environ["CONFIG_ENCRYPTION_KEY"] = "unit-test-config-key"

        self.mock_db = MagicMock()
        self.mock_db.execute = AsyncMock()
        self.mock_db.get = AsyncMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.flush = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.refresh = AsyncMock()
        self.mock_db.delete = AsyncMock()

        app.dependency_overrides[get_db] = lambda: self.mock_db
        app.dependency_overrides[require_authenticated_user] = lambda: MagicMock()
        app.dependency_overrides[require_admin_user] = lambda: MagicMock()

        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        if self._original_key is None:
            os.environ.pop("CONFIG_ENCRYPTION_KEY", None)
        else:
            os.environ["CONFIG_ENCRYPTION_KEY"] = self._original_key

    def test_create_provider_invalid_name(self):
        """POST /api/providers with spaces in name returns 422."""
        payload = {
            "name": "has spaces",
            "base_url": "http://localhost:11434/v1",
            "model": "claude-sonnet-4-20250514",
        }
        response = self.client.post("/api/providers", json=payload)

        self.assertEqual(response.status_code, 422)

    def test_create_provider_invalid_base_url(self):
        """POST /api/providers with ftp:// URL returns 422."""
        payload = {
            "name": "my-provider",
            "base_url": "ftp://files.example.com",
            "model": "claude-sonnet-4-20250514",
        }
        response = self.client.post("/api/providers", json=payload)

        self.assertEqual(response.status_code, 422)

    def test_create_provider_max_turns_out_of_range(self):
        """POST /api/providers with max_turns=0 returns 422."""
        payload = {
            "name": "my-provider",
            "base_url": "http://localhost:11434/v1",
            "model": "claude-sonnet-4-20250514",
            "max_turns": 0,
        }
        response = self.client.post("/api/providers", json=payload)

        self.assertEqual(response.status_code, 422)

    def test_create_provider_duplicate_name_409(self):
        """POST /api/providers with an existing name returns 409."""
        existing = _make_provider(id=1, name="duplicate-name")

        # First execute() call: check for existing provider by name -> found
        name_check_result = MagicMock()
        name_check_result.scalar_one_or_none.return_value = existing
        self.mock_db.execute = AsyncMock(return_value=name_check_result)

        payload = {
            "name": "duplicate-name",
            "base_url": "http://localhost:11434/v1",
            "model": "claude-sonnet-4-20250514",
        }
        response = self.client.post("/api/providers", json=payload)

        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json()["detail"])

    def test_create_first_provider_disabled_409(self):
        """The first provider would become default, so it cannot be created disabled."""
        name_check_result = MagicMock()
        name_check_result.scalar_one_or_none.return_value = None
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        self.mock_db.execute = AsyncMock(side_effect=[name_check_result, count_result])

        response = self.client.post(
            "/api/providers",
            json={
                "name": "first-provider",
                "base_url": "http://localhost:11434/v1",
                "model": "claude-sonnet-4-20250514",
                "is_disabled": True,
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("Default provider cannot be disabled", response.json()["detail"])


# ---------------------------------------------------------------------------
# Update provider
# ---------------------------------------------------------------------------


class ProviderUpdateTests(unittest.TestCase):
    """Tests for PATCH /api/providers/{id}."""

    def setUp(self):
        self._original_key = os.environ.get("CONFIG_ENCRYPTION_KEY")
        os.environ["CONFIG_ENCRYPTION_KEY"] = "unit-test-config-key"

        self.mock_db = MagicMock()
        self.mock_db.execute = AsyncMock()
        self.mock_db.get = AsyncMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.flush = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.refresh = AsyncMock()
        self.mock_db.delete = AsyncMock()

        app.dependency_overrides[get_db] = lambda: self.mock_db
        app.dependency_overrides[require_authenticated_user] = lambda: MagicMock()
        app.dependency_overrides[require_admin_user] = lambda: MagicMock()

        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        if self._original_key is None:
            os.environ.pop("CONFIG_ENCRYPTION_KEY", None)
        else:
            os.environ["CONFIG_ENCRYPTION_KEY"] = self._original_key

    def test_update_default_provider_disabled_409(self):
        """PATCH /api/providers/{id} rejects disabling the current default provider."""
        provider = _make_provider(id=1, is_default=True, is_disabled=False)
        self.mock_db.get = AsyncMock(return_value=provider)

        response = self.client.patch("/api/providers/1", json={"is_disabled": True})

        self.assertEqual(response.status_code, 409)
        self.assertIn("Default provider cannot be disabled", response.json()["detail"])

    def test_update_protocol_validates_against_existing_provider_kind(self):
        """A protocol-only PATCH cannot cross the provider-kind boundary."""
        provider = _make_provider(id=1)
        provider.provider_kind = "anthropic_compatible"
        provider.model_protocol = "anthropic_messages"
        self.mock_db.get = AsyncMock(return_value=provider)

        response = self.client.patch(
            "/api/providers/1", json={"model_protocol": "openai_responses"}
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("cannot consume model_protocol", response.json()["detail"])
        self.mock_db.commit.assert_not_awaited()
        self.assertEqual(provider.model_protocol, "anthropic_messages")

    def test_update_kind_validates_against_existing_protocol(self):
        """A kind-only PATCH cannot cross the provider-kind boundary."""
        provider = _make_provider(id=1)
        provider.provider_kind = "openai_compatible"
        provider.model_protocol = "openai_responses"
        self.mock_db.get = AsyncMock(return_value=provider)

        response = self.client.patch(
            "/api/providers/1", json={"provider_kind": "anthropic_compatible"}
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("cannot consume model_protocol", response.json()["detail"])
        self.mock_db.commit.assert_not_awaited()
        self.assertEqual(provider.provider_kind, "openai_compatible")

    def test_update_protocol_accepts_valid_pair_against_existing_kind(self):
        """A protocol-only PATCH can switch between OpenAI-compatible protocols."""
        provider = _make_provider(id=1)
        provider.provider_kind = "openai_compatible"
        provider.model_protocol = "openai_responses"
        self.mock_db.get = AsyncMock(return_value=provider)

        response = self.client.patch(
            "/api/providers/1", json={"model_protocol": "openai_chat_completions"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["model_protocol"], "openai_chat_completions")
        self.mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# Delete provider
# ---------------------------------------------------------------------------


class ProviderDeleteTests(unittest.TestCase):
    """Tests for DELETE /api/providers/{id}."""

    def setUp(self):
        self._original_key = os.environ.get("CONFIG_ENCRYPTION_KEY")
        os.environ["CONFIG_ENCRYPTION_KEY"] = "unit-test-config-key"

        self.mock_db = MagicMock()
        self.mock_db.execute = AsyncMock()
        self.mock_db.get = AsyncMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.flush = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.refresh = AsyncMock()
        self.mock_db.delete = AsyncMock()

        app.dependency_overrides[get_db] = lambda: self.mock_db
        app.dependency_overrides[require_authenticated_user] = lambda: MagicMock()
        app.dependency_overrides[require_admin_user] = lambda: MagicMock()

        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        if self._original_key is None:
            os.environ.pop("CONFIG_ENCRYPTION_KEY", None)
        else:
            os.environ["CONFIG_ENCRYPTION_KEY"] = self._original_key

    def test_delete_nonexistent_404(self):
        """DELETE /api/providers/{id} returns 404 when provider does not exist."""
        self.mock_db.get = AsyncMock(return_value=None)

        response = self.client.delete("/api/providers/9999")

        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_delete_last_provider_409(self):
        """DELETE /api/providers/{id} returns 409 when it is the only provider."""
        provider = _make_provider(id=1, is_default=True)
        self.mock_db.get = AsyncMock(return_value=provider)

        # execute() is called for count query -> returns 1
        count_result = MagicMock()
        count_result.scalar.return_value = 1
        self.mock_db.execute = AsyncMock(return_value=count_result)

        response = self.client.delete("/api/providers/1")

        self.assertEqual(response.status_code, 409)
        self.assertIn("only provider", response.json()["detail"].lower())

    def test_delete_default_provider_without_enabled_replacement_409(self):
        """Deleting the default provider must not promote a disabled replacement."""
        provider = _make_provider(id=1, is_default=True)
        self.mock_db.get = AsyncMock(return_value=provider)

        total_result = MagicMock()
        total_result.scalar.return_value = 2
        active_count_result = MagicMock()
        active_count_result.scalar.return_value = 0
        replacement_result = MagicMock()
        replacement_result.scalar_one_or_none.return_value = None
        self.mock_db.execute = AsyncMock(
            side_effect=[total_result, active_count_result, replacement_result]
        )

        response = self.client.delete("/api/providers/1")

        self.assertEqual(response.status_code, 409)
        self.assertIn("no enabled provider remains", response.json()["detail"])


# ---------------------------------------------------------------------------
# Set default provider
# ---------------------------------------------------------------------------


class ProviderSetDefaultTests(unittest.TestCase):
    """Tests for POST /api/providers/{id}/set-default."""

    def setUp(self):
        self._original_key = os.environ.get("CONFIG_ENCRYPTION_KEY")
        os.environ["CONFIG_ENCRYPTION_KEY"] = "unit-test-config-key"

        self.mock_db = MagicMock()
        self.mock_db.execute = AsyncMock()
        self.mock_db.get = AsyncMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.flush = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.refresh = AsyncMock()
        self.mock_db.delete = AsyncMock()

        app.dependency_overrides[get_db] = lambda: self.mock_db
        app.dependency_overrides[require_authenticated_user] = lambda: MagicMock()
        app.dependency_overrides[require_admin_user] = lambda: MagicMock()

        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        if self._original_key is None:
            os.environ.pop("CONFIG_ENCRYPTION_KEY", None)
        else:
            os.environ["CONFIG_ENCRYPTION_KEY"] = self._original_key

    def test_set_default_nonexistent_404(self):
        """POST /api/providers/{id}/set-default returns 404 for missing provider."""
        self.mock_db.get = AsyncMock(return_value=None)

        response = self.client.post("/api/providers/9999/set-default")

        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_set_default_disabled_provider_409(self):
        """POST /api/providers/{id}/set-default rejects disabled providers."""
        provider = _make_provider(id=2, is_default=False, is_disabled=True)
        self.mock_db.get = AsyncMock(return_value=provider)

        response = self.client.post("/api/providers/2/set-default")

        self.assertEqual(response.status_code, 409)
        self.assertIn("Disabled provider cannot be set as default", response.json()["detail"])


class ProviderConnectionTestTests(unittest.TestCase):
    """Tests for POST /api/providers/{id}/test-connection."""

    def setUp(self):
        self._original_key = os.environ.get("CONFIG_ENCRYPTION_KEY")
        os.environ["CONFIG_ENCRYPTION_KEY"] = "unit-test-config-key"

        self.mock_db = MagicMock()
        self.mock_db.get = AsyncMock()

        app.dependency_overrides[get_db] = lambda: self.mock_db
        app.dependency_overrides[require_authenticated_user] = lambda: MagicMock()
        app.dependency_overrides[require_admin_user] = lambda: MagicMock()

        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        if self._original_key is None:
            os.environ.pop("CONFIG_ENCRYPTION_KEY", None)
        else:
            os.environ["CONFIG_ENCRYPTION_KEY"] = self._original_key

    def test_anthropic_connection_uses_messages_endpoint(self):
        provider = _make_provider(
            id=1,
            base_url="https://api.example/v1",
            api_key="test-key",
            model="claude-test",
        )
        provider.model_protocol = "anthropic_messages"
        self.mock_db.get.return_value = provider

        upstream = MagicMock(status_code=200)
        http_client = MagicMock()
        http_client.__aenter__ = AsyncMock(return_value=http_client)
        http_client.__aexit__ = AsyncMock(return_value=None)
        http_client.post = AsyncMock(return_value=upstream)

        with patch("app.api.providers.httpx.AsyncClient", return_value=http_client):
            response = self.client.post("/api/providers/1/test-connection")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status_code"], 200)
        request = http_client.post.await_args
        self.assertEqual(request.args[0], "https://api.example/v1/messages")
        self.assertEqual(request.kwargs["headers"]["x-api-key"], "test-key")
        self.assertEqual(request.kwargs["json"]["model"], "claude-test")

    def test_openai_connection_uses_responses_endpoint(self):
        provider = _make_provider(
            id=2,
            base_url="https://api.example",
            api_key="test-key",
            model="gpt-test",
        )
        provider.provider_kind = "openai_compatible"
        provider.model_protocol = "openai_responses"
        self.mock_db.get.return_value = provider

        upstream = MagicMock(status_code=200)
        http_client = MagicMock()
        http_client.__aenter__ = AsyncMock(return_value=http_client)
        http_client.__aexit__ = AsyncMock(return_value=None)
        http_client.post = AsyncMock(return_value=upstream)

        with patch("app.api.providers.httpx.AsyncClient", return_value=http_client):
            response = self.client.post("/api/providers/2/test-connection")

        self.assertEqual(response.status_code, 200)
        request = http_client.post.await_args
        self.assertEqual(request.args[0], "https://api.example/v1/responses")
        self.assertEqual(request.kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(request.kwargs["json"]["max_output_tokens"], 1)

    def test_custom_ca_keeps_public_ca_trust_for_connection_test(self):
        from app.api.providers import _provider_connection_verify

        context = MagicMock()
        with (
            patch("app.api.providers.get_ssl_verify", return_value="/custom-ca.pem"),
            patch("app.api.providers.certifi.where", return_value="/public-ca.pem"),
            patch("app.api.providers.ssl.create_default_context", return_value=context) as create,
        ):
            self.assertIs(_provider_connection_verify(), context)

        create.assert_called_once_with(cafile="/public-ca.pem")
        context.load_verify_locations.assert_called_once_with(cafile="/custom-ca.pem")

    def test_opencode_connection_adds_routing_session_header(self):
        provider = _make_provider(
            id=4,
            base_url="https://opencode.ai/zen/go",
            api_key="test-key",
            model="minimax-m2.7",
        )
        self.mock_db.get.return_value = provider

        upstream = MagicMock(status_code=200)
        http_client = MagicMock()
        http_client.__aenter__ = AsyncMock(return_value=http_client)
        http_client.__aexit__ = AsyncMock(return_value=None)
        http_client.post = AsyncMock(return_value=upstream)

        with patch("app.api.providers.httpx.AsyncClient", return_value=http_client):
            response = self.client.post("/api/providers/4/test-connection")

        self.assertEqual(response.status_code, 200)
        headers = http_client.post.await_args.kwargs["headers"]
        self.assertRegex(headers["x-opencode-session"], r"^codify-connection-test-[0-9a-f]{32}$")

    def test_upstream_error_does_not_return_response_body(self):
        provider = _make_provider(id=3, api_key="test-key")
        self.mock_db.get.return_value = provider

        upstream = MagicMock(status_code=401, text='{"secret":"should-not-leak"}')
        http_client = MagicMock()
        http_client.__aenter__ = AsyncMock(return_value=http_client)
        http_client.__aexit__ = AsyncMock(return_value=None)
        http_client.post = AsyncMock(return_value=upstream)

        with patch("app.api.providers.httpx.AsyncClient", return_value=http_client):
            response = self.client.post("/api/providers/3/test-connection")

        self.assertEqual(response.status_code, 400)
        self.assertIn("HTTP 401", response.json()["detail"])
        self.assertNotIn("should-not-leak", response.text)




class ProviderAuthScopeTests(unittest.TestCase):
    """Tests that provider routes use the expected auth scopes."""

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_list_providers_uses_authenticated_dependency(self):
        """GET /api/providers should be available to authenticated users."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[require_authenticated_user] = lambda: MagicMock()
        app.dependency_overrides[require_admin_user] = lambda: (_ for _ in ()).throw(Exception("wrong dependency"))

    def test_write_provider_routes_still_use_admin_dependency(self):
        """POST /api/providers should still require admin access."""
        mock_db = MagicMock()

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[require_authenticated_user] = lambda: MagicMock()
        app.dependency_overrides[require_admin_user] = lambda: (_ for _ in ()).throw(Exception("wrong dependency"))

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/providers",
            json={
                "name": "test-provider",
                "base_url": "http://localhost:11434/v1",
                "model": "claude-sonnet-4-20250514",
            },
        )

        self.assertEqual(response.status_code, 500)


# ---------------------------------------------------------------------------
# Phase 2 Task 2.3: Endpoint fields + credential lifecycle
# ---------------------------------------------------------------------------

import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.providers import CreateProviderRequest, UpdateProviderRequest
from app.core.config_crypto import decrypt_config_secret
from app.models import Base, ModelCredential


def _valid_create_kwargs(**overrides):
    kwargs = {
        "name": "endpoint",
        "base_url": "https://api.example.com/v1",
        "model": "model-x",
    }
    kwargs.update(overrides)
    return kwargs


class ProviderEndpointFieldSchemaTests(unittest.TestCase):
    def test_accepts_valid_kind_protocol_pairs(self):
        CreateProviderRequest(
            **_valid_create_kwargs(
                provider_kind="openai_compatible", model_protocol="openai_responses"
            )
        )
        CreateProviderRequest(
            **_valid_create_kwargs(
                provider_kind="openai_compatible",
                model_protocol="openai_chat_completions",
            )
        )
        CreateProviderRequest(
            **_valid_create_kwargs(
                provider_kind="anthropic_compatible",
                model_protocol="anthropic_messages",
            )
        )
    def test_rejects_invalid_kind_protocol_pairs(self):
        for kwargs in (
            {"provider_kind": "openai_compatible", "model_protocol": "anthropic_messages"},
            {"provider_kind": "anthropic_compatible", "model_protocol": "openai_responses"},
            {"provider_kind": "unknown_kind", "model_protocol": "anthropic_messages"},
            {"provider_kind": "anthropic_compatible", "model_protocol": "unknown_protocol"},
        ):
            with pytest.raises(ValidationError):
                CreateProviderRequest(**_valid_create_kwargs(**kwargs))

    def test_update_validates_kind_protocol(self):
        UpdateProviderRequest(model_protocol="openai_responses")
        with pytest.raises(ValidationError):
            UpdateProviderRequest(
                provider_kind="anthropic_compatible", model_protocol="openai_responses"
            )
        with pytest.raises(ValidationError):
            UpdateProviderRequest(
                provider_kind="openai_compatible", model_protocol="anthropic_messages"
            )


class ProviderCredentialLifecycleTests(unittest.TestCase):
    """Provider create/delete drives the independent credential lifecycle."""

    def setUp(self):
        os.environ["CONFIG_ENCRYPTION_KEY"] = "unit-test-key"
        from app.config import get_settings

        get_settings.cache_clear()
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
        )
        asyncio.run(_create_schema(self.engine))
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)
        app.dependency_overrides[require_admin_user] = lambda: MagicMock()
        app.dependency_overrides[require_authenticated_user] = lambda: MagicMock()

    def tearDown(self):
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())

    def _client(self):
        async def override_db():
            async with self.factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        return TestClient(app, raise_server_exceptions=False)

    def test_create_with_key_binds_credential_and_delete_retires_it(self):
        client = self._client()
        resp = client.post(
            "/api/providers",
            json={
                "name": "ds-key",
                "base_url": "https://api.deepseek.com/anthropic",
                "model": "deepseek-v4-flash",
                "api_key": "sk-test-secret",
                "provider_kind": "anthropic_compatible",
                "model_protocol": "anthropic_messages",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        body = resp.json()
        self.assertEqual(body["credential_status"], "active")
        self.assertIsNotNone(body["credential_ref"])

        provider_id = body["id"]
        ref = body["credential_ref"]

        async def _assert_credential_active_and_decryptable():
            async with self.factory() as session:
                from sqlalchemy import select
                credential = (
                    await session.execute(
                        select(ModelCredential).where(ModelCredential.ref == ref)
                    )
                ).scalar_one()
                self.assertEqual(credential.status, "active")
                self.assertEqual(decrypt_config_secret(credential.secret_encrypted), "sk-test-secret")

        asyncio.run(_assert_credential_active_and_decryptable())

        # A second provider so the first is not the "only provider".
        second = client.post(
            "/api/providers",
            json={
                "name": "other",
                "base_url": "https://api.example.com/v1",
                "model": "m",
            },
        )
        self.assertEqual(second.status_code, 201, second.text)

        # Deleting the provider retires the credential, never hard-deletes it.
        del_resp = client.delete(f"/api/providers/{provider_id}")
        self.assertEqual(del_resp.status_code, 204)

        async def _assert_credential_retired():
            async with self.factory() as session:
                from sqlalchemy import select
                credential = (
                    await session.execute(
                        select(ModelCredential).where(ModelCredential.ref == ref)
                    )
                ).scalar_one()
                self.assertEqual(credential.status, "retired")
                self.assertIsNotNone(credential.retired_at)

        asyncio.run(_assert_credential_retired())

    def test_update_rotates_credential_and_retires_old(self):
        client = self._client()
        resp = client.post(
            "/api/providers",
            json={
                "name": "rotating",
                "base_url": "https://api.example.com/v1",
                "model": "m",
                "api_key": "sk-old",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        provider_id = resp.json()["id"]
        old_ref = resp.json()["credential_ref"]

        upd = client.patch(
            f"/api/providers/{provider_id}",
            json={"api_key": "sk-new"},
        )
        self.assertEqual(upd.status_code, 200, upd.text)
        new_ref = upd.json()["credential_ref"]
        self.assertNotEqual(new_ref, old_ref)

        async def _assert_rotation():
            async with self.factory() as session:
                from sqlalchemy import select
                old = (
                    await session.execute(
                        select(ModelCredential).where(ModelCredential.ref == old_ref)
                    )
                ).scalar_one()
                new = (
                    await session.execute(
                        select(ModelCredential).where(ModelCredential.ref == new_ref)
                    )
                ).scalar_one()
                self.assertEqual(old.status, "retired")
                self.assertEqual(new.status, "active")
                self.assertEqual(
                    decrypt_config_secret(new.secret_encrypted), "sk-new"
                )

        asyncio.run(_assert_rotation())


async def _create_schema(engine):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


# ---------------------------------------------------------------------------
# Phase: Provider request options (provider_options)
# ---------------------------------------------------------------------------


class ProviderRequestOptionsSchemaTests(unittest.TestCase):
    """Create/update schemas keep the provider_options contract."""

    def test_create_accepts_arbitrary_request_options(self):
        request = CreateProviderRequest(
            **_valid_create_kwargs(
                provider_options={
                    "temperature": 0.6,
                    "chat_template_kwargs": {
                        "thinking": True,
                        "reasoning_effort": "high",
                    },
                }
            )
        )

        self.assertEqual(
            request.provider_options["chat_template_kwargs"],
            {"thinking": True, "reasoning_effort": "high"},
        )

    def test_create_rejects_reserved_request_options(self):
        with self.assertRaises(ValidationError) as error:
            CreateProviderRequest(
                **_valid_create_kwargs(
                    provider_options={"model": "hijack", "stream": False}
                )
            )

        message = str(error.exception)
        self.assertIn("model", message)
        self.assertIn("stream", message)

    def test_update_rejects_reserved_request_options(self):
        with self.assertRaises(ValidationError) as error:
            UpdateProviderRequest(
                provider_kind="anthropic_compatible",
                model_protocol="anthropic_messages",
                provider_options={"tools": []},
            )

        self.assertIn("tools", str(error.exception))


class ProviderRequestOptionsApiTests(unittest.TestCase):
    """Endpoint-level provider_options behavior, including the connection test."""

    def setUp(self):
        self._original_key = os.environ.get("CONFIG_ENCRYPTION_KEY")
        os.environ["CONFIG_ENCRYPTION_KEY"] = "unit-test-config-key"

        self.mock_db = MagicMock()
        self.mock_db.execute = AsyncMock()
        self.mock_db.get = AsyncMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.flush = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.refresh = AsyncMock()
        self.mock_db.delete = AsyncMock()

        app.dependency_overrides[get_db] = lambda: self.mock_db
        app.dependency_overrides[require_authenticated_user] = lambda: MagicMock()
        app.dependency_overrides[require_admin_user] = lambda: MagicMock()

        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        if self._original_key is None:
            os.environ.pop("CONFIG_ENCRYPTION_KEY", None)
        else:
            os.environ["CONFIG_ENCRYPTION_KEY"] = self._original_key

    def test_create_rejects_reserved_request_options(self):
        response = self.client.post(
            "/api/providers",
            json={
                "name": "reserved-options",
                "base_url": "https://api.example.com/v1",
                "model": "model-x",
                "provider_options": {"model": "hijack", "stream": False},
            },
        )

        self.assertEqual(response.status_code, 422)
        detail = str(response.json())
        self.assertIn("model", detail)
        self.assertIn("stream", detail)

    def test_create_accepts_arbitrary_request_options(self):
        name_check = MagicMock()
        name_check.scalar_one_or_none.return_value = None
        count_result = MagicMock()
        count_result.scalar.return_value = 1
        self.mock_db.execute = AsyncMock(side_effect=[name_check, count_result])

        async def fake_refresh(provider):
            provider.created_at = datetime(2026, 1, 1)
            provider.updated_at = datetime(2026, 1, 1)

        self.mock_db.refresh = AsyncMock(side_effect=fake_refresh)

        response = self.client.post(
            "/api/providers",
            json={
                "name": "arbitrary-options",
                "base_url": "https://api.example.com/v1",
                "model": "model-x",
                "provider_options": {
                    "temperature": 0.6,
                    "chat_template_kwargs": {"thinking": True},
                },
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(
            response.json()["provider_options"],
            {"temperature": 0.6, "chat_template_kwargs": {"thinking": True}},
        )

    def test_update_rejects_reserved_request_options(self):
        provider = _make_provider(id=1)
        provider.provider_kind = "anthropic_compatible"
        provider.model_protocol = "anthropic_messages"
        provider.provider_options = {}
        self.mock_db.get = AsyncMock(return_value=provider)

        response = self.client.patch(
            "/api/providers/1",
            json={"provider_options": {"messages": []}},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("messages", response.json()["detail"])

    def test_update_clears_options_with_an_empty_object(self):
        provider = _make_provider(id=1)
        provider.provider_kind = "anthropic_compatible"
        provider.model_protocol = "anthropic_messages"
        provider.provider_options = {"temperature": 0.6}
        self.mock_db.get = AsyncMock(return_value=provider)

        response = self.client.patch("/api/providers/1", json={"provider_options": {}})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(provider.provider_options, {})

    def test_connection_test_sends_merged_provider_options(self):
        provider = _make_provider(
            id=1,
            base_url="https://api.example/v1",
            api_key="test-key",
            model="claude-test",
        )
        provider.model_protocol = "anthropic_messages"
        provider.provider_options = {
            "temperature": 0.6,
            "chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"},
        }
        self.mock_db.get = AsyncMock(return_value=provider)

        upstream = MagicMock(status_code=200)
        http_client = MagicMock()
        http_client.__aenter__ = AsyncMock(return_value=http_client)
        http_client.__aexit__ = AsyncMock(return_value=None)
        http_client.post = AsyncMock(return_value=upstream)

        with patch("app.api.providers.httpx.AsyncClient", return_value=http_client):
            response = self.client.post("/api/providers/1/test-connection")

        self.assertEqual(response.status_code, 200, response.text)
        payload = http_client.post.await_args.kwargs["json"]
        self.assertEqual(payload["temperature"], 0.6)
        self.assertEqual(
            payload["chat_template_kwargs"],
            {"thinking": True, "reasoning_effort": "high"},
        )
        self.assertEqual(payload["model"], "claude-test")
        self.assertEqual(payload["messages"], [{"role": "user", "content": "ping"}])

    def test_connection_test_rejects_legacy_reserved_options(self):
        provider = _make_provider(id=1, api_key="test-key")
        provider.model_protocol = "anthropic_messages"
        provider.provider_options = {"stream": False}
        self.mock_db.get = AsyncMock(return_value=provider)

        with patch("app.api.providers.httpx.AsyncClient") as client_cls:
            response = self.client.post("/api/providers/1/test-connection")

        self.assertEqual(response.status_code, 422)
        self.assertIn("stream", response.json()["detail"])
        client_cls.assert_not_called()
