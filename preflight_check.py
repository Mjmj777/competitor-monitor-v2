"""Static consistency guard for the Competitor Intelligence Monitor release."""
from __future__ import annotations
import json,re,sys,zipfile
from pathlib import Path

BASE=Path(__file__).resolve().parent
ERRORS=[]
def fail(msg): ERRORS.append(msg)

required=[
    'index.html','competitor.html','item.html','monitor.py','enhance.py','export_excel.py','preflight_check.py','postflight_check.py','config.json','requirements.txt',
    'competitor_campaigns_template.xlsx','inventory.json','manual_overrides.json','.github/workflows/monitor.yml','assets/common.js','assets/index.js','assets/competitor.js','assets/item.js','assets/styles.css'
]
for name in required:
    if not (BASE/name).exists(): fail(f'Missing required file: {name}')

try:
    config=json.loads((BASE/'config.json').read_text(encoding='utf-8'))
    comps=config.get('competitors',[])
    if len(comps)!=6: fail(f'Expected 6 competitors, found {len(comps)}')
    urls=[]
    for c in comps:
        feeds=c.get('social_feeds',{})
        if set(feeds)!={'instagram','facebook','x','tiktok'}: fail(f"{c.get('id')}: social feeds must contain instagram/facebook/x/tiktok")
        sites=c.get('website_sources',[])
        if not sites: fail(f"{c.get('id')}: missing official website source")
        for s in sites:
            if s.get('discovery_mode')!='modal' and not s.get('require_detail_link',False): fail(f"{c.get('id')}: website source must require a detail link unless it uses verified modal discovery")
            urls.append(s.get('url'))
        urls.extend(feeds.values())
    if len(urls)!=30: fail(f'Expected 30 discovery sources, found {len(urls)}')
    if len(set(urls))!=len(urls): fail('Duplicate discovery source URLs found in config.json')
except Exception as exc: fail(f'config.json invalid: {exc}')


# Browser fallback guard: JS-heavy sources require Playwright + Chromium in the workflow.
try:
    req=(BASE/'requirements.txt').read_text(encoding='utf-8').casefold()
    wf=(BASE/'.github/workflows/monitor.yml').read_text(encoding='utf-8').casefold()
    fallback=[c.get('id') for c in config.get('competitors',[]) for src in c.get('website_sources',[]) if src.get('browser_fallback')]
    if fallback and 'playwright' not in req: fail('requirements.txt: Playwright is required for browser-fallback sources')
    if fallback and 'playwright install' not in wf: fail('Workflow must install a Playwright browser for browser-fallback sources')
    tiq=next((c for c in config.get('competitors',[]) if c.get('id')=='tiqmo'),None)
    if tiq:
        tsrc=(tiq.get('website_sources') or [{}])[0]
        if tsrc.get('discovery_mode')!='modal': fail('tiqmo source must use modal discovery')
        if tsrc.get('require_detail_link'): fail('tiqmo modal source must not require a separate detail URL')
        if '/en/offers' not in str(tsrc.get('url','')): fail('tiqmo modal parser must use the English official offers page')
    mob=next((c for c in config.get('competitors',[]) if c.get('id')=='mobily-pay'),None)
    if mob:
        src=(mob.get('website_sources') or [{}])[0]
        if '/ar/offers.html' not in str(src.get('url','')): fail('Mobily Pay official offers source must use the Arabic offers index')
        if not src.get('expired_headings'): fail('Mobily Pay source must define expired-offer headings to exclude historical cards')
except Exception as exc: fail(f'Browser/source parser guard failed: {exc}')

# Deterministic parser/date regression checks.
try:
    import monitor as _monitor
    import enhance as _enhance
    samples=[
        ('يسري العرض من 1 أغسطس حتى 31 أكتوبر2026.', '2026-08-01', '2026-10-31'),
        ('The campaign runs from 19 August 2026 to 19 October 2026', '2026-08-19', '2026-10-19'),
        ('Validity December 31, 2026', None, '2026-12-31'),
        ('The offer is valid from May 1, 2026, at 12:00 AM until December 31, 2026, at 11:59 PM, KSA time.', '2026-05-01', '2026-12-31'),
    ]
    for text,exp_start,exp_end in samples:
        st,en,_=_enhance.extract_dates_from_text(text)
        if exp_start and not str(st or '').startswith(exp_start): fail(f'Date parser missed start date: {text}')
        if exp_end and not str(en or '').startswith(exp_end): fail(f'Date parser missed end date: {text}')
    mob=next(c for c in config.get('competitors',[]) if c.get('id')=='mobily-pay')
    src=(mob.get('website_sources') or [{}])[0]
    fixture='<h2>تعرّف على أحدث العروض المتاحة</h2><div><h3>عرض حالي</h3><a href="/ar/offers/offer-56.html">استكشف المزيد</a></div><h3>العروض المنتهية</h3><div><h3>عرض قديم</h3><a href="/ar/offers/offer-1.html">استكشف المزيد</a></div>'
    rows,_=_monitor.extract_website_candidates(fixture,mob,src,config,'test')
    titles={r.get('title') for r in rows}
    if 'عرض حالي' not in titles or 'عرض قديم' in titles: fail('Mobily Pay parser mixed expired offers into current discovery')

    # Requests may assume Latin-1 when a UTF-8 page omits charset= from its
    # Content-Type. The collector must preserve Arabic in that exact scenario.
    class _Utf8Response:
        content='عرض حالي من موبايلي باي'.encode('utf-8')
        headers={'Content-Type':'text/html'}
        apparent_encoding='utf-8'
        encoding='ISO-8859-1'
    if _monitor.response_text(_Utf8Response())!='عرض حالي من موبايلي باي':
        fail('UTF-8 HTML without an HTTP charset was decoded as Latin-1')

    # tiqmo regression: multiple different campaigns intentionally share the same generic /offers URL.
    tiq_generic='https://tiqmo.com/en/offers'
    sample=[
        {'id':'campaign:tiqmo:5','competitor_id':'tiqmo','source_type':'inventory','content_type':'campaign','campaign_category':'card','title':'Zero International Card Transaction Fees','link':tiq_generic,'official_campaign_page_url':tiq_generic},
        {'id':'campaign:tiqmo:6','competitor_id':'tiqmo','source_type':'inventory','content_type':'campaign','campaign_category':'card','title':'SAR 250,000 Spend & Win Campaign','link':tiq_generic,'official_campaign_page_url':tiq_generic},
        {'id':'post:tiqmo:x:test','competitor_id':'tiqmo','source_type':'social','content_type':'social_post','campaign_id':'campaign:tiqmo:6'}
    ]
    deduped=_monitor.deduplicate_campaign_records(sample,config)
    ids={r.get('id') for r in deduped}
    if not {'campaign:tiqmo:5','campaign:tiqmo:6'}.issubset(ids): fail('tiqmo generic offers URL incorrectly merged distinct campaigns')
    post=next((r for r in deduped if r.get('id')=='post:tiqmo:x:test'),{})
    if post.get('campaign_id')!='campaign:tiqmo:6': fail('tiqmo campaign reference changed while distinct campaigns share the generic offers URL')

    # True duplicates with a unique campaign URL must merge and redirect linked posts.
    duplicate=[
        {'id':'campaign:test','competitor_id':'stc-bank','source_type':'inventory','content_type':'campaign','campaign_category':'card','title':'Reference Test Offer','link':'https://stcbank.com.sa/en/w/reference-test','official_campaign_page_url':'https://stcbank.com.sa/en/w/reference-test'},
        {'id':'detected:test','competitor_id':'stc-bank','source_type':'website','content_type':'campaign','campaign_category':'card','title':'Reference Test Offer','link':'https://www.stcbank.com.sa/en/w/reference-test','official_campaign_page_url':'https://www.stcbank.com.sa/en/w/reference-test'},
        {'id':'post:test','competitor_id':'stc-bank','source_type':'social','content_type':'social_post','campaign_id':'detected:test'}
    ]
    fixed=_monitor.deduplicate_campaign_records(duplicate,config)
    ids={r.get('id') for r in fixed}; post=next((r for r in fixed if r.get('id')=='post:test'),{})
    if 'campaign:test' not in ids or 'detected:test' in ids or post.get('campaign_id')!='campaign:test': fail('Campaign dedup did not repair linked campaign_id references')
except Exception as exc: fail(f'Parser/date regression check failed: {exc}')

# English must be the initial language; the UI may persist the user's later choice.
for name in ['index.html','competitor.html','item.html']:
    try:
        txt=(BASE/name).read_text(encoding='utf-8')
        if 'lang="en"' not in txt or 'dir="ltr"' not in txt: fail(f'{name}: initial HTML language must be English/LTR')
    except Exception as exc: fail(f'{name}: {exc}')

try:
    common=(BASE/'assets/common.js').read_text(encoding='utf-8')
    if '||"en"' not in common: fail('assets/common.js: English is not the default language')
    block=common.split('const language=')[0]
    i18n=set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*:',block))
    used=set()
    ui_files=list(BASE.glob('*.html'))+list((BASE/'assets').glob('*.js'))
    for f in ui_files:
        text=f.read_text(encoding='utf-8',errors='ignore')
        used.update(re.findall(r'data-i18n(?:-placeholder)?=["\']([^"\']+)',text))
        used.update(re.findall(r'\bt\(["\']([^"\']+)',text))
    missing=sorted(used-i18n)
    if missing: fail('Missing i18n keys: '+', '.join(missing))
except Exception as exc: fail(f'i18n check failed: {exc}')

for page,js in [('index.html','assets/index.js'),('competitor.html','assets/competitor.js'),('item.html','assets/item.js')]:
    try:
        html=(BASE/page).read_text(encoding='utf-8'); code=(BASE/js).read_text(encoding='utf-8')
        ids=set(re.findall(r'id=["\']([^"\']+)',html))
        refs=set(re.findall(r'(?:getElementById|byId)\(["\']([^"\']+)',code))
        missing=sorted(refs-ids)
        if missing: fail(f'{js} references missing {page} IDs: '+', '.join(missing))
    except Exception as exc: fail(f'{page}/{js} DOM check failed: {exc}')

try:
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(BASE/'competitor_campaigns_template.xlsx') as z:
        if 'xl/workbook.xml' not in z.namelist():
            fail('Excel template is not a valid XLSX workbook')
        else:
            ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            wb=ET.fromstring(z.read('xl/workbook.xml'))
            sheets=len(wb.findall('.//m:sheet',ns))
            formulas=0
            for name in z.namelist():
                if name.startswith('xl/worksheets/sheet') and name.endswith('.xml'):
                    formulas += len(ET.fromstring(z.read(name)).findall('.//m:f',ns))
            tables=len([name for name in z.namelist() if name.startswith('xl/tables/table') and name.endswith('.xml')])
            if sheets!=8: fail(f'Excel template structure changed: expected 8 sheets, found {sheets}')
            if tables!=6: fail(f'Excel template structure changed: expected 6 tables, found {tables}')
            if formulas!=1331: fail(f'Excel template formulas changed: expected 1331, found {formulas}')
except Exception as exc: fail(f'Excel template invalid: {exc}')

# The deployed workflow must run semantic validation after enrichment and before Excel/deploy.
try:
    wf=(BASE/'.github/workflows/monitor.yml').read_text(encoding='utf-8')
    pos_enhance=wf.find('python enhance.py')
    pos_post=wf.find('python postflight_check.py')
    pos_export=wf.find('python export_excel.py')
    if min(pos_enhance,pos_post,pos_export)<0 or not (pos_enhance < pos_post < pos_export):
        fail('Workflow must run enhance.py -> postflight_check.py -> export_excel.py in this order')
    if 'cron: "0 * * * *"' not in wf and "cron: '0 * * * *'" not in wf:
        fail('Workflow schedule must run once per hour')
    if 'workflow_dispatch:' not in wf or 'python monitor.py --competitor "$TARGET_COMPETITOR"' not in wf:
        fail('Workflow manual competitor input is not connected to monitor.py')
    if 'python enhance.py --competitor "$TARGET_COMPETITOR"' not in wf:
        fail('Workflow manual competitor input is not connected to enhance.py')
    if 'cancel-in-progress: true' in wf:
        fail('Manual refreshes must queue instead of cancelling a running monitor job')
    detail_interval=float(config.get('settings',{}).get('detail_verification_interval_hours',99))
    if not (1 <= detail_interval <= 6):
        fail('Stable offer detail verification interval must be between 1 and 6 hours')
    if float(config.get('settings',{}).get('detail_verification_missing_date_hours',99)) > 2:
        fail('Offers missing dates must be rechecked within 2 hours')
    if int(config.get('settings',{}).get('max_detail_checks_per_run',999)) > 30:
        fail('max_detail_checks_per_run is too high for the hourly workflow')
except Exception as exc: fail(f'Workflow consistency check failed: {exc}')

# Manual refresh controls must be Admin-only in the UI and include both scoped/all runs.
try:
    idx=(BASE/'index.html').read_text(encoding='utf-8')
    competitor=(BASE/'competitor.html').read_text(encoding='utf-8')
    common=(BASE/'assets/common.js').read_text(encoding='utf-8')
    indexjs=(BASE/'assets/index.js').read_text(encoding='utf-8')
    competitorjs=(BASE/'assets/competitor.js').read_text(encoding='utf-8')
    if 'id="refresh-all"' not in idx or 'data-admin-only hidden' not in idx:
        fail('Admin refresh-all control is missing from index.html')
    if 'id="refresh-competitor"' not in competitor or 'data-admin-only hidden' not in competitor:
        fail('Admin competitor refresh control is missing from competitor.html')
    if '/__refresh' not in common or 'if(!isAdmin())return false' not in common:
        fail('Client refresh helper is missing its Admin guard')
    if 'triggerRefresh("all"' not in indexjs or 'triggerRefresh(comp.id' not in indexjs:
        fail('Home page must support refresh-all and per-competitor refresh')
    if 'triggerRefresh(state.competitor.id' not in competitorjs:
        fail('Competitor page scoped refresh is not connected')
except Exception as exc: fail(f'Admin manual-refresh guard failed: {exc}')

# Verification timestamps/timing are operational metadata and must be admin-only.
try:
    idx=(BASE/'index.html').read_text(encoding='utf-8')
    itemjs=(BASE/'assets/item.js').read_text(encoding='utf-8')
    indexjs=(BASE/'assets/index.js').read_text(encoding='utf-8')
    if 'id="last-check" class="meta-chip" data-admin-only hidden' not in idx:
        fail('Global verification timestamp must be admin-only')
    if 'if (C.isAdmin())' not in itemjs or 'lastReviewed' not in itemjs:
        fail('Item verification timestamps must be guarded by admin role')
    if 'detail_verification_stats' not in indexjs:
        fail('Admin verification timing display is missing')
except Exception as exc: fail(f'Admin verification-time guard failed: {exc}')

# Client fallback is intentional: stale backend zeros must never hide known direct social links.
try:
    itemjs=(BASE/'assets/item.js').read_text(encoding='utf-8')
    commonjs=(BASE/'assets/common.js').read_text(encoding='utf-8')
    if 'function socialMetrics' not in itemjs: fail('assets/item.js: social analytics fallback is missing')
    if 'knownSocialCount' not in commonjs: fail('assets/common.js: campaign-card social fallback is missing')
except Exception as exc: fail(f'Social analytics UI guard failed: {exc}')

ui='\n'.join((BASE/f).read_text(encoding='utf-8',errors='ignore') for f in ['index.html','competitor.html','item.html','assets/index.js','assets/competitor.js','assets/item.js'])
for term in ['activity score','campaign strength score','promotion score','market score']:
    if term in ui.casefold(): fail(f'User-facing scoring term found: {term}')

if ERRORS:
    print('PRE-FLIGHT FAILED')
    for x in ERRORS: print(' -',x)
    sys.exit(1)
print('PRE-FLIGHT OK: project files, UI bindings, language, sources and Excel template are consistent.')
