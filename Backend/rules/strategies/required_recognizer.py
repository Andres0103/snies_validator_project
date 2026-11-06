from __future__ import annotations

import re

from rules.models import ConditionalRequirement, ValidationRule
from rules.strategies.base import RuleRecognizer

# "Obligatorio para fuente internacional", "Obligatorio para fuente nacional",
# "Obligatorio si..." -> obligatoriedad condicional a otro campo.
_CONDITIONAL_PATTERN = re.compile(
    r"\bobligatorio\s+(para|si)\s+([^.,\n]+)", re.IGNORECASE
)
_REQUIRED_PATTERN = re.compile(r"\bobligatorio\b", re.IGNORECASE)
_OPTIONAL_PATTERN = re.compile(r"\bopcional\b", re.IGNORECASE)


class RequiredRecognizer(RuleRecognizer):
    """Detecta si el campo es obligatorio, opcional, u obligatorio condicional."""

    def recognize(self, normalized_text: str, rule: ValidationRule) -> str:
        text = normalized_text

        conditional_match = _CONDITIONAL_PATTERN.search(text)
        if conditional_match:
            rule.required = False
            rule.conditional_requirement = ConditionalRequirement(
                raw_text=conditional_match.group(0).strip()
            )
            text = text[: conditional_match.start()] + text[conditional_match.end():]
            return text

        if _REQUIRED_PATTERN.search(text):
            rule.required = True
            text = _REQUIRED_PATTERN.sub("", text, count=1)
        elif _OPTIONAL_PATTERN.search(text):
            rule.required = False
            text = _OPTIONAL_PATTERN.sub("", text, count=1)

        return text
