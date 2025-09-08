# services/common/locale.py
from __future__ import annotations
import re

def norm_market(m: str | None, default: str | None = "PT") -> str | None:
    """
    Normaliza códigos de país para o formato ISO-3166 alpha-2 (PT, US, ES…).
    Aceita variantes como 'pt-PT', 'pt_PT', ' pt ', 'uk' (→ GB).
    Se não conseguir normalizar, devolve `default` (que pode ser None).
    """
    if not m:
        return default
    s = str(m).strip()
    # apanha prefixo antes de hífen/underscore (pt-PT -> pt)
    s = re.split(r"[-_]", s, maxsplit=1)[0] if s else s
    s = s.upper()
    # mapeamentos comuns
    if s == "UK":
        s = "GB"
    # valida alpha-2
    if len(s) == 2 and s.isalpha():
        return s
    return default
