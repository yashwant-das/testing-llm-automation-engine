# Adding a New LLM Provider or Model

> How to extend the LLM layer with a new provider or model configuration.

---

## What You Need to Change

Adding a new provider that speaks the OpenAI-compatible API (most local LLM runtimes do) requires only:

1. Add environment variable support in `src/llm/client.py`
2. Register the model in `src/llm/registry.py`
3. Update `.env` documentation

No changes to `LLMRouter`, `planner.py`, `generator.py`, or any pipeline module.

---

## Adding a New OpenAI-Compatible Provider

### 1. Update `src/llm/client.py`

Add a new branch in `LLMClientFactory.create()`:

```python
elif config.provider == "my_provider":
    base_url = os.getenv("MY_PROVIDER_URL", "http://localhost:8080/v1")
    api_key = os.getenv("MY_PROVIDER_API_KEY", "my-provider")
    return OpenAI(base_url=base_url, api_key=api_key)
```

Add a `ProviderConfig` entry:

```python
MY_PROVIDER_CONFIG = ProviderConfig(
    provider="my_provider",
    model=os.getenv("MY_PROVIDER_MODEL", "default-model-name"),
    vision_model=os.getenv("MY_PROVIDER_VISION_MODEL", ""),
    api_key=os.getenv("MY_PROVIDER_API_KEY", "my-provider"),
    base_url=os.getenv("MY_PROVIDER_URL", "http://localhost:8080/v1"),
)
```

### 2. Register the Model

Add capability metadata in `src/llm/registry.py`:

```python
"my-model-name": ModelCapabilities(
    supports_vision=False,
    supports_structured_output=True,
    context_window=32768,
    cost_per_1k_input=0.0,    # local inference — no token cost
    cost_per_1k_output=0.0,
),
```

### 3. Update Environment Variables

Set `LLM_PROVIDER=my_provider` in `.env` and add the provider-specific variables.

---

## Adding a Non-OpenAI Provider (Requires More Work)

If the new provider does not expose an OpenAI-compatible API, you need to:

1. Add a new client class in `src/llm/client.py` that wraps the provider's SDK
2. Update `LLMClientFactory.create()` to return it
3. Ensure the client returns an object that `LLMRouter` can call with `client.chat.completions.create()`

At this point, LiteLLM becomes the right tool. LiteLLM normalises diverse provider APIs into a single OpenAI-compatible interface. Add it as a dependency and replace `LLMClientFactory.create()` with a `litellm.completion()` call. See ADR-007 for the original evaluation.

---

## Switching the Default Model

The default router is configured at first call to `get_default_router()` via `_build_default_config()` in `src/llm/__init__.py`. Change the environment variables — no code change required.

```env
# Switch to a different Ollama model
OLLAMA_MODEL=llama3.3:70b
```

The new model is picked up on the next cold start (or after restarting the app).

---

## Testing the New Provider

Unit tests mock the router — they do not call any real provider. To test your new provider integration:

1. Start the provider
2. Set `LLM_PROVIDER=my_provider` in `.env`
3. Run a single healing session via the UI or the service layer
4. Check `logs/traces.jsonl` — the `model` field in the `llm` span should show the provider's model name
5. Check `tests/artifacts/` — the `model_used` field should appear in the `HealingDecision` artifact

If `model_used` is empty, the provider's response did not include the model name in the `model` field of the ChatCompletion response. Update `LLMRouter._build_response()` to extract the model name from wherever the provider puts it.

---

## Vision Model

Vision models are separate from text/code models. They are configured via `*_VISION_MODEL` environment variables and used in `router.complete_vision()`. The same provider infrastructure handles both — the only difference is which model name is passed in the request.

If the vision model speaks the OpenAI Vision API (image URL or base64 in the user message), no additional code changes are needed. If it uses a different image format, update `src/services/vision_service.py` to format the image correctly.
