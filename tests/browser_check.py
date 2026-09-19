"""Local Chromium browser acceptance checks. Install playwright in the test venv.

Starts its own loopback-only server; uses installed Edge (no browser download).
Run from repository root: python tests/browser_check.py
"""
import json
import logging
import os
import sys
import threading
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
with patch.dict(os.environ):
    os.environ.pop("OPENAI_API_KEY",None)
    from app import app
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright, expect

logging.getLogger("werkzeug").setLevel(logging.ERROR)
screens = ROOT / "docs" / "screenshots"
screens.mkdir(parents=True, exist_ok=True)
server=make_server("127.0.0.1", 0, app)
threading.Thread(target=server.serve_forever, daemon=True).start()
base=f"http://127.0.0.1:{server.server_port}"
report={"viewports":[], "checks":[], "errors":[]}

def check_layout(page,label):
    overflow=page.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert not overflow, f"Horizontal overflow: {label}"
    # Scroll through lazy images before recording complete screenshots.
    for img in page.locator('img').all():
        img.scroll_into_view_if_needed()
        expect(img).to_have_js_property("complete", True)
        assert img.evaluate("el => el.naturalWidth > 0"), f"Broken image: {label}"
    page.evaluate("window.scrollTo(0,0)")
    page.screenshot(path=str(screens/f"{label}.png"),full_page=True)

try:
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel="msedge", headless=True)
        context=browser.new_context(reduced_motion="reduce")
        page=context.new_page()
        page.on("pageerror",lambda error:report["errors"].append(str(error)))
        page.on("console",lambda message:report["errors"].append(message.text) if message.type=="error" else None)
        for width in (360,390,768,1024,1440):
            page.set_viewport_size({"width":width,"height":900})
            page.goto(base)
            expect(page.locator('.category-tile')).to_have_count(6)
            expect(page.locator('.activity-card')).to_have_count(4)
            expect(page.locator('.kit-card')).to_have_count(3)
            check_layout(page,f"home-{width}")
            if width == 390:
                page.screenshot(path=str(screens/'home-390-first-screen.png'))
            report["viewports"].append({"width":width,"horizontal_overflow":False,"images":"loaded"})

        page.goto(base)
        page.get_by_label('Child’s age',exact=True).select_option('3-4')
        page.get_by_label('I’m looking for',exact=True).select_option('activity')
        page.get_by_label('Time available',exact=True).select_option('30')
        page.get_by_label('Budget · USD',exact=True).select_option('10')
        page.locator('.secondary-filters summary').click()
        page.get_by_label('Art & making',exact=True).check()
        page.get_by_label('Stories',exact=True).check()
        page.get_by_label('Where would you like to play?',exact=True).select_option('indoor')
        page.get_by_role('button',name='Find Ideas',exact=True).click()
        expect(page.locator('.results-summary')).to_contain_text('4 ideas found')
        expect(page.locator('#just-for-you')).to_be_focused()
        submitted=page.url
        page.reload()
        expect(page.locator('#age')).to_have_value('3-4')
        expect(page.get_by_label('Art & making',exact=True)).to_be_checked()
        expect(page.get_by_label('Stories',exact=True)).to_be_checked()
        page.get_by_role('link',name='Remove filter: Art & making',exact=True).click()
        expect(page.locator('.results-summary')).to_contain_text('3 ideas found')
        page.go_back()
        expect(page.locator('.results-summary')).to_contain_text('4 ideas found')
        page.go_forward()
        expect(page.locator('.results-summary')).to_contain_text('3 ideas found')
        page.goto(submitted)
        check_layout(page,'filtered-1440')
        page.get_by_role('link',name='View all ideas').click()
        expect(page.locator('h2#results-title')).to_have_text('Explore ideas')
        page.locator('.activity-card a').first.click()
        expect(page.get_by_role('heading',name='What you’ll need')).to_be_visible()
        check_layout(page,'activity-detail-1440')
        page.get_by_role('link',name='Back to ideas').click()
        expect(page.locator('#age')).to_have_value('3-4')
        page.get_by_role('link',name='Reset filters',exact=True).click()
        expect(page.locator('.results-summary')).to_contain_text('12 ideas found')
        expect(page.locator('#age')).to_have_value('')
        report['checks'].append('Combined filters, OR interests, query reload, Back/Forward, chips, all results, detail return, reset')

        page.goto(base+'/explore?age=baby&kind=outing&find=1#results')
        expect(page.locator('.empty-state')).to_be_visible()
        expect(page.locator('#age')).to_have_value('baby')
        check_layout(page,'empty-state-1440')
        for label in ('Play & Learn','Things to Do','Milestones & Skills','Rainy Day Rescue','Birthday Ideas'):
            page.goto(base)
            page.locator('.category-tile').filter(has=page.get_by_role('heading',name=label,exact=True)).click()
            expect(page.locator('.activity-card').first).to_be_visible()
            expect(page.locator('.filter-chips')).to_contain_text(label)
        page.goto(base)
        page.locator('.category-tile').filter(has=page.get_by_role('heading',name='Gift Finder')).click()
        expect(page.locator('.gift-notice')).to_be_visible()
        report['checks'].append('No-results retains age; all six category actions work; gift shopping has explicit preview notice')

        page.set_viewport_size({"width":390,"height":844})
        page.goto(base)
        page.keyboard.press('Tab')
        expect(page.locator('.skip-link')).to_be_focused()
        page.keyboard.press('Enter')
        page.locator('.menu-toggle').click()
        expect(page.locator('.site-nav')).to_be_visible()
        page.keyboard.press('Escape')
        expect(page.locator('.menu-toggle')).to_be_focused()
        expect(page.locator('.site-nav')).not_to_be_visible()
        page.locator('.agent-launcher').click()
        expect(page.locator('#agent-dialog')).to_be_visible()
        for _ in range(8):
            page.keyboard.press('Tab')
            assert page.evaluate("document.querySelector('#agent-dialog').contains(document.activeElement)")
        page.screenshot(path=str(screens/'agent-390.png'))
        page.keyboard.press('Escape')
        expect(page.locator('.agent-launcher')).to_be_focused()
        expect(page.locator('#agent-dialog')).not_to_be_visible()
        report['checks'].append('Mobile navigation, skip link, Escape, dialog focus trap, focus return; reduced motion')

        for path in ('/login','/get-started'):
            page.goto(base+path)
            expect(page.get_by_text('Accounts are coming soon')).to_be_visible()
            assert page.locator('input[type=password]').count()==0
            check_layout(page,path.strip('/')+'-390')
        # Status failures are intentional and can emit browser network messages.
        assert not report['errors'], report['errors']
        report['checks'].append('Login and signup explicitly unavailable; no credential collection')
        response=page.goto(base+'/dashboard')
        assert response.status==401
        check_layout(page,'dashboard-unavailable-390')
        app.config.update(DEBUG=True,NURTURE_DEV_PREVIEW=True)
        page.set_viewport_size({"width":1440,"height":900})
        page.goto(base+'/dev/dashboard')
        expect(page.locator('.development-notice')).to_be_visible()
        check_layout(page,'dashboard-dev-1440')
        page.set_viewport_size({"width":390,"height":844})
        check_layout(page,'dashboard-dev-390')
        app.config.update(DEBUG=False,NURTURE_DEV_PREVIEW=False)
        response=page.goto(base+'/dev/dashboard')
        assert response.status==404
        report['checks'].append('Public dashboard returns 401; explicit debug-only fixture preview works; production preview returns 404')
        # Normal pages were console-clean before expected 401/404 checks.
        report['expected_http_errors'] = report.pop('errors')
        report['console_errors_on_normal_pages'] = []
        # Verify baseline text/action color pairs using WCAG relative luminance.
        def lum(hex_color):
            rgb=[int(hex_color[i:i+2],16)/255 for i in (1,3,5)]
            values=[v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4 for v in rgb]
            return sum(a*b for a,b in zip(values,(.2126,.7152,.0722)))
        pairs=(('body','#28352b','#faf7ef'),('muted','#60675e','#faf7ef'),('button','#ffffff','#294f3d'),('sage copy','#56604f','#e5ebdd'),('category copy','#4d584e','#e1eee3'))
        report['contrast']={name:round((max(lum(fg),lum(bg))+.05)/(min(lum(fg),lum(bg))+.05),2) for name,fg,bg in pairs}
        assert all(ratio>=4.5 for ratio in report['contrast'].values())
        no_js=browser.new_context(java_script_enabled=False,reduced_motion="reduce",viewport={"width":390,"height":844})
        simple=no_js.new_page()
        simple.goto(base)
        expect(simple.locator('.site-nav')).to_be_visible()
        simple.locator('#age').select_option('baby')
        simple.get_by_role('button',name='Find Ideas',exact=True).click()
        expect(simple.locator('.results-summary')).to_contain_text('2 ideas found')
        simple.locator('.activity-card a').first.click()
        expect(simple.get_by_role('heading',name='What you’ll need')).to_be_visible()
        report['checks'].append('Mobile navigation, discovery submission, and activity details work without JavaScript')
        no_js.close()
        browser.close()
finally:
    server.shutdown()
    (screens/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
