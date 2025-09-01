import re
from playwright.sync_api import sync_playwright, Page, expect

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto("http://localhost:8080")

        # Wait for the page to be ready by looking for the input field
        user_input = page.get_by_placeholder("Type your message...")
        expect(user_input).to_be_visible(timeout=10000)

        # Send a message that will trigger tool use and thoughts
        user_input.fill("My name is Jules. Please remember that.")
        page.get_by_role("button", name="Send").click()

        # Wait for the "Thinking..." container to appear
        thoughts_container = page.locator(".thoughts-container")
        expect(thoughts_container).to_be_visible(timeout=10000)

        # Wait for some text to appear in the thoughts content
        thoughts_content = page.locator(".thoughts-content pre code")
        expect(thoughts_content).to_have_text(re.compile(r".+"), timeout=10000) # Wait for any text

        # Take the screenshot
        page.screenshot(path="jules-scratch/verification/thought_streaming.png")

        browser.close()

if __name__ == "__main__":
    run()
