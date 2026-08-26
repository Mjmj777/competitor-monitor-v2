"""Semantic validation of generated competitor-monitor data after monitor.py + enhance.py."""
from __future__ import annotations
import json, re, sys, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urlencode

BASE=Path(__file__).resolve().parent
DATA=BASE/'data.json'; CONFIG=BASE/'config.json'
errors=[]; warnings=[]
def fail(x): errors.append(x)
def warn(x): warnings.append(x)

SOCIAL_HOSTS=("instagram.com","facebook.com","m.facebook.com","x.com","twitter.com","tiktok.com")
DIAC=re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
STOP={"offer","offers","campaign","campaigns","promotion","promotions","promo","deal","deals","عرض","عروض","حملة","حملات"}
LOGIN_MARKERS=("instagram تسجيل الدخول","instagram log in","log into instagram","instagram from meta","meta verified","تحميل جهات الاتصال وغير المستخدمين")

def norm_title(v):
    s=unicodedata.normalize('NFKC',str(v or '')).casefold().replace('ـ','');s=DIAC.sub('',s)
    s=re.sub(r'[^\w%]+',' ',s,flags=re.UNICODE)
    return ' '.join(x for x in s.split() if x not in STOP)

def is_social(v):
    if not v:return False
    try:
        h=(urlsplit(str(v)).hostname or '').casefold().removeprefix('www.')
        return any(h==x or h.endswith('.'+x) for x in SOCIAL_HOSTS)
    except Exception:return False

def social_id(v):
    if not v:return ''
    try:
        p=urlsplit(str(v).strip());h=(p.hostname or '').casefold().removeprefix('www.')
        if h=='twitter.com':h='x.com'
        if h=='m.facebook.com':h='facebook.com'
        path=re.sub(r'/{2,}','/',p.path or '/').rstrip('/').casefold() or '/'
        return h+path
    except Exception:return str(v).strip().casefold().rstrip('/')

def url_id(v):
    if not v:return ''
    try:
        p=urlsplit(str(v).strip());h=(p.hostname or '').casefold().removeprefix('www.')
        path=re.sub(r'/{2,}','/',p.path or '/').rstrip('/').casefold() or '/';path=re.sub(r'^/(?:ar|en)(?=/)','',path)
        q=urlencode(sorted((k.casefold(),val) for k,val in parse_qsl(p.query,keep_blank_values=True) if not k.casefold().startswith('utm_')))
        return h+path+('?'+q if q else '')
    except Exception:return str(v).strip().casefold().rstrip('/')

def specific_social(v):
    if not is_social(v):return False
    p=urlsplit(str(v));h=(p.hostname or '').casefold();path=(p.path or '').casefold()
    if 'instagram.com' in h:return bool(re.search(r'/(?:p|reel|reels|tv)/[^/]+',path))
    if 'x.com' in h or 'twitter.com' in h:return '/status/' in path
    if 'tiktok.com' in h:return '/video/' in path
    if 'facebook.com' in h:return any(x in path for x in ('/posts/','/videos/','/reel/','/share/','/photo','/permalink')) or 'story.php' in str(v).casefold()
    return False

def generic_competitor_source_url(v, competitor_id, config):
    if not v or not competitor_id:return False
    ident=url_id(v)
    for comp in config.get('competitors',[]):
        if comp.get('id')!=competitor_id:continue
        vals=[comp.get('website'),comp.get('offers_url')]+[src.get('url') for src in comp.get('website_sources',[]) if src.get('url')]
        return any(url_id(x)==ident for x in vals if x)
    return False

try:data=json.loads(DATA.read_text(encoding='utf-8'));config=json.loads(CONFIG.read_text(encoding='utf-8'))
except Exception as exc:
    print('POST-FLIGHT FAILED\n - Cannot load data/config:',exc);raise SystemExit(1)

items=data.get('items',[]);byid={i.get('id'):i for i in items};valid_comp={c.get('id') for c in config.get('competitors',[])}
# Every configured discovery source should have a status row after monitor execution.
expected={f"website:{c['id']}:{s['id']}" for c in config.get('competitors',[]) for s in c.get('website_sources',[])} | {f"social:{c['id']}:{p}" for c in config.get('competitors',[]) for p in c.get('social_feeds',{})}
actual={s.get('source_key') for s in data.get('source_status',[])}
missing=sorted(expected-actual)
if missing:fail('Missing discovery source status rows: '+', '.join(missing))

seen_title={};seen_url={}
for i in items:
    iid=i.get('id') or '<no-id>';comp=i.get('competitor_id');ctype=i.get('content_type')
    if comp not in valid_comp:fail(f'{iid}: unknown competitor_id {comp}')
    if comp in {'mobily-pay','tiqmo'}:
        rendered=' '.join(str(i.get(field) or '') for field in ('title','summary','snippet','evidence_snapshot'))
        if 'Ø' in rendered or 'Ù' in rendered or '\ufffd' in rendered:
            fail(f'{iid}: official offer text contains mojibake')
    if i.get('source_type')=='social' and ctype in {'campaign','merchant_offer'}:fail(f'{iid}: social item promoted to counted {ctype}')
    if i.get('post_role')=='winner_announcement' and not i.get('campaign_id') and ctype!='review':fail(f'{iid}: unlinked winner announcement must be Needs Review')
    cid=i.get('campaign_id')
    if cid:
        target=byid.get(cid)
        if not target:fail(f'{iid}: campaign_id points to missing record {cid}')
        elif target.get('competitor_id')!=comp:fail(f'{iid}: cross-competitor campaign link to {cid}')

    ev=str(i.get('evidence_snapshot') or '').casefold()
    if any(x in ev for x in LOGIN_MARKERS):fail(f'{iid}: login/navigation shell stored as evidence')

    if ctype in {'campaign','merchant_offer'}:
        if i.get('source_type')=='website' and i.get('official_discovery'):
            sv=(i.get('source_verification') or {}).get('status')
            if sv!='verified_website':fail(f'{iid}: auto-registered official website item is not verified')
            if (i.get('source_verification') or {}).get('verification_method')=='official_website_modal' and not i.get('source_locator'):
                fail(f'{iid}: modal-verified item is missing its source locator')
        end=i.get('end_date')
        if end:
            try:
                d=datetime.fromisoformat(str(end).replace('Z','+00:00'))
                if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
                if d.date()<datetime.now(timezone.utc).date() and i.get('active') is not False:
                    fail(f'{iid}: expired offer is still active')
            except Exception:pass
        # Hard duplicate check within same competitor + record type.
        tk=norm_title(i.get('title'))
        if tk:
            k=(comp,ctype,tk)
            if k in seen_title:fail(f'{iid}: duplicate title with {seen_title[k]} ({i.get("title")})')
            seen_title[k]=iid
        modal_source=(i.get('source_verification') or {}).get('verification_method')=='official_website_modal' and bool(i.get('source_locator'))
        for u in (i.get('official_campaign_page_url'),i.get('primary_official_source_url'),i.get('link')):
            if not u or is_social(u) or modal_source or generic_competitor_source_url(u,comp,config):continue
            ident=url_id(u);k=(comp,ctype,ident)
            if ident and k in seen_url and seen_url[k]!=iid:fail(f'{iid}: duplicate official URL with {seen_url[k]}')
            if ident:seen_url[k]=iid

        # Campaign media must be proven to come from the same official detail page.
        m=i.get('media') or {}
        if m:
            official=i.get('official_campaign_page_url') or i.get('primary_official_source_url')
            if m.get('source_type')!='official_website' or not m.get('source_url') or not official or is_social(m.get('source_url')) or url_id(m.get('source_url'))!=url_id(official):
                fail(f'{iid}: campaign media has invalid/unproven provenance')

        # Social analytics must include all approved/master links and all linked RSS posts exactly once.
        unique={};master_ids=set()
        for platform,raw in (i.get('social_links') or {}).items():
            vals=raw if isinstance(raw,list) else [raw]
            for u in vals:
                if not u:continue
                if not specific_social(u):
                    warn(f'{iid}: {platform} link is not a specific social post: {u}')
                    continue
                ident=social_id(u)
                if ident:master_ids.add(ident);unique[ident]=platform
        for p in i.get('linked_posts') or []:
            u=p.get('link')
            if not specific_social(u):
                if u:warn(f'{iid}: linked post is not a specific social post: {u}')
                continue
            ident=social_id(u)
            if ident:unique[ident]=p.get('platform') or unique.get(ident)
        total=len(unique);reported=int(i.get('social_posts_total') or 0)
        counts=i.get('social_post_counts') or {};countsum=sum(int(counts.get(p,0) or 0) for p in ('instagram','x','facebook','tiktok'))
        platform_count=sum(int(counts.get(p,0) or 0)>0 for p in ('instagram','x','facebook','tiktok'))
        if master_ids and reported==0:fail(f'{iid}: has {len(master_ids)} approved social link(s) but social_posts_total is 0')
        if reported!=total:fail(f'{iid}: social_posts_total={reported}, expected unique links/posts={total}')
        if countsum!=reported:fail(f'{iid}: social platform counts sum to {countsum}, total is {reported}')
        if int(i.get('social_platform_count') or 0)!=platform_count:fail(f'{iid}: social_platform_count is inconsistent')

if errors:
    print('POST-FLIGHT FAILED')
    for x in errors:print(' -',x)
    if warnings:
        print('WARNINGS')
        for x in warnings[:20]:print(' -',x)
    sys.exit(1)
print(f'POST-FLIGHT OK: {len(items)} records; no duplicate counted offers, cross-company links, social-count mismatches, login-shell evidence, or unproven campaign media.')
if warnings:
    print(f'POST-FLIGHT WARNINGS: {len(warnings)}')
    for x in warnings[:20]:print(' -',x)
