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
CHART_NS="http://schemas.openxmlformats.org/drawingml/2006/chart"
DRAWING_NS="http://schemas.openxmlformats.org/drawingml/2006/main"
OFFICE_REL_NS="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS="http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS="http://schemas.openxmlformats.org/package/2006/content-types"
ET.register_namespace("x",NS)
ET.register_namespace("c",CHART_NS)
ET.register_namespace("a",DRAWING_NS)
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
    for field in ("start_date","first_seen","last_changed"):
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
        clear(cell(row,"E"))
        for letter,field in [("F","start_date"),("G","end_date")]:number(cell(row,letter),serial(parse_date(i.get(field))))
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

def update_dashboard(xml_bytes,as_of,research_cutoff,social_counts,campaigns):
    root=ET.fromstring(xml_bytes);sheet_data=root.find(f"{{{NS}}}sheetData");rows={int(r.attrib["r"]):r for r in sheet_data.findall(f"{{{NS}}}row")}
    number(cell(rows[3],"B"),serial(research_cutoff));number(cell(rows[3],"K"),serial(as_of))
    totals={cid:len(items) for cid,items in campaigns.items()};total_campaigns=sum(totals.values())
    remittance={cid:sum(1 for i in items if str(i.get("campaign_category") or "").lower()=="remittance") for cid,items in campaigns.items()}
    remittance_total=sum(remittance.values());social_total=sum(sum(v.values()) for v in social_counts.values())
    expiring=sum(1 for items in campaigns.values() for i in items if (end:=parse_date(i.get("end_date"))) and as_of.date()<=end.date()<=(as_of+timedelta(days=30)).date())
    categories=("remittance","musaned","sadad","card","engagement","other")
    category_totals={category:0 for category in categories}
    for items in campaigns.values():
        for item in items:
            category=str(item.get("campaign_category") or "other").lower()
            category_totals[category if category in categories[:-1] else "other"]+=1
    for index,cid in enumerate(SHEETS,start=2):
        label=COMPETITOR_LABELS[cid]
        text(cell(rows[index],"X"),label);number(cell(rows[index],"Y"),totals[cid])
        text(cell(rows[index],"AA"),label);number(cell(rows[index],"AB"),remittance[cid])
        social_row=rows[index+10];text(cell(social_row,"X"),label)
        for column,platform in zip(("Y","Z","AA","AB"),PLATFORMS):number(cell(social_row,column),social_counts[cid][platform])
    for row_number,category in enumerate(categories,start=2):
        text(cell(rows[row_number],"AD"),CATEGORY[category]);number(cell(rows[row_number],"AE"),category_totals[category])
    text(cell(rows[12],"AD"),"Expiring ≤30 Days");number(cell(rows[12],"AE"),expiring)
    cached(cell(rows[6],"A"),total_campaigns);cached(cell(rows[6],"D"),remittance_total);cached(cell(rows[6],"G"),social_total);cached(cell(rows[6],"J"),expiring);cached(cell(rows[6],"M"),len(campaigns))
    chart_data={
        "xl/drawings/charts/chart1.xml":([COMPETITOR_LABELS[cid] for cid in SHEETS],[[totals[cid] for cid in SHEETS]]),
        "xl/drawings/charts/chart2.xml":([CATEGORY[category] for category in categories],[[category_totals[category] for category in categories]]),
        "xl/drawings/charts/chart3.xml":([COMPETITOR_LABELS[cid] for cid in SHEETS],[[remittance[cid] for cid in SHEETS]]),
        "xl/drawings/charts/chart4.xml":([COMPETITOR_LABELS[cid] for cid in SHEETS],[[social_counts[cid][platform] for cid in SHEETS] for platform in PLATFORMS]),
    }
    return ET.tostring(root,encoding="utf-8",xml_declaration=True),chart_data

def set_chart_cache(cache,values):
    for point in list(cache.findall(f"{{{CHART_NS}}}pt")):cache.remove(point)
    point_count=cache.find(f"{{{CHART_NS}}}ptCount")
    if point_count is None:point_count=ET.SubElement(cache,f"{{{CHART_NS}}}ptCount")
    point_count.set("val",str(len(values)))
    insert_at=list(cache).index(point_count)+1
    for index,value in enumerate(values):
        point=ET.Element(f"{{{CHART_NS}}}pt",{"idx":str(index)})
        ET.SubElement(point,f"{{{CHART_NS}}}v").text=str(value)
        cache.insert(insert_at+index,point)

def update_chart(xml_bytes,labels,series_values):
    root=ET.fromstring(xml_bytes);series=root.findall(f".//{{{CHART_NS}}}ser")
    if len(series)!=len(series_values):raise SystemExit(f"Excel chart series mismatch: expected {len(series_values)}, found {len(series)}")
    for node,values in zip(series,series_values):
        category_cache=node.find(f".//{{{CHART_NS}}}cat/{{{CHART_NS}}}strRef/{{{CHART_NS}}}strCache")
        value_cache=node.find(f".//{{{CHART_NS}}}val/{{{CHART_NS}}}numRef/{{{CHART_NS}}}numCache")
        if category_cache is None or value_cache is None:raise SystemExit("Excel chart cache is missing")
        set_chart_cache(category_cache,labels);set_chart_cache(value_cache,values)
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)

def update_workbook(xml_bytes):
    root=ET.fromstring(xml_bytes);calc=root.find(f"{{{NS}}}calcPr")
    if calc is None:calc=ET.SubElement(root,f"{{{NS}}}calcPr")
    calc.set("calcMode","auto");calc.set("fullCalcOnLoad","1");calc.set("forceFullCalc","1")
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)

def remove_worksheet(parts,name):
    workbook=ET.fromstring(parts["xl/workbook.xml"]);sheets=workbook.find(f"{{{NS}}}sheets")
    target=next((sheet for sheet in sheets.findall(f"{{{NS}}}sheet") if sheet.attrib.get("name")==name),None)
    if target is None:return
    relationship_id=target.attrib.get(f"{{{OFFICE_REL_NS}}}id");sheets.remove(target)
    relationships=ET.fromstring(parts["xl/_rels/workbook.xml.rels"])
    relationship=next((rel for rel in relationships.findall(f"{{{PACKAGE_REL_NS}}}Relationship") if rel.attrib.get("Id")==relationship_id),None)
    if relationship is None:raise SystemExit(f"Excel worksheet relationship is missing: {name}")
    worksheet_path=relationship.attrib["Target"].lstrip("/")
    if not worksheet_path.startswith("xl/"):worksheet_path=f"xl/{worksheet_path}"
    relationships.remove(relationship)
    content_types=ET.fromstring(parts["[Content_Types].xml"])
    for override in list(content_types.findall(f"{{{CONTENT_TYPES_NS}}}Override")):
        if override.attrib.get("PartName","").lstrip("/")==worksheet_path:content_types.remove(override)
    parts["xl/workbook.xml"]=ET.tostring(workbook,encoding="utf-8",xml_declaration=True)
    ET.register_namespace("",PACKAGE_REL_NS)
    parts["xl/_rels/workbook.xml.rels"]=ET.tostring(relationships,encoding="utf-8",xml_declaration=True)
    ET.register_namespace("",CONTENT_TYPES_NS)
    parts["[Content_Types].xml"]=ET.tostring(content_types,encoding="utf-8",xml_declaration=True)
    parts.pop(worksheet_path,None)
    sheet_rel_path=f"{worksheet_path.rsplit('/',1)[0]}/_rels/{worksheet_path.rsplit('/',1)[1]}.rels"
    parts.pop(sheet_rel_path,None)

def validate_output(path):
    expected_sheets=["Executive Dashboard","STC Bank","barq","Mobily Pay","tiqmo","urpay","alinma pay"]
    with zipfile.ZipFile(path,"r") as workbook:
        damaged=workbook.testzip()
        if damaged:raise SystemExit(f"Generated Excel file is damaged: {damaged}")
        root=ET.fromstring(workbook.read("xl/workbook.xml"))
        sheet_names=[sheet.attrib.get("name") for sheet in root.findall(f".//{{{NS}}}sheet")]
        if sheet_names!=expected_sheets:raise SystemExit(f"Generated Excel sheets do not match the approved report: {sheet_names}")
        if "xl/worksheets/sheet8.xml" in workbook.namelist():raise SystemExit("Update Guide was not removed from the generated report")
        for index in range(1,5):
            chart=ET.fromstring(workbook.read(f"xl/drawings/charts/chart{index}.xml"))
            caches=chart.findall(f".//{{{CHART_NS}}}strCache")+chart.findall(f".//{{{CHART_NS}}}numCache")
            if not caches or any(cache.find(f"{{{CHART_NS}}}ptCount") is None or cache.find(f"{{{CHART_NS}}}ptCount").attrib.get("val")!="6" for cache in caches):
                raise SystemExit(f"Dashboard chart {index} does not contain the current six-competitor data cache")

def main():
    if not TEMPLATE.exists():raise SystemExit(f"Missing Excel template: {TEMPLATE.name}")
    data=json.loads(DATA.read_text(encoding="utf-8"));as_of=datetime.now(timezone.utc);research_cutoff=parse_date(data.get("generated_at")) or as_of
    social_index=campaign_social_index(data);social_counts=social_activity(data,as_of)
    campaigns={cid:eligible(data,cid,as_of) for cid in SHEETS}
    with zipfile.ZipFile(TEMPLATE,"r") as zin:
        infos=zin.infolist();parts={info.filename:zin.read(info.filename) for info in infos}
        dashboard,chart_data=update_dashboard(parts["xl/worksheets/sheet1.xml"],as_of,research_cutoff,social_counts,campaigns)
        parts["xl/worksheets/sheet1.xml"]=dashboard
        for path,(labels,series_values) in chart_data.items():parts[path]=update_chart(parts[path],labels,series_values)
        for cid,(path,table_path,start) in SHEETS.items():
            updated,last_row=update_sheet(parts[path],campaigns[cid],start,merchant_offer_count(data,cid,as_of),social_index,as_of)
            parts[path]=updated;parts[table_path]=update_table(parts[table_path],last_row)
        parts["xl/workbook.xml"]=update_workbook(parts["xl/workbook.xml"]);remove_worksheet(parts,"Update Guide")
        with zipfile.ZipFile(OUTPUT,"w",compression=zipfile.ZIP_DEFLATED) as zout:
            for info in infos:
                if info.filename in parts:zout.writestr(info,parts[info.filename])
    validate_output(OUTPUT)
    print(f"Generated {OUTPUT.name}")

if __name__=="__main__":main()
