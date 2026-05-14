# Shared Contracts

This package is reserved for generated API contracts and cross-service type definitions.

Sprint 0 keeps contracts in the API Pydantic schemas first. Move OpenAPI-derived TypeScript
types here once the API surface stabilizes enough for web integration tests.

Current shared contracts:

- `model-routing-policy.v0.1.json`: model tier, budget class, specialist-agent, and runtime-agent routing policy used by the orchestrator and Agent Card `model_policy`.

