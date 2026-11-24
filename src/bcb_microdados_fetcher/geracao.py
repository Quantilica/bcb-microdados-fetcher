"""Data de geração dos dados: a versão baixada não pode ser mais velha que a vigente.

Os CSVs do ESTBAN e do COSIF começam com ``Data de geracao dos dados: AAAA-MM-DD``.
O nome do bruto leva o carimbo do ``Last-Modified`` do servidor, e o conversor e a
visão vigente tratam o carimbo mais novo como a versão vigente. Em 23/11/2026 o BCB
sobrescreveu em lote (``Last-Modified`` com poucos segundos de diferença) arquivos de
meses antigos com gerações anteriores às que já estavam no bruto: o carimbo novo
fazia a versão mais velha virar a vigente. Aqui o download é descartado quando a
geração dele é anterior à da versão vigente do mesmo arquivo.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

_GERACAO = re.compile(
    r"^\s*Data de gera[cç][aã]o dos dados:\s*(\d{4})-(\d{2})-(\d{2})",
    re.IGNORECASE | re.MULTILINE,
)
_CARIMBO = re.compile(r"@(\d{8}(?:T\d{6})?)(?=\.)")
_SIDECAR = ".manifest.json"


def data_geracao(path: Path) -> dt.date | None:
    """Data de geração do cabeçalho do CSV (ou do 1º CSV do ZIP); ``None`` sem ela."""
    try:
        with open(path, "rb") as fh:
            ziped = fh.read(4).startswith(b"PK")
        if ziped:
            with zipfile.ZipFile(path) as zf:
                nomes = [i for i in zf.infolist() if not i.is_dir()]
                if not nomes:
                    return None
                with zf.open(nomes[0]) as inner:
                    head = inner.read(4096)
        else:
            with open(path, "rb") as fh:
                head = fh.read(4096)
    except (OSError, zipfile.BadZipFile):
        return None
    m = _GERACAO.search(head.decode("latin-1"))
    if not m:
        return None
    try:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None


def _chave_e_carimbo(nome: str) -> tuple[str, str] | None:
    m = _CARIMBO.search(nome)
    return (nome[: m.start()], m[1]) if m else None


def versao_vigente_anterior(path: Path) -> Path | None:
    """A versão de carimbo mais novo, e anterior a ``path``, do mesmo arquivo."""
    ident = _chave_e_carimbo(path.name)
    if ident is None:
        return None
    chave, carimbo = ident
    candidatos = []
    for outro in path.parent.glob(f"{chave}@*"):
        if outro == path or outro.name.endswith(_SIDECAR):
            continue
        achado = _chave_e_carimbo(outro.name)
        if achado and achado[0] == chave and achado[1] < carimbo:
            candidatos.append((achado[1], outro))
    return max(candidatos)[1] if candidatos else None


def manter_geracao_vigente(path: Path) -> Path:
    """Descarta ``path`` se a geração dele é anterior à da versão vigente.

    Devolve ``path`` quando vale, ou a versão vigente quando o download foi
    descartado (o arquivo e o sidecar do manifesto saem). Sem data de geração em
    qualquer das duas, ou sem versão anterior, vale o download.
    """
    anterior = versao_vigente_anterior(path)
    if anterior is None:
        return path
    nova, vigente = data_geracao(path), data_geracao(anterior)
    if nova is None or vigente is None or nova >= vigente:
        return path
    logger.warning(
        "%s: data de geração %s anterior à da versão vigente %s (%s); "
        "download descartado",
        path.name,
        nova,
        vigente,
        anterior.name,
    )
    path.unlink(missing_ok=True)
    Path(f"{path}{_SIDECAR}").unlink(missing_ok=True)
    return anterior
