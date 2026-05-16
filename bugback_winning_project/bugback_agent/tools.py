from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from .models import BrowserEvidence, ComplaintPlan


class DataTools:
    def __init__(self, logs_path="data/system_logs.json", flags_path="data/feature_flags.json"):
        self.logs_path = Path(logs_path)
        self.flags_path = Path(flags_path)

    def read_logs(self) -> List[Dict[str, Any]]:
        return json.loads(self.logs_path.read_text(encoding="utf-8"))

    def read_feature_flags(self) -> List[Dict[str, Any]]:
        return json.loads(self.flags_path.read_text(encoding="utf-8"))

    def search_logs(self, area: str) -> List[Dict[str, Any]]:
        return [log for log in self.read_logs() if log.get("area") == area]

    def search_flags(self, area: str) -> List[Dict[str, Any]]:
        return [flag for flag in self.read_feature_flags() if flag.get("area") == area and flag.get("enabled")]


class BrowserReproductionTool:
    def __init__(self, base_url="http://127.0.0.1:5001", screenshot_dir="outputs/screenshots"):
        self.base_url = base_url.rstrip("/")
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def run(self, plan: ComplaintPlan) -> BrowserEvidence:
        if plan.affected_area == "checkout":
            return self._test_discount_disappears(plan)
        if plan.affected_area == "payments":
            return self._test_duplicate_charge(plan)
        if plan.affected_area == "frontend":
            return self._test_cart_freeze(plan)
        return BrowserEvidence(
            verified=False,
            bug_type=plan.issue_type,
            steps=["No browser reproduction tool exists for this issue type yet."],
            observations=["Escalation required: unknown issue category."],
        )

    def _test_discount_disappears(self, plan: ComplaintPlan) -> BrowserEvidence:
        steps, obs = [], []
        screenshot = str(self.screenshot_dir / "discount_bug.png")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"{self.base_url}/reset")
            steps.append("Opened demo store and reset session.")
            page.click("#add-to-cart")
            steps.append("Added product to cart.")
            page.fill("#discount-code", plan.test_data.get("discount_code", "SAVE20"))
            page.click("#apply-discount")
            steps.append("Applied discount code SAVE20 in cart.")
            cart_total = page.locator("#cart-total").inner_text()
            discount_line = page.locator("#discount-line").inner_text()
            obs.append(f"Cart before checkout: {discount_line}; {cart_total}")
            page.click("#checkout-link")
            steps.append("Proceeded to checkout.")
            checkout_total = page.locator("#checkout-total").inner_text()
            checkout_discount = page.locator("#checkout-discount").inner_text()
            obs.append(f"Checkout page: {checkout_discount}; {checkout_total}")
            page.screenshot(path=screenshot, full_page=True)
            browser.close()
        verified = "80" in cart_total and "100" in checkout_total and "missing" in checkout_discount.lower()
        return BrowserEvidence(verified=verified, bug_type="discount_disappears", steps=steps, observations=obs, screenshot_path=screenshot)

    def _test_duplicate_charge(self, plan: ComplaintPlan) -> BrowserEvidence:
        steps, obs = [], []
        screenshot = str(self.screenshot_dir / "duplicate_charge_bug.png")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"{self.base_url}/reset")
            steps.append("Opened demo store and reset session.")
            page.click("#add-to-cart")
            steps.append("Added product to cart.")
            page.click("#checkout-link")
            steps.append("Moved to checkout.")
            page.click("#pay-button")
            steps.append("Submitted payment one time.")
            charge_count = page.locator("#charge-count").inner_text()
            payment_message = page.locator("#payment-message").inner_text()
            obs.append(f"Confirmation page: {charge_count}; {payment_message}")
            page.screenshot(path=screenshot, full_page=True)
            browser.close()
        verified = "2" in charge_count or "twice" in payment_message.lower()
        return BrowserEvidence(verified=verified, bug_type="duplicate_charge", steps=steps, observations=obs, screenshot_path=screenshot)

    def _test_cart_freeze(self, plan: ComplaintPlan) -> BrowserEvidence:
        steps, obs = [], []
        screenshot = str(self.screenshot_dir / "cart_freeze_bug.png")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"{self.base_url}/reset")
            steps.append("Opened demo store and reset session.")
            page.click("#open-cart")
            steps.append("Clicked Open cart drawer.")
            page.wait_for_timeout(800)
            overlay_visible = page.locator("#freeze").is_visible()
            flag_value = page.evaluate("() => Boolean(window.__BUGBACK_FRONTEND_FREEZE__)")
            obs.append(f"Freeze overlay visible: {overlay_visible}")
            obs.append(f"Frontend freeze flag set: {flag_value}")
            page.screenshot(path=screenshot, full_page=True)
            browser.close()
        verified = bool(overlay_visible and flag_value)
        return BrowserEvidence(verified=verified, bug_type="cart_freeze", steps=steps, observations=obs, screenshot_path=screenshot)
