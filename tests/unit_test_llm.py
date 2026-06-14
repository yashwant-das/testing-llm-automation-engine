"""
Unit tests for the src/llm/ layer.

All router tests mock the OpenAI client — no live LLM required.

Coverage:
  ProviderConfig        — from_env, named constructors, field validation
  LLMClientFactory      — create returns OpenAI instance, from_env delegates
  RetryPolicy           — field validation, total_attempts, backoff config
  TimeoutPolicy         — field validation
  ModelCapabilities     — field validation
  ModelRegistry         — register, get, is_vision_capable, all_models, from_env, clear
  LLMRequest            — field validation, defaults
  LLMResponse           — field validation
  LLMRouter             — success, retry, fallback, fallback-failure, lazy client,
                          complete_primary, complete_vision, token logging
  get_default_router    — returns LLMRouter singleton
"""

import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from src.llm import (
    LLMClientFactory,
    LLMRequest,
    LLMResponse,
    LLMRouter,
    ModelCapabilities,
    ModelRegistry,
    ProviderConfig,
    RetryPolicy,
    TimeoutPolicy,
    get_default_router,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completion(
    content: str = "result",
    model: str = "test-model",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
):
    """Build a mock ChatCompletion that mimics the OpenAI SDK response shape."""
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens

    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    completion = MagicMock()
    completion.choices = [choice]
    completion.model = model
    completion.usage = usage
    return completion


def _make_router(
    primary_model: str = "primary-model",
    vision_model: str = "vision-model",
    fallback_config: ProviderConfig | None = None,
    fallback_model: str | None = None,
    retry_policy: RetryPolicy | None = None,
    timeout_policy: TimeoutPolicy | None = None,
) -> LLMRouter:
    """Build an LLMRouter with a dummy ProviderConfig (no network calls at init)."""
    config = ProviderConfig(
        name="test", base_url="http://localhost:9999/v1", api_key="test-key"
    )
    return LLMRouter(
        primary_config=config,
        primary_model=primary_model,
        vision_model=vision_model,
        fallback_config=fallback_config,
        fallback_model=fallback_model,
        retry_policy=retry_policy or RetryPolicy(max_retries=0),
        timeout_policy=timeout_policy or TimeoutPolicy(timeout_seconds=10),
    )


# ---------------------------------------------------------------------------
# ProviderConfig
# ---------------------------------------------------------------------------


class TestProviderConfig(unittest.TestCase):
    def test_custom_config(self):
        cfg = ProviderConfig(
            name="custom", base_url="http://localhost:1234/v1", api_key="key"
        )
        self.assertEqual(cfg.name, "custom")
        self.assertEqual(cfg.base_url, "http://localhost:1234/v1")

    def test_for_lm_studio_defaults(self):
        with patch.dict("os.environ", {}, clear=False):
            cfg = ProviderConfig.for_lm_studio()
        self.assertEqual(cfg.name, "lm_studio")
        self.assertIn("localhost", cfg.base_url)

    def test_for_ollama_defaults(self):
        cfg = ProviderConfig.for_ollama()
        self.assertEqual(cfg.name, "ollama")
        self.assertIn("11434", cfg.base_url)
        self.assertEqual(cfg.api_key, "ollama")

    def test_from_env_lm_studio(self):
        with patch.dict("os.environ", {"LM_STUDIO_URL": "http://custom:1234/v1"}):
            cfg = ProviderConfig.from_env("lm_studio")
        self.assertEqual(cfg.base_url, "http://custom:1234/v1")

    def test_from_env_ollama(self):
        with patch.dict("os.environ", {"OLLAMA_URL": "http://custom:11434/v1"}):
            cfg = ProviderConfig.from_env("ollama")
        self.assertEqual(cfg.base_url, "http://custom:11434/v1")

    def test_from_env_unknown_defaults_to_lm_studio(self):
        cfg = ProviderConfig.from_env("unknown_provider")
        self.assertEqual(cfg.name, "lm_studio")

    def test_missing_name_raises(self):
        with self.assertRaises(ValidationError):
            ProviderConfig(base_url="http://localhost/v1")  # missing name


# ---------------------------------------------------------------------------
# LLMClientFactory
# ---------------------------------------------------------------------------


class TestLLMClientFactory(unittest.TestCase):
    def test_create_returns_openai_client(self):
        from openai import OpenAI

        cfg = ProviderConfig(
            name="test", base_url="http://localhost:9999/v1", api_key="k"
        )
        client = LLMClientFactory.create(cfg)
        self.assertIsInstance(client, OpenAI)

    def test_from_env_returns_openai_client(self):
        from openai import OpenAI

        client = LLMClientFactory.from_env("lm_studio")
        self.assertIsInstance(client, OpenAI)

    def test_create_does_not_call_network(self):
        """Creating a client must not make any network calls."""
        cfg = ProviderConfig(
            name="test", base_url="http://localhost:9999/v1", api_key="k"
        )
        # If OpenAI() made a network call here, it would raise or time out.
        # The test succeeding is the assertion.
        client = LLMClientFactory.create(cfg)
        self.assertIsNotNone(client)


# ---------------------------------------------------------------------------
# RetryPolicy
# ---------------------------------------------------------------------------


class TestRetryPolicy(unittest.TestCase):
    def test_defaults(self):
        p = RetryPolicy()
        self.assertEqual(p.max_retries, 3)
        self.assertAlmostEqual(p.initial_delay_seconds, 1.0)
        self.assertAlmostEqual(p.backoff_multiplier, 2.0)

    def test_total_attempts(self):
        self.assertEqual(RetryPolicy(max_retries=0).total_attempts, 1)
        self.assertEqual(RetryPolicy(max_retries=3).total_attempts, 4)

    def test_zero_retries_valid(self):
        p = RetryPolicy(max_retries=0)
        self.assertEqual(p.max_retries, 0)

    def test_negative_retries_raises(self):
        with self.assertRaises(ValidationError):
            RetryPolicy(max_retries=-1)

    def test_backoff_below_one_raises(self):
        with self.assertRaises(ValidationError):
            RetryPolicy(backoff_multiplier=0.5)

    def test_zero_delay_raises(self):
        with self.assertRaises(ValidationError):
            RetryPolicy(initial_delay_seconds=0)


# ---------------------------------------------------------------------------
# TimeoutPolicy
# ---------------------------------------------------------------------------


class TestTimeoutPolicy(unittest.TestCase):
    def test_default(self):
        p = TimeoutPolicy()
        self.assertEqual(p.timeout_seconds, 60)

    def test_custom(self):
        p = TimeoutPolicy(timeout_seconds=120)
        self.assertEqual(p.timeout_seconds, 120)

    def test_zero_raises(self):
        with self.assertRaises(ValidationError):
            TimeoutPolicy(timeout_seconds=0)


# ---------------------------------------------------------------------------
# ModelCapabilities
# ---------------------------------------------------------------------------


class TestModelCapabilities(unittest.TestCase):
    def test_defaults(self):
        caps = ModelCapabilities(model_id="foo", provider="bar")
        self.assertFalse(caps.is_vision_capable)
        self.assertEqual(caps.context_window, 8192)

    def test_vision_flag(self):
        caps = ModelCapabilities(
            model_id="v-model", provider="test", is_vision_capable=True
        )
        self.assertTrue(caps.is_vision_capable)

    def test_negative_context_window_raises(self):
        with self.assertRaises(ValidationError):
            ModelCapabilities(model_id="m", provider="p", context_window=0)


# ---------------------------------------------------------------------------
# ModelRegistry
# ---------------------------------------------------------------------------


class TestModelRegistry(unittest.TestCase):
    def setUp(self):
        ModelRegistry.clear()

    def tearDown(self):
        ModelRegistry.clear()

    def test_register_and_get(self):
        caps = ModelCapabilities(model_id="test-model", provider="test")
        ModelRegistry.register(caps)
        result = ModelRegistry.get("test-model")
        self.assertIsNotNone(result)
        self.assertEqual(result.model_id, "test-model")

    def test_get_unknown_returns_none(self):
        self.assertIsNone(ModelRegistry.get("does-not-exist"))

    def test_is_vision_capable_true(self):
        ModelRegistry.register(
            ModelCapabilities(model_id="v", provider="p", is_vision_capable=True)
        )
        self.assertTrue(ModelRegistry.is_vision_capable("v"))

    def test_is_vision_capable_false(self):
        ModelRegistry.register(
            ModelCapabilities(model_id="t", provider="p", is_vision_capable=False)
        )
        self.assertFalse(ModelRegistry.is_vision_capable("t"))

    def test_is_vision_capable_unregistered_returns_false(self):
        self.assertFalse(ModelRegistry.is_vision_capable("unknown"))

    def test_all_models(self):
        ModelRegistry.register(ModelCapabilities(model_id="a", provider="p"))
        ModelRegistry.register(ModelCapabilities(model_id="b", provider="p"))
        models = ModelRegistry.all_models()
        self.assertEqual(len(models), 2)

    def test_clear(self):
        ModelRegistry.register(ModelCapabilities(model_id="x", provider="p"))
        ModelRegistry.clear()
        self.assertEqual(ModelRegistry.all_models(), [])

    def test_from_env(self):
        with patch.dict(
            "os.environ",
            {
                "LM_STUDIO_TEXT_MODEL": "test-text",
                "LM_STUDIO_VISION_MODEL": "test-vision",
                "OLLAMA_TEXT_MODEL": "ollama-text",
                "OLLAMA_VISION_MODEL": "ollama-vision",
            },
        ):
            ModelRegistry.from_env()

        self.assertIsNotNone(ModelRegistry.get("test-text"))
        self.assertIsNotNone(ModelRegistry.get("test-vision"))
        self.assertTrue(ModelRegistry.is_vision_capable("test-vision"))
        self.assertFalse(ModelRegistry.is_vision_capable("test-text"))


# ---------------------------------------------------------------------------
# LLMRequest
# ---------------------------------------------------------------------------


class TestLLMRequest(unittest.TestCase):
    def test_valid(self):
        req = LLMRequest(messages=[{"role": "user", "content": "hello"}], model="m")
        self.assertEqual(req.temperature, 0.1)
        self.assertIsNone(req.max_tokens)

    def test_custom_temperature(self):
        req = LLMRequest(messages=[], model="m", temperature=0.7)
        self.assertAlmostEqual(req.temperature, 0.7)

    def test_temperature_out_of_range_raises(self):
        with self.assertRaises(ValidationError):
            LLMRequest(messages=[], model="m", temperature=3.0)

    def test_negative_max_tokens_raises(self):
        with self.assertRaises(ValidationError):
            LLMRequest(messages=[], model="m", max_tokens=-1)

    def test_missing_model_raises(self):
        with self.assertRaises(ValidationError):
            LLMRequest(messages=[])  # model is required


# ---------------------------------------------------------------------------
# LLMResponse
# ---------------------------------------------------------------------------


class TestLLMResponse(unittest.TestCase):
    def test_valid(self):
        r = LLMResponse(
            content="hello",
            model_used="test",
            provider="local",
            latency_ms=42,
        )
        self.assertEqual(r.input_tokens, 0)
        self.assertEqual(r.retry_count, 0)

    def test_negative_latency_raises(self):
        with self.assertRaises(ValidationError):
            LLMResponse(content="x", model_used="m", provider="p", latency_ms=-1)

    def test_negative_retry_count_raises(self):
        with self.assertRaises(ValidationError):
            LLMResponse(
                content="x", model_used="m", provider="p", latency_ms=0, retry_count=-1
            )


# ---------------------------------------------------------------------------
# LLMRouter — core behaviour (mocked OpenAI client)
# ---------------------------------------------------------------------------


class TestLLMRouterSuccess(unittest.TestCase):
    def test_complete_returns_llm_response(self):
        router = _make_router()
        mock_completion = _make_completion(content="test response")

        with patch("src.llm.router.LLMClientFactory.create", return_value=MagicMock()):
            router._LLMRouter__primary_client = MagicMock()
            router._LLMRouter__primary_client.chat.completions.create.return_value = (
                mock_completion
            )

            response = router.complete(LLMRequest(messages=[], model="primary-model"))

        self.assertIsInstance(response, LLMResponse)
        self.assertEqual(response.content, "test response")
        self.assertEqual(response.model_used, "test-model")

    def test_complete_primary_uses_primary_model(self):
        router = _make_router(primary_model="my-text-model")
        mock_completion = _make_completion()

        router._LLMRouter__primary_client = MagicMock()
        router._LLMRouter__primary_client.chat.completions.create.return_value = (
            mock_completion
        )

        router.complete_primary(messages=[{"role": "user", "content": "hi"}])

        call_kwargs = (
            router._LLMRouter__primary_client.chat.completions.create.call_args
        )
        self.assertEqual(call_kwargs.kwargs["model"], "my-text-model")

    def test_complete_vision_uses_vision_model(self):
        router = _make_router(vision_model="my-vision-model")
        mock_completion = _make_completion()

        router._LLMRouter__primary_client = MagicMock()
        router._LLMRouter__primary_client.chat.completions.create.return_value = (
            mock_completion
        )

        router.complete_vision(messages=[{"role": "user", "content": "look at image"}])

        call_kwargs = (
            router._LLMRouter__primary_client.chat.completions.create.call_args
        )
        self.assertEqual(call_kwargs.kwargs["model"], "my-vision-model")

    def test_response_captures_token_counts(self):
        router = _make_router()
        mock_completion = _make_completion(prompt_tokens=100, completion_tokens=50)

        router._LLMRouter__primary_client = MagicMock()
        router._LLMRouter__primary_client.chat.completions.create.return_value = (
            mock_completion
        )

        response = router.complete(LLMRequest(messages=[], model="primary-model"))

        self.assertEqual(response.input_tokens, 100)
        self.assertEqual(response.output_tokens, 50)

    def test_response_retry_count_zero_on_success(self):
        router = _make_router()
        mock_completion = _make_completion()

        router._LLMRouter__primary_client = MagicMock()
        router._LLMRouter__primary_client.chat.completions.create.return_value = (
            mock_completion
        )

        response = router.complete(LLMRequest(messages=[], model="primary-model"))

        self.assertEqual(response.retry_count, 0)

    def test_max_tokens_passed_when_set(self):
        router = _make_router()
        mock_completion = _make_completion()

        router._LLMRouter__primary_client = MagicMock()
        router._LLMRouter__primary_client.chat.completions.create.return_value = (
            mock_completion
        )

        router.complete(LLMRequest(messages=[], model="m", max_tokens=500))

        call_kwargs = (
            router._LLMRouter__primary_client.chat.completions.create.call_args
        )
        self.assertEqual(call_kwargs.kwargs.get("max_tokens"), 500)

    def test_max_tokens_not_passed_when_none(self):
        router = _make_router()
        mock_completion = _make_completion()

        router._LLMRouter__primary_client = MagicMock()
        router._LLMRouter__primary_client.chat.completions.create.return_value = (
            mock_completion
        )

        router.complete(LLMRequest(messages=[], model="m"))

        call_kwargs = (
            router._LLMRouter__primary_client.chat.completions.create.call_args
        )
        self.assertNotIn("max_tokens", call_kwargs.kwargs)


class TestLLMRouterRetry(unittest.TestCase):
    def test_retries_on_failure_then_succeeds(self):
        """Router should retry and succeed on the second attempt."""
        router = _make_router(
            retry_policy=RetryPolicy(max_retries=2, initial_delay_seconds=0.01)
        )
        mock_completion = _make_completion(content="success")

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            ConnectionError("connection refused"),
            mock_completion,
        ]
        router._LLMRouter__primary_client = mock_client

        response = router.complete(LLMRequest(messages=[], model="m"))

        self.assertEqual(response.content, "success")
        self.assertEqual(response.retry_count, 1)
        self.assertEqual(mock_client.chat.completions.create.call_count, 2)

    def test_exhausts_retries_and_raises(self):
        """Router should raise RuntimeError after all retries fail."""
        router = _make_router(
            retry_policy=RetryPolicy(max_retries=2, initial_delay_seconds=0.01)
        )

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = ConnectionError(
            "always fails"
        )
        router._LLMRouter__primary_client = mock_client

        with self.assertRaises(RuntimeError) as ctx:
            router.complete(LLMRequest(messages=[], model="m"))

        self.assertIn("attempt", str(ctx.exception).lower())
        self.assertEqual(
            mock_client.chat.completions.create.call_count, 3
        )  # 1 + 2 retries

    def test_no_retries_when_max_retries_zero(self):
        """With max_retries=0 the router should fail on the first error, no sleep."""
        router = _make_router(retry_policy=RetryPolicy(max_retries=0))

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("boom")
        router._LLMRouter__primary_client = mock_client

        with self.assertRaises(RuntimeError):
            router.complete(LLMRequest(messages=[], model="m"))

        self.assertEqual(mock_client.chat.completions.create.call_count, 1)


class TestLLMRouterFallback(unittest.TestCase):
    def _make_router_with_fallback(self) -> LLMRouter:
        primary_cfg = ProviderConfig(
            name="primary", base_url="http://p:1234/v1", api_key="k"
        )
        fallback_cfg = ProviderConfig(
            name="fallback", base_url="http://f:1234/v1", api_key="k"
        )
        return LLMRouter(
            primary_config=primary_cfg,
            primary_model="primary-model",
            fallback_config=fallback_cfg,
            fallback_model="fallback-model",
            retry_policy=RetryPolicy(max_retries=0),
            timeout_policy=TimeoutPolicy(timeout_seconds=10),
        )

    def test_uses_fallback_after_primary_fails(self):
        router = self._make_router_with_fallback()
        fallback_completion = _make_completion(
            content="fallback result", model="fallback-model"
        )

        primary_client = MagicMock()
        primary_client.chat.completions.create.side_effect = ConnectionError(
            "primary down"
        )
        fallback_client = MagicMock()
        fallback_client.chat.completions.create.return_value = fallback_completion

        router._LLMRouter__primary_client = primary_client
        router._LLMRouter__fallback_client = fallback_client

        response = router.complete(LLMRequest(messages=[], model="primary-model"))

        self.assertEqual(response.content, "fallback result")
        self.assertEqual(response.provider, "fallback")

    def test_fallback_uses_fallback_model_not_request_model(self):
        """The fallback should use its own model, ignoring the request model."""
        router = self._make_router_with_fallback()
        fallback_completion = _make_completion(model="fallback-model")

        primary_client = MagicMock()
        primary_client.chat.completions.create.side_effect = ConnectionError("down")
        fallback_client = MagicMock()
        fallback_client.chat.completions.create.return_value = fallback_completion

        router._LLMRouter__primary_client = primary_client
        router._LLMRouter__fallback_client = fallback_client

        router.complete(LLMRequest(messages=[], model="primary-model"))

        call_kwargs = fallback_client.chat.completions.create.call_args
        self.assertEqual(call_kwargs.kwargs["model"], "fallback-model")

    def test_raises_when_both_primary_and_fallback_fail(self):
        router = self._make_router_with_fallback()

        primary_client = MagicMock()
        primary_client.chat.completions.create.side_effect = ConnectionError(
            "primary down"
        )
        fallback_client = MagicMock()
        fallback_client.chat.completions.create.side_effect = ConnectionError(
            "fallback down"
        )

        router._LLMRouter__primary_client = primary_client
        router._LLMRouter__fallback_client = fallback_client

        with self.assertRaises(RuntimeError) as ctx:
            router.complete(LLMRequest(messages=[], model="m"))

        self.assertIn("fallback", str(ctx.exception).lower())

    def test_no_fallback_configured_raises_on_primary_failure(self):
        """No fallback means RuntimeError on primary failure."""
        router = _make_router(retry_policy=RetryPolicy(max_retries=0))

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = ConnectionError("down")
        router._LLMRouter__primary_client = mock_client

        with self.assertRaises(RuntimeError):
            router.complete(LLMRequest(messages=[], model="m"))


class TestLLMRouterLazyInit(unittest.TestCase):
    def test_client_not_created_at_init(self):
        """LLMClientFactory.create must not be called during LLMRouter.__init__."""
        with patch("src.llm.router.LLMClientFactory.create") as mock_create:
            config = ProviderConfig(name="test", base_url="http://x:1/v1", api_key="k")
            LLMRouter(primary_config=config, primary_model="m")
            mock_create.assert_not_called()

    def test_client_created_on_first_complete(self):
        """LLMClientFactory.create is called the first time _primary_client is accessed."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_completion()

        with patch(
            "src.llm.router.LLMClientFactory.create", return_value=mock_client
        ) as mock_create:
            config = ProviderConfig(name="test", base_url="http://x:1/v1", api_key="k")
            router = LLMRouter(
                primary_config=config,
                primary_model="m",
                retry_policy=RetryPolicy(max_retries=0),
            )
            mock_create.assert_not_called()  # still not called

            router.complete_primary(messages=[])
            mock_create.assert_called_once()  # called lazily


class TestLLMRouterFromEnv(unittest.TestCase):
    def test_from_env_lm_studio(self):
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "lm_studio",
                "LM_STUDIO_TEXT_MODEL": "test-text",
                "LM_STUDIO_VISION_MODEL": "test-vision",
            },
        ):
            router = LLMRouter.from_env()

        self.assertEqual(router.primary_model, "test-text")
        self.assertEqual(router.vision_model, "test-vision")

    def test_from_env_ollama(self):
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "ollama",
                "OLLAMA_TEXT_MODEL": "ollama-text",
                "OLLAMA_VISION_MODEL": "ollama-vision",
            },
        ):
            router = LLMRouter.from_env()

        self.assertEqual(router.primary_model, "ollama-text")
        self.assertEqual(router.vision_model, "ollama-vision")

    def test_from_env_vision_model_optional(self):
        """Vision model missing → router builds fine; vision_model is None."""
        env = {"LLM_PROVIDER": "lm_studio", "LM_STUDIO_TEXT_MODEL": "text-only"}
        with (
            patch("src.llm.router.load_dotenv"),
            patch.dict("os.environ", env, clear=False),
        ):
            import os as _os

            saved = _os.environ.pop("LM_STUDIO_VISION_MODEL", None)
            try:
                router = LLMRouter.from_env()
            finally:
                if saved is not None:
                    _os.environ["LM_STUDIO_VISION_MODEL"] = saved

        self.assertEqual(router.primary_model, "text-only")
        self.assertIsNone(router.vision_model)

    def test_from_env_missing_text_model_raises(self):
        """Missing text model env var → clear ValueError with guidance."""
        env = {"LLM_PROVIDER": "lm_studio"}
        with (
            patch("src.llm.router.load_dotenv"),
            patch.dict("os.environ", env, clear=False),
        ):
            import os as _os

            saved = _os.environ.pop("LM_STUDIO_TEXT_MODEL", None)
            try:
                with self.assertRaises(ValueError) as ctx:
                    LLMRouter.from_env()
            finally:
                if saved is not None:
                    _os.environ["LM_STUDIO_TEXT_MODEL"] = saved

        self.assertIn("LM_STUDIO_TEXT_MODEL", str(ctx.exception))
        self.assertIn(".env", str(ctx.exception))

    def test_complete_vision_raises_when_model_not_configured(self):
        """complete_vision() raises ValueError if vision model is not set."""
        router = _make_router(primary_model="text-model", vision_model=None)
        with self.assertRaises(ValueError) as ctx:
            router.complete_vision(messages=[])
        self.assertIn("LM_STUDIO_VISION_MODEL", str(ctx.exception))
        self.assertIn(".env", str(ctx.exception))


# ---------------------------------------------------------------------------
# get_default_router — singleton
# ---------------------------------------------------------------------------


class TestGetDefaultRouter(unittest.TestCase):
    def setUp(self):
        from src.llm import _reset_default_router_for_testing

        _reset_default_router_for_testing()

    def tearDown(self):
        from src.llm import _reset_default_router_for_testing

        _reset_default_router_for_testing()

    def test_returns_llm_router(self):
        router = get_default_router()
        self.assertIsInstance(router, LLMRouter)

    def test_returns_same_instance(self):
        r1 = get_default_router()
        r2 = get_default_router()
        self.assertIs(r1, r2)

    def test_reset_allows_new_router(self):
        from src.llm import _reset_default_router_for_testing

        r1 = get_default_router()
        _reset_default_router_for_testing()
        r2 = get_default_router()
        self.assertIsNot(r1, r2)

    def test_router_reads_env_on_first_call(self):
        from src.llm import _reset_default_router_for_testing

        # Pin LLM_PROVIDER so the .env file's value doesn't interfere.
        with patch.dict(
            "os.environ",
            {"LLM_PROVIDER": "lm_studio", "LM_STUDIO_TEXT_MODEL": "env-test-model"},
        ):
            _reset_default_router_for_testing()
            router = get_default_router()
        self.assertEqual(router.primary_model, "env-test-model")


if __name__ == "__main__":
    unittest.main()
