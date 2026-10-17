# InvoiceFlow AI — PDF-first prototype

The simplified interface accepts PDF documents and shows a readable reconciliation report. JSON is not exposed in the user interface.

## Windows setup
Extract the ZIP. Open the extracted folder in File Explorer, click the address bar, type `cmd`, press Enter, then run one command at a time:

```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

If activation fails, use the environment directly:
```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

## Linux setup
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Upload an invoice PDF and either use the built-in sample PO or upload a PO PDF.

## Limitations
PDF parsing is best-effort and layout-dependent. Scanned PDFs require OCR, not included yet. Review extracted data before acting. Approval is simulated; no ERP or payment provider is connected. Use synthetic documents during development.
