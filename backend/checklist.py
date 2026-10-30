"""The RAMS review checklist, as an extraction schema.

A generic checklist built from the content a method statement and a risk
assessment are usually expected to cover (HSE guidance on risk assessment
and safe systems of work). Adapt the items to your own review form: each item
becomes one field of the structured extraction schema. The extracted value is
a list of short verbatim quotes proving the item is covered (one per table
row, list line or ticked option); an empty list means the reviewer question
is answered NO.

Item tuple: (key, label, what the document must provide, max quotes).
"""

METHOD_STATEMENT = [
    ("ms_document_control", "Document control",
     "the document control details of the pack: project name or number, revision, date of issue, who prepared "
     "and who approved it, and where the works take place (usually on the cover sheet)", 4),
    ("ms_scope", "Scope and sequence of works",
     "a description of the work to be done and how: the task, the step-by-step sequence, the work area and how "
     "operatives get to it and leave it", 2),
    ("ms_supervision", "Supervision and competence",
     "a named supervisor or person in charge on site, and evidence the operatives are competent: named people, "
     "cards, training or certificates (CSCS, IPAF, PASMA, electrical qualifications and so on)", 4),
    ("ms_briefing", "Briefing of the workforce",
     "how the method statement is explained to the people doing the work: toolbox talks, start-of-shift "
     "briefings, a briefing sign-off, and how operatives who do not read English are briefed", 3),
    ("ms_ppe", "Task-specific PPE",
     "personal protective equipment listed for this task, ideally with standards or grades, and any specialist "
     "items or face-fit testing", 6),
    ("ms_plant", "Plant, tools and equipment",
     "the plant, access equipment and tools the subcontractor brings, with their inspection or certification and "
     "how they are used, moved and stored. 'Equipment by others' or 'no plant used' does not count", 4),
    ("ms_coshh", "Hazardous substances (COSHH)",
     "the hazardous substances used or produced by the work, with their COSHH assessment and safety data sheets", 4),
    ("ms_housekeeping_environment", "Housekeeping, waste and environment",
     "how materials are stored, how the work area is kept tidy, how waste is segregated and removed, and how "
     "noise, dust and pollution are controlled", 4),
    ("ms_permits", "Permits to work",
     "the permits this work needs (hot works, isolation, work at height, confined space...), who issues them and "
     "how", 3),
    ("ms_emergency", "Emergency arrangements",
     "what happens in an emergency on this site: fire alarm and escape routes, assembly point, first aiders, "
     "rescue plan, spill or incident procedure", 4),
    ("ms_monitoring", "Monitoring and review",
     "who checks that the work follows the method statement, how often, and when the document is reviewed", 2),
    ("ms_occupational_health", "Occupational health",
     "health risks of the task (noise, dust, vibration, manual handling) with their controls and any health "
     "surveillance", 4),
]

RISK_ASSESSMENT = [
    ("ra_details", "Assessment details",
     "the header of the risk assessment itself: task, assessment number or reference, assessor, date and review "
     "date", 4),
    ("ra_hazards", "Hazards match the scope",
     "the hazards listed in the risk assessment table for the tasks of the scope of works: return every active "
     "hazard row", 8),
    ("ra_plant_hazards", "Plant and equipment hazards",
     "hazards that come from plant, power tools, access equipment, lifting equipment or materials, assessed in "
     "the risk assessment", 6),
    ("ra_persons_at_risk", "Persons at risk",
     "who may be harmed: only the options actually ticked or selected (operatives, other trades, client staff, "
     "visitors, public), or groups named in the assessment", 6),
    ("ra_control_hierarchy", "Controls beyond PPE",
     "control measures against the hazards other than PPE: elimination, substitution, engineering controls "
     "(barriers, edge protection, extraction, isolation) and procedures (exclusion zones, permits, training)", 6),
    ("ra_risk_rating", "Risk rating",
     "a risk rating for the hazards, before and after the controls: likelihood, severity, risk score or "
     "high / medium / low", 6),
    ("ra_health_hazards", "Health hazards",
     "health hazards (hazardous substances, silica or wood dust, noise, vibration, manual handling) assessed as "
     "their own rows with controls", 6),
    ("ra_exposure_limits", "Exposure limits",
     "workplace exposure limits, noise action values or vibration exposure points, stated or monitored", 4),
    ("ra_emergency", "Emergency scenarios",
     "emergencies considered in the risk assessment: rescue from height or a confined space, fire, injury, "
     "spill or plant failure", 4),
]

ALL_ITEMS = [("method_statement", "Does the Method Statement...", METHOD_STATEMENT),
             ("risk_assessment", "Does the Risk Assessment...", RISK_ASSESSMENT)]

SECTION_NOTES = {
    "method_statement": (
        "These questions are about the METHOD STATEMENT part of the pack: cover sheet, form pages, "
        "methodology, site arrangements, PPE, emergency and communication sections."
    ),
    "risk_assessment": (
        "These questions are about the RISK ASSESSMENT part of the pack: the risk assessment sheet header, "
        "the persons-affected selection and the hazard / risk / control measure tables. Answer them from those "
        "pages, not from the method statement narrative. If the pack contains no risk assessment, every item "
        "is null."
    ),
}


def build_schema(items):
    properties = {}
    for key, label, detail, limit in items:
        if limit == 1:
            count = "ONE short verbatim quote (a single array element)"
        else:
            count = (f"the verbatim FILLED-IN CONTENT that proves it: one array element per table row, list line "
                     f"or ticked option, at most {limit} elements")
        properties[key] = {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "description": (
                f"{label}: does the document actually PROVIDE {detail}? Return {count}, each under 25 words and "
                "copied exactly as printed. Return null (the item is NOT satisfied) when the document does not "
                "genuinely provide this."
            ),
        }
    return {"schema": {"type": "object", "properties": properties, "additionalProperties": False}}


INSTRUCTIONS = (
    "You are reviewing a construction RAMS pack (Risk Assessment and Method Statement) submitted by a "
    "subcontractor to the main contractor, checking whether each required point is genuinely addressed. When page "
    "images are provided, use them to read tick boxes and to notice deleted text. Read the WHOLE document, "
    "including tables and appendices, and capture real filled-in content wherever it appears "
    "(a hazard table, a controls list, a persons-at-risk selection, a methodology paragraph, etc.) even when "
    "it is brief.\n\n"
    "Return the ANSWER, never the question. Many RAMS use a form/table layout: a printed field LABEL with "
    "italic GUIDANCE on the left (or above) and the author's FILLED-IN ANSWER on the right (or beside). Read "
    "the answer side. Never return the printed label, the section heading, or the italic guidance that tells "
    "the author what to write. Example: the form prints 'COSHH: A comprehensive list of materials is to be "
    "entered here...' as the label and 'N/A' as the answer - the answer is 'N/A', so that item is NOT "
    "satisfied; return null. Guidance phrases like 'to be entered here', 'how will you...', 'what "
    "activities...', 'describe...', 'this will highlight...' are never valid evidence.\n\n"
    "When the form has a dedicated field for a topic (COSHH, permits, housekeeping, plant/equipment, waste, "
    "noise, manual handling, work at height...), that field's answer decides: if it is N/A, None, blank or "
    "'No', the item is NOT satisfied even if the topic is mentioned in passing elsewhere.\n\n"
    "Struck-through text (a line drawn through the words) has been deleted by the author and is not part of "
    "the document: never quote it and never count it as evidence. Tick boxes and YES/NO toggles: only an "
    "option carrying a tick, cross or other mark is selected; options without a mark are NOT selected and "
    "must never be returned. A tick may appear in the text as a symbol such as ✓, ✔, x or the "
    "Wingdings glyph U+F0FC, placed next to the option it marks.\n\n"
    "When the evidence is a table or list (hazards, controls, PPE items, persons at risk), return every "
    "relevant active row or ticked option as its own array element, in document order.\n\n"
    "Treat an item as NOT satisfied (return null) only when the answer is genuinely missing: a blank answer "
    "cell, an answer that is nothing but 'N/A'/'None'/'Nil'/a dash/'TBC', an unticked YES / NO toggle, "
    "struck-through text, or an unfilled pre-printed prompt. When real content IS present, return it.\n\n"
    "Copy answers verbatim. Give each checklist item its own distinct evidence - do not reuse one sentence "
    "for several different items."
)


def instructions_for(section_key):
    return INSTRUCTIONS + "\n\n" + SECTION_NOTES[section_key]
