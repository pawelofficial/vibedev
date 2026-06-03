from pydantic import BaseModel
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from vibedev import config
from vibedev.utils.logging import ConversationLogger, get_transcript


class StructuredOutputError(RuntimeError):
    """An agent's work could not be turned into valid structured output."""


COERCE_SYSTEM = (
    "You convert content into structured JSON. "
    "You are given the final output of another agent that did the work but failed "
    "to format its response. Reshape it to match the required schema exactly. "
    "Do NOT add, invent, or drop information — only reformat what is given. "
    "Respond with structured JSON only."
)


async def _stream_session(
    role: str, model: str, options: ClaudeAgentOptions, prompt: str
) -> tuple[dict, str]:
    """Drive one ``query()`` session. Returns ``(structured_output, narration)`` where
    ``structured_output`` is ``{}`` if the session produced none, and ``narration`` is
    whatever text the agent emitted."""
    logger: ConversationLogger | None = None
    result_data: dict = {}
    narration: list[str] = []

    print(f"\n{'='*50}")
    print(f"AGENT: {role}  [{model}]")
    print(f"{'='*50}")

    async for message in query(prompt=prompt, options=options):
        if logger is None and hasattr(message, "session_id") and message.session_id:
            logger = ConversationLogger(message.session_id, role)
            logger.log("agent_start", role=role, model=model, prompt=prompt)

        if logger:
            try:
                logger.log("message", type=type(message).__name__, data=message.__dict__)
            except Exception:
                logger.log("message", type=type(message).__name__, data=str(message))

        # Best-effort capture of any text the agent emits — this is what we coerce
        # into the schema if structured output fails.
        content = getattr(message, "content", None)
        if isinstance(content, list):
            for block in content:
                text = getattr(block, "text", None)
                if text:
                    narration.append(text)

        print(message)

        if isinstance(message, ResultMessage):
            if message.subtype == "success" and message.structured_output:
                result_data = message.structured_output
                if logger:
                    logger.log("structured_output", data=result_data)
            elif message.subtype == "error_max_structured_output_retries":
                if logger:
                    logger.log("error", reason="max_structured_output_retries")

    if logger:
        logger.log("agent_end", role=role)
        logger.flush()

    transcript = get_transcript()
    if transcript:
        transcript.agent(
            role=role,
            model=model,
            prompt=prompt,
            output=result_data,
            narration="\n".join(narration),
        )

    return result_data, "\n".join(narration)


async def _coerce_to_schema(role: str, text: str, output_schema: type[BaseModel]) -> dict:
    """Reshape ``text`` (an agent's unstructured output) into ``output_schema`` with a
    cheap, tool-less call. Retries only this formatting step — never redoes the work."""
    # Reshaping text into JSON is easy work; keep it on the cheap default model
    # regardless of which (possibly pricier) model did the original task.
    model = config.DEFAULT_MODEL
    options = ClaudeAgentOptions(
        model=model,
        system_prompt=COERCE_SYSTEM,
        allowed_tools=[],  # pure reformatting: no tools, nothing re-executed
        permission_mode=config.CONFIG["permission_mode"],
        cwd=config.OUTPUT_DIR,
        output_format={
            "type": "json_schema",
            "schema": output_schema.model_json_schema(),
        },
    )
    prompt = (
        "Convert the following content into JSON matching the required schema. "
        "Only restructure what is given; do not invent anything.\n\n"
        f"CONTENT:\n{text}"
    )

    for attempt in range(1, config.MAX_STRUCTURED_OUTPUT_ATTEMPTS + 1):
        structured, _ = await _stream_session(
            f"{role} → structuring (attempt {attempt})", model, options, prompt
        )
        if structured:
            return structured
        print(f"  ! {role}: structuring failed on attempt {attempt}/{config.MAX_STRUCTURED_OUTPUT_ATTEMPTS}.")

    raise StructuredOutputError(
        f"[{role}] could not be coerced into structured output after "
        f"{config.MAX_STRUCTURED_OUTPUT_ATTEMPTS} attempts."
    )


async def run_agent(
    role: str,
    system_prompt: str,
    prompt: str,
    output_schema: type[BaseModel],
) -> dict:
    model = config.model_for(role)
    options = ClaudeAgentOptions(
        model=model,
        system_prompt=system_prompt,
        allowed_tools=config.CONFIG["allowed_tools"],
        permission_mode=config.CONFIG["permission_mode"],
        add_dirs=config.CONFIG["extra_dirs"],
        cwd=config.OUTPUT_DIR,
        output_format={
            "type": "json_schema",
            "schema": output_schema.model_json_schema(),
        },
    )

    # Do the real (tool-using) work exactly once.
    result_data, narration = await _stream_session(role, model, options, prompt)
    if result_data:
        return result_data

    # The agent worked but didn't format its answer. Don't redo the work — take what
    # it said and coerce just that into the schema.
    if not narration.strip():
        raise StructuredOutputError(f"[{role}] produced no output to structure.")

    print(f"  ↻ {role}: no structured output; coercing the agent's response into the schema.")
    return await _coerce_to_schema(role, narration, output_schema)
