"""
web_agent.py — Natural-language web interaction agent powered by Claude.

The agent uses Claude's tool-use API so you can describe what you want
in plain English and it will drive the browser automatically.

Usage:
    python web_agent.py "Go to news.ycombinator.com and list the top 5 story titles"

Or from Python:
    from web_agent import WebAgent

    agent = WebAgent()
    result = agent.run("Go to wikipedia.org and search for 'Python programming'")
    print(result)
"""

import json
import os
import sys
from typing import Any

import anthropic

from browser_tools import BrowserSession

# ------------------------------------------------------------------ #
# Tool definitions exposed to Claude
# ------------------------------------------------------------------ #

TOOLS: list[dict] = [
    {
        "name": "navigate",
        "description": "Navigate to a URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The full URL to navigate to."},
                "wait_until": {
                    "type": "string",
                    "enum": ["domcontentloaded", "load", "networkidle"],
                    "description": "When to consider navigation done.",
                    "default": "domcontentloaded",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "click",
        "description": "Click an element on the page using a CSS selector or text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the element to click."},
                "text": {"type": "string", "description": "Visible text of the element to click (used if selector not given)."},
            },
        },
    },
    {
        "name": "fill",
        "description": "Clear an input field and type text into it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the input field."},
                "text": {"type": "string", "description": "Text to type."},
            },
            "required": ["selector", "text"],
        },
    },
    {
        "name": "press_key",
        "description": "Press a keyboard key, e.g. Enter, Tab, Escape, ArrowDown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key name, e.g. 'Enter', 'Tab', 'Escape'."},
                "selector": {"type": "string", "description": "Optional: focus this element first."},
            },
            "required": ["key"],
        },
    },
    {
        "name": "scroll",
        "description": "Scroll the page. Use direction='down'/'up' for page scrolling, or provide a selector to scroll to an element.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["down", "up", "bottom", "top"]},
                "amount": {"type": "integer", "description": "Pixels to scroll (default 500)."},
                "selector": {"type": "string", "description": "Scroll to this element instead."},
            },
        },
    },
    {
        "name": "get_page_content",
        "description": "Get the visible text content of the current page (or a specific element).",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector to extract from. Defaults to 'body'."},
                "max_chars": {"type": "integer", "description": "Truncate output to this many characters. Default 4000."},
            },
        },
    },
    {
        "name": "get_page_info",
        "description": "Get the current page URL, title, and element counts.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_links",
        "description": "Return all hyperlinks on the current page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filter_text": {"type": "string", "description": "Only return links whose text contains this string (case-insensitive)."},
            },
        },
    },
    {
        "name": "get_inputs",
        "description": "Return all form inputs visible on the page.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "screenshot",
        "description": "Take a screenshot of the current page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path for the screenshot. Default: screenshot.png"},
                "full_page": {"type": "boolean", "description": "Capture full scrollable page. Default false."},
            },
        },
    },
    {
        "name": "select_option",
        "description": "Select an option from a <select> dropdown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the <select> element."},
                "value": {"type": "string", "description": "Option value attribute."},
                "label": {"type": "string", "description": "Visible option label text."},
            },
            "required": ["selector"],
        },
    },
    {
        "name": "wait_for_element",
        "description": "Wait until an element appears on the page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector to wait for."},
                "state": {"type": "string", "enum": ["visible", "hidden", "attached", "detached"], "default": "visible"},
                "timeout_ms": {"type": "integer", "description": "Max wait time in ms. Default 10000."},
            },
            "required": ["selector"],
        },
    },
    {
        "name": "go_back",
        "description": "Navigate back in browser history.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "go_forward",
        "description": "Navigate forward in browser history.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "reload",
        "description": "Reload the current page.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_javascript",
        "description": "Execute arbitrary JavaScript on the page and return the result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "JavaScript expression or statement to execute."},
            },
            "required": ["code"],
        },
    },
    {
        "name": "extract_table",
        "description": "Extract an HTML table as a 2-D list of strings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the table. Default: 'table'."},
            },
        },
    },
    {
        "name": "hover",
        "description": "Hover the mouse over an element.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the element."},
            },
            "required": ["selector"],
        },
    },
    {
        "name": "new_tab",
        "description": "Open a new browser tab.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "switch_tab",
        "description": "Switch to a tab by index (0-based).",
        "input_schema": {
            "type": "object",
            "properties": {
                "index": {"type": "integer"},
            },
            "required": ["index"],
        },
    },
    {
        "name": "close_tab",
        "description": "Close the current tab.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "check",
        "description": "Check a checkbox or radio button.",
        "input_schema": {
            "type": "object",
            "properties": {"selector": {"type": "string"}},
            "required": ["selector"],
        },
    },
    {
        "name": "uncheck",
        "description": "Uncheck a checkbox.",
        "input_schema": {
            "type": "object",
            "properties": {"selector": {"type": "string"}},
            "required": ["selector"],
        },
    },
]


# ------------------------------------------------------------------ #
# Tool executor
# ------------------------------------------------------------------ #

def execute_tool(browser: BrowserSession, tool_name: str, tool_input: dict) -> Any:
    """Dispatch a tool call to the BrowserSession."""
    match tool_name:
        case "navigate":
            url = tool_input["url"]
            wait = tool_input.get("wait_until", "domcontentloaded")
            final_url = browser.goto(url, wait_until=wait)
            return {"ok": True, "url": final_url, "title": browser.title}

        case "click":
            selector = tool_input.get("selector")
            text = tool_input.get("text")
            if selector:
                browser.click(selector)
            elif text:
                browser.find_and_click(text)
            else:
                return {"error": "Provide selector or text"}
            return {"ok": True, "url": browser.url}

        case "fill":
            browser.fill(tool_input["selector"], tool_input["text"])
            return {"ok": True}

        case "press_key":
            browser.press(tool_input["key"], tool_input.get("selector"))
            return {"ok": True, "url": browser.url}

        case "scroll":
            selector = tool_input.get("selector")
            if selector:
                browser.scroll_to_element(selector)
            else:
                direction = tool_input.get("direction", "down")
                amount = tool_input.get("amount", 500)
                match direction:
                    case "down":
                        browser.scroll(0, amount)
                    case "up":
                        browser.scroll(0, -amount)
                    case "bottom":
                        browser.scroll_to_bottom()
                    case "top":
                        browser.scroll_to_top()
            return {"ok": True}

        case "get_page_content":
            sel = tool_input.get("selector", "body")
            max_chars = tool_input.get("max_chars", 4000)
            text = browser.get_text(sel)
            if len(text) > max_chars:
                text = text[:max_chars] + f"\n... [truncated, {len(text)} total chars]"
            return {"text": text, "url": browser.url, "title": browser.title}

        case "get_page_info":
            return browser.get_page_info()

        case "get_links":
            links = browser.get_all_links()
            f = tool_input.get("filter_text", "").lower()
            if f:
                links = [l for l in links if f in l["text"].lower()]
            return {"links": links[:100], "total": len(links)}

        case "get_inputs":
            return {"inputs": browser.get_all_inputs()}

        case "screenshot":
            path = tool_input.get("path", "screenshot.png")
            full = tool_input.get("full_page", False)
            saved = browser.screenshot(path=path, full_page=full)
            return {"ok": True, "saved_to": saved}

        case "select_option":
            browser.select_option(
                tool_input["selector"],
                value=tool_input.get("value"),
                label=tool_input.get("label"),
            )
            return {"ok": True}

        case "wait_for_element":
            browser.wait_for_selector(
                tool_input["selector"],
                state=tool_input.get("state", "visible"),
                timeout=tool_input.get("timeout_ms", 10_000),
            )
            return {"ok": True}

        case "go_back":
            browser.back()
            return {"ok": True, "url": browser.url}

        case "go_forward":
            browser.forward()
            return {"ok": True, "url": browser.url}

        case "reload":
            browser.reload()
            return {"ok": True}

        case "run_javascript":
            result = browser.evaluate(tool_input["code"])
            return {"result": result}

        case "extract_table":
            sel = tool_input.get("selector", "table")
            rows = browser.extract_table(sel)
            return {"rows": rows}

        case "hover":
            browser.hover(tool_input["selector"])
            return {"ok": True}

        case "new_tab":
            browser.new_tab()
            return {"ok": True, "tab_count": browser.tab_count}

        case "switch_tab":
            browser.switch_tab(tool_input["index"])
            return {"ok": True, "url": browser.url}

        case "close_tab":
            browser.close_tab()
            return {"ok": True, "tab_count": browser.tab_count}

        case "check":
            browser.check(tool_input["selector"])
            return {"ok": True}

        case "uncheck":
            browser.uncheck(tool_input["selector"])
            return {"ok": True}

        case _:
            return {"error": f"Unknown tool: {tool_name}"}


# ------------------------------------------------------------------ #
# Agent class
# ------------------------------------------------------------------ #

class WebAgent:
    """
    A Claude-powered agent that drives a real browser to complete
    natural-language web tasks.
    """

    SYSTEM_PROMPT = """You are a web automation assistant that can control a real browser.
You have access to tools that let you navigate, click, type, scroll, and extract content from any website.

Guidelines:
- Use get_page_info or get_page_content to understand what is on the page before acting.
- Prefer CSS selectors like #id, .class, button[type=submit], input[name=q].
- When a selector is unclear, use get_links or get_inputs to discover element details first.
- After clicking links or submitting forms, wait for navigation to settle before extracting content.
- Be concise and accurate in your final answer. Include URLs and titles when relevant.
- If a task requires multiple steps, execute all of them before reporting the final result.
"""

    def __init__(
        self,
        api_key: str = None,
        model: str = "claude-sonnet-4-6",
        headless: bool = True,
        max_turns: int = 20,
        verbose: bool = True,
    ):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._model = model
        self._headless = headless
        self._max_turns = max_turns
        self._verbose = verbose
        self._client = anthropic.Anthropic(api_key=self._api_key)

    def _log(self, *args):
        if self._verbose:
            print(*args, flush=True)

    def run(self, task: str) -> str:
        """Run a natural-language web task and return the final answer."""
        messages = [{"role": "user", "content": task}]

        with BrowserSession(headless=self._headless) as browser:
            for turn in range(self._max_turns):
                self._log(f"\n[Turn {turn + 1}]")

                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    system=self.SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages,
                )

                self._log(f"  Stop reason: {response.stop_reason}")

                # Collect assistant content blocks
                assistant_blocks = []
                tool_calls = []

                for block in response.content:
                    assistant_blocks.append(block)
                    if block.type == "tool_use":
                        tool_calls.append(block)
                    elif block.type == "text" and block.text:
                        self._log(f"  Assistant: {block.text[:200]}")

                messages.append({"role": "assistant", "content": assistant_blocks})

                # If no tool calls, we have the final answer
                if response.stop_reason == "end_turn" or not tool_calls:
                    for block in assistant_blocks:
                        if hasattr(block, "text"):
                            return block.text
                    return "(No text response)"

                # Execute all tool calls and collect results
                tool_results = []
                for tc in tool_calls:
                    self._log(f"  Tool: {tc.name}({json.dumps(tc.input)[:120]})")
                    try:
                        result = execute_tool(browser, tc.name, tc.input)
                    except Exception as exc:
                        result = {"error": str(exc)}
                    self._log(f"  Result: {str(result)[:200]}")
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": json.dumps(result),
                        }
                    )

                messages.append({"role": "user", "content": tool_results})

        return "Max turns reached without a final answer."


# ------------------------------------------------------------------ #
# CLI entry point
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python web_agent.py '<task description>'")
        print("Example: python web_agent.py 'Go to python.org and tell me the latest Python version'")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    agent = WebAgent()
    answer = agent.run(task)
    print("\n=== RESULT ===")
    print(answer)
