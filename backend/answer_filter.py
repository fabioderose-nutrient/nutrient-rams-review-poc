"""Deterministic safety net rejecting non-answers.

The AI confidence score reflects how sure the model is that the quoted text
appears in the document, not whether it actually answers the checklist
question. So a value can be verbatim-present yet be the form's pre-printed
guidance, a bare "N/A", or an unfilled prompt. Those are demoted to NOT
satisfied here, whatever the model returned.
"""

import re

# Pre-printed guidance / instruction phrases seen on RAMS form templates: if the
# extracted value is built around one of these, it is the label side of the
# form, not the author's answer.
_GUIDANCE = re.compile(
    r"to be entered here|to be attached|to be advised|to be confirmed|"
    r"how will you|what activities|what training|describe the|describe access|"
    r"this will highlight|this section is|comprehensive list of|"
    r"reference should be made|list of materials to be used|"
    r"list of plant and equipment|delete as appropriate|insert details|enter details",
    re.IGNORECASE,
)

# A value that, once stripped of punctuation, is only a non-answer token.
_NON_ANSWER = {"", "n a", "na", "none", "nil", "tbc", "tba", "yes", "no", "yes no",
               "not applicable", "n a n a"}


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def is_real_answer(value):
    if not value or not value.strip():
        return False
    norm = _norm(value)
    if norm in _NON_ANSWER:
        return False
    if _GUIDANCE.search(value):
        return False
    if value.strip().endswith("?"):
        return False
    # "N/A" plus nothing but a heading (e.g. "COSHH: N/A") is still a non-answer.
    tail = _norm(value.split(":")[-1])
    if tail in _NON_ANSWER:
        return False
    return True
