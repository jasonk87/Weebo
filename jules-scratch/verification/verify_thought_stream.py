from playwright.sync_api import sync_playwright, Page, expect
import re

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Navigate to the frontend server
        page.goto("http://localhost:8080")

        # 2. Send a message that will trigger tool use
        user_input = page.get_by_placeholder("Type your message...")
        user_input.fill("Remember my name is Jules")
        page.get_by_role("button", name="Send").click()

        # 3. Wait for the "Thinking..." container to appear
        thoughts_container = page.locator(".thoughts-container")
        expect(thoughts_container).to_be_visible(timeout=10000)

        # 4. Wait for the thought content to appear
        # We expect to see the thought about executing the save_fact tool
        thought_content = thoughts_container.locator(".thoughts-content")
        expect(thought_content).to_contain_text(re.compile("Executing tool: save_fact"), timeout=10000)

        # 5. Take a screenshot showing the thoughts
        page.screenshot(path="jules-scratch/verification/thought-stream.png")

        browser.close()

if __name__ == "__main__":
    run()
