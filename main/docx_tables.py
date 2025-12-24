from docx.shared import Pt,Cm
from docx.enum.table import  WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def fix_table_layout(table):
    table.autofit = False
    tbl = table._tbl
    tblPr = tbl.tblPr

    for el in tblPr.findall("w:tblLayout", tbl.nsmap):
        tblPr.remove(el)

    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)


def set_col_width(cell, cm):
    twips = int(cm * 567)
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()

    for el in tcPr.findall("w:tcW", tcPr.nsmap):
        tcPr.remove(el)

    tcW = OxmlElement("w:tcW")
    tcW.set(qn("w:w"), str(twips))
    tcW.set(qn("w:type"), "dxa")
    tcPr.append(tcW)


def set_cell_text(cell, text, bold=False, center=False):
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run("" if text is None else str(text))
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)
    run.bold = bold

    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1

    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def set_table_borders(table):
    tbl = table._tbl
    tblPr = tbl.tblPr

    for el in tblPr.findall("w:tblBorders", tbl.nsmap):
        tblPr.remove(el)

    borders = OxmlElement("w:tblBorders")
    for side in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "8")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        borders.append(el)

    tblPr.append(borders)


def force_tbl_grid(table, widths_cm):
    tbl = table._tbl

    # eski tblGrid ni o‘chiramiz
    for el in tbl.findall("w:tblGrid", tbl.nsmap):
        tbl.remove(el)

    tblGrid = OxmlElement("w:tblGrid")

    for w in widths_cm:
        gridCol = OxmlElement("w:gridCol")
        gridCol.set(qn("w:w"), str(int(w * 567)))
        tblGrid.append(gridCol)

    # ❗ tblGrid HAR DOIM tblPr DAN KEYIN turishi shart
    tbl.insert(1, tblGrid)



def replace_text(doc, replacements: dict):
    """
    DOCX ichidagi barcha paragraph va table cell run'larida
    matnlarni almashtiradi (Word + LibreOffice mos).
    """
    # Oddiy paragraphlar
    for p in doc.paragraphs:
        for run in p.runs:
            for old, new in replacements.items():
                if old in run.text:
                    run.text = run.text.replace(old, new)
                    run.font.name = "Times New Roman"
                    run.font.size = Pt(12)

    # Jadval ichidagi matnlar
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for run in p.runs:
                        for old, new in replacements.items():
                            if old in run.text:
                                run.text = run.text.replace(old, new)
                                run.font.name = "Times New Roman"
                                run.font.size = Pt(12)


def create_table_10cols(doc, title, data, headers):

    widths = [1, 4, 3, 3, 2, 2, 5, 4, 3]

    h = doc.add_paragraph()
    r = h.add_run(title)
    r.bold = True
    r.font.name = "Times New Roman"
    r.font.size = Pt(12)

    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    fix_table_layout(table)
    set_table_borders(table)
    force_tbl_grid(table, widths)

    hdr = table.rows[0].cells
    for i, text in enumerate(headers):
        set_cell_text(hdr[i], text, bold=True, center=True)
        set_col_width(hdr[i], widths[i])

    for idx, row in enumerate(data, start=1):
        cells = table.add_row().cells
        full = [idx] + row
        for i, val in enumerate(full):
            set_cell_text(cells[i], val, center=True)
            set_col_width(cells[i], widths[i])

    return h, table


def set_column_widths(table, widths_cm):
    """
    Ustun kengliklarini sm bo‘yicha o‘rnatish.
    widths_cm: [1, 3.5, 3, 2] kabi ro‘yxat (sm).
    """
    for col, w in zip(table.columns, widths_cm):
        col.width = Cm(w)


def style_cell_paragraph(cell, bold=False, center=True, font_size=11):
    """
    Har bir katak matnini normal ko‘rinishga keltirish:
    - Times New Roman
    - 11 pt
    - bo‘sh joylarsiz
    """
    for p in cell.paragraphs:
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1
        if center:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        for r in p.runs:
            r.font.name = 'Times New Roman'
            r.font.size = Pt(font_size)
            r.bold = bold


def create_table(doc, title, data, headers):
    if not data:
        return None, None

    # 🔥 WORD-FIRST WIDTHS (sm)
    if len(headers) == 4:
        widths = [1, 6, 4, 4]
    else:
        widths = [1, 7, 4]

    # --- Sarlavha ---
    h = doc.add_paragraph()
    r = h.add_run(title)
    r.bold = True
    r.font.name = "Times New Roman"
    r.font.size = Pt(12)

    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Normal Table"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # 🔥 MUHIM SOZLAMALAR
    fix_table_layout(table)
    set_table_borders(table)
    force_tbl_grid(table, widths)

    # --- Header ---
    hdr = table.rows[0].cells
    for i, text in enumerate(headers):
        hdr[i].text = text
        style_cell_paragraph(hdr[i], bold=True, center=True)
        set_col_width(hdr[i], widths[i])

    # --- Data ---
    for idx, row in enumerate(data, start=1):
        tr = table.add_row().cells
        tr[0].text = str(idx)
        tr[1].text = row.get("name") or ""

        if len(headers) == 4:
            tr[2].text = row.get("serial") or ""
            tr[3].text = row.get("inventory") or ""
        else:
            tr[2].text = row.get("serial") or ""

        for i, cell in enumerate(tr):
            style_cell_paragraph(cell, center=True)
            set_col_width(cell, widths[i])

    return h, table
