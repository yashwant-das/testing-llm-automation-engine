"""
Service layer — orchestrates agents for the UI layer.

Each service module provides streaming generator functions that yield
(timeline_markdown, …) tuples for Gradio's progressive update model.

app.py imports only from here; no agent or subprocess calls live in app.py.

Modules
-------
generation_service   generate_test_streaming, run_test_streaming
vision_service       analyze_visual_streaming, run_vision_test_streaming
healing_service      heal_test_streaming
"""
