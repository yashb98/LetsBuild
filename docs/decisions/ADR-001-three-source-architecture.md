# ADR-001: Three-Source Architecture Pattern Integration

## Status
Accepted

## Date
2026-03-27

## Context
LetsBuild needed a production-grade agent architecture that goes beyond naive LLM orchestration. We evaluated dozens of open-source agent frameworks to identify proven patterns rather than inventing everything from scratch.

## Decision
Integrate patterns from three proven sources:

1. **DeerFlow** (43K+ stars, ByteDance) — 8 patterns: sandbox execution, middleware chain, sub-agent parallelism, progressive skills, memory, MCP, message gateway, multi-model
2. **Claude Certified Architect** (Anthropic Official) — 9 patterns: stop_reason loops, PostToolUse hooks, structured errors, tool_choice config, context management, independent review, retry-with-feedback, scoped tools, .claude/ config
3. **Ruflo** (24.8K+ stars) — 6 patterns: ReasoningBank learning pipeline, Q-Learning model router, compiled policy gates, configurable topologies, ADRs, agent-level hooks

Total: 23 production-grade patterns unified in one domain-specific system.

## Alternatives Considered

### Alternative 1: Build from Scratch
- **Pros:** Full control, no adaptation needed
- **Cons:** Years of development, no proven patterns, higher risk
- **Why rejected:** Time-to-market too slow, would repeat mistakes others already solved

### Alternative 2: Fork DeerFlow Directly
- **Pros:** Ready infrastructure, large community
- **Cons:** No JD awareness, no portfolio intelligence, general-purpose overhead
- **Why rejected:** Domain-specific requirements don't fit general agent harness

### Alternative 3: Use LangGraph/CrewAI
- **Pros:** Popular, well-documented
- **Cons:** Don't implement Architect exam patterns, no ReasoningBank, vendor lock-in
- **Why rejected:** Missing critical patterns for production Claude systems

## Consequences

### Positive
- Every pattern is proven at scale (combined 67K+ GitHub stars)
- Studying LetsBuild's code doubles as Claude Certified Architect exam prep
- ReasoningBank enables genuine self-improvement over time

### Negative
- Higher initial complexity (23 patterns to implement)
- Must maintain compatibility with all three pattern sources
- Contributors need to understand the provenance of patterns

## References
- DeerFlow: github.com/bytedance/deer-flow
- Claude Certified Architect: Anthropic certification program
- Ruflo: github.com/ruvnet/ruflo
