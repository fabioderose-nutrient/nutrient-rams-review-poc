"""Generates the fictitious RAMS packs in inputs/.

Every company, project, person and reference in these documents is invented.
The three packs are built to exercise the reviewer:

  fenwick-ductwork-high-level.pdf    a complete pack: every item is covered
  brightline-containment-first-fix.pdf  a good pack with gaps: unticked persons
                                     at risk, a struck-through hazard row, no
                                     exposure limits, no monitoring
  harrow-soft-strip.pdf              a weak pack: form guidance left in place,
                                     N/A and TBC answers, generic PPE, rows
                                     deleted with a line through them

    pip install -r samples/requirements.txt
    python samples/generate_rams.py
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, NextPageTemplate, PageBreak, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

OUT = Path(__file__).resolve().parent.parent / "inputs"

BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9, leading=11.5)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=10)
GUIDE = ParagraphStyle("guide", parent=BODY, fontName="Helvetica-Oblique", fontSize=7.5, leading=9.5,
                       textColor=colors.HexColor("#555555"))
LABEL = ParagraphStyle("label", parent=BODY, fontName="Helvetica-Bold")
H1 = ParagraphStyle("h1", parent=BODY, fontName="Helvetica-Bold", fontSize=18, leading=22, alignment=TA_CENTER)
H2 = ParagraphStyle("h2", parent=BODY, fontName="Helvetica-Bold", fontSize=12, leading=15, spaceBefore=6,
                    spaceAfter=4)
CENTER = ParagraphStyle("center", parent=BODY, alignment=TA_CENTER)

TICK = "[X]"   # a ticked box, as typed in a Word form
BOX = "[&nbsp;&nbsp;]"   # an empty box
GRID = [("GRID", (0, 0), (-1, -1), 0.6, colors.black), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
SHADE = colors.HexColor("#e4e8ee")


def p(text, style=BODY):
    return Paragraph(text, style)


def struck(text):
    return f"<strike>{text}</strike>"


class Pack:
    """One RAMS document: a cover sheet, the method statement as a two-column
    form (printed label and guidance on the left, the author's answer on the
    right), then a landscape risk assessment table."""

    def __init__(self, filename, company, reference, title, project, location):
        self.filename, self.company, self.reference, self.title = filename, company, reference, title
        self.project, self.location = project, location
        self.story = []

    def _header(self, canvas, doc):
        canvas.saveState()
        w, h = doc.pagesize
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(15 * mm, h - 12 * mm, self.company)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - 15 * mm, h - 12 * mm, f"{self.reference}  -  {self.title}")
        canvas.line(15 * mm, h - 14 * mm, w - 15 * mm, h - 14 * mm)
        canvas.drawString(15 * mm, 10 * mm, "Uncontrolled when printed")
        canvas.drawRightString(w - 15 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    def cover(self, rows, approved):
        s = self.story
        s += [Spacer(1, 18 * mm), p(self.company, CENTER), Spacer(1, 4 * mm),
              p("RISK ASSESSMENT AND METHOD STATEMENT", H1), Spacer(1, 3 * mm), p(self.title, H1),
              Spacer(1, 12 * mm)]
        data = [[p("Project", LABEL), p(self.project)], [p("Location of works", LABEL), p(self.location)],
                [p("Document reference", LABEL), p(self.reference)]] + [[p(k, LABEL), p(v)] for k, v in rows]
        s.append(Table(data, colWidths=[55 * mm, 115 * mm], style=GRID + [("BACKGROUND", (0, 0), (0, -1), SHADE)]))
        s.append(Spacer(1, 10 * mm))
        s.append(p("Revision history", H2))
        rev = [[p(x, LABEL) for x in ("Rev", "Date", "Description", "Prepared by", "Approved by")]] + \
              [[p(c) for c in r] for r in approved]
        s.append(Table(rev, colWidths=[14 * mm, 24 * mm, 62 * mm, 35 * mm, 35 * mm],
                       style=GRID + [("BACKGROUND", (0, 0), (-1, 0), SHADE)]))
        s.append(PageBreak())

    def form(self, heading, rows):
        """Method statement section: label + guidance | answer."""
        self.story.append(p(heading, H2))
        data = [[[p(label, LABEL), p(guide, GUIDE)], [p(a) for a in (answer if isinstance(answer, list) else [answer])]]
                for label, guide, answer in rows]
        self.story.append(Table(data, colWidths=[62 * mm, 118 * mm],
                                style=GRID + [("BACKGROUND", (0, 0), (0, -1), SHADE)]))
        self.story.append(Spacer(1, 4 * mm))

    def text(self, heading, paragraphs):
        self.story.append(p(heading, H2))
        for para in paragraphs:
            self.story += [p(para), Spacer(1, 2 * mm)]

    def risk_assessment(self, header, persons, rows, footer=None):
        s = self.story
        s += [NextPageTemplate("landscape"), PageBreak(), p("RISK ASSESSMENT", H2)]
        pairs = [[p(k, LABEL), p(v), p(k2, LABEL), p(v2)] for (k, v), (k2, v2) in zip(header[0::2], header[1::2])]
        s.append(Table(pairs,
                       colWidths=[38 * mm, 95 * mm, 38 * mm, 95 * mm],
                       style=GRID + [("BACKGROUND", (0, 0), (0, -1), SHADE), ("BACKGROUND", (2, 0), (2, -1), SHADE)]))
        s.append(Spacer(1, 3 * mm))
        options = "&nbsp;&nbsp;&nbsp;&nbsp;".join(f"{TICK if on else BOX} {name}" for name, on in persons)
        s.append(Table([[p("Persons at risk (tick all that apply)", LABEL), p(options)]],
                       colWidths=[60 * mm, 206 * mm], style=GRID + [("BACKGROUND", (0, 0), (0, 0), SHADE)]))
        s.append(Spacer(1, 3 * mm))
        head = ["Activity / hazard", "Risk", "L", "S", "R", "Control measures", "Residual"]
        data = [[p(h, LABEL) for h in head]]
        for row in rows:
            data.append([p(c, SMALL) for c in row])
        s.append(Table(data, colWidths=[42 * mm, 52 * mm, 8 * mm, 8 * mm, 9 * mm, 125 * mm, 22 * mm],
                       repeatRows=1, style=GRID + [("BACKGROUND", (0, 0), (-1, 0), SHADE)]))
        s.append(p("L = likelihood, S = severity (1 to 5), R = L x S. 1-6 low, 8-12 medium, 15-25 high.", SMALL))
        if footer:
            s += [Spacer(1, 3 * mm)] + [p(f, BODY) for f in footer]

    def briefing(self, names):
        s = self.story
        s += [NextPageTemplate("portrait"), PageBreak(), p("BRIEFING RECORD", H2),
              p("I confirm that the contents of this RAMS have been explained to me and that I understand them.")]
        data = [[p(h, LABEL) for h in ("Name", "Company", "Card / qualification", "Signature", "Date")]]
        data += [[p(n), p(c), p(q), p(""), p(d)] for n, c, q, d in names]
        data += [[p("")] * 5 for _ in range(4)]
        s.append(Table(data, colWidths=[40 * mm, 40 * mm, 45 * mm, 30 * mm, 25 * mm],
                       rowHeights=[None] + [9 * mm] * (len(data) - 1),
                       style=GRID + [("BACKGROUND", (0, 0), (-1, 0), SHADE)]))

    def build(self):
        doc = BaseDocTemplate(str(OUT / self.filename), pagesize=A4, title=f"{self.reference} {self.title}",
                              author=self.company, leftMargin=15 * mm, rightMargin=15 * mm,
                              topMargin=20 * mm, bottomMargin=16 * mm)
        pw, ph = A4
        lw, lh = landscape(A4)
        doc.addPageTemplates([
            PageTemplate("portrait", [Frame(15 * mm, 16 * mm, pw - 30 * mm, ph - 36 * mm)], onPage=self._header,
                         pagesize=A4),
            PageTemplate("landscape", [Frame(15 * mm, 16 * mm, lw - 30 * mm, lh - 36 * mm)], onPage=self._header,
                         pagesize=landscape(A4)),
        ])
        doc.build(self.story)
        print(self.filename)


# ------------------------------------------------------------------ packs

def complete_pack():
    d = Pack("fenwick-ductwork-high-level.pdf", "Fenwick Air Systems Ltd", "FAS-RAMS-014",
             "Installation of ductwork at high level", "Quayside House, Level 3 office fit-out",
             "Quayside House, 40 Dock Street, Northbridge NB1 7HS - Level 3 open plan and riser 2")
    d.cover([("Activity", "Installation of supply and extract ductwork, supports and fire dampers above the "
                          "ceiling grid"),
             ("Programme", "Start 9 November 2026, duration 4 weeks, Monday to Friday 07:30 to 17:00"),
             ("Prepared by", "Lena Marsh, Contracts Manager"), ("Approved by", "Owen Pryce, H&S Manager")],
            [("A", "12/10/2026", "First issue for comment", "L. Marsh", "O. Pryce"),
             ("B", "26/10/2026", "Main contractor comments: rescue plan, briefing", "L. Marsh", "O. Pryce")])
    d.form("1. SCOPE AND SEQUENCE OF WORKS", [
        ("Scope of works", "Describe the work to be carried out and where.",
         "Install galvanised supply and extract ductwork (approx. 220 m), threaded rod supports, 14 fire "
         "dampers and 36 grilles above the suspended ceiling grid on Level 3, and connect to the risers."),
        ("Sequence", "Set out the work step by step.",
         ["1. Set out support positions from the coordinated drawings and mark the soffit.",
          "2. Drill and fix anchors with on-tool dust extraction, install drop rods and unistrut.",
          "3. Lift duct sections with a material hoist and fix to supports from podium steps or MEWP.",
          "4. Install fire dampers in the riser walls, seal joints, pressure test and label."]),
        ("Access and egress", "How will operatives reach and leave the work area?",
         "Access via the main core stair and goods lift to Level 3. Work area segregated with barriers and "
         "signage; walkways kept clear to the fire exits in core A and core B."),
    ])
    d.form("2. PEOPLE", [
        ("Supervisor", "Who is in charge of the work on site?",
         "Site supervisor: Callum Reid (SSSTS, first aid at work), on site full time."),
        ("Competence", "What training and cards do the operatives hold?",
         ["All operatives hold CSCS cards (ductwork installer, blue skilled worker).",
          "MEWP operators hold IPAF 3a/3b; two operatives hold PASMA for the mobile tower.",
          "Fire damper installers trained by the damper manufacturer (certificates in appendix C)."]),
        ("Briefing", "How will the RAMS be communicated to the workforce?",
         ["The supervisor briefs this RAMS to every operative before starting; each signs the briefing record.",
          "Daily start-of-shift briefing on the work area, permits and changes to the sequence.",
          "Operatives with limited English are briefed with a translated summary and a team leader who "
          "speaks their language."]),
    ])
    d.form("3. EQUIPMENT AND MATERIALS", [
        ("PPE", "List the PPE required for this task.",
         ["Safety helmet to EN 397 with chin strap when working from the MEWP.",
          "Safety boots S3, hi-vis vest, cut-resistant gloves level C (EN 388).",
          "Safety glasses EN 166, FFP3 disposable mask (face-fit tested) when drilling concrete."]),
        ("Plant and equipment", "List plant, tools and access equipment and their inspection.",
         ["Scissor lift MEWP (Genie GS-1932 or similar): LOLER certificate, daily pre-use check.",
          "Podium steps and one mobile aluminium tower: weekly inspection, tagged.",
          "110 V drills with on-tool extraction, PAT tested; material hoist with valid LOLER thorough examination."]),
        ("COSHH", "List hazardous substances and attach COSHH assessments.",
         ["Duct sealant (water based): COSHH assessment CA-031 and safety data sheet attached.",
          "Fire-rated mastic for damper installation: COSHH assessment CA-044 and safety data sheet attached.",
          "Concrete dust from drilling: controlled by on-tool extraction and FFP3 masks."]),
        ("Storage, housekeeping and waste", "How will materials and waste be managed?",
         ["Duct sections delivered just in time and stored in the agreed laydown area on Level 3.",
          "Work area cleaned at the end of each shift; offcuts segregated into the metal skip.",
          "Packaging returned to the supplier; dust controlled by extraction, no dry sweeping."]),
        ("Permits", "Which permits to work are needed?",
         ["Hot works permit from the main contractor for any cutting in the riser (none planned).",
          "Permit to work at height on the MEWP issued daily by the main contractor site manager."]),
    ])
    d.form("4. EMERGENCY, MONITORING AND HEALTH", [
        ("Emergency arrangements", "Describe the site emergency procedures.",
         ["On the fire alarm, stop work, lower the MEWP and leave by the nearest protected stair.",
          "Assembly point: Dock Street car park, point B.",
          "First aiders: Callum Reid and the main contractor's site team; first aid kit in the site office.",
          "MEWP rescue plan: ground-level controls operated by a trained second person (appendix D)."]),
        ("Monitoring", "How will the safe system of work be monitored?",
         ["Callum Reid checks the work area and MEWP daily and records it in the daily diary.",
          "Contracts manager inspection every two weeks; RAMS reviewed if the scope or sequence changes."]),
        ("Occupational health", "Which health risks apply and how are they controlled?",
         ["Noise from drilling: low-noise drills, hearing protection in the marked zone.",
          "Hand-arm vibration: drilling limited to 60 minutes per operative per day (below the exposure action "
          "value of 100 points).",
          "Manual handling: duct sections over 20 kg lifted with the material hoist; health surveillance for "
          "drilling operatives."]),
    ])
    d.risk_assessment(
        [("Task", "Ductwork installation at high level"), ("Assessment no.", "FAS-RA-014"),
         ("Assessed by", "Lena Marsh"), ("Date", "26/10/2026"),
         ("Review date", "Start of works or any change of scope"), ("Location", "Quayside House, Level 3")],
        [("Own operatives", True), ("Other trades", True), ("Client staff", False), ("Visitors", True),
         ("Members of the public", False)],
        [("Work at height from MEWP", "Fall from platform, operative injured", "3", "5", "15",
          "Trained IPAF operators only; harness with short lanyard on boom lifts; guardrails closed; floor "
          "checked for loading and openings; exclusion zone below.", "Low (5)"),
         ("Falling objects", "Tools or duct sections fall on people below", "3", "4", "12",
          "Exclusion zone with barriers and signs; tool lanyards; duct secured before release.", "Low (4)"),
         ("Drilling concrete soffit", "Silica dust inhaled", "4", "4", "16",
          "On-tool extraction (M-class), FFP3 masks face-fit tested, no dry sweeping.", "Low (6)"),
         ("Hand-arm vibration from drills", "HAVS", "3", "3", "9",
          "Low-vibration drills, trigger time recorded, rotation of tasks, exposure kept below 100 points.",
          "Low (3)"),
         ("Manual handling of duct sections", "Back injury", "3", "3", "9",
          "Material hoist for sections over 20 kg, two-person lifts, trolleys on the floor.", "Low (3)"),
         ("Noise", "Hearing damage", "3", "3", "9",
          "Low-noise tools; hearing protection zone above 80 dB(A); daily exposure checked.", "Low (3)"),
         ("Use of 110 V power tools", "Electric shock", "2", "4", "8",
          "110 V CTE supply, PAT tested tools, leads routed off the floor.", "Low (2)"),
         ("Hot works in riser (if needed)", "Fire", "2", "5", "10",
          "Hot works permit, fire watch 60 minutes after work, extinguisher at the work area.", "Low (4)")],
        footer=["Emergency: MEWP rescue by ground controls (trained second person on every shift); fire alarm "
                "procedure and assembly point as section 4; spill kit for sealant in the site store."])
    d.briefing([("Callum Reid", "Fenwick Air Systems", "CSCS, SSSTS, IPAF 3a/3b", "09/11/2026"),
                ("Tomasz Wrona", "Fenwick Air Systems", "CSCS, IPAF 3a/3b", "09/11/2026"),
                ("Dev Malhotra", "Fenwick Air Systems", "CSCS, PASMA", "09/11/2026")])
    d.build()


def pack_with_gaps():
    d = Pack("brightline-containment-first-fix.pdf", "Brightline Electrical Contractors Ltd", "BLE-RAMS-007",
             "Electrical containment and first fix", "Riverside Quarter office refurbishment",
             "Riverside Quarter, 3 Wharf Road, Northbridge NB3 8AF - floors 2 and 3")
    d.cover([("Activity", "Installation of cable tray, basket and conduit, and first fix wiring to the "
                          "small power and lighting circuits"),
             ("Prepared by", "Priya Natt"), ("Date of issue", "19/10/2026")],
            [("01", "19/10/2026", "First issue", "P. Natt", "G. Holloway")])
    d.form("METHOD STATEMENT", [
        ("Scope of works", "Describe the work to be carried out and where.",
         "Install cable tray and basket in the ceiling void and conduit drops to floor boxes on floors 2 and 3, "
         "then pull and terminate first fix cabling to distribution boards DB2A and DB3A."),
        ("Sequence of works", "Set out the work step by step.",
         ["Mark out routes from the containment drawings E-201 and E-301.",
          "Fix tray supports, install tray and basket, earth bond all sections.",
          "Install conduit drops, pull cables from drums on stands, label and test continuity."]),
        ("Supervisor and competence", "Who supervises and what are the operatives' qualifications?",
         ["Supervisor: Gary Holloway, Approved Electrician (JIB), SMSTS.",
          "Electricians hold ECS gold cards; apprentices work under direct supervision."]),
        ("Communication", "How will the RAMS be briefed?",
         "Toolbox talk on this RAMS before the start, briefing record signed by all operatives."),
        ("PPE", "List the PPE required for this task.",
         ["Safety helmet, safety boots, hi-vis vest, gloves to EN 388.",
          "Safety glasses when drilling or cutting tray; dust mask FFP3 when drilling."]),
        ("Plant and equipment", "List plant and tools and how they are inspected.",
         ["Podium steps (weekly inspection, tagged) and one scissor lift with LOLER certificate.",
          "Cordless drills and tray cutters; cable drum stands and rollers."]),
        ("COSHH", "List hazardous substances and attach COSHH assessments.",
         "Cable pulling lubricant: COSHH assessment BLE-C-12 and safety data sheet attached."),
        ("Housekeeping and waste", "How will materials and waste be managed?",
         ["Cable drums stored on the floor laydown area, tray in racks.",
          "Offcuts of tray and cable segregated in the metal and cable recycling bins at the end of each day."]),
        ("Permits", "Which permits to work are needed?",
         "Permit to work for any work on or near the existing live distribution boards, issued by the "
         "main contractor's authorised person. Isolation and lock-off before connection."),
        ("Emergency", "Describe the emergency procedures.",
         ["Fire: raise the alarm, leave by the nearest stair, assemble at Wharf Road gate.",
          "Electric shock: isolate, call 999, trained first aider Gary Holloway; defibrillator at reception."]),
        ("Monitoring", "How will the safe system of work be monitored?", "N/A"),
        ("Occupational health", "Which health risks apply and how are they controlled?",
         "Manual handling of cable drums: drum stands and rollers, two-person lifts."),
    ])
    d.risk_assessment(
        [("Task", "Containment and first fix wiring"), ("Assessment no.", "BLE-RA-007"),
         ("Assessed by", "Priya Natt"), ("Date", "19/10/2026"),
         ("Review date", "19/01/2027"), ("Location", "Riverside Quarter, floors 2 and 3")],
        [("Own operatives", True), ("Other trades", False), ("Client staff", False), ("Visitors", False),
         ("Members of the public", False)],
        [("Work from podium steps and scissor lift", "Fall from height", "3", "4", "12",
          "Podium steps with gates closed; IPAF-trained scissor lift operators; no over-reaching.", "Low (4)"),
         ("Use of power tools and tray cutters", "Cuts, entanglement", "3", "3", "9",
          "Guards fitted, cut-resistant gloves, tools inspected before use.", "Low (3)"),
         ("Cable pulling", "Manual handling, strain injury", "3", "3", "9",
          "Drum stands and rollers, two-person pulls, rotation of tasks.", "Low (3)"),
         ("Work near live boards", "Electric shock, burns", "2", "5", "10",
          "Permit to work, safe isolation procedure, lock-off, proving unit, insulated tools.", "Low (5)"),
         (struck("Asbestos in ceiling void"), struck("Exposure to asbestos fibres"), struck("2"), struck("5"),
          struck("10"), struck("Refurbishment survey checked before work; stop and report if suspect material "
                              "is found."), struck("Low (5)")),
         ("Drilling into concrete", "Dust", "3", "3", "9",
          "Cordless drills with dust shrouds, FFP3 masks.", "Low (3)")],
        footer=["Emergency: rescue from the scissor lift by ground controls; electric shock procedure as the "
                "method statement."])
    d.briefing([("Gary Holloway", "Brightline Electrical", "ECS gold, SMSTS", "02/11/2026"),
                ("Ana Ribeiro", "Brightline Electrical", "ECS gold", "02/11/2026")])
    d.build()


def weak_pack():
    d = Pack("harrow-soft-strip.pdf", "Harrow & Stone Demolition Ltd", "HSD-RAMS-002",
             "Soft strip of office floor", "Riverside Quarter office refurbishment",
             "Riverside Quarter, 3 Wharf Road, Northbridge NB3 8AF")
    d.cover([("Activity", "Soft strip"), ("Prepared by", "M. Kerr")],
            [("1", "05/10/2026", "Issued", "M. Kerr", "")])
    d.form("METHOD STATEMENT", [
        ("Scope of works", "Describe the work to be carried out and where.",
         "Strip out of ceilings, raised floor, partitions and carpets on floor 2 and load out to skips."),
        ("Sequence of works", "Set out the work step by step.",
         "Work will be carried out in a safe manner in accordance with company procedures."),
        ("Supervisor", "Who is in charge of the work on site? Insert details.",
         "Insert details"),
        ("Communication", "How will you communicate this RAMS to the workforce?",
         "How will you communicate this RAMS to the workforce?"),
        ("PPE", "List the PPE required for this task.", "PPE to be worn at all times."),
        ("Plant and equipment", "List of plant and equipment to be used.", "Equipment provided by others."),
        ("COSHH", "A comprehensive list of materials is to be entered here with the COSHH assessments attached.",
         "N/A"),
        ("Housekeeping and waste", "How will materials and waste be managed?",
         ["Waste loaded into skips provided by the main contractor.",
          struck("Waste segregated into wood, metal, plasterboard and general skips.")]),
        ("Permits", "Which permits to work are needed?", "TBC"),
        ("Emergency", "Describe the emergency procedures.", "As site induction."),
        ("Monitoring", "How will the safe system of work be monitored?", "-"),
        ("Occupational health", "Which health risks apply and how are they controlled?", "None"),
    ])
    d.risk_assessment(
        [("Task", "Soft strip"), ("Assessment no.", ""), ("Assessed by", "M. Kerr"), ("Date", "05/10/2026"),
         ("Review date", ""), ("Location", "Floor 2")],
        [("Own operatives", False), ("Other trades", False), ("Client staff", False), ("Visitors", False),
         ("Members of the public", False)],
        [("Manual handling", "Injury", "", "", "", "Lift correctly.", ""),
         ("Slips, trips and falls", "Injury", "", "", "", "Keep area tidy.", ""),
         (struck("Removal of ceiling tiles from tower"), struck("Fall from height"), struck("3"), struck("5"),
          struck("15"), struck("PASMA-trained operatives, tower inspected, guardrails fitted."), struck("Low")),
         (struck("Cutting partitions"), struck("Dust, noise"), struck("3"), struck("3"), struck("9"),
          struck("On-tool extraction, FFP3 masks, hearing protection."), struck("Low"))])
    d.build()


def main():
    OUT.mkdir(exist_ok=True)
    complete_pack()
    pack_with_gaps()
    weak_pack()


if __name__ == "__main__":
    main()
