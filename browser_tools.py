"""
browser_tools.py — Playwright-based web interaction toolkit.

Provides a BrowserSession class with methods for navigating, clicking,
typing, scrolling, extracting content, and taking screenshots.

Usage:
    from browser_tools import BrowserSession

    with BrowserSession(headless=True) as browser:
        browser.goto("https://example.com")
        browser.click("a.some-link")
        browser.fill("#search", "hello world")
        browser.press("Enter")
        print(browser.get_text("h1"))
        browser.screenshot("result.png")
"""

import json
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, Locator

CHROMIUM_EXEC = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
DEFAULT_ARGS = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]


class BrowserSession:
    """A managed Playwright browser session."""

    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        viewport: dict = None,
        ignore_https_errors: bool = True,
        timeout: int = 30_000,
    ):
        self._headless = headless
        self._slow_mo = slow_mo
        self._viewport = viewport or {"width": 1280, "height": 800}
        self._ignore_https_errors = ignore_https_errors
        self._timeout = timeout
        self._pw = None
        self._browser: Browser = None
        self._context: BrowserContext = None
        self.page: Page = None

    # ------------------------------------------------------------------ #
    # Context-manager lifecycle
    # ------------------------------------------------------------------ #

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.close()

    def start(self):
        """Start the browser session."""
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self._headless,
            executable_path=CHROMIUM_EXEC,
            slow_mo=self._slow_mo,
            args=DEFAULT_ARGS,
        )
        self._context = self._browser.new_context(
            viewport=self._viewport,
            ignore_https_errors=self._ignore_https_errors,
        )
        self._context.set_default_timeout(self._timeout)
        self.page = self._context.new_page()
        return self

    def close(self):
        """Close the browser and all associated resources."""
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #

    def goto(self, url: str, wait_until: str = "domcontentloaded") -> str:
        """Navigate to a URL. Returns the final URL after any redirects."""
        self.page.goto(url, wait_until=wait_until)
        return self.page.url

    def back(self):
        """Navigate back in browser history."""
        self.page.go_back()

    def forward(self):
        """Navigate forward in browser history."""
        self.page.go_forward()

    def reload(self):
        """Reload the current page."""
        self.page.reload()

    @property
    def url(self) -> str:
        return self.page.url

    @property
    def title(self) -> str:
        return self.page.title()

    # ------------------------------------------------------------------ #
    # Mouse interactions
    # ------------------------------------------------------------------ #

    def click(self, selector: str, button: str = "left", count: int = 1):
        """Click an element matching selector."""
        self.page.click(selector, button=button, click_count=count)

    def dblclick(self, selector: str):
        """Double-click an element."""
        self.page.dblclick(selector)

    def right_click(self, selector: str):
        """Right-click (context menu) an element."""
        self.page.click(selector, button="right")

    def hover(self, selector: str):
        """Hover over an element."""
        self.page.hover(selector)

    def click_xy(self, x: int, y: int, button: str = "left"):
        """Click at absolute page coordinates."""
        self.page.mouse.click(x, y, button=button)

    def move_mouse(self, x: int, y: int):
        """Move the mouse to absolute page coordinates."""
        self.page.mouse.move(x, y)

    def drag(self, source_selector: str, target_selector: str):
        """Drag an element to another element."""
        src = self.page.locator(source_selector)
        tgt = self.page.locator(target_selector)
        src.drag_to(tgt)

    def drag_xy(self, x1: int, y1: int, x2: int, y2: int):
        """Drag from one coordinate to another."""
        self.page.mouse.move(x1, y1)
        self.page.mouse.down()
        self.page.mouse.move(x2, y2)
        self.page.mouse.up()

    # ------------------------------------------------------------------ #
    # Keyboard interactions
    # ------------------------------------------------------------------ #

    def fill(self, selector: str, text: str):
        """Clear an input field and type text into it."""
        self.page.fill(selector, text)

    def type_text(self, selector: str, text: str, delay: int = 50):
        """Type text character-by-character (simulates a real user)."""
        self.page.type(selector, text, delay=delay)

    def press(self, key: str, selector: str = None):
        """Press a keyboard key (e.g. 'Enter', 'Tab', 'Escape', 'ArrowDown').
        If selector is given, focuses that element first.
        """
        if selector:
            self.page.focus(selector)
        self.page.keyboard.press(key)

    def key_down(self, key: str):
        """Hold a key down."""
        self.page.keyboard.down(key)

    def key_up(self, key: str):
        """Release a key."""
        self.page.keyboard.up(key)

    # ------------------------------------------------------------------ #
    # Scrolling
    # ------------------------------------------------------------------ #

    def scroll(self, x: int = 0, y: int = 500):
        """Scroll the page by (x, y) pixels."""
        self.page.mouse.wheel(x, y)

    def scroll_to_element(self, selector: str):
        """Scroll until an element is visible."""
        self.page.locator(selector).scroll_into_view_if_needed()

    def scroll_to_bottom(self):
        """Scroll to the very bottom of the page."""
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    def scroll_to_top(self):
        """Scroll to the top of the page."""
        self.page.evaluate("window.scrollTo(0, 0)")

    # ------------------------------------------------------------------ #
    # Form controls
    # ------------------------------------------------------------------ #

    def select_option(self, selector: str, value: str = None, label: str = None, index: int = None):
        """Select an option in a <select> element by value, label, or index."""
        if value is not None:
            self.page.select_option(selector, value=value)
        elif label is not None:
            self.page.select_option(selector, label=label)
        elif index is not None:
            self.page.select_option(selector, index=index)

    def check(self, selector: str):
        """Check a checkbox or radio button."""
        self.page.check(selector)

    def uncheck(self, selector: str):
        """Uncheck a checkbox."""
        self.page.uncheck(selector)

    def upload_file(self, selector: str, file_path: str):
        """Attach a file to a file-input element."""
        self.page.set_input_files(selector, file_path)

    # ------------------------------------------------------------------ #
    # Waiting
    # ------------------------------------------------------------------ #

    def wait_for_selector(self, selector: str, state: str = "visible", timeout: int = None):
        """Wait for an element to reach a given state ('visible', 'hidden', 'attached', 'detached')."""
        self.page.wait_for_selector(selector, state=state, timeout=timeout or self._timeout)

    def wait_for_url(self, pattern: str, timeout: int = None):
        """Wait for the URL to match a glob pattern or regex."""
        self.page.wait_for_url(pattern, timeout=timeout or self._timeout)

    def wait_for_load(self, state: str = "networkidle"):
        """Wait for the page to reach a load state ('load', 'domcontentloaded', 'networkidle')."""
        self.page.wait_for_load_state(state)

    def wait_ms(self, ms: int):
        """Wait for a fixed number of milliseconds."""
        self.page.wait_for_timeout(ms)

    # ------------------------------------------------------------------ #
    # Content extraction
    # ------------------------------------------------------------------ #

    def get_text(self, selector: str = "body") -> str:
        """Return the inner text of an element."""
        return self.page.inner_text(selector)

    def get_html(self, selector: str = "html") -> str:
        """Return the outer HTML of an element."""
        return self.page.locator(selector).evaluate("el => el.outerHTML")

    def get_attribute(self, selector: str, attr: str) -> str:
        """Return an attribute value from an element."""
        return self.page.get_attribute(selector, attr)

    def get_value(self, selector: str) -> str:
        """Return the current value of an input/textarea/select."""
        return self.page.input_value(selector)

    def get_all_links(self) -> list[dict]:
        """Return all hyperlinks on the page as [{text, href}]."""
        return self.page.evaluate("""
            () => Array.from(document.querySelectorAll('a[href]'))
                .map(a => ({ text: a.innerText.trim(), href: a.href }))
                .filter(l => l.href)
        """)

    def get_all_inputs(self) -> list[dict]:
        """Return all input/textarea/select elements and their current values."""
        return self.page.evaluate("""
            () => Array.from(document.querySelectorAll('input,textarea,select'))
                .map(el => ({
                    tag: el.tagName.toLowerCase(),
                    type: el.type || null,
                    name: el.name || null,
                    id: el.id || null,
                    placeholder: el.placeholder || null,
                    value: el.value
                }))
        """)

    def query_all(self, selector: str) -> list[str]:
        """Return inner text of all elements matching selector."""
        elements = self.page.locator(selector).all()
        return [el.inner_text() for el in elements]

    def count(self, selector: str) -> int:
        """Return the count of elements matching a selector."""
        return self.page.locator(selector).count()

    def is_visible(self, selector: str) -> bool:
        """Return True if the element is visible on screen."""
        return self.page.is_visible(selector)

    def is_enabled(self, selector: str) -> bool:
        """Return True if the element is enabled (not disabled)."""
        return self.page.is_enabled(selector)

    def get_page_info(self) -> dict:
        """Return a summary of the current page state."""
        return {
            "url": self.page.url,
            "title": self.page.title(),
            "links_count": len(self.get_all_links()),
            "inputs_count": len(self.get_all_inputs()),
        }

    # ------------------------------------------------------------------ #
    # JavaScript execution
    # ------------------------------------------------------------------ #

    def evaluate(self, js: str) -> Any:
        """Run JavaScript in the page context and return the result."""
        return self.page.evaluate(js)

    def evaluate_on_selector(self, selector: str, js: str) -> Any:
        """Run JavaScript on a specific element: el => el.textContent."""
        return self.page.eval_on_selector(selector, js)

    # ------------------------------------------------------------------ #
    # Screenshots & PDF
    # ------------------------------------------------------------------ #

    def screenshot(self, path: str = "screenshot.png", full_page: bool = False) -> str:
        """Take a screenshot. Returns the saved file path."""
        self.page.screenshot(path=path, full_page=full_page)
        return path

    def screenshot_element(self, selector: str, path: str = "element.png") -> str:
        """Screenshot a single element."""
        self.page.locator(selector).screenshot(path=path)
        return path

    def save_pdf(self, path: str = "page.pdf"):
        """Save the page as a PDF (only works in headless Chromium)."""
        self.page.pdf(path=path)
        return path

    # ------------------------------------------------------------------ #
    # Dialogs / alerts
    # ------------------------------------------------------------------ #

    def accept_dialog(self):
        """Auto-accept the next alert/confirm/prompt dialog."""
        self.page.on("dialog", lambda d: d.accept())

    def dismiss_dialog(self):
        """Auto-dismiss the next dialog."""
        self.page.on("dialog", lambda d: d.dismiss())

    # ------------------------------------------------------------------ #
    # Multi-tab management
    # ------------------------------------------------------------------ #

    def new_tab(self) -> Page:
        """Open a new tab and switch to it (returns the new Page)."""
        self.page = self._context.new_page()
        return self.page

    def switch_tab(self, index: int):
        """Switch to an existing tab by index."""
        pages = self._context.pages
        if index >= len(pages):
            raise IndexError(f"Tab index {index} out of range (have {len(pages)} tabs)")
        self.page = pages[index]

    @property
    def tab_count(self) -> int:
        return len(self._context.pages)

    def close_tab(self, index: int = None):
        """Close the current tab (or tab at index) and switch to the last remaining."""
        pages = self._context.pages
        target = pages[index] if index is not None else self.page
        target.close()
        remaining = self._context.pages
        if remaining:
            self.page = remaining[-1]

    # ------------------------------------------------------------------ #
    # Cookies & storage
    # ------------------------------------------------------------------ #

    def get_cookies(self) -> list[dict]:
        return self._context.cookies()

    def set_cookies(self, cookies: list[dict]):
        self._context.add_cookies(cookies)

    def clear_cookies(self):
        self._context.clear_cookies()

    def get_local_storage(self) -> dict:
        return self.page.evaluate("() => Object.assign({}, window.localStorage)")

    def set_local_storage(self, key: str, value: str):
        self.page.evaluate(f"() => window.localStorage.setItem({json.dumps(key)}, {json.dumps(value)})")

    # ------------------------------------------------------------------ #
    # Network interception
    # ------------------------------------------------------------------ #

    def intercept_requests(self, url_pattern: str, handler):
        """Intercept requests matching url_pattern. handler(route, request) -> route.continue_() or route.abort()."""
        self.page.route(url_pattern, handler)

    def block_resources(self, resource_types: list[str] = None):
        """Block resource types to speed up page loads. Default: ['image', 'font', 'media']."""
        types = set(resource_types or ["image", "font", "media"])
        self.page.route("**/*", lambda route: route.abort() if route.request.resource_type in types else route.continue_())

    # ------------------------------------------------------------------ #
    # Accessibility / ARIA helpers
    # ------------------------------------------------------------------ #

    def get_by_text(self, text: str) -> Locator:
        """Locate elements by their visible text."""
        return self.page.get_by_text(text)

    def get_by_role(self, role: str, name: str = None) -> Locator:
        """Locate elements by ARIA role (e.g. 'button', 'link', 'heading')."""
        return self.page.get_by_role(role, name=name)

    def get_by_label(self, label: str) -> Locator:
        """Locate form controls by their associated label text."""
        return self.page.get_by_label(label)

    def get_by_placeholder(self, placeholder: str) -> Locator:
        return self.page.get_by_placeholder(placeholder)

    def get_by_testid(self, test_id: str) -> Locator:
        return self.page.get_by_test_id(test_id)

    # ------------------------------------------------------------------ #
    # Convenience helpers
    # ------------------------------------------------------------------ #

    def find_and_click(self, text: str):
        """Click the first element containing the given visible text."""
        self.page.get_by_text(text).first.click()

    def search(self, input_selector: str, query: str, submit_selector: str = None):
        """Fill a search field and submit (press Enter or click submit button)."""
        self.fill(input_selector, query)
        if submit_selector:
            self.click(submit_selector)
        else:
            self.press("Enter", input_selector)

    def slow_scroll_to_bottom(self, step: int = 300, delay_ms: int = 200):
        """Scroll to bottom gradually, useful for lazy-loaded pages."""
        height = self.page.evaluate("document.body.scrollHeight")
        current = 0
        while current < height:
            current += step
            self.page.evaluate(f"window.scrollTo(0, {current})")
            self.wait_ms(delay_ms)
            height = self.page.evaluate("document.body.scrollHeight")

    def extract_table(self, selector: str = "table") -> list[list[str]]:
        """Extract all rows from an HTML table as a 2-D list of strings."""
        return self.page.evaluate(f"""
            () => Array.from(document.querySelector({json.dumps(selector)})
                ?.querySelectorAll('tr') ?? [])
                .map(row => Array.from(row.querySelectorAll('th,td'))
                    .map(cell => cell.innerText.trim()))
        """)

    def extract_list(self, selector: str) -> list[str]:
        """Extract all <li> inner texts from a list element."""
        return self.page.evaluate(f"""
            () => Array.from(document.querySelectorAll({json.dumps(selector + ' li')}))
                .map(li => li.innerText.trim())
        """)
