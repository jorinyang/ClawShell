"""Agent discovery and injection — ClawShell v3.0 agent system.

Discover agent instances (beyond framework-level), track injection
status, and auto-inject missing integration methods.

Components:
  scanner.py  — AgentScanner: discovers individual agent instances
  profile.py  — AgentProfileStore: local persistence
  injector.py — AgentInjector: 5-way injection execution
"""
