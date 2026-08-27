"""Refresh the approved Excel master template while preserving its design, formulas, charts and dashboard."""
from __future__ import annotations
import json,re,zipfile
from collections import defaultdict
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

BASE=Path(__file__).resolve().parent
TEMPLATE=BASE/"competitor_campaigns_template.xlsx"
DATA=BASE/"data.json";OUTPUT=BASE/"competitor_campaigns_latest.xlsx"
NS="http://schemas.openxmlformats.org/spreadsheetml/2006/main";XML="http://www.w3.org/XML/1998/namespace"
ET.register_namespace("x",NS)
SHEETS={
    "stc-bank":("xl/worksheets/sheet2.xml","xl/tables/table1.xml",9),
    "barq":("xl/worksheets/sheet3.xml","xl/tables/table2.xml",9),
    "mobily-pay":("xl/worksheets/sheet4.xml","xl/tables/table3.xml",9),
    "tiqmo":("xl/worksheets/sheet5.xml","xl/tables/table4.xml",9),
    "urpay":("xl/worksheets/sheet6.xml","xl/tables/table5.xml",9),
    "alinma-pay":("xl/worksheets/sheet7.xml","xl/tables/table6.xml",9),
}
CATEGORY={"remittance":"Remittance","musaned":"Musaned","sadad":"SADAD","card":"Card","engagement":"Engagement","other":"Other","merchant":"Merchant"}
PLATFORMS=("instagram","x","facebook","tiktok")
PLATFORM_LABELS={"instagram":"Instagram","x":"X","facebook":"Facebook","tiktok":"TikTok"}
COMPETITOR_ROWS={"stc-bank":54,"barq":55,"mobily-pay":56,"tiqmo":57,"urpay":58,"alinma-pay":59}
COMPETITOR_LABELS={"stc-bank":"STC Bank","barq":"barq","mobily-pay":"Mobily Pay","tiqmo":"tiqmo","urpay":"urpay","alinma-pay":"alinma pay"}

def parse_date(v):
    if not v:return None
    try:
        d=datetime.fromisoformat(str(v).replace("Z","+00:00"));return d.replace(tzinfo=d.tzinfo or timezone.utc)
    except Exception:return None

def serial(d):
    if not d:return None
    epoch=datetime(1899,12,30,tzinfo=timezone.utc);return (d.astimezone(timezone.utc)-epoch).total_seconds()/86400

def col(ref):return re.match(r"[A-Z]+",ref).group(0)
def order(s):
    n=0
    for ch in s:n=n*26+ord(ch)-64
    return n

def cell(row,letter):
    for c in row.findall(f"{{{NS}}}c"):
        if col(c.attrib.get("r",""))==letter:return c
    c=ET.Element(f"{{{NS}}}c",{"r":f"{letter}{row.attrib['r']}"});cells=row.findall(f"{{{NS}}}c")
    for idx,e in enumerate(cells):
        if order(col(e.attrib["r"]))>order(letter):row.insert(idx,c);return c
    row.append(c);return c

def clear(c):
    for child in list(c):
        if child.tag in {f"{{{NS}}}v",f"{{{NS}}}is",f"{{{NS}}}f"}:c.remove(child)
    c.attrib.pop("t",None)

def text(c,v):
    clear(c)
    if v is None or str(v)=="":return
    c.set("t","inlineStr");isel=ET.SubElement(c,f"{{{NS}}}is");t=ET.SubElement(isel,f"{{{NS}}}t");t.set(f"{{{XML}}}space","preserve");t.text=str(v)

def number(c,v):
    clear(c)
    if v is None:return
    c.set("t","n");ET.SubElement(c,f"{{{NS}}}v").text=str(v)

def cached(c,v):
    for child in list(c):
        if child.tag in {f"{{{NS}}}v",f"{{{NS}}}is"}:c.remove(child)
    c.attrib.pop("t",None)
    if v is None or v=="":return
    if isinstance(v,str):c.set("t","str")
    else:c.set("t","n")
    ET.SubElement(c,f"{{{NS}}}v").text=str(v)

def brief(value,limit=180):
    value=re.sub(r"\s+"," ",str(value or "")).strip()
    if len(value)<=limit:return value
    return value[:limit-1].rsplit(" ",1)[0].rstrip(" ,.;:-")+"…"

def approved(item):
    return not (item.get("review_required") and item.get("source_type")!="inventory")

def expired(item,as_of):
    if str(item.get("current_status") or "").strip().lower()=="expired":return True
    if item.get("active") is False:return True
    end=parse_date(item.get("end_date"))
    return bool(end and end.date()<as_of.date())

def campaign_status(item,as_of):
    end=parse_date(item.get("end_date"))
    if not end:return "End Date Not Stated"
    days=(end.date()-as_of.date()).days
    if days<=7:return "Expiring ≤7 Days"
    if days<=30:return "Expiring 8–30 Days"
    return "Active"

def sort_date(item):
    for field in ("start_date","published_at","first_seen","last_changed"):
        value=parse_date(item.get(field))
        if value:return value
    return datetime(1900,1,1,tzinfo=timezone.utc)

def eligible(data,cid,as_of):
    rows=[]
    for i in data.get("items",[]):
        if i.get("competitor_id")!=cid or i.get("content_type")!="campaign":continue
        if str(i.get("campaign_category") or "").lower()=="merchant":continue
        if not approved(i) or expired(i,as_of):continue
        rows.append(i)
    return sorted(rows,key=lambda i:(-sort_date(i).timestamp(),str(i.get("title") or "").casefold()))

def merchant_offer_count(data,cid,as_of):
    return sum(
        1 for item in data.get("items",[])
        if item.get("competitor_id")==cid
        and (item.get("content_type")=="merchant_offer" or str(item.get("campaign_category") or "").lower()=="merchant")
        and approved(item)
        and not expired(item,as_of)
    )

def normalize_url(value):
    try:
        parsed=urlsplit(str(value or "").strip())
        host=parsed.netloc.lower().removeprefix("www.").removeprefix("m.")
        return f"{host}{parsed.path.rstrip('/')}".lower()
    except Exception:return str(value or "").strip().lower()

def campaign_social_index(data):
    index=defaultdict(dict)
    for item in data.get("items",[]):
        if item.get("source_type")!="social" or not item.get("campaign_id"):continue
        platform=str(item.get("platform") or "").lower()
        link=item.get("link")
        if platform not in PLATFORMS or not link:continue
        index[str(item["campaign_id"])][normalize_url(link)]=platform
    return index

def campaign_social_summary(item,index):
    posts=dict(index.get(str(item.get("id")),{}))
    for platform,link in (item.get("social_links") or {}).items():
        platform=str(platform).lower()
        if platform in PLATFORMS and link:posts.setdefault(normalize_url(link),platform)
    platforms=sorted(set(posts.values()),key=PLATFORMS.index)
    return len(posts),", ".join(PLATFORM_LABELS[p] for p in platforms)

def social_activity(data,as_of):
    cutoff=as_of-timedelta(days=14);seen=set();counts={cid:{p:0 for p in PLATFORMS} for cid in SHEETS}
    for item in data.get("items",[]):
        cid=item.get("competitor_id");platform=str(item.get("platform") or "").lower();link=item.get("link")
        if cid not in counts or item.get("source_type")!="social" or platform not in PLATFORMS or not link:continue
        published=parse_date(item.get("published_at"))
        if not published or published<cutoff or published>as_of+timedelta(hours=6):continue
        if item.get("direct_link") is False or item.get("verified") is False:continue
        key=(cid,normalize_url(link))
        if key in seen:continue
        seen.add(key);counts[cid][platform]+=1
    return counts

def rebase_row(source_row,row_number):
    old=int(source_row.attrib["r"]);row=deepcopy(source_row);row.set("r",str(row_number))
    for c in row.findall(f"{{{NS}}}c"):
        c.set("r",f"{col(c.attrib['r'])}{row_number}")
        formula=c.find(f"{{{NS}}}f")
        if formula is not None and formula.text:
            formula.text=re.sub(rf"(\$?[A-Z]{{1,3}}\$?){old}\b",rf"\g<1>{row_number}",formula.text)
    return row

def update_sheet(xml_bytes,items,start,merchant_count,social_index,as_of):
    root=ET.fromstring(xml_bytes);sheet_data=root.find(f"{{{NS}}}sheetData");rows={int(r.attrib["r"]):r for r in sheet_data.findall(f"{{{NS}}}row")};write_cols=["B","C","D","E","F","G","J","K","L","N","O","P","Q","R","S","T"]
    existing_data_rows=[rnum for rnum in rows if rnum>=start]
    template_row=rows[max(existing_data_rows)] if existing_data_rows else None
    if template_row is None:raise SystemExit("Excel template is missing its campaign data row")
    last_row=max(start,start+len(items)-1,max(existing_data_rows))
    for rnum in range(start,last_row+1):
        if rnum not in rows:
            rows[rnum]=rebase_row(template_row,rnum);sheet_data.append(rows[rnum])
    sheet_data[:]=sorted(sheet_data,key=lambda r:int(r.attrib.get("r","0")))
    write_cols.append("U")
    for rnum in range(start,last_row+1):
        row=rows[rnum]
        idx=rnum-start;i=items[idx] if idx<len(items) else None
        if not i:
            for letter in write_cols:clear(cell(row,letter))
            for letter in ("A","H","I","M"):cached(cell(row,letter),None)
            continue
        links=i.get("social_links") or {}
        social_count,platforms=campaign_social_summary(i,social_index)
        official_link=i.get("official_campaign_page_url") or i.get("primary_official_source_url") or i.get("link")
        vals={"B":CATEGORY.get(i.get("campaign_category"),i.get("campaign_category") or "Other"),"C":i.get("title"),"D":brief(i.get("summary") or i.get("snippet")),"J":i.get("operation_type"),"K":i.get("mechanic"),"L":i.get("eligibility"),"N":official_link,"O":links.get("instagram"),"P":links.get("x"),"Q":links.get("facebook"),"R":links.get("tiktok"),"S":i.get("terms_note"),"U":platforms}
        for letter,v in vals.items():text(cell(row,letter),v)
        for letter,field in [("E","published_at"),("F","start_date"),("G","end_date")]:number(cell(row,letter),serial(parse_date(i.get(field))))
        cached(cell(row,"A"),idx+1)
        end=parse_date(i.get("end_date"));cached(cell(row,"H"),(end.date()-as_of.date()).days if end else None)
        cached(cell(row,"I"),campaign_status(i,as_of));cached(cell(row,"M"),official_link)
        social_cell=cell(row,"T");social_cell.set("s",cell(row,"A").attrib.get("s","0"));number(social_cell,social_count)
    summary_row=rows.get(5)
    if summary_row is not None:
        cached(cell(summary_row,"A"),len(items))
        cached(cell(summary_row,"D"),sum(1 for i in items if campaign_status(i,as_of)=="End Date Not Stated"))
        cached(cell(summary_row,"G"),sum(1 for i in items if str(i.get("campaign_category") or "").lower()=="remittance"))
        cached(cell(summary_row,"J"),sum(1 for i in items if campaign_status(i,as_of) in {"Expiring ≤7 Days","Expiring 8–30 Days"}))
        number(cell(summary_row,"M"),None)
    header_row=rows.get(4)
    if header_row is not None:text(cell(header_row,"M"),f"Merchant Offers (Count Only): {merchant_count}")
    dimension=root.find(f"{{{NS}}}dimension")
    if dimension is not None:dimension.set("ref",f"A1:U{last_row}")
    return ET.tostring(root,encoding="utf-8",xml_declaration=True),last_row

def update_table(xml_bytes,last_row):
    root=ET.fromstring(xml_bytes);ref=f"A8:U{last_row}";root.set("ref",ref)
    auto_filter=root.find(f"{{{NS}}}autoFilter")
    if auto_filter is not None:auto_filter.set("ref",ref)
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)

def update_dashboard(xml_bytes,data,as_of,social_counts,campaigns):
    root=ET.fromstring(xml_bytes);sheet_data=root.find(f"{{{NS}}}sheetData");rows={int(r.attrib["r"]):r for r in sheet_data.findall(f"{{{NS}}}row")}
    number(cell(rows[3],"B"),serial(as_of));cached(cell(rows[3],"E"),serial(as_of))
    for cid,row_number in COMPETITOR_ROWS.items():
        row=rows[row_number]
        for offset,platform in enumerate(PLATFORMS,start=2):number(cell(row,chr(64+offset)),social_counts[cid][platform])
        cached(cell(row,"F"),sum(social_counts[cid].values()))
    totals={cid:len(items) for cid,items in campaigns.items()};largest=max(totals,key=totals.get);total_campaigns=sum(totals.values())
    remittance={cid:sum(1 for i in items if str(i.get("campaign_category") or "").lower()=="remittance") for cid,items in campaigns.items()}
    remittance_total=sum(remittance.values());remittance_leader=max(remittance,key=remittance.get);social_total=sum(sum(v.values()) for v in social_counts.values());social_leader=max(social_counts,key=lambda cid:sum(social_counts[cid].values()))
    expiring=sum(1 for items in campaigns.values() for i in items if (end:=parse_date(i.get("end_date"))) and as_of.date()<=end.date()<=(as_of+timedelta(days=30)).date())
    categories=("remittance","musaned","sadad","card","engagement","other")
    category_counts={cid:{category:sum(1 for i in campaigns[cid] if str(i.get("campaign_category") or "other").lower()==category) for category in categories} for cid in campaigns}
    status_counts={cid:{
        "active":sum(1 for i in campaigns[cid] if campaign_status(i,as_of)=="Active"),
        "undated":sum(1 for i in campaigns[cid] if campaign_status(i,as_of)=="End Date Not Stated"),
        "seven":sum(1 for i in campaigns[cid] if campaign_status(i,as_of)=="Expiring ≤7 Days"),
        "thirty":sum(1 for i in campaigns[cid] if campaign_status(i,as_of)=="Expiring 8–30 Days"),
    } for cid in campaigns}
    dashboard_rows={"stc-bank":10,"barq":11,"mobily-pay":12,"tiqmo":13,"urpay":14,"alinma-pay":15}
    for cid,row_number in dashboard_rows.items():
        row=rows[row_number];values=[totals[cid],status_counts[cid]["active"],status_counts[cid]["undated"],status_counts[cid]["seven"],status_counts[cid]["thirty"]]
        values.extend(category_counts[cid][category] for category in categories);values.append(sum(social_counts[cid].values()))
        for offset,value in enumerate(values,start=2):cached(cell(row,chr(64+offset)),value)
        category_row=rows[21+(row_number-10)]
        for offset,category in enumerate(categories,start=2):cached(cell(category_row,chr(64+offset)),category_counts[cid][category])
        remittance_row=rows[33+(row_number-10)];cached(cell(remittance_row,"B"),remittance[cid]);cached(cell(remittance_row,"C"),(remittance[cid]/totals[cid] if totals[cid] else 0))
        helper_row=rows[31+(row_number-10)];cached(cell(helper_row,"Y"),remittance[cid])
    category_totals={category:sum(category_counts[cid][category] for cid in campaigns) for category in categories}
    for offset,category in enumerate(categories,start=2):
        cached(cell(rows[27],chr(64+offset)),category_totals[category]);cached(cell(rows[18+offset-1],"Y"),category_totals[category])
    cached(cell(rows[39],"B"),remittance_total);cached(cell(rows[39],"C"),(remittance_total/total_campaigns if total_campaigns else 0))
    for offset,platform in enumerate(PLATFORMS,start=2):cached(cell(rows[60],chr(64+offset)),sum(social_counts[cid][platform] for cid in social_counts))
    cached(cell(rows[60],"F"),social_total)
    cached(cell(rows[6],"A"),total_campaigns);cached(cell(rows[6],"C"),remittance_total);cached(cell(rows[6],"E"),social_total);cached(cell(rows[6],"G"),expiring);cached(cell(rows[6],"I"),len(campaigns))
    signals=[
        f"Largest active campaign portfolio: {COMPETITOR_LABELS[largest]} ({totals[largest]} campaigns).",
        f"Active remittance campaigns: {remittance_total}; market leader: {COMPETITOR_LABELS[remittance_leader]} ({remittance[remittance_leader]}).",
        f"Remittance share of active campaigns: {(remittance_total/total_campaigns if total_campaigns else 0):.0%}.",
        f"Social posts in the latest 14 days: {social_total}; most active: {COMPETITOR_LABELS[social_leader]} ({sum(social_counts[social_leader].values())}).",
        f"Campaigns expiring within 30 days: {expiring}.",
    ]
    for row_number,value in zip(range(43,48),signals):text(cell(rows[row_number],"A"),value)
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)

def update_workbook(xml_bytes):
    root=ET.fromstring(xml_bytes);calc=root.find(f"{{{NS}}}calcPr")
    if calc is None:calc=ET.SubElement(root,f"{{{NS}}}calcPr")
    calc.set("calcMode","auto");calc.set("fullCalcOnLoad","1");calc.set("forceFullCalc","1")
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)

def main():
    if not TEMPLATE.exists():raise SystemExit(f"Missing Excel template: {TEMPLATE.name}")
    data=json.loads(DATA.read_text(encoding="utf-8"));replace={};as_of=parse_date(data.get("generated_at")) or datetime.now(timezone.utc)
    social_index=campaign_social_index(data);social_counts=social_activity(data,as_of)
    campaigns={cid:eligible(data,cid,as_of) for cid in SHEETS}
    with zipfile.ZipFile(TEMPLATE,"r") as zin:
        replace["xl/worksheets/sheet1.xml"]=update_dashboard(zin.read("xl/worksheets/sheet1.xml"),data,as_of,social_counts,campaigns)
        for cid,(path,table_path,start) in SHEETS.items():
            updated,last_row=update_sheet(zin.read(path),campaigns[cid],start,merchant_offer_count(data,cid,as_of),social_index,as_of)
            replace[path]=updated;replace[table_path]=update_table(zin.read(table_path),last_row)
        replace["xl/workbook.xml"]=update_workbook(zin.read("xl/workbook.xml"))
        with zipfile.ZipFile(OUTPUT,"w",compression=zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():zout.writestr(info,replace.get(info.filename,zin.read(info.filename)))
    print(f"Generated {OUTPUT.name}")

if __name__=="__main__":main()
