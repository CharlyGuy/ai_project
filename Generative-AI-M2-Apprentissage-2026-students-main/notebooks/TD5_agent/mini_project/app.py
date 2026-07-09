"""
app.py — PIM Copilot FastAPI backend.

Exposes the agent as a POST /chat endpoint. Connects to the TD4 MCP server
and runs the enrichment loop.
"""

import os
import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent import run_agent

# --- config ---
HERE = Path(__file__).parent
TD4_SERVER_PATH = (HERE.parent.parent / "TD4_mcp" / "mini_project" / "pim_server.py").resolve()

if not TD4_SERVER_PATH.exists():
    print(f"⚠️  Warning: TD4 server not found at {TD4_SERVER_PATH}")
    print("   Make sure you have completed the TD4 mini-project first.")
    print("   The app will fail when you try to chat.")

# --- FastAPI setup ---
app = FastAPI(title="PIM Copilot")

# Serve static files from the current directory (for index.html, etc.)
if (HERE / "static").exists():
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")


# --- models ---
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    success: bool


# --- routes ---
@app.get("/")
async def index():
    """Serve the chat UI."""
    return FileResponse(HERE / "index.html")


@app.post("/chat")
async def chat(request: ChatRequest):
    """Run the agent on the user's message and return the enriched product."""
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if not TD4_SERVER_PATH.exists():
        return ChatResponse(
            reply="Error: TD4 server not found. Did you complete the TD4 mini-project?",
            success=False,
        )

    try:
        # Run the agent
        result = await run_agent(
            goal=message,
            td4_server_path=str(TD4_SERVER_PATH),
        )
        return ChatResponse(reply=result, success=True)
    except Exception as e:
        return ChatResponse(
            reply=f"Agent error: {str(e)}",
            success=False,
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
