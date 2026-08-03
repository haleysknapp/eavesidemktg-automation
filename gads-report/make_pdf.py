#!/usr/bin/env python3
"""Render a report HTML file to a print-ready PDF (Letter, branded margins).
Usage: python3 make_pdf.py <input.html> <output.pdf>"""
import sys
from playwright.sync_api import sync_playwright

def make_pdf(html_path, pdf_path):
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        pg.goto(f"file://{html_path}")
        pg.wait_for_timeout(600)
        pg.pdf(path=pdf_path, format="Letter", print_background=True,
               margin={"top": "0.75in", "bottom": "0.65in", "left": "0.45in", "right": "0.45in"})
        b.close()

if __name__ == "__main__":
    make_pdf(sys.argv[1], sys.argv[2])
    print(f"[saved] {sys.argv[2]}")
