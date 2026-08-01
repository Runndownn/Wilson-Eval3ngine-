#!/usr/bin/env python3
"""Comprehensive E2E test: chart generation, deletion, sample separation, modal close."""
import json
import requests
from playwright.sync_api import sync_playwright

GUI_URL = "http://127.0.0.1:8080"

def test_comprehensive():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        all_console = []
        page_errors = []
        page.on("console", lambda msg: all_console.append(f"[console:{msg.type}] {msg.text}"))
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        # 1. Load page
        page.goto(GUI_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        print("[1] Page loaded")

        # 2. Click Charts tab and verify gallery
        page.click("text=Charts")
        page.wait_for_timeout(3000)

        run_sections = page.eval_on_selector_all(".chart-run-section", """els => els.map(el => ({
            runId: el.dataset.runId,
            isSample: el.dataset.isSample === 'true',
            hasSampleClass: el.classList.contains('chart-run-section-sample'),
            cardCount: el.querySelectorAll('.chart-card').length
        }))""")
        print(f"[2] Run sections: {json.dumps(run_sections, indent=2)}")

        # 3. Wait for gallery to populate if empty (auto-generation takes time)
        if not run_sections:
            print("    Gallery empty, waiting for auto-generation...")
            page.wait_for_function(
                "document.querySelectorAll('.chart-run-section').length > 0",
                timeout=60000
            )
            page.wait_for_timeout(3000)
            run_sections = page.eval_on_selector_all(".chart-run-section", """els => els.map(el => ({
                runId: el.dataset.runId,
                isSample: el.dataset.isSample === 'true',
                cardCount: el.querySelectorAll('.chart-card').length
            }))""")
            print(f"    After wait: {json.dumps(run_sections, indent=2)}")

        # 4. Test Generate Charts button
        print("\n[3] Testing Generate Charts button...")
        page.click("#generate-charts-btn")
        page.wait_for_timeout(12000)

        gen_status = page.eval_on_selector("#charts-status-text", "el => el.textContent || ''")
        print(f"    Status: {gen_status}")

        after_gen = page.eval_on_selector_all(".chart-run-section", """els => els.map(el => ({
            runId: el.dataset.runId,
            isSample: el.dataset.isSample === 'true',
            cardCount: el.querySelectorAll('.chart-card').length
        }))""")
        print(f"    After generation: {json.dumps(after_gen, indent=2)}")

        # Verify no sample charts mixed with real charts
        sample_runs = [r for r in run_sections if r.get("isSample")]
        real_runs = [r for r in run_sections if not r.get("isSample")]
        print(f"    Sample runs: {len(sample_runs)}, Real runs: {len(real_runs)}")

        # 5. Test chart modal close (X button, Esc)
        print("\n[4] Testing chart modal close...")
        first_card = page.locator(".chart-card").first
        if first_card.count() > 0:
            first_card.click()
            page.wait_for_timeout(1000)

            modal = page.locator("#chart-modal")
            modal_visible = modal.evaluate("el => el.style.display !== 'none' && el.classList.contains('active')")
            print(f"    Modal visible after click: {modal_visible}")

            # Test Esc key
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            modal_visible_after_esc = modal.evaluate("el => el.style.display !== 'none' && el.classList.contains('active')")
            print(f"    Modal visible after Esc: {modal_visible_after_esc}")

            # Reopen and test X button
            first_card.click()
            page.wait_for_timeout(1000)
            page.click("#chart-modal .chart-modal-close")
            page.wait_for_timeout(500)
            modal_visible_after_x = modal.evaluate("el => el.style.display !== 'none' && el.classList.contains('active')")
            print(f"    Modal visible after X button: {modal_visible_after_x}")

        # 6. Test run deletion + Refresh persistence
        print("\n[5] Testing run deletion + Refresh persistence...")
        non_sample_sections = page.locator(".chart-run-section:not(.chart-run-section-sample)")
        section_count = non_sample_sections.count()
        print(f"    Non-sample sections: {section_count}")

        if section_count > 0:
            first_non_sample = non_sample_sections.first
            run_id = first_non_sample.get_attribute("data-run-id")
            print(f"    Deleting run: {run_id}")

            del_btn = first_non_sample.locator(".chart-run-delete-all")
            del_btn.click()
            page.wait_for_timeout(2000)

            sections_after_delete = page.eval_on_selector_all(".chart-run-section", "els => els.length")
            print(f"    Sections after delete: {sections_after_delete}")

            # Verify via REST API
            resp = requests.get(f"{GUI_URL}/api/charts/runs")
            remaining_runs = [r['runId'] for r in resp.json()['runs']]
            print(f"    REST API runs after delete: {remaining_runs}")
            print(f"    Deleted run in REST API: {run_id in remaining_runs}")

            # Click Refresh
            print(f"    Clicking Refresh...")
            page.click("#refresh-charts-btn")
            page.wait_for_timeout(3000)

            sections_after_refresh = page.eval_on_selector_all(".chart-run-section", "els => els.length")
            # Check if the SPECIFIC deleted run reappeared
            deleted_resurrected = any(r['runId'] == run_id for r in (resp.json().get('runs', []) if resp.status_code == 200 else []))
            # Also check on disk
            import os
            deleted_on_disk = os.path.exists(f"/mnt/geezer-venvs/work/Wilson-Eval3ngine/gui/static/charts/{run_id}")
            print(f"    Sections after Refresh: {sections_after_refresh}")
            print(f"    Deleted run ({run_id}) in REST API: {run_id in remaining_runs}")
            print(f"    Deleted run ({run_id}) directory on disk: {deleted_on_disk}")

            # Check no sample charts mixed with real
            sample_after = page.locator(".chart-run-section-sample").count()
            real_after = page.locator(".chart-run-section:not(.chart-run-section-sample)").count()
            print(f"    After refresh - Sample sections: {sample_after}, Real sections: {real_after}")

        # 7. Final error check
        page_errors_filtered = [e for e in page_errors if 'PDF' not in str(e)]
        console_errors = [e for e in all_console if '[console:error]' in e and 'PDF' not in str(e) and 'Failed to load' not in str(e)]
        print(f"\n[FINAL] Page errors (non-PDF): {page_errors_filtered[:5]}")
        print(f"  Console errors (non-PDF/non-404): {console_errors[:5]}")

        browser.close()

if __name__ == "__main__":
    test_comprehensive()
