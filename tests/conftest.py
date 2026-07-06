"""
Ensures the project root is on sys.path so tests can import top-level
packages (agents, valuation, mcp_server) the same way they did before the
tests/ folder existed. Without this, pytest adds only this file's own
directory to sys.path, and imports like `from agents.critic_agent import
CriticAgent` would fail when tests are run from outside the project root.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
