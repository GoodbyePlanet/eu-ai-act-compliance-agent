import logging
import os
import uuid

from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from compliance_agent.config import (
    AGENT_DESCRIPTION,
    AGENT_INSTRUCTION,
    APP_NAME,
    MAX_SEARCHES,
)
from compliance_agent.guardrails import (
    validate_input_guardrail,
    output_validation_guardrail,
    tool_input_guardrail,
)
from compliance_agent.tools import compliance_search_tool

load_dotenv()
logger = logging.getLogger(__name__)

root_agent = Agent(
    model=LiteLlm(model="anthropic/claude-sonnet-4-5-20250929"),
    name=APP_NAME,
    description=AGENT_DESCRIPTION,
    instruction=AGENT_INSTRUCTION,
    tools=[compliance_search_tool],
    # Guardrails
    before_agent_callback=validate_input_guardrail,
    after_agent_callback=output_validation_guardrail,
    before_tool_callback=tool_input_guardrail,
)

db_url = os.getenv("DATABASE_URL")

if not db_url:
    raise ValueError("DATABASE_URL environment variable not set.")

session_service = DatabaseSessionService(db_url=db_url)
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)


async def execute(request):
    """
    Execute a compliance assessment for the given AI tool.

    Args:
        request: Request object containing ai_tool name and optional session_id.

    Returns:
        Dictionary with 'summary' (the compliance report) and 'session_id',
        or None if execution fails.
    """
    logger.info(
        f"Request received with message: {request.ai_tool} - with session ID {request.session_id}"
    )

    if request.user_email:
        user_email = request.user_email
    else:
        user_email = f"Guest_{uuid.uuid4()}" # TODO: Later on we want to allow guest users to use the app

    current_session = (
        request.session_id if request.session_id else f"session_{uuid.uuid4()}"
    )
    existing_session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_email, session_id=current_session
    )

    if existing_session is None:
        logger.info(f"No session found. Initializing new session with ID: {current_session}")
        await session_service.create_session(
            app_name=APP_NAME, user_id=user_email, session_id=current_session
        )
    else:
        logger.info(f"Session {current_session} retrieved successfully.")

    search_count = 0
    prompt = f"Assess AI tool - {request.ai_tool}"
    message = types.Content(role="user", parts=[types.Part(text=prompt)])

    try:
        async for event in runner.run_async(
                user_id=user_email, session_id=current_session, new_message=message
        ):
            if event.content and any(
                    part.function_call for part in event.content.parts
            ):
                search_count += 1
                logger.info(f"Agent is using tool (Search {search_count}/{MAX_SEARCHES})")

                if search_count > MAX_SEARCHES:
                    logger.warning(
                        "Max search limit reached! Forcing agent to synthesize results."
                    )
                    return {
                        "summary": "### Search Limit Reached\nThe agent exceeded the maximum search limit while researching. Please refine your query or check specific tool documentation manually.",
                        "session_id": current_session,
                    }

            if event.is_final_response():
                return {
                    "summary": event.content.parts[0].text,
                    "session_id": current_session,
                }
    except Exception as e:
        logger.error(f"Error during execution: {e}")

    return None
