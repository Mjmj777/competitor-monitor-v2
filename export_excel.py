"""Refresh the approved Excel master template while preserving its design, formulas, charts and dashboard."""
from __future__ import annotations
import json,re,zipfile
from datetime import datetime,timezone
from pathlib import Path
from xml.etree import ElementTree as ET

BASE=Path(__file__).resolve().parent
TEMPLATE=BASE/"competitor_campaigns_template.xlsx"
DATA=BASE/"data.json";OUTPUT=BASE/"competitor_campaigns_latest.xlsx"
NS="http://schemas.openxmlformats.org/spreadsheetml/2006/main";XML="http://www.w3.org/XML/1998/namespace"
ET.register_namespace("x",NS)
SHEETS={"stc-bank":("xl/worksheets/sheet2.xml",9,53),"barq":("xl/worksheets/sheet3.xml",9,42),"mobily-pay":("xl/worksheets/sheet4.xml",9,42),"tiqmo":("xl/worksheets/sheet5.xml",9,42),"urpay":("xl/worksheets/sheet6.xml",9,46),"alinma-pay":("xl/worksheets/sheet7.xml",9,42)}
CATEGORY={"remittance":"Remittance","musaned":"Musaned","sadad":"SADAD","card":"Card","engagement":"Engagement","other":"Other","merchant":"Merchant"}

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
        if child.tag in {f"{{{NS}}}v",f"{{{NS}}}is"}:c.remove(child)
    c.attrib.pop("t",None)

def text(c,v):
    clear(c)
    if v is None or str(v)=="":return
    c.set("t","inlineStr");isel=ET.SubElement(c,f"{{{NS}}}is");t=ET.SubElement(isel,f"{{{NS}}}t");t.set(f"{{{XML}}}space","preserve");t.text=str(v)

def number(c,v):
    clear(c)
    if v is None:return
    c.set("t","n");ET.SubElement(c,f"{{{NS}}}v").text=str(v)

def eligible(data,cid):
    rows=[]
    for i in data.get("items",[]):
        if i.get("competitor_id")!=cid or i.get("content_type") not in {"campaign","merchant_offer"}:continue
        # Unapproved newly discovered/review rows do not enter the master until reviewed.
        if i.get("review_required") and i.get("source_type") not in {"inventory"}:continue
        rows.append(i)
    def key(i):
        try:return (0,int(i.get("record_id")))
        except Exception:return (1,i.get("title", ""))
    return sorted(rows,key=key)

def update_sheet(xml_bytes,items,start,end):
    root=ET.fromstring(xml_bytes);sheet_data=root.find(f"{{{NS}}}sheetData");rows={int(r.attrib["r"]):r for r in sheet_data.findall(f"{{{NS}}}row")};write_cols=["B","C","D","E","F","G","J","K","L","N","O","P","Q","R","S","T"]
    for rnum in range(start,end+1):
        row=rows.get(rnum)
        if row is None:continue
        idx=rnum-start;i=items[idx] if idx<len(items) else None
        if not i:
            for letter in write_cols:clear(cell(row,letter))
            continue
        links=i.get("social_links") or {}
        vals={"B":CATEGORY.get(i.get("campaign_category"),i.get("campaign_category") or "Other"),"C":i.get("title"),"D":i.get("summary") or i.get("snippet"),"J":i.get("operation_type"),"K":i.get("mechanic"),"L":i.get("eligibility"),"N":i.get("official_campaign_page_url"),"O":links.get("instagram"),"P":links.get("x"),"Q":links.get("facebook"),"R":links.get("tiktok"),"S":i.get("terms_note")}
        for letter,v in vals.items():text(cell(row,letter),v)
        for letter,field in [("E","published_at"),("F","start_date"),("G","end_date"),("T","last_reviewed")]:number(cell(row,letter),serial(parse_date(i.get(field))))
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)

def update_workbook(xml_bytes):
    root=ET.fromstring(xml_bytes);calc=root.find(f"{{{NS}}}calcPr")
    if calc is None:calc=ET.SubElement(root,f"{{{NS}}}calcPr")
    calc.set("calcMode","auto");calc.set("fullCalcOnLoad","1");calc.set("forceFullCalc","1")
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)

def main():
    if not TEMPLATE.exists():raise SystemExit(f"Missing Excel template: {TEMPLATE.name}")
    data=json.loads(DATA.read_text(encoding="utf-8"));replace={}
    with zipfile.ZipFile(TEMPLATE,"r") as zin:
        for cid,(path,start,end) in SHEETS.items():
            items=eligible(data,cid)
            if len(items)>end-start+1:raise SystemExit(f"Template capacity exceeded for {cid}: {len(items)}")
            replace[path]=update_sheet(zin.read(path),items,start,end)
        replace["xl/workbook.xml"]=update_workbook(zin.read("xl/workbook.xml"))
        with zipfile.ZipFile(OUTPUT,"w",compression=zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():zout.writestr(info,replace.get(info.filename,zin.read(info.filename)))
    print(f"Generated {OUTPUT.name}")

if __name__=="__main__":main()
