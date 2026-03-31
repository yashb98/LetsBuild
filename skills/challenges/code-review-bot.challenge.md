---
name: code-review-bot
display_name: "AI Code Review Bot"
category: agentic
difficulty: 8
requirements:
  - "Read Python source files and identify bugs"
  - "Detect common security vulnerabilities (SQL injection, path traversal, hardcoded secrets)"
  - "Suggest fixes with explanations for each finding"
  - "Output structured JSON with file, line, severity, description, suggestion"
  - "Process multiple files in a single run"
  - "Zero false positives on clean code samples"
bonus_features:
  - "Support for JavaScript/TypeScript in addition to Python"
  - "Severity classification (critical, high, medium, low, info)"
  - "Auto-fix mode that generates patch files"
time_limits:
  research: 1800
  architecture: 900
  build: 5400
  cross_review: 900
  fix_sprint: 900
judging_weights:
  functionality: 0.30
  code_quality: 0.20
  test_coverage: 0.15
  ux_design: 0.15
  architecture: 0.10
  innovation: 0.10
constraints:
  stack: "Python+Claude API"
  auth: false
  must_run: "python -m code_review_bot --help"
hidden_test_path: "tests/arena/hidden/code_review_bot_tests.py"
---

# AI Code Review Bot

Build an AI-powered code review agent that reads source files, finds bugs and security issues, and suggests fixes with explanations.

The bot should use Claude's tool_use for structured output — never parse free text. Each finding should include the exact file, line number, severity, a clear description of the issue, and a concrete suggestion for fixing it.

The bot must have zero false positives on known-clean code. Precision matters more than recall. Test with both buggy and clean code samples.
