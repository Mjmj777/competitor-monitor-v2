"""Static consistency guard for the Competitor Intelligence Monitor release."""
from __future__ import annotations
import json,re,sys,zipfile
from pathlib import Path

BASE=Path(__file__).resolve().parent
ERRORS=[]
def fail(msg): ERRORS.append(msg)

required=[
    'index.html','competitor.html','item.html','monitor.py','enhance.py','export_excel.py','config.json','requirements.txt',
    'competitor_campaigns_template.xlsx','inventory.json','manual_overrides.json','assets/common.js','assets/index.js','assets/competitor.js','assets/item.js','assets/styles.css'
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
            if not s.get('require_detail_link',False): fail(f"{c.get('id')}: website source must require a detail link")
            urls.append(s.get('url'))
        urls.extend(feeds.values())
    if len(urls)!=30: fail(f'Expected 30 discovery sources, found {len(urls)}')
    if len(set(urls))!=len(urls): fail('Duplicate discovery source URLs found in config.json')
except Exception as exc: fail(f'config.json invalid: {exc}')

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
    with zipfile.ZipFile(BASE/'competitor_campaigns_template.xlsx') as z:
        if 'xl/workbook.xml' not in z.namelist(): fail('Excel template is not a valid XLSX workbook')
except Exception as exc: fail(f'Excel template invalid: {exc}')

ui='\n'.join((BASE/f).read_text(encoding='utf-8',errors='ignore') for f in ['index.html','competitor.html','item.html','assets/index.js','assets/competitor.js','assets/item.js'])
for term in ['activity score','campaign strength score','promotion score','market score']:
    if term in ui.casefold(): fail(f'User-facing scoring term found: {term}')

if ERRORS:
    print('PRE-FLIGHT FAILED')
    for x in ERRORS: print(' -',x)
    sys.exit(1)
print('PRE-FLIGHT OK: project files, UI bindings, language, sources and Excel template are consistent.')
