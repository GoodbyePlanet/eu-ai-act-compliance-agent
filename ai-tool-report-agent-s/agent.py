from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

from dotenv import load_dotenv

load_dotenv()

root_agent = Agent(
    model=LiteLlm(model="anthropic/claude-sonnet-4-5-20250929"),
    name='root_agent',
    description='A helpful assistant for user questions.',
    instruction='Answer user questions to the best of your knowledge',
)
