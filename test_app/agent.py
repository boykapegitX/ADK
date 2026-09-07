from google.adk.agents.llm_agent import Agent
from google.adk.tools import google_search

root_agent = Agent(
    model="gemini-2.5-flash",
    name="research_assistant",
    description="A helpful research assistant that can search the web to answer questions.",
    instruction="""
        You are a helpful research assistant. 
        When asked a question, use the Google Search tool to find accurate, 
        up-to-date information. Always cite your sources and summarize clearly.
    """,
    tools=[google_search]
)

