from playwright.sync_api import sync_playwright, Page, expect
import re

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto("http://localhost:8080", timeout=20000)

        # Wait for the page to be ready
        expect(page.get_by_placeholder("Type your message...")).to_be_visible(timeout=10000)

        # Send a message
        user_input = page.get_by_placeholder("Type your message...")
        user_input.fill("Hello, world!")
        page.get_by_role("button", name="Send").click()

        # Wait for the bot's response message to appear
        bot_message = page.locator(".bot-message .answer-container")
        expect(bot_message).to_be_visible(timeout=10000)

        # Take the screenshot
        page.screenshot(path="jules-scratch/verification/new_ui.png")

        browser.close()

if __name__ == "__main__":
    run()
