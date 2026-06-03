from pydantic import BaseModel
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from vibedev import config
from vibedev.utils.logging import ConversationLogger, get_transcript


async def run_agent(
    role: str,
    system_prompt: str,
    prompt: str,
    output_schema: type[BaseModel],
) -> dict:
    options = ClaudeAgentOptions(
        model=config.CONFIG["model"],
        system_prompt=system_prompt,
        allowed_tools=config.CONFIG["allowed_tools"],
        cwd=config.OUTPUT_DIR,
        output_format={
            "type": "json_schema",
            "schema": output_schema.model_json_schema(),
        },
    )

    logger: ConversationLogger | None = None
    result_data: dict = {}
    narration: list[str] = []

    print(f"\n{'='*50}")
    print(f"AGENT: {role}  [{config.CONFIG['model']}]")
    print(f"{'='*50}")

    async for message in query(prompt=prompt, options=options):
        if logger is None and hasattr(message, "session_id") and message.session_id:
            logger = ConversationLogger(message.session_id, role)
            logger.log("agent_start", role=role, model=config.CONFIG["model"], prompt=prompt)

        if logger:
            try:
                logger.log("message", type=type(message).__name__, data=message.__dict__)
            except Exception:
                logger.log("message", type=type(message).__name__, data=str(message))

        # Best-effort capture of any text the agent emits, for the transcript.
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
                raise RuntimeError(f"[{role}] Failed to produce valid structured output")

    if logger:
        logger.log("agent_end", role=role)
        logger.flush()

    transcript = get_transcript()
    if transcript:
        transcript.agent(
            role=role,
            model=config.CONFIG["model"],
            prompt=prompt,
            output=result_data,
            narration="\n".join(narration),
        )

    return result_data
