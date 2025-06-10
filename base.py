from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urljoin

import requests
import yaml


@dataclass
class Tool:
    """Simple representation of a callable or OpenAPI tool."""

    name: str
    description: str
    func: Optional[Callable] = None
    method: Optional[str] = None
    url: Optional[str] = None
    parameters: Optional[dict] = None


class Agent:
    """
    Unified Agent capable of:
    - Hosting local Python tools (decorated with @function_tool)
    - Discovering tools from MCP servers via OpenAPI specs
    - Delegating to sub-agents via `handoffs`
    """

    def __init__(
        self,
        name: str,
        instructions: str,
        tools: Optional[List[Callable]] = None,
        handoffs: Optional[List[Agent]] = None,
        mcp_servers: Optional[List[str]] = None,
    ):
        self.name = name
        self.instructions = instructions
        self.tools: List[Tool] = self._wrap_python_tools(tools or [])
        self.handoffs = handoffs or []
        self.mcp_servers = mcp_servers or []
        self.tools += self._fetch_mcp_tools()

    def _wrap_python_tools(self, funcs: List[Callable]) -> List[Tool]:
        """Wrap @function_tool functions into Tool instances."""
        wrapped = []
        for func in funcs:
            if getattr(func, "is_tool", False):
                wrapped.append(
                    Tool(
                        func=func,
                        name=getattr(func, "tool_name", func.__name__),
                        description=getattr(func, "tool_description", func.__doc__),
                    )
                )
        return wrapped

    def _fetch_mcp_tools(self) -> List[Tool]:
        """Fetch tools from MCP servers that expose OpenAPI specs."""
        tools = []
        for server in self.mcp_servers:
            try:
                url = urljoin(server, "/openapi.yaml")
                print(f"📡 Fetching OpenAPI spec from {url}")
                resp = requests.get(url)
                resp.raise_for_status()
                spec = yaml.safe_load(resp.text)
                tools.extend(self._convert_openapi_to_tools(spec, server))
            except Exception as e:
                print(f"⚠️ Failed to fetch from {server}: {e}")
        return tools

    def _convert_openapi_to_tools(self, spec: Dict[str, Any], base_url: str) -> List[Tool]:
        tools = []
        for path, methods in spec.get("paths", {}).items():
            for method, op in methods.items():
                op_id = op.get("operationId")
                if not op_id:
                    continue
                tools.append(
                    Tool(
                        name=op_id,
                        description=op.get("summary", ""),
                        method=method.upper(),
                        url=urljoin(base_url, path),
                        parameters=op.get("requestBody", {})
                        .get("content", {})
                        .get("application/json", {})
                        .get("schema"),
                    )
                )
        return tools

    def dispatch(self, name: str, args: dict = {}) -> dict:
        """Dispatch a tool by name (either Python or OpenAPI-based)."""
        import logging

        for tool in self.tools:
            if tool.name == name:
                try:
                    if tool.func:  # Python function tool
                        logging.info(f"Dispatching to local Python tool: {tool.name}")
                        return tool.func(**args)
                    elif tool.url and tool.method:
                        logging.info(
                            f"Dispatching to remote OpenAPI tool: {tool.name} at {tool.url} with method {tool.method}"
                        )
                        if tool.method == "POST":
                            resp = requests.post(tool.url, json=args)
                        elif tool.method == "GET":
                            resp = requests.get(tool.url, params=args)
                        else:
                            raise ValueError(f"Unsupported method: {tool.method}")
                        resp.raise_for_status()
                        return resp.json()
                except Exception as e:
                    logging.error(f"Failed to dispatch {tool.name}: {e}", exc_info=True)
                    raise RuntimeError(f"Failed to dispatch {tool.name}: {e}")
        logging.error(f"No tool found with name: {name}")
        raise ValueError(f"No tool found with name: {name}")


def function_tool(func: Callable) -> Callable:
    """Decorator to mark a function as a usable tool."""
    func.is_tool = True
    func.tool_name = func.__name__
    func.tool_description = func.__doc__ or "No description provided."
    return func


def handoff(agent: Agent) -> Agent:
    """Helper used to register a sub-agent for delegation."""
    return agent
