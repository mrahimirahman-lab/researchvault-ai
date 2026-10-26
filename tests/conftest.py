"""Keep the baseline suite independent of the user's active AI provider.

Ollama tests explicitly select their provider in isolated subprocesses or patches.
"""
import os
os.environ['AI_PROVIDER'] = 'openai'
