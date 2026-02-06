1. Input Validation (Before Agent Execution) - execute() function, lines 184-206
   Why: Prevent malicious or inappropriate inputs from reaching the agent.
   Current gap: The request.ai_tool value is passed directly to the agent without validation.
   Guardrails to add:
- Input sanitization (remove prompt injection attempts)
- Length limits on input
- Block prohibited terms/patterns
- Validate input format

2. Tool-Level Guardrails - deep_compliance_search() function, lines 123-155
   Why: The search tool can access the web - you need to control what queries are allowed.
   Current gap: Any query string is passed directly to SerpAPI.
   Guardrails to add:
- Query sanitization
- Block searches for sensitive topics
- Rate limiting per session
- URL/domain allowlisting for results

3. Output Validation (After Agent Response) - execute() function, line 223
   Why: Ensure the agent's output doesn't contain harmful, inappropriate, or policy-violating content.
   Current gap: The final response is returned directly without inspection.
   Guardrails to add:
- Content filtering for harmful output
- PII detection and redaction
- Verify response follows expected structure
- Block unexpected code execution patterns

4. Agent Instructions (Instruction-Level Guardrails) - agent_instruction, lines 22-118
   Why: The LLM follows instructions - adding safety rules directly in instructions is a first line of defense.
   Current gap: No explicit safety boundaries defined.
   Guardrails to add:
- Explicit "do not" rules
- Scope limitations
- Response format enforcement
- Handling of adversarial prompts

5. Session/Runtime Controls - runner and session_service, lines 177-181
   Why: Prevent abuse through session manipulation or excessive resource usage.
   Current gap: Limited to search count (line 204-220), but no other runtime controls.
   Guardrails to add:
- Session timeout limits
- Total token/cost limits
- Concurrent request limits