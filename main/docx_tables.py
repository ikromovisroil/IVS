from docx.shared import Pt,Cm
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

#Akt
def fix_table_layout(table):
    table.autofit = False
    tbl = table._tbl
    tblPr = tbl.tblPr

    for el in tblPr.findall("w:tblLayout", tbl.nsmap):
        tblPr.remove(el)

    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)

#Akt width
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

#Akt text
def set_cell_text(cell, text, bold=False, center=False):
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run("" if text is None else str(text))
    run.font.name = "Times New Roman"
    run.font.size = Pt(8)
    run.bold = bold

    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1

    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

#Akt
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

#Akt
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

#Akt table all
def create_table_akt(doc, title, data, headers):

    widths = [1, 4, 3, 5, 2, 2, 4, 4, 3]

    h = doc.add_paragraph()
    r = h.add_run(title)
    r.bold = True
    r.font.name = "Times New Roman"
    r.font.size = Pt(10)

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

#Dallatnoma table
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

#Svod table
def create_table_cols_svod(doc, data, headers, grand_total=0):
    widths = [1, 7.5, 2, 2, 4, 4, 5.5, 2]

    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    fix_table_layout(table)
    set_table_borders(table)
    force_tbl_grid(table, widths)

    # Header
    hdr = table.rows[0].cells
    for i, text in enumerate(headers):
        set_cell_text(hdr[i], text, bold=True, center=True)
        set_col_width(hdr[i], widths[i])

    # Data
    for idx, row in enumerate(data, start=1):
        cells = table.add_row().cells
        full = [idx] + list(row)

        while len(full) < len(headers):
            full.append("")

        for i, val in enumerate(full[:len(headers)]):
            set_cell_text(cells[i], val, center=True)
            set_col_width(cells[i], widths[i])

    # ✅ 1 ta JAMI qator (0..5 merge, summa 5-ustunda)
    sum_value = f"{grand_total:,}".replace(",", " ")

    r = table.add_row().cells

    # 0..4 merge qilsak, 5-ustun (Umumiy qiymati) alohida qoladi
    m = r[0]
    for j in range(1, 5):   # 0..4 merge
        m = m.merge(r[j])

    set_cell_text(r[0], "J A M I:", bold=True, center=True)
    set_cell_text(r[5], sum_value, bold=True, center=True)

    # qolgan ustunlar bo'sh qoladi
    set_cell_text(r[6], "", center=False)  # Eslatma
    set_cell_text(r[7], "", center=True)   # Kod 1C

    return table

#Reestr text
def set_cell_text_reestr(cell, text, bold=False, center=False, font_size=7):
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run("" if text is None else str(text))
    run.font.name = "Times New Roman"
    run.font.size = Pt(font_size)
    run.bold = bold

    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1

    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

#Reestr table
def create_table_cols_reestr(doc, data, grand_total=0):
    """
    data: har bir qator 14 ta qiymat (№ bu funksiyada qo‘shiladi)
    [Qurilma, Seriya, Material, Soni, Birlik narx, Umumiy,
     FIO, Lavozim, Tashkilot, Kim o‘rnatgan, Sana, Sorov №, Sorov sana, 1C]
    """

    # 15 ta ustun uchun width ham 15 ta bo‘lsin
    widths = [0.7, 2.2, 2, 3.0, 0.9, 1.7, 1.9, 2.7, 2.0, 3.0, 2.7, 1.7, 1.4, 1.7, 1.4]

    # ✅ 2 qatorli header, 15 ustun
    table = doc.add_table(rows=2, cols=15)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    fix_table_layout(table)
    set_table_borders(table)
    force_tbl_grid(table, widths)

    h1 = table.rows[0].cells
    h2 = table.rows[1].cells

    # Bitta ustunli sarlavhalar (yuqoridan pastga merge)
    single = {
        0: "№",
        1: "Qurilma nomi",
        2: "Seriya №",
        3: "Sarf materiallari nomi",
        4: "Soni",
        5: "Birlikdagi narxi",
        6: "Materiallarning\numumiy qiymati",
        9: "Tashkilot, bo'lim nomi",
        10: "Kim tomonidan\no'rnatilgan",
        11: "O'rnatish\nsanasi",
        12: "So'rovnoma №",
        13: "So'rovnoma\nsanasi",
        14: "1C\nkodi",
    }

    for col_idx, text in single.items():
        cell = h1[col_idx].merge(h2[col_idx])
        set_cell_text_reestr(cell, text, bold=True, center=True, font_size=7)
        set_col_width(cell, widths[col_idx])

    # Guruhlangan header: Qurilmadan foydalanuvchi (7,8)
    grp = h1[7].merge(h1[8])
    set_cell_text_reestr(grp, "Qurilmadan foydalanuvchi", bold=True, center=True, font_size=7)

    set_cell_text_reestr(h2[7], "F.I.Sh.", bold=True, center=True, font_size=8)
    set_cell_text_reestr(h2[8], "Lavozimi", bold=True, center=True, font_size=8)

    set_col_width(h2[7], widths[7])
    set_col_width(h2[8], widths[8])

    # ✅ Data qatorlari
    for idx, row in enumerate(data, start=1):
        cells = table.add_row().cells

        # row: 14 ta bo‘lishi kerak, № boshiga qo‘shiladi => 15
        full = [idx] + list(row)

        while len(full) < 15:
            full.append("")

        for i, val in enumerate(full[:15]):
            set_cell_text_reestr(cells[i], val, center=True, font_size=8)
            set_col_width(cells[i], widths[i])

    # ✅ JAMI qatori: summa 6-ustunda (Umumiy qiymat)
    sum_value = f"{int(grand_total or 0):,}".replace(",", " ")
    r = table.add_row().cells

    # 0..5 merge (№ dan Birlik narxigacha)
    merged = r[0]
    for j in range(1, 6):   # 1..5
        merged = merged.merge(r[j])

    set_cell_text_reestr(r[0], "J A M I:", bold=True, center=True, font_size=8)
    set_cell_text_reestr(r[6], sum_value, bold=True, center=True, font_size=8)

    # qolgan ustunlar bo‘sh
    for k in range(7, 15):
        set_cell_text_reestr(r[k], "", center=True, font_size=8)

    return table



