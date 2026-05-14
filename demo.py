"""
demo.py — Example usage of BrowserSession and WebAgent.

Run directly:
    python demo.py

Or import individual examples as functions.
"""

from browser_tools import BrowserSession


def example_basic_navigation():
    """Navigate, extract text, take a screenshot."""
    print("=== Basic Navigation ===")
    with BrowserSession(headless=True) as b:
        b.goto("https://example.com")
        print("URL:", b.url)
        print("Title:", b.title)
        info = b.get_page_info()
        print("Page info:", info)
        b.screenshot("example_screenshot.png")
        print("Screenshot saved.")


def example_form_fill():
    """Fill a form, submit, and extract results."""
    print("\n=== Form Fill ===")
    with BrowserSession(headless=True) as b:
        b.goto("https://httpbin.org/forms/post")
        b.fill("input[name=custname]", "Test User")
        b.fill("input[name=custtel]", "555-1234")
        b.fill("textarea[name=comments]", "Hello from browser_tools!")
        b.select_option("select[name=size]", label="Large")
        b.screenshot("form_filled.png", full_page=True)
        print("Form filled, screenshot saved.")


def example_click_and_navigate():
    """Click a link and navigate."""
    print("\n=== Click & Navigate ===")
    with BrowserSession(headless=True) as b:
        b.goto("https://quotes.toscrape.com")
        print("Initial URL:", b.url)
        links = b.get_all_links()
        print(f"Found {len(links)} links")
        # Click 'Next' to go to page 2
        b.click("li.next a")
        b.wait_for_load("domcontentloaded")
        print("After click URL:", b.url)
        quotes = b.query_all("span.text")
        for q in quotes[:3]:
            print(" -", q[:80])


def example_scroll_and_extract():
    """Slowly scroll a page and extract content."""
    print("\n=== Scroll & Extract ===")
    with BrowserSession(headless=True) as b:
        b.goto("https://quotes.toscrape.com/scroll")
        b.slow_scroll_to_bottom(step=500, delay_ms=300)
        quotes = b.query_all("span.text")
        print(f"Loaded {len(quotes)} quotes after scrolling.")


def example_multi_tab():
    """Open multiple tabs and switch between them."""
    print("\n=== Multi-Tab ===")
    with BrowserSession(headless=True) as b:
        b.goto("https://example.com")
        print("Tab 0:", b.url)

        b.new_tab()
        b.goto("https://example.org")
        print("Tab 1:", b.url)

        b.switch_tab(0)
        print("Back to Tab 0:", b.url)
        print("Total tabs:", b.tab_count)


def example_javascript():
    """Execute custom JavaScript on the page."""
    print("\n=== JavaScript Execution ===")
    with BrowserSession(headless=True) as b:
        b.goto("https://example.com")
        user_agent = b.evaluate("navigator.userAgent")
        print("User agent:", user_agent)
        dimensions = b.evaluate("({w: window.innerWidth, h: window.innerHeight})")
        print("Viewport:", dimensions)


def example_web_agent():
    """Use the WebAgent for natural-language instructions (requires ANTHROPIC_API_KEY)."""
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n=== WebAgent (skipped — set ANTHROPIC_API_KEY) ===")
        return

    print("\n=== WebAgent ===")
    from web_agent import WebAgent
    agent = WebAgent()
    result = agent.run("Go to quotes.toscrape.com and list the first 3 quote texts on the page.")
    print("Result:", result)


if __name__ == "__main__":
    example_basic_navigation()
    example_click_and_navigate()
    example_javascript()
    example_web_agent()
    print("\nAll demos complete.")
