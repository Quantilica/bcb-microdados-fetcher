"""Universal Hive Parquet Lake converter for bcb-microdados-fetcher."""

from __future__ import annotations

import codecs
import glob
import json
import logging
import os
import re
import tempfile
import unicodedata
import zipfile
from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import polars as pl
    import pyarrow.parquet as pq
    from quantilica.analytics.lake import (
        META_MEMBERS,
        ConvertResult,
        GroupMember,
        LakeWriter,
        footer_from_metadata,
        origin_matches,
        sha256_file,
    )
    from quantilica.analytics.schema import DataContract
    from quantilica.core.lake import (
        LAYOUT_VERSION,
        DatasetDescriptor,
        composite_file_key,
        file_key,
        partition_dir,
        partition_types_for,
        select_current,
    )
except ImportError as exc:
    raise ImportError(
        "bcb_microdados_fetcher.lake requer o extra 'analysis': "
        "uv add 'bcb-microdados-fetcher[analysis]' "
        "--index https://index.quantilica.com/simple/"
    ) from exc

from .constants import COSIF_SEGMENTOS, moeda_for_date

SOURCE_ID = "bcb-microdados"
DATASETS = [
    "scr",
    "estban_municipio",
    "estban_agencia",
    "cosif",
    "pix_municipio_transacoes",
    "scr_sub_regiao",
]
#: datasets Olinda (JSON mensal); identificados pelo diretório do grupo, exato,
#: porque ``scr_sub_regiao`` contém "scr" e não pode cair no conversor do SCR.data.
OLINDA_DATASETS = ("pix_municipio_transacoes", "scr_sub_regiao")


def _norm_col(col_name: str) -> str:
    s = unicodedata.normalize("NFKD", col_name)
    s = s.encode("ascii", "ignore").decode("ascii")
    # Preserve '+' for compound verbetes like '461+467+468'
    return re.sub(r"[^a-z0-9+]+", "_", s.lower()).strip("_")


def _parse_verbete(col_str: str) -> tuple[str, str]:
    """Separa codigo e nome de uma coluna de verbete ESTBAN ja normalizada.

    "verbete_110_disponibilidades" -> ("110", "disponibilidades")
    "461+467+468_outras" -> ("461+467+468", "outras")
    "verbete_141_corresp_exterior_+_verbete_142_corresp_pais"
        -> ("141+142", "corresp_exterior+corresp_pais")
    """
    codigos, nomes = [], []
    for parte in col_str.split("+"):
        m = re.fullmatch(r"_*(?:verbete_)?(\d{3})(?:_(.*?))?_*", parte)
        if not m:
            return col_str, ""
        codigos.append(m.group(1))
        if m.group(2):
            nomes.append(m.group(2))
    return "+".join(codigos), "+".join(nomes)


logger = logging.getLogger(__name__)

# Encoding declarado por dataset (igual em todos os membros do ZIP). Decodificacao
# estrita: byte invalido vira erro contado do membro, nunca U+FFFD.
ENCODINGS = {
    "scr": "utf-8",
    "estban_municipio": "latin-1",
    "estban_agencia": "latin-1",
    "cosif": "cp1252",
}
#: Particao do cosif: um Parquet por segmento e mes (``write_group``).
COSIF_PARTITION_KEYS = ["segmento", "ano", "mes"]
#: Versoes gravadas em cada membro do grupo; subir uma reconverte o cosif.
#: Suba ``COSIF_CONVERTER_VERSION`` quando mudar o que decide o grupo de um membro
#: (segmento, mês, esquema de colunas, nome do grupo) ou o filtro de membros: o
#: build sem mudança só confere sha256 e versões, nunca recalcula o destino.
COSIF_CONTRACT_VERSION = 1
COSIF_CONVERTER_VERSION = "1"
#: Revisão do layout de ``scr``, ``estban_*`` e dos datasets do Olinda (um Parquet
#: por membro ou arquivo). O rodapé desses Parquets só guarda o sha256 do bruto,
#: então a regra que deriva a partição (``ano``/``mes``) dos dados, do nome ou de
#: ``data_base`` não é conferida pelo build sem mudança. Suba esta constante
#: quando essa regra, o nome da chave do arquivo ou as colunas gravadas mudarem:
#: da revisão 2 em diante a versão vai no rodapé como versão de contrato e o que
#: foi gravado com outra revisão é reconvertido uma vez. A 1 é o layout de sempre
#: (nenhum contrato no rodapé), por isso nada do lake atual muda.
LAYOUT_REVISION = 1
# Identificadores sempre como texto: zeros a esquerda importam (BB = 00000000) e
# o CNPJ dos prudenciais traz codigo de conglomerado (C0085111) apos milhares de
# linhas numericas, alem da janela de inferencia.
_COSIF_TEXTO = {
    c: pl.Utf8
    for c in (
        "CNPJ",
        "AGENCIA",
        "COD_CONGL",
        "COD.CONGLOMERADO",
        "TAXONOMIA",
        "CONTA",
    )
}
_ESTBAN_TEXTO = {c: pl.Utf8 for c in ("CNPJ", "AGENCIA")}
_CHUNK = 1 << 20


def _c1_passthrough(exc: UnicodeDecodeError) -> tuple[str, int]:
    """Bytes que o cp1252 deixa indefinidos (0x81, 0x8D, 0x8F, 0x90, 0x9D) viram o
    caractere C1 de mesmo codigo (mapeamento latin-1): sem perda e sem U+FFFD."""
    if exc.encoding.lower().replace("-", "").replace("_", "") != "cp1252":
        raise exc
    return "".join(chr(b) for b in exc.object[exc.start : exc.end]), exc.end


codecs.register_error("quantilica_c1", _c1_passthrough)


def _transcode_to_utf8(source, dest: Path, encoding: str) -> None:
    """Copia ``source`` (binario) para ``dest`` em UTF-8, em blocos, estrito."""
    enc = encoding.lower()
    errors = "quantilica_c1" if enc in ("cp1252", "windows-1252") else "strict"
    codec = "utf-8-sig" if enc in ("utf-8", "utf8") else encoding
    decoder = codecs.getincrementaldecoder(codec)(errors=errors)
    with open(dest, "w", encoding="utf-8", newline="") as out:
        while chunk := source.read(_CHUNK):
            out.write(decoder.decode(chunk))
        out.write(decoder.decode(b"", final=True))


def _csv_member_names(path: Path) -> list[str] | None:
    """Nomes dos CSVs do ZIP; ``None`` quando ``path`` nao e um ZIP."""
    with open(path, "rb") as f:
        if not f.read(4).startswith(b"PK"):
            return None
    with zipfile.ZipFile(path) as zf:
        return [
            i.filename
            for i in zf.infolist()
            if not i.is_dir() and ".csv" in i.filename.lower()
        ]


@contextmanager
def _member_as_utf8(path: Path, name: str | None, encoding: str) -> Iterator[Path]:
    """CSV de um membro (ou do proprio arquivo) em UTF-8 num temporario (streaming)."""
    with tempfile.TemporaryDirectory(
        dir=os.environ.get("QUANTILICA_LAKE_SCRATCH") or None
    ) as tmp:
        dest = Path(tmp) / "membro.csv"
        if name is None:
            with open(path, "rb") as fh:
                _transcode_to_utf8(fh, dest, encoding)
        else:
            with zipfile.ZipFile(path) as zf, zf.open(name) as fh:
                _transcode_to_utf8(fh, dest, encoding)
        yield dest


def _iter_members(raw_file: Path, *, require_zip: bool = False) -> list[str | None]:
    """Membros: nomes do ZIP, ``[None]`` para CSV solto, ``[]`` se ignorado.

    Com ``require_zip``, um arquivo ``.zip`` sem a assinatura ``PK`` (vazio, ou uma
    página HTML baixada no lugar) é ``BadZipFile``, não um arquivo ignorado.
    """
    names = _csv_member_names(raw_file)
    if names is not None:
        return list(names)
    if raw_file.suffix.lower() in (".csv", ".txt"):
        return [None]
    if require_zip and raw_file.suffix.lower() == ".zip":
        raise zipfile.BadZipFile(
            f"{raw_file.name} nao tem a assinatura de ZIP (PK): "
            f"{raw_file.stat().st_size} bytes, vazio ou nao e um ZIP"
        )
    return []


def _preamble_skip(csv_path: Path, prefixes: tuple[str, ...]) -> int:
    """Linhas de preambulo antes do cabecalho (prefixos), olhando as 15 primeiras."""
    with open(csv_path, encoding="utf-8", newline="") as fh:
        for idx, line in enumerate(fh):
            if idx >= 15:
                break
            if any(line.strip().startswith(p) for p in prefixes):
                return idx
    return 0


def _scan(
    csv_path: Path,
    *,
    skip_rows: int = 0,
    decimal_comma: bool = False,
    schema_overrides: dict[str, Any] | None = None,
) -> pl.LazyFrame:
    return pl.scan_csv(
        csv_path,
        separator=";",
        skip_rows=skip_rows,
        decimal_comma=decimal_comma,
        schema_overrides=schema_overrides,
        infer_schema_length=5000,
        encoding="utf8",
    )


def _first_value(lf: pl.LazyFrame, col: str) -> Any:
    return lf.select(pl.col(col).first()).collect().item()


def _contract_version() -> int | None:
    """Versão de contrato que carrega a revisão de layout (``None`` na revisão 1)."""
    return None if LAYOUT_REVISION <= 1 else LAYOUT_REVISION


def _contrato(dataset_id: str) -> DataContract | None:
    """Contrato sem colunas, só para gravar a revisão de layout no rodapé."""
    if LAYOUT_REVISION <= 1:
        return None
    return DataContract(dataset_id, [], version=LAYOUT_REVISION)


def _registrada(
    dataset_dir: Path, key: str, digest: str, layout_version: int = LAYOUT_VERSION
) -> bool:
    """Se ``key`` já está no lake com este sha256, em qualquer partição ``ano=/mes=``.

    O mesmo teste de ``LakeWriter.is_current`` (``origin_matches``), sem precisar da
    partição, que só se conhece lendo os dados: lista as pastas que têm um Parquet
    dessa chave e confere o rodapé de cada uma. Só diretório e rodapé do lake.
    """
    pattern = f"ano=*/mes=*/{glob.escape(key)}*.parquet"
    pastas = sorted({p.parent for p in dataset_dir.glob(pattern)})
    return any(
        origin_matches(
            d,
            key,
            digest,
            layout_version=layout_version,
            contract_version=_contract_version(),
        )
        for d in pastas
    )


def _em_dia(writer: LakeWriter, key: str, raw_file: Path) -> bool:
    """Se o lake do ``writer`` já tem ``key`` deste bruto (sempre falso com force)."""
    if writer.force:
        return False
    return _registrada(
        writer.dataset_dir,
        key,
        sha256_file(raw_file),
        writer.descriptor.layout_version,
    )


def _drop_superseded(
    dataset_dir: Path, raw_file: Path, keep: set[str], dataset_id: str
) -> list[Path]:
    """Apaga o Parquet que uma versao anterior do mesmo bruto gravou com outra chave.

    A chave do Parquet vem do nome do bruto e do membro: o BCB trocou o formato de
    alguns meses (``x@2023.csv`` virou ``x@2026.zip``), e a chave passou de ``x`` para
    ``x__x_csv``. A versao nova escreve a chave nova na mesma particao e o Parquet da
    chave antiga ficaria em duplicidade (``versao_duplicada``) com a origem superada.
    So sai o Parquet por membro deste dataset, de um bruto de mesma ``file_key`` (chave
    sem extensao e sem carimbo), cuja chave nao esta em ``keep`` (as chaves de todos os
    membros do bruto vigente). Devolve o que apagou.
    """
    base = file_key(raw_file).lower()
    gone = []
    for path in sorted(dataset_dir.glob(f"ano=*/mes=*/{glob.escape(base)}*.parquet")):
        stem = path.stem
        if stem in keep or not (stem == base or stem.startswith(f"{base}__")):
            continue
        try:
            meta = footer_from_metadata(pq.ParquetFile(path).metadata)
        except Exception:
            logger.warning("%s: %s ilegivel; mantido", dataset_id, path)
            continue
        if (
            meta.get("quantilica.source_id") != SOURCE_ID
            or meta.get("quantilica.dataset_id") != dataset_id
            or META_MEMBERS in meta
            or meta.get("quantilica.file_key") != stem
        ):
            continue
        path.unlink()
        gone.append(path)
        logger.warning(
            "%s: %s de versao anterior de %s removido", dataset_id, path, raw_file.name
        )
    return gone


def _convert_members(
    raw_file: Path,
    writer: LakeWriter,
    res: ConvertResult,
    label: str,
    encoding: str,
    build,
) -> None:
    """Converte cada membro com chave composta zip+membro (sem pular os demais).

    ``build(csv_path, member_name)`` devolve ``(lazyframe, partitions)`` ou ``None``.
    """
    # CSV solto já no lake: nem abre o arquivo para saber que não é um ZIP. Só vale
    # para .csv/.txt: o Parquet de um ZIP gravado com a chave do próprio ZIP (layout
    # anterior) não pode dar o ZIP por convertido, os membros ainda faltam.
    try:
        if raw_file.suffix.lower() in (".csv", ".txt") and _em_dia(
            writer, composite_file_key(raw_file, None).lower(), raw_file
        ):
            res.skipped += 1
            return
    except OSError as exc:
        logger.debug("%s %s: sha256 indisponível (%s)", label, raw_file.name, exc)
    try:
        members = _iter_members(raw_file)
    except (OSError, zipfile.BadZipFile) as exc:
        res.errors.append(f"{label} {raw_file.name}: ZIP ilegivel: {exc}")
        return
    for name in members:
        shown = name or raw_file.name
        key = composite_file_key(raw_file, name).lower()
        try:
            # Membro já no lake: não transcodifica nem monta o plano de leitura.
            if _em_dia(writer, key, raw_file):
                res.skipped += 1
                continue
            with _member_as_utf8(raw_file, name, encoding) as csv_path:
                built = build(csv_path, shown)
                if built is None:
                    continue
                lf, partitions = built
                contrato = _contrato(writer.descriptor.dataset_id)
                if writer.is_current(
                    raw_file,
                    partitions=partitions,
                    file_key_name=key,
                    contract=contrato,
                ):
                    res.skipped += 1
                    continue
                written = writer.write_polars(
                    lf,
                    src=raw_file,
                    partitions=partitions,
                    file_key_name=key,
                    contract=contrato,
                )
            if written.status == "skipped":
                res.skipped += 1
            else:
                res.converted += 1
        except Exception as exc:
            res.errors.append(
                f"Erro ao converter {label} {shown} em {raw_file.name}: {exc}"
            )


def _extract_year_month(val: Any) -> tuple[int, int]:
    """Extract (year, month) from date string, integer, or filename."""
    s = str(val or "").strip()
    # Match YYYY-MM or YYYYMM
    m = re.search(r"(\d{4})[-_]?(\d{2})", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    # Fallback to year only
    y = re.search(r"(\d{4})", s)
    if y:
        return int(y.group(1)), 1
    return 2000, 1


def _identify_cosif_segmento(filename: str) -> str:
    """Identify COSIF segment from filename or path."""
    name_upper = filename.upper()
    for slug, meta in COSIF_SEGMENTOS.items():
        sufixo = meta["sufixo"].upper()
        pasta = meta["pasta"].upper()
        if sufixo in name_upper or pasta in name_upper or slug.upper() in name_upper:
            return slug
    return "bancos"


_MONEY = pl.Decimal(precision=20, scale=2)


def _olinda_vazio(path: Path) -> bool:
    """True se o JSON é ``{"value": []}``: o BCB ainda não publicou o mês."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return isinstance(payload, dict) and payload.get("value") == []


def _read_olinda(path: Path, dataset: str) -> tuple[pl.DataFrame, dict[str, int]]:
    """Lê o JSON ``{"value": [...]}`` de uma função OData e tipa as colunas.

    Códigos de município/UF e de sub-região são texto; valores monetários são
    decimais (2 casas); contagens, inteiros. A partição ``ano``/``mes`` vem do
    próprio dado (``AnoMes``/``DATA_BASE``) e precisa ser única no arquivo.

    Raises:
        ValueError: JSON sem ``value``, vazio, ou com mais de um mês.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("value") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("JSON do Olinda sem linhas em 'value'")
    df = pl.DataFrame(rows, infer_schema_length=None)
    if dataset == "pix_municipio_transacoes":
        period_col = "AnoMes"
        df = df.with_columns(
            pl.col("Municipio_Ibge").cast(pl.String).str.zfill(7),
            pl.col("Estado_Ibge").cast(pl.String).str.zfill(2),
            *[pl.col(c).cast(_MONEY) for c in df.columns if c.startswith("VL_")],
            *[pl.col(c).cast(pl.Int64) for c in df.columns if c.startswith("QT_")],
        )
        renames = {c: re.sub(r"(PF|PJ)$", r"_\1", c) for c in df.columns}
        renames.update({"Municipio_Ibge": "codigo_ibge", "Estado_Ibge": "uf_ibge"})
        df = df.rename(renames)
    else:
        period_col = "DATA_BASE"
        df = df.with_columns(
            pl.col("SUB_REGIAO").cast(pl.String),
            pl.col("OPERACOES").cast(pl.Int64),
            *[
                pl.col(c).cast(_MONEY)
                for c in df.columns
                if c
                not in {
                    "DATA_BASE",
                    "CLIENTE",
                    "ESTADO",
                    "SUB_REGIAO",
                    "MODALIDADE",
                    "RISCO",
                    "OPERACOES",
                }
            ],
        )
    periods = df[period_col].unique().to_list()
    if len(periods) != 1:
        raise ValueError(f"arquivo com {len(periods)} períodos em {period_col}")
    ano, mes = _extract_year_month(periods[0])
    df = df.rename({c: _norm_col(c) for c in df.columns if c != _norm_col(c)})
    df = df.drop(_norm_col(period_col))
    return df, {"ano": ano, "mes": mes}


class BcbMicrodadosLakeConverter:
    """Universal Hive Lake converter for BCB SCR, ESTBAN, and COSIF datasets."""

    def __init__(self, source_id: str = SOURCE_ID) -> None:
        self.source_id = source_id

    def datasets(self) -> list[str]:
        """Return available dataset identifiers."""
        return list(DATASETS)

    def convert(
        self,
        input_dir: Path,
        lake_dir: Path,
        *,
        datasets: Sequence[str] | None = None,
        force: bool = False,
    ) -> ConvertResult:
        res = ConvertResult()
        input_path = Path(input_dir)
        lake_path = Path(lake_dir)

        if not input_path.exists():
            return res

        target_datasets = set(datasets or DATASETS)

        # Initialize writers
        writers: dict[str, LakeWriter] = {}
        for olinda_ds in OLINDA_DATASETS:
            if olinda_ds in target_datasets:
                writers[olinda_ds] = LakeWriter(
                    lake_path / self.source_id / olinda_ds,
                    DatasetDescriptor(
                        source_id=self.source_id,
                        dataset_id=olinda_ds,
                        alias=olinda_ds,
                        partition_keys=["ano", "mes"],
                        partition_types=partition_types_for(["ano", "mes"]),
                    ),
                    force=force,
                )
        if "scr" in target_datasets:
            writers["scr"] = LakeWriter(
                lake_path / self.source_id / "scr",
                DatasetDescriptor(
                    source_id=self.source_id,
                    dataset_id="scr",
                    alias="scr",
                    partition_keys=["ano", "mes"],
                    partition_types=partition_types_for(["ano", "mes"]),
                ),
                force=force,
            )
        if "estban_municipio" in target_datasets:
            writers["estban_municipio"] = LakeWriter(
                lake_path / self.source_id / "estban_municipio",
                DatasetDescriptor(
                    source_id=self.source_id,
                    dataset_id="estban_municipio",
                    alias="estban_municipio",
                    partition_keys=["ano", "mes"],
                    partition_types=partition_types_for(["ano", "mes"]),
                ),
                force=force,
            )
        if "estban_agencia" in target_datasets:
            writers["estban_agencia"] = LakeWriter(
                lake_path / self.source_id / "estban_agencia",
                DatasetDescriptor(
                    source_id=self.source_id,
                    dataset_id="estban_agencia",
                    alias="estban_agencia",
                    partition_keys=["ano", "mes"],
                    partition_types=partition_types_for(["ano", "mes"]),
                ),
                force=force,
            )
        if "cosif" in target_datasets:
            writers["cosif"] = LakeWriter(
                lake_path / self.source_id / "cosif",
                DatasetDescriptor(
                    source_id=self.source_id,
                    dataset_id="cosif",
                    alias="cosif",
                    partition_keys=COSIF_PARTITION_KEYS,
                    partition_types=partition_types_for(COSIF_PARTITION_KEYS),
                ),
                force=force,
            )

        # Find current raw files
        all_raw_files = [f for f in input_path.rglob("*") if f.is_file()]
        active_files = select_current(all_raw_files)

        # Formatos gemeos de uma mesma publicacao (x@D.csv e x@D.zip) ficam os dois:
        # um nao substitui o outro, entao a limpeza de chaves antigas nao se aplica.
        gemeos = {
            k
            for k, n in Counter(
                file_key(f).lower()
                for f in active_files
                if not f.name.endswith(".manifest.json")
            ).items()
            if n > 1
        }

        cosif_files: list[Path] = []
        for raw_file in active_files:
            # Sidecar de manifesto não é dado (nenhum ramo o convertia).
            if raw_file.name.endswith(".manifest.json"):
                continue
            fname = raw_file.name.lower()
            parent = raw_file.parent.name.lower()

            # 0. Olinda (JSON mensal): grupo exato, antes do "scr" por substring
            if parent in OLINDA_DATASETS:
                if raw_file.name.endswith(".manifest.json"):
                    continue
                if parent in writers:
                    self._convert_olinda(raw_file, parent, writers[parent], res)
            # 1. SCR files
            elif "scr" in fname or "scr" in parent or "scrdata" in fname:
                if "scr" in writers:
                    self._convert_scr(raw_file, writers["scr"], res)
            # 2. ESTBAN files
            elif "estban" in fname or "estban" in parent:
                if "estban_municipio" in writers or "estban_agencia" in writers:
                    self._convert_estban(raw_file, writers, res, lake_path, gemeos)
            # 3. COSIF files
            elif (
                "cosif" in fname
                or "cosif" in parent
                or any(m["sufixo"].lower() in fname for m in COSIF_SEGMENTOS.values())
            ):
                if "cosif" in writers:
                    cosif_files.append(raw_file)

        # O cosif e agrupado por segmento e mes: so depois de ver todos os brutos.
        if cosif_files:
            _convert_cosif_groups(cosif_files, writers["cosif"], res)
        if "cosif" in writers:
            _report_legacy_cosif(writers["cosif"].dataset_dir, res)

        return res

    def _convert_olinda(
        self, raw_file: Path, dataset: str, writer: LakeWriter, res: ConvertResult
    ) -> None:
        """Converte o JSON mensal de uma função OData do Olinda."""
        try:
            if _em_dia(writer, file_key(raw_file), raw_file):
                res.skipped += 1
                return
            if _olinda_vazio(raw_file):
                logger.warning(
                    "%s %s: a API ainda não publicou este mês (value vazio); pulado",
                    dataset,
                    raw_file.name,
                )
                res.skipped += 1
                return
            df, partitions = _read_olinda(raw_file, dataset)
            contrato = _contrato(dataset)
            if writer.is_current(raw_file, partitions=partitions, contract=contrato):
                res.skipped += 1
                return
            written = writer.write_polars(
                df, src=raw_file, partitions=partitions, contract=contrato
            )
        except Exception as exc:
            res.errors.append(f"Erro ao converter {dataset} {raw_file.name}: {exc}")
            return
        if written.status == "skipped":
            res.skipped += 1
        else:
            res.converted += 1

    def _convert_scr(
        self, raw_file: Path, writer: LakeWriter, res: ConvertResult
    ) -> None:
        """Convert SCR.data files (annual ZIP or monthly CSV)."""

        def build(csv_path: Path, name: str):
            lf = _scan(csv_path, decimal_comma=True)
            if lf.head(1).collect().height == 0:
                return None
            lf = lf.rename({c: _norm_col(c) for c in lf.collect_schema().names()})
            cols = lf.collect_schema().names()

            if "data_base" in cols:
                ano, mes = _extract_year_month(_first_value(lf, "data_base"))
            else:
                ano, mes = _extract_year_month(name)

            # Statistical secrecy: numero_de_operacoes == -1
            if "numero_de_operacoes" in cols:
                lf = lf.with_columns(
                    pl.col("numero_de_operacoes").cast(pl.Float64, strict=False)
                )
                sigilo_expr = pl.col("numero_de_operacoes") == -1
                lf = lf.with_columns(
                    sigilo_expr.alias("sigilo"),
                    pl.when(sigilo_expr)
                    .then(None)
                    .otherwise(pl.col("numero_de_operacoes"))
                    .alias("numero_de_operacoes"),
                )
            else:
                lf = lf.with_columns(pl.lit(False).alias("sigilo"))

            lf = lf.with_columns(
                pl.lit(ano).cast(pl.Int32).alias("ano"),
                pl.lit(mes).cast(pl.Int32).alias("mes"),
            )
            return lf, {"ano": ano, "mes": mes}

        _convert_members(raw_file, writer, res, "SCR", ENCODINGS["scr"], build)

    def _convert_estban(
        self,
        raw_file: Path,
        writers: dict[str, LakeWriter],
        res: ConvertResult,
        lake_path: Path,
        gemeos: frozenset[str] | set[str] = frozenset(),
    ) -> None:
        """Convert ESTBAN files (município e agência) into long format.

        Um membro sem linhas (cabeçalho só) é gravado como Parquet vazio, com o
        esquema: o bruto vigente é isso, e sem o Parquet o arquivo ficaria sem
        cobertura e o Parquet da versão anterior, superado, sem ser substituído.
        Depois de gravar, o Parquet que uma versão anterior do mesmo bruto deixou
        com outra chave (CSV solto que virou ZIP) é removido.
        """
        # municipio x agencia depende das colunas de cada membro; o writer e escolhido
        # por membro, entao o laco de membros fica aqui.
        try:
            members = _iter_members(raw_file)
        except (OSError, zipfile.BadZipFile) as exc:
            res.errors.append(f"ESTBAN {raw_file.name}: ZIP ilegivel: {exc}")
            return

        keep = {composite_file_key(raw_file, n).lower() for n in members}
        limpar = file_key(raw_file).lower() not in gemeos
        digest = None
        for name in members:
            shown = name or raw_file.name
            key = composite_file_key(raw_file, name).lower()
            try:
                # Membro já no lake (município ou agência, em qualquer partição):
                # não transcodifica nem lê. Se está no dataset de outra tarefa, não
                # é desta (como no caminho completo, que o ignora sem contar).
                if not any(w.force for w in writers.values()):
                    digest = digest or sha256_file(raw_file)
                    dono = [
                        ds
                        for ds in ("estban_municipio", "estban_agencia")
                        if _registrada(
                            lake_path / self.source_id / ds,
                            key,
                            digest,
                            writers[ds].descriptor.layout_version
                            if ds in writers
                            else LAYOUT_VERSION,
                        )
                    ]
                    if dono:
                        if any(ds in writers for ds in dono):
                            res.skipped += 1
                        continue
                with _member_as_utf8(
                    raw_file, name, ENCODINGS["estban_municipio"]
                ) as csv_path:
                    skip = _preamble_skip(
                        csv_path, ("#DATA_BASE", "#DATA", "DATA_BASE", "#")
                    )
                    lf = _scan(csv_path, skip_rows=skip, schema_overrides=_ESTBAN_TEXTO)
                    lf = lf.rename(
                        {
                            c: _norm_col(c.lstrip("#").strip())
                            for c in lf.collect_schema().names()
                        }
                    )
                    cols = lf.collect_schema().names()

                    is_agencia = (
                        "agencia" in cols
                        or "_ag" in shown.lower()
                        or "_ag" in raw_file.name.lower()
                    )
                    target_ds = "estban_agencia" if is_agencia else "estban_municipio"
                    if target_ds not in writers:
                        continue
                    writer = writers[target_ds]

                    if "agencia" in cols:
                        lf = lf.with_columns(
                            pl.col("agencia")
                            .cast(pl.Utf8)
                            .str.strip_prefix("'")
                            .alias("agencia")
                        )

                    # Texto com espacos de preenchimento ("COMERCINHO      ").
                    lf = lf.with_columns(pl.col(pl.String).str.strip_chars())
                    # Contagem de agencias (so no arquivo por municipio): atributo da
                    # linha, nao verbete; sem isto viravam verbete_codigo "agen_*".
                    agen_cols = [
                        c for c in ("agen_esperadas", "agen_processadas") if c in cols
                    ]
                    if agen_cols:
                        lf = lf.with_columns(
                            pl.col(agen_cols).cast(pl.Int64, strict=False)
                        )
                    dim_candidates = {
                        "data_base",
                        "cnpj",
                        "nome_instituicao",
                        "agencia",
                        "codmun",
                        "municipio",
                        "uf",
                        "codmun_ibge",
                        "agen_esperadas",
                        "agen_processadas",
                    }
                    id_cols = [c for c in cols if c in dim_candidates]
                    verbete_cols = [c for c in cols if c not in dim_candidates]

                    # Sem linhas não há data-base: o período vem do nome do membro.
                    primeiro = (
                        _first_value(lf, "data_base") if "data_base" in cols else None
                    )
                    ano, mes = _extract_year_month(primeiro or shown)
                    partitions = {"ano": ano, "mes": mes}

                    if verbete_cols:
                        parsed = {v: _parse_verbete(v) for v in verbete_cols}
                        lf_long = lf.unpivot(
                            index=id_cols,
                            on=verbete_cols,
                            variable_name="verbete_col",
                            value_name="valor_raw",
                        )
                        lf_final = lf_long.with_columns(
                            pl.col("verbete_col")
                            .replace_strict(
                                {k: v[0] for k, v in parsed.items()},
                                return_dtype=pl.Utf8,
                            )
                            .alias("verbete_codigo"),
                            pl.col("verbete_col")
                            .replace_strict(
                                {k: v[1] for k, v in parsed.items()},
                                return_dtype=pl.Utf8,
                            )
                            .alias("verbete_nome"),
                            pl.col("valor_raw")
                            .cast(pl.Int64, strict=False)
                            .alias("valor"),
                            pl.lit(moeda_for_date(ano, mes)).alias("moeda"),
                            pl.lit(ano).cast(pl.Int32).alias("ano"),
                            pl.lit(mes).cast(pl.Int32).alias("mes"),
                        ).drop(["verbete_col", "valor_raw"])
                    else:
                        lf_final = lf.with_columns(
                            pl.lit("").alias("verbete_codigo"),
                            pl.lit("").alias("verbete_nome"),
                            pl.lit(None).cast(pl.Int64).alias("valor"),
                            pl.lit(moeda_for_date(ano, mes)).alias("moeda"),
                            pl.lit(ano).cast(pl.Int32).alias("ano"),
                            pl.lit(mes).cast(pl.Int32).alias("mes"),
                        )

                    contrato = _contrato(target_ds)
                    if writer.is_current(
                        raw_file,
                        partitions=partitions,
                        file_key_name=key,
                        contract=contrato,
                    ):
                        res.skipped += 1
                        if limpar:
                            _drop_superseded(
                                writer.dataset_dir, raw_file, keep, target_ds
                            )
                        continue
                    written = writer.write_polars(
                        lf_final,
                        src=raw_file,
                        partitions=partitions,
                        file_key_name=key,
                        contract=contrato,
                    )
                if limpar:
                    _drop_superseded(writer.dataset_dir, raw_file, keep, target_ds)
                if written.status == "skipped":
                    res.skipped += 1
                else:
                    res.converted += 1
            except Exception as exc:
                res.errors.append(
                    f"Erro ao converter ESTBAN {shown} em {raw_file.name}: {exc}"
                )


@dataclass(frozen=True)
class CosifInfo:
    """Onde um membro do cosif cai: segmento, mes e esquema (nomes das colunas)."""

    segmento: str
    ano: int
    mes: int
    colunas: tuple[str, ...]


def _cosif_build(csv_path: Path, name: str) -> tuple[pl.LazyFrame, CosifInfo] | None:
    """Le o CSV do cosif (UTF-8) e devolve o ``LazyFrame`` final e a particao.

    ``None`` para arquivo sem linhas ou marcador de mes sem dados.
    """
    skip = _preamble_skip(csv_path, ("#DATA_BASE", "#DATA", "DATA;", "DATA_BASE", "#"))
    lf = _scan(
        csv_path,
        skip_rows=skip,
        decimal_comma=True,
        schema_overrides=_COSIF_TEXTO,
    )
    if lf.head(1).collect().height == 0:
        return None

    col_map = {}
    for c in lf.collect_schema().names():
        norm = _norm_col(c.lstrip("#").strip())
        if norm in ("data", "data_base"):
            col_map[c] = "data_base"
        elif norm in ("nome_instituicao", "nomeinstituicao"):
            col_map[c] = "nome_instituicao"
        elif norm in ("nome_conta", "nomeconta"):
            col_map[c] = "nome_conta"
        elif norm in ("cod_congl", "cod_conglomerado"):
            col_map[c] = "cod_congl"
        elif norm in ("nome_congl", "nome_conglomerado"):
            col_map[c] = "nome_congl"
        else:
            col_map[c] = norm
    lf = lf.rename(col_map)
    schema = lf.collect_schema()
    cols = schema.names()

    # Layout de largura fixa (conglomerados 2007-2010): texto com espacos de
    # preenchimento e SALDO com espaco no lugar do sinal (" 0000...,18").
    lf = lf.with_columns(pl.col(pl.String).str.strip_chars())
    if schema.get("saldo") == pl.String:
        lf = lf.with_columns(
            pl.col("saldo").str.replace(",", ".", literal=True).cast(pl.Float64)
        )

    segmento = _identify_cosif_segmento(name)
    if "data_base" in cols:
        primeiro = _first_value(lf, "data_base")
        # Marcador de mes sem dados (consorcios 2009-2010): uma linha so,
        # "200901 **** NAO EXISTE DADOS PARA ESTE SEGMENTO DATA**** H".
        if "NAO EXISTE DADOS" in str(primeiro).upper():
            return None
        ano, mes = _extract_year_month(primeiro)
    else:
        ano, mes = _extract_year_month(name)

    plano = "cosif_2025" if ano >= 2025 else "cosif_1988"
    if "conta" in cols:
        lf = lf.with_columns(
            pl.col("conta").cast(pl.Utf8).str.strip_chars().alias("conta")
        )
        if plano == "cosif_1988":
            # L8: comeca com '00' e tem 10 digitos no plano antigo
            lf = lf.with_columns(
                pl.when(
                    pl.col("conta").str.starts_with("00")
                    & (pl.col("conta").str.len_chars() == 10)
                )
                .then(pl.col("conta").str.slice(2))
                .otherwise(pl.col("conta"))
                .alias("conta")
            )

    lf = lf.with_columns(
        pl.lit(moeda_for_date(ano, mes)).alias("moeda"),
        pl.lit(plano).alias("plano"),
        pl.lit(segmento).alias("segmento"),
        pl.lit(ano).cast(pl.Int32).alias("ano"),
    )
    nomes = tuple(
        sorted(c for c in lf.collect_schema().names() if c not in COSIF_PARTITION_KEYS)
    )
    return lf, CosifInfo(segmento, ano, mes, nomes)


def _head_as_utf8(
    path: Path, name: str | None, encoding: str, limit: int, dest: Path
) -> bool:
    """Grava em ``dest`` o inicio do CSV em UTF-8, cortado na ultima quebra de linha.

    Devolve ``True`` se leu o arquivo inteiro (nao cortou nada).
    """
    enc = encoding.lower()
    errors = "quantilica_c1" if enc in ("cp1252", "windows-1252") else "strict"
    codec = "utf-8-sig" if enc in ("utf-8", "utf8") else encoding
    decoder = codecs.getincrementaldecoder(codec)(errors=errors)

    def read(fh) -> tuple[str, bool]:
        raw = fh.read(limit + 1)
        whole = len(raw) <= limit
        text = decoder.decode(raw[:limit], final=whole)
        if not whole:
            text = text[: text.rfind("\n") + 1]
        return text, whole

    if name is None:
        with open(path, "rb") as fh:
            text, whole = read(fh)
    else:
        with zipfile.ZipFile(path) as zf, zf.open(name) as fh:
            text, whole = read(fh)
    dest.write_text(text, encoding="utf-8", newline="")
    return whole


_PEEK_LIMITS = (1 << 16, 1 << 21)


def _cosif_peek(raw_file: Path, name: str | None, shown: str) -> CosifInfo | None:
    """Segmento, mes e esquema de um membro lendo so o inicio do arquivo.

    E o que decide o grupo do membro antes de qualquer decodificacao completa. Usa
    o mesmo ``_cosif_build`` da conversao, sobre o inicio do CSV; se o inicio nao
    basta (so preambulo e cabecalho, ou erro de leitura), tenta um trecho maior e,
    por fim, o arquivo inteiro. ``None``: arquivo vazio ou mes sem dados.
    """
    with tempfile.TemporaryDirectory(
        dir=os.environ.get("QUANTILICA_LAKE_SCRATCH") or None
    ) as tmp:
        head = Path(tmp) / "inicio.csv"
        for limit in _PEEK_LIMITS:
            whole = _head_as_utf8(raw_file, name, ENCODINGS["cosif"], limit, head)
            try:
                built = _cosif_build(head, shown)
            except Exception:
                if whole:
                    raise
                continue
            if built is not None:
                return built[1]
            if whole:
                return None
    with _member_as_utf8(raw_file, name, ENCODINGS["cosif"]) as csv_path:
        built = _cosif_build(csv_path, shown)
    return built[1] if built else None


@dataclass
class _CosifMember:
    raw_file: Path
    name: str | None
    shown: str
    key: str
    sha256: str
    info: CosifInfo


def _legacy_cosif_cleanup(
    dataset_dir: Path, members: Sequence[_CosifMember], dataset_id: str = "cosif"
) -> int:
    """Apaga os Parquets por membro do layout anterior (``segmento=/ano=/<chave>``).

    Cada membro publicado num grupo tinha, antes, o proprio Parquet em
    ``segmento=X/ano=AAAA/<chave>.parquet``, com a mesma chave de arquivo. So esse
    arquivo, escrito por este dataset e nao agrupado, e apagado: o grupo traz todas
    as linhas do membro (inclusive as de uma versao anterior do mesmo bruto, que ele
    substitui). Qualquer outro Parquet da pasta fica. Devolve quantos apagou.
    """
    removed = 0
    for m in members:
        legacy_dir = dataset_dir / f"segmento={m.info.segmento}" / f"ano={m.info.ano}"
        path = legacy_dir / f"{m.key}.parquet"
        if not path.is_file():
            continue
        try:
            meta = footer_from_metadata(pq.ParquetFile(path).metadata)
        except Exception:
            logger.warning("cosif: %s ilegivel; mantido", path)
            continue
        if (
            meta.get("quantilica.source_id") != SOURCE_ID
            or meta.get("quantilica.dataset_id") != dataset_id
            or META_MEMBERS in meta
        ):
            logger.warning("cosif: %s nao e um Parquet por membro deste dataset", path)
            continue
        path.unlink()
        removed += 1
    return removed


def _drop_stale_groups(directory: Path, keep: set[str], dataset_id: str) -> list[Path]:
    """Apaga, na pasta de um mes, os arquivos agrupados que nenhum grupo atual gera.

    Acontece quando o esquema de um membro muda e o grupo muda de chave: o arquivo
    com a chave antiga traria as mesmas linhas em duplicidade.
    """
    gone = []
    for path in sorted(directory.glob("*.parquet")):
        try:
            meta = footer_from_metadata(pq.ParquetFile(path).metadata)
        except Exception:
            continue
        if (
            meta.get("quantilica.source_id") == SOURCE_ID
            and meta.get("quantilica.dataset_id") == dataset_id
            and META_MEMBERS in meta
            and meta.get("quantilica.file_key") not in keep
        ):
            path.unlink()
            gone.append(path)
            logger.warning("cosif: grupo obsoleto %s removido", path)
    return gone


def _cosif_do_lake(
    raw_files: Sequence[Path], writer: LakeWriter, res: ConvertResult
) -> bool:
    """Decide só por sidecars e rodapés se o cosif já está em dia no lake.

    Para cada membro dos brutos (só o índice do ZIP é aberto), procura-o nos
    membros dos arquivos agrupados do lake com o sha256 e as versões de agora e
    confere cada arquivo agrupado com ``is_current_group`` (membros que o rodapé
    lista, sem órfãos), sem ``_cosif_peek`` nem transcodificação. Membro sem
    registro só entra se, olhado de perto, é vazio ou sem dados do mês; se tem
    dados (novo, ou mudou), ou qualquer coisa falha, devolve ``False`` com ``res``
    intacto e o caminho completo roda. Em caso de sucesso faz a mesma contagem e
    a mesma limpeza dele.
    """
    if writer.force:
        return False
    dataset_dir = writer.dataset_dir
    grupos: dict[Path, tuple[str, dict[str, dict[str, Any]]]] = {}
    por_chave: dict[str, list[Path]] = {}
    for path in sorted(dataset_dir.glob("segmento=*/ano=*/mes=*/*.parquet")):
        try:
            meta = footer_from_metadata(pq.ParquetFile(path).metadata)
        except Exception:
            return False
        if (
            meta.get("quantilica.source_id") != SOURCE_ID
            or meta.get("quantilica.dataset_id") != "cosif"
            or META_MEMBERS not in meta
        ):
            continue
        entradas = json.loads(meta[META_MEMBERS])
        grupos[path] = (meta.get("quantilica.file_key", ""), entradas)
        for key in entradas:
            por_chave.setdefault(key, []).append(path)

    brutos: dict[str, tuple[Path, str]] = {}  # chave -> (arquivo, sha256)
    sem_registro: list[tuple[Path, str | None, str]] = []
    try:
        for raw_file in sorted(raw_files):
            names = _iter_members(raw_file, require_zip=True)
            digest = sha256_file(raw_file) if names else ""
            for name in names:
                key = composite_file_key(raw_file, name).lower()
                destinos = por_chave.get(key, [])
                entrada = grupos[destinos[0]][1][key] if len(destinos) == 1 else None
                if (
                    entrada is not None
                    and entrada.get("origin_sha256") == digest
                    and entrada.get("contract_version") == COSIF_CONTRACT_VERSION
                    and entrada.get("converter_version") == COSIF_CONVERTER_VERSION
                ):
                    brutos[key] = (raw_file, digest)
                elif destinos:
                    return False  # mudou ou está em mais de um arquivo
                else:
                    sem_registro.append((raw_file, name, name or raw_file.name))
        # Sem registro: só vale se não há dados do mês (vazio, "NAO EXISTE DADOS").
        for raw_file, name, shown in sem_registro:
            if _cosif_peek(raw_file, name, shown) is not None:
                return False
    except Exception:
        return False

    contados = 0
    conferidos: list[tuple[Path, str, dict[str, Any], list[GroupMember]]] = []
    for path, (group_key, entradas) in grupos.items():
        membros = [k for k in entradas if k in brutos]
        if not membros:
            continue
        try:
            rel = path.relative_to(dataset_dir).parts
            valores = dict(p.split("=", 1) for p in rel[:-1])
            partitions = {
                "segmento": valores["segmento"],
                "ano": int(valores["ano"]),
                "mes": valores["mes"],
            }
        except (ValueError, KeyError):
            return False
        if (
            list(valores) != COSIF_PARTITION_KEYS
            or partition_dir(dataset_dir, partitions) != path.parent
            or group_key != path.stem
        ):
            return False
        gm = [
            GroupMember(brutos[k][0], _nunca_lida, key=k, sha256=brutos[k][1])
            for k in membros
        ]
        if not writer.is_current_group(
            group_key,
            gm,
            partitions=partitions,
            contract_version=COSIF_CONTRACT_VERSION,
            converter_version=COSIF_CONVERTER_VERSION,
            prune=True,
        ):
            return False
        contados += len(gm)
        conferidos.append((path, group_key, partitions, gm))

    res.skipped += contados
    keep_por_pasta: dict[Path, set[str]] = {}
    for path, group_key, partitions, gm in conferidos:
        keep_por_pasta.setdefault(path.parent, set()).add(group_key)
        _legacy_cosif_cleanup(
            dataset_dir,
            [
                _CosifMember(
                    brutos[g.key][0],
                    None,
                    "",
                    g.key,
                    brutos[g.key][1],
                    CosifInfo(partitions["segmento"], partitions["ano"], 0, ()),
                )
                for g in gm
            ],
        )
    for pasta, keep in keep_por_pasta.items():
        _drop_stale_groups(pasta, keep, "cosif")
    return True


def _nunca_lida() -> pl.LazyFrame:
    raise AssertionError("membro lido durante a checagem de grupo em dia")


def _convert_cosif_groups(
    raw_files: Sequence[Path], writer: LakeWriter, res: ConvertResult
) -> None:
    """Converte o cosif: um Parquet por segmento e mes (``write_group``).

    O membro de um ZIP so se sabe de que mes e segmento e depois de olhar o inicio
    dele (``_cosif_peek``); os membros do mesmo segmento e mes viram o grupo
    ``cosif_<segmento>_<AAAAMM>``. Membros de esquemas diferentes (nomes de colunas
    diferentes) no mesmo mes e segmento nao se misturam: o primeiro esquema (na
    ordem da chave dos membros) fica com a chave simples e os demais com ``-v2``,
    ``-v3``... Com algum membro ilegivel, o grupo nao descarta os membros ausentes
    da lista (``prune=False``): nao se sabe a que grupo ele pertencia.
    """
    if _cosif_do_lake(raw_files, writer, res):
        return
    members: list[_CosifMember] = []
    inspection_failed = False
    for raw_file in sorted(raw_files):
        try:
            names = _iter_members(raw_file, require_zip=True)
            digest = sha256_file(raw_file) if names else ""
        except (OSError, zipfile.BadZipFile) as exc:
            res.errors.append(f"COSIF {raw_file.name}: ZIP ilegivel: {exc}")
            inspection_failed = True
            continue
        for name in names:
            shown = name or raw_file.name
            try:
                info = _cosif_peek(raw_file, name, shown)
            except Exception as exc:
                res.errors.append(
                    f"Erro ao converter COSIF {shown} em {raw_file.name}: {exc}"
                )
                inspection_failed = True
                continue
            if info is None:
                continue
            key = composite_file_key(raw_file, name).lower()
            members.append(_CosifMember(raw_file, name, shown, key, digest, info))

    by_month: dict[tuple[str, int, int], list[_CosifMember]] = {}
    for m in sorted(members, key=lambda m: m.key):
        by_month.setdefault((m.info.segmento, m.info.ano, m.info.mes), []).append(m)

    partitions_done: dict[Path, tuple[set[str], bool]] = {}
    for (segmento, ano, mes), month_members in sorted(by_month.items()):
        variants: dict[tuple[str, ...], list[_CosifMember]] = {}
        for m in month_members:
            variants.setdefault(m.info.colunas, []).append(m)
        base = f"cosif_{segmento}_{ano:04d}{mes:02d}"
        partitions = {"segmento": segmento, "ano": ano, "mes": f"{mes:02d}"}
        target = writer.dataset_dir / "/".join(
            f"{k}={v}" for k, v in partitions.items()
        )
        keep, ok = partitions_done.setdefault(target, (set(), True))
        if len(variants) > 1:
            logger.warning(
                "cosif: %s/%04d%02d tem %d esquemas de colunas; um Parquet por esquema",
                segmento,
                ano,
                mes,
                len(variants),
            )
        for n, group in enumerate(variants.values(), start=1):
            group_key = base if n == 1 else f"{base}-v{n}"
            keep.add(group_key)
            try:
                with ExitStack() as stack:
                    gm = [_group_member(m, stack) for m in group]
                    options = {
                        "partitions": partitions,
                        "contract_version": COSIF_CONTRACT_VERSION,
                        "converter_version": COSIF_CONVERTER_VERSION,
                        "prune": not inspection_failed,
                    }
                    if writer.is_current_group(group_key, gm, **options):
                        res.skipped += len(gm)
                    else:
                        written = writer.write_group(
                            group_key, gm, converter="bcb-microdados-fetcher", **options
                        )
                        res.converted += len(written.written)
                        res.skipped += len(written.kept)
            except Exception as exc:
                ok = False
                partitions_done[target] = (keep, False)
                res.errors.append(f"Erro ao converter COSIF {group_key}: {exc}")
                continue
            _legacy_cosif_cleanup(writer.dataset_dir, group)
    if not inspection_failed:
        for target, (keep, ok) in partitions_done.items():
            if ok:
                _drop_stale_groups(target, keep, "cosif")


def _report_legacy_cosif(dataset_dir: Path, res: ConvertResult) -> None:
    """Lista, em ``errors``, os Parquets do layout antigo que sobraram.

    O layout anterior gravava ``segmento=X/ano=AAAA/<chave>.parquet`` direto na
    pasta do ano. O que a migracao nao substituiu (ZIP fora do bruto visto, mes sem
    dados, arquivo ilegivel ou de outro dataset, erro de leitura ou de gravacao) fica
    no lake e e listado, com o caminho, para o operador decidir; nada e apagado.
    """
    if not dataset_dir.is_dir():
        return
    for path in sorted(dataset_dir.glob("segmento=*/ano=*/*.parquet")):
        res.errors.append(
            f"cosif: Parquet do layout antigo (um por arquivo de origem, fora de "
            f"mes=) mantido; o ZIP de origem ({path.stem}) nao foi convertido nesta "
            "execucao (ausente do bruto visto, sem dados ou com erro acima) ou o "
            f"arquivo nao e deste dataset; apague a mao se for residuo: {path}"
        )


def _group_member(m: _CosifMember, stack: ExitStack) -> GroupMember:
    """Membro do grupo; o CSV so e decodificado se o membro tiver de ser escrito."""

    def data() -> pl.LazyFrame:
        csv_path = stack.enter_context(
            _member_as_utf8(m.raw_file, m.name, ENCODINGS["cosif"])
        )
        built = _cosif_build(csv_path, m.shown)
        if built is None:
            raise ValueError(f"{m.shown}: sem linhas na conversao completa")
        if built[1] != m.info:
            raise ValueError(f"{m.shown}: segmento, mes ou colunas mudaram na leitura")
        lf = built[0]
        if "data_base" in m.info.colunas:
            # Um membro e um mes: so a primeira linha define a pasta, entao as
            # outras tem de concordar (senao o mes seria gravado na pasta errada).
            esperado = f"{m.info.ano:04d}{m.info.mes:02d}"
            meses = (
                lf.select(
                    pl.col("data_base")
                    .cast(pl.String)
                    .str.strip_chars()
                    .str.slice(0, 6)
                    .drop_nulls()
                    .unique()
                    .sort()
                )
                .collect()
                .to_series()
                .to_list()
            )
            if set(meses) != {esperado}:
                raise ValueError(
                    f"{m.shown}: mais de uma data_base no mesmo arquivo "
                    f"({len(meses)} meses: {', '.join(meses[:6])}); a primeira "
                    f"linha e de {esperado}. Arquivo nao gravado"
                )
        return lf

    return GroupMember(m.raw_file, data, key=m.key, sha256=m.sha256)


converter = BcbMicrodadosLakeConverter()
