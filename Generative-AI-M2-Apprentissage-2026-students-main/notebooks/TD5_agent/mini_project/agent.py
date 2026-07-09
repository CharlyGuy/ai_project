"""
agent.py — PIM enrichment agent.

The reason → act → observe loop over MCP. Connects to the TD4 PIM server
via stdio transport and runs Haiku in a tool-use loop until the goal is reached.
"""

import json
import asyncio
import sys
from typing import Optional

import anthropic
from mcp.client.stdio import StdioServerParameters, stdio_client

# The agent's skill/SOP (abbreviated here; see the notebook for the full version)
SKILL = """You are a PIM (Product Information Management) enrichment agent.
Your job: read supplier product information and enrich the Fnac catalog.

PROCESS:
1. Understand the product (name, brand, specs) from the supplier info.
2. Call get_category_tree() to see available categories.
3. Determine the right leaf category by reading the supplier info.
4. Call get_category_attributes(category) to get the expected attributes.
5. Call search_products() to find similar existing products as style exemplars.
6. Write a short_description (one-line tagline) and long_description (2-4 sentences),
   matching the tone of similar products.
7. Fill ALL category attributes, using null where unknown.
8. Collect any supplier info that doesn't map to category attributes into `extra`
   (e.g., wholesale price, MOQ, warranty, supplier SKU, ship week).
9. Call create_product() with everything, including extra.

OUTPUT: JSON dict with the created product and a summary of what was enriched.
"""

MODEL = "claude-haiku-4-5"


async def get_anthropic_tools(mcp_session):
    """Discover tools from the MCP server and convert to Anthropic format."""
    tools_response = await mcp_session.list_tools()
    anthropic_tools = []
    for tool in tools_response.tools:
        anthropic_tools.append({
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema,
        })
    return anthropic_tools


async def run_agent(
    goal: str,
    td4_server_path: str,
    td4_server_args: Optional[list] = None,
    max_iters: int = 12,
) -> str:
    """Run Haiku in a tool-use loop until it stops requesting tools.

    Args:
        goal: The enrichment task (e.g., product specs to enrich).
        td4_server_path: Absolute path to TD4's pim_server.py.
        td4_server_args: Additional args passed to the server (default: []).
        max_iters: Max iterations before stopping (runaway guard).

    Returns:
        The final assistant text (the created product summary).
    """
    if td4_server_args is None:
        td4_server_args = []

    # Connect to TD4 server over stdio
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[td4_server_path] + td4_server_args,
    )

    # Use the stdio client context manager
    from mcp.client.session import ClientSession
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Get the tool catalog from MCP and convert to Anthropic format
            anthropic_tools = await get_anthropic_tools(session)

            # Initialize Anthropic client
            client = anthropic.Anthropic()

            # Start the conversation
            messages = [{"role": "user", "content": goal}]
            trace = []

            # Agent loop
            for iteration in range(max_iters):
                # Reason: ask the model
                resp = client.messages.create(
                    model=MODEL,
                    max_tokens=2048,
                    system=SKILL,
                    tools=anthropic_tools,
                    messages=messages,
                )

                # Check stop condition: if the model is done (no more tool calls), return
                if resp.stop_reason != "tool_use":
                    # Collect the final answer
                    final_text = "".join(
                        block.text
                        for block in resp.content
                        if hasattr(block, "text") and block.text
                    )
                    trace.append(f"[Final answer]")
                    return final_text

                # Record the assistant turn
                messages.append({"role": "assistant", "content": resp.content})

                # Act + Observe: execute every tool_use block this turn
                tool_results = []
                for block in resp.content:
                    if block.type == "tool_use":
                        trace.append(f"-> call: {block.name}({json.dumps(block.input)[:100]}...)")

                        # Call the tool over MCP
                        result = await session.call_tool(block.name, block.input)
                        result_text = "\n".join(c.text for c in result.content)

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_text,
                        })

                # Feed all observations back
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})

            # Runaway guard: max iterations reached
            return "[Agent runaway: max iterations reached]"


# For testing: simple wrapper
def run_agent_sync(goal: str, td4_server_path: str, td4_server_args: Optional[list] = None):
    """Synchronous wrapper around run_agent for use in Flask/FastAPI."""
    return asyncio.run(run_agent(goal, td4_server_path, td4_server_args))
