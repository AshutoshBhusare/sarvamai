import streamlit as st
import pandas as pd
from invoice_engine import extract_pdf_text, parse_invoice_text, parse_purchase_order_text, analyze_invoice

st.set_page_config(page_title="InvoiceFlow AI", page_icon="🧾", layout="wide")
st.markdown("""<style>.block-container{max-width:1180px;padding-top:2rem;padding-bottom:3rem}div[data-testid="stMetric"]{border:1px solid rgba(128,128,128,.22);padding:1rem;border-radius:12px}</style>""", unsafe_allow_html=True)
st.title("InvoiceFlow AI")
st.caption("Accounts payable review · PDF extraction · Purchase order validation")
st.divider()

def sample_po():
    return {"po_number":"PO-2026-0081","vendor":"Northstar Office Supplies","currency":"INR","items":[{"name":"Wireless Mouse","quantity":30,"unit_price":400.0},{"name":"USB-C Cable","quantity":20,"unit_price":250.0}]}

with st.sidebar:
    st.subheader("Document upload")
    invoice_file=st.file_uploader("Invoice PDF",type=["pdf"])
    po_mode=st.radio("Purchase order",["Use sample PO","Upload PO PDF"])
    po_file=st.file_uploader("Purchase order PDF",type=["pdf"]) if po_mode=="Upload PO PDF" else None
    st.caption("Text-based PDFs are supported. Scanned PDFs require OCR, which is not included yet.")
    run=st.button("Analyze documents",type="primary",use_container_width=True,disabled=not invoice_file or (po_mode=="Upload PO PDF" and not po_file))

if run:
    try:
        invoice_text=extract_pdf_text(invoice_file)
        invoice=parse_invoice_text(invoice_text)
        po=sample_po() if po_mode=="Use sample PO" else parse_purchase_order_text(extract_pdf_text(po_file))
        if invoice["vendor"]=="Unknown vendor" or not invoice["items"]:
            st.error("Could not confidently identify the vendor or line items. Try a text-based PDF with clearly labeled fields.")
            with st.expander("Extracted text for troubleshooting"): st.text(invoice_text[:6000])
        elif po["vendor"]=="Unknown vendor" or not po["items"]:
            st.error("Could not confidently identify the vendor or line items in the purchase order. Check the PDF format.")
        else:
            st.session_state["result"]=analyze_invoice(invoice,po)
            st.rerun()
    except Exception as exc:
        st.error(f"Unable to process the uploaded documents: {exc}")

result=st.session_state.get("result")
if not result:
    st.info("Upload an invoice PDF to begin. The analysis report will appear here.")
else:
    st.subheader("Review summary")
    st.caption(f"Invoice {result['invoice_number']} · Purchase order {result['po_number']} · {result['vendor']}")
    a,b,c=st.columns(3)
    a.metric("Invoice total",f"{result['currency']} {result['invoice_total']:,.2f}")
    b.metric("Items compared",len(result["line_comparison"]))
    c.metric("Review status",result["recommended_status"])
    if result["recommended_status"]=="Matched": st.success("No discrepancies were identified by the current validation checks.")
    else: st.warning(f"{len(result['discrepancies'])} discrepancy item(s) require review before approval.")
    st.subheader("Discrepancy report")
    if result["discrepancies"]:
        df=pd.DataFrame(result["discrepancies"])[["severity","category","details","expected","observed"]]
        df.columns=["Priority","Category","Finding","Expected value","Invoice value"]
        st.dataframe(df,use_container_width=True,hide_index=True)
    else: st.write("No discrepancies to report.")
    st.subheader("Line-item reconciliation")
    st.dataframe(pd.DataFrame(result["line_comparison"]),use_container_width=True,hide_index=True)
    with st.expander("Validation checks"):
        for item in result["checks"]: st.write(("✓" if item["passed"] else "✕")+f" **{item['name']}** — {item['message']}")
    st.subheader("Workflow")
    status=st.session_state.get("workflow_status","Pending review")
    st.write(f"Current status: **{status}**")
    if result["recommended_status"]=="Matched":
        if st.button("Mark approved (demo only)",type="primary"):
            st.session_state["workflow_status"]="Approved (demo)"; st.rerun()
    elif st.button("Mark as under manual review"):
        st.session_state["workflow_status"]="Under manual review"; st.rerun()
    st.caption("Prototype only: approval is simulated. No ERP or payment provider is connected.")
    if st.button("Clear analysis"):
        st.session_state.pop("result",None); st.session_state.pop("workflow_status",None); st.rerun()
