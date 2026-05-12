"""Cloud Brain — LLM-powered analysis and reasoning engine.

v1.12.0: Direct LLM integration for ClawShell Cloud Hub.
Provides event-driven and scheduled analysis capabilities.

Modules:
- llm_client.py: LLM API client (OpenAI-compatible, stdlib only)
- analyst.py: Cloud analysis engine (root cause, insight, planning, review)
"""

from cloud.brain.llm_client import LLMClient
from cloud.brain.analyst import CloudAnalyst
