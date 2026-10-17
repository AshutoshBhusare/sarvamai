import re
from pypdf import PdfReader

def extract_pdf_text(uploaded_file):
    reader=PdfReader(uploaded_file)
    text="\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if not text: raise ValueError("No selectable text found. This may be a scanned PDF; OCR is not included yet.")
    return text

def first(patterns,text,default=""):
    for pattern in patterns:
        m=re.search(pattern,text,re.I|re.M)
        if m: return m.group(1).strip()
    return default

def parse_rows(text):
    items=[]
    for line in text.splitlines():
        m=re.match(r"^(.{2,80}?)\s*(?:\||\t{1,}|\s{2,})\s*(\d+(?:\.\d+)?)\s*(?:\||\t{1,}|\s{2,})\s*(?:₹|INR\s*|Rs\.?\s*)?([\d,]+(?:\.\d{1,2})?)\s*$",line.strip(),re.I)
        if m:
            name=m.group(1).strip(" |-")
            if name.lower() not in {"item","description","product"} and not re.search(r"subtotal|total|tax|quantity|unit price",name,re.I):
                items.append({"name":name,"quantity":float(m.group(2)),"unit_price":float(m.group(3).replace(",",""))})
    # Some PDF extractors split table cells into separate lines: description, quantity, price.
    if not items:
        lines=[line.strip() for line in text.splitlines() if line.strip()]
        for i in range(len(lines)-2):
            name, qty, price = lines[i], lines[i+1], lines[i+2]
            if re.fullmatch(r"\d+(?:\.\d+)?", qty) and re.fullmatch(r"(?:₹|INR\s*|Rs\.?\s*)?[\d,]+(?:\.\d{1,2})?", price, re.I):
                if name.lower() not in {"item","description","product","quantity","unit price (inr)"} and not re.search(r"subtotal|grand total|invoice|vendor|currency|tax|total", name, re.I):
                    items.append({"name":name,"quantity":float(qty),"unit_price":float(re.sub(r"[^0-9.]", "", price.replace(",", "")))})
    return items

def parse_invoice_text(text):
    number=first([r"(?:invoice\s*(?:no\.?|number|#|id))\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-/]+)",r"\b(INV[-/][A-Z0-9\-/]+)\b"],text,"UNKNOWN")
    vendor=first([r"(?:vendor|supplier|seller|billed\s+by|from)\s*[:\-]\s*([^\n]+)"],text,"Unknown vendor")
    currency="INR" if re.search(r"₹|\bINR\b|\bRs\.?\b",text,re.I) else ("USD" if "$" in text or re.search(r"\bUSD\b",text,re.I) else "INR")
    items=parse_rows(text)
    sub=first([r"(?:sub\s*total|subtotal)\s*[:\-]?\s*(?:₹|INR\s*|Rs\.?\s*)?([\d,]+(?:\.\d{1,2})?)"],text)
    tax=first([r"(?:tax|GST|VAT)\s*[:\-]?\s*(?:₹|INR\s*|Rs\.?\s*)?([\d,]+(?:\.\d{1,2})?)"],text,"0")
    total=first([r"(?:grand\s+total|invoice\s+total|total\s+due|\btotal\b)\s*[:\-]?\s*(?:₹|INR\s*|Rs\.?\s*)?([\d,]+(?:\.\d{1,2})?)"],text)
    subtotal=float(sub.replace(",","")) if sub else round(sum(i["quantity"]*i["unit_price"] for i in items),2)
    tax=float(tax.replace(",","")); total=float(total.replace(",","")) if total else subtotal+tax
    return {"invoice_number":number,"vendor":vendor,"currency":currency,"items":items,"subtotal":subtotal,"tax":tax,"total":total}

def parse_purchase_order_text(text):
    number=first([r"(?:purchase\s*order|PO)\s*(?:no\.?|number|#)?\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-/]+)"],text,"UNKNOWN")
    vendor=first([r"(?:vendor|supplier|seller|ordered\s+from)\s*[:\-]\s*([^\n]+)"],text,"Unknown vendor")
    currency="INR" if re.search(r"₹|\bINR\b|\bRs\.?\b",text,re.I) else ("USD" if "$" in text or re.search(r"\bUSD\b",text,re.I) else "INR")
    return {"po_number":number,"vendor":vendor,"currency":currency,"items":parse_rows(text)}

def analyze_invoice(invoice,po,tolerance=0.01):
    issues=[]; checks=[]; lines=[]
    def check(name,ok,message): checks.append({"name":name,"passed":bool(ok),"message":message})
    vendor_ok=invoice["vendor"].strip().casefold()==po["vendor"].strip().casefold()
    check("Vendor match",vendor_ok,"Vendor matches purchase order." if vendor_ok else "Invoice vendor differs from purchase order vendor.")
    if not vendor_ok: issues.append({"category":"Vendor","severity":"High","details":"Invoice vendor does not match purchase order vendor.","expected":po["vendor"],"observed":invoice["vendor"]})
    currency_ok=invoice["currency"].upper()==po["currency"].upper()
    check("Currency match",currency_ok,"Currency matches." if currency_ok else "Invoice and purchase order currencies differ.")
    if not currency_ok: issues.append({"category":"Currency","severity":"High","details":"Invoice and purchase order use different currencies.","expected":po["currency"],"observed":invoice["currency"]})
    calc_sub=round(sum(i["quantity"]*i["unit_price"] for i in invoice["items"]),2); sub_ok=abs(calc_sub-float(invoice["subtotal"]))<=tolerance
    check("Subtotal arithmetic",sub_ok,"Line-item sum matches subtotal." if sub_ok else "Line-item sum differs from the stated subtotal.")
    if not sub_ok: issues.append({"category":"Subtotal calculation","severity":"Medium","details":"Line-item sum does not match the stated subtotal.","expected":f"{invoice['currency']} {calc_sub:.2f}","observed":f"{invoice['currency']} {invoice['subtotal']:.2f}"})
    total_ok=abs(float(invoice["subtotal"])+float(invoice["tax"])-float(invoice["total"]))<=tolerance
    check("Total arithmetic",total_ok,"Subtotal plus tax equals total." if total_ok else "Subtotal plus tax does not equal invoice total.")
    if not total_ok: issues.append({"category":"Total calculation","severity":"Medium","details":"Subtotal plus tax does not equal the stated total.","expected":f"{invoice['currency']} {invoice['subtotal']+invoice['tax']:.2f}","observed":f"{invoice['currency']} {invoice['total']:.2f}"})
    po_items={x["name"].strip().casefold():x for x in po["items"]}; seen=set()
    for item in invoice["items"]:
        key=item["name"].strip().casefold()
        if key in seen: issues.append({"category":"Duplicate item","severity":"Medium","details":f"Duplicate invoice line item: {item['name']}.","expected":"One line per item","observed":"Duplicate line"})
        seen.add(key); expected=po_items.get(key)
        if expected is None:
            lines.append({"Item":item["name"],"Invoice quantity":item["quantity"],"PO quantity":"—","Invoice unit price":item["unit_price"],"PO unit price":"—","Result":"Not in PO"})
            issues.append({"category":"Unordered item","severity":"High","details":f"{item['name']} was not found in the purchase order.","expected":"Item listed in PO","observed":item["name"]}); continue
        qty_ok=float(item["quantity"])<=float(expected["quantity"]); price_ok=abs(float(item["unit_price"])-float(expected["unit_price"]))<=tolerance
        if not qty_ok: issues.append({"category":"Quantity variance","severity":"High","details":f"{item['name']}: invoiced quantity exceeds the PO quantity.","expected":str(expected["quantity"]),"observed":str(item["quantity"])})
        if not price_ok: issues.append({"category":"Unit price variance","severity":"High","details":f"{item['name']}: invoice unit price differs from the PO.","expected":f"{po['currency']} {expected['unit_price']:.2f}","observed":f"{invoice['currency']} {item['unit_price']:.2f}"})
        lines.append({"Item":item["name"],"Invoice quantity":item["quantity"],"PO quantity":expected["quantity"],"Invoice unit price":item["unit_price"],"PO unit price":expected["unit_price"],"Result":"Matched" if qty_ok and price_ok else "Review"})
    names={i["name"].strip().casefold() for i in invoice["items"]}
    for item in po["items"]:
        if item["name"].strip().casefold() not in names: lines.append({"Item":item["name"],"Invoice quantity":"—","PO quantity":item["quantity"],"Invoice unit price":"—","PO unit price":item["unit_price"],"Result":"Not billed"})
    check("Purchase order matching",not issues,"No discrepancies found." if not issues else f"{len(issues)} issue(s) require review.")
    return {"invoice_number":invoice["invoice_number"],"po_number":po["po_number"],"vendor":invoice["vendor"],"currency":invoice["currency"],"invoice_total":round(float(invoice["total"]),2),"discrepancies":issues,"checks":checks,"line_comparison":lines,"recommended_status":"Matched" if not issues else "Review required"}
