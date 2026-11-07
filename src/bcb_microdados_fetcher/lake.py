"""Universal Hive Parquet Lake converter for bcb-microdados-fetcher."""

from __future__ import annotations

import codecs
import json
import logging
import os
import re
import tempfile
import unicodedata
import zipfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:
    import polars as pl
    from quantilica.analytics.lake import ConvertResult, LakeWriter
    from quantilica.core.lake import (
        DatasetDescriptor,
        composite_file_key,
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


logger = logging.getLogger(__name__)

# Encoding declarado por dataset (igual em todos os membros do ZIP). Decodificacao
# estrita: byte invalido vira erro contado do membro, nunca U+FFFD.
ENCODINGS = {
    "scr": "utf-8",
    "estban_municipio": "latin-1",
    "estban_agencia": "latin-1",
    "cosif": "cp1252",
}
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


def _iter_members(raw_file: Path) -> list[str | None]:
    """Membros: nomes do ZIP, ``[None]`` para CSV solto, ``[]`` se ignorado."""
    names = _csv_member_names(raw_file)
    if names is not None:
        return list(names)
    if raw_file.suffix.lower() in (".csv", ".txt"):
        return [None]
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
    try:
        members = _iter_members(raw_file)
    except (OSError, zipfile.BadZipFile) as exc:
        res.errors.append(f"{label} {raw_file.name}: ZIP ilegivel: {exc}")
        return
    for name in members:
        shown = name or raw_file.name
        key = composite_file_key(raw_file, name).lower()
        try:
            with _member_as_utf8(raw_file, name, encoding) as csv_path:
                built = build(csv_path, shown)
                if built is None:
                    continue
                lf, partitions = built
                if writer.is_current(
                    raw_file, partitions=partitions, file_key_name=key
                ):
                    res.skipped += 1
                    continue
                written = writer.write_polars(
                    lf, src=raw_file, partitions=partitions, file_key_name=key
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
                    partition_keys=["segmento", "ano"],
                    partition_types=partition_types_for(["segmento", "ano"]),
                ),
                force=force,
            )

        # Find current raw files
        all_raw_files = [f for f in input_path.rglob("*") if f.is_file()]
        active_files = select_current(all_raw_files)

        for raw_file in active_files:
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
                self._convert_estban(raw_file, writers, res)
            # 3. COSIF files
            elif (
                "cosif" in fname
                or "cosif" in parent
                or any(m["sufixo"].lower() in fname for m in COSIF_SEGMENTOS.values())
            ):
                if "cosif" in writers:
                    self._convert_cosif(raw_file, writers["cosif"], res)

        return res

    def _convert_olinda(
        self, raw_file: Path, dataset: str, writer: LakeWriter, res: ConvertResult
    ) -> None:
        """Converte o JSON mensal de uma função OData do Olinda."""
        try:
            df, partitions = _read_olinda(raw_file, dataset)
            if writer.is_current(raw_file, partitions=partitions):
                res.skipped += 1
                return
            written = writer.write_polars(df, src=raw_file, partitions=partitions)
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
        self, raw_file: Path, writers: dict[str, LakeWriter], res: ConvertResult
    ) -> None:
        """Convert ESTBAN files (município e agência) into long format."""
        # municipio x agencia depende das colunas de cada membro; o writer e escolhido
        # por membro, entao o laco de membros fica aqui.
        try:
            members = _iter_members(raw_file)
        except (OSError, zipfile.BadZipFile) as exc:
            res.errors.append(f"ESTBAN {raw_file.name}: ZIP ilegivel: {exc}")
            return

        for name in members:
            shown = name or raw_file.name
            key = composite_file_key(raw_file, name).lower()
            try:
                with _member_as_utf8(
                    raw_file, name, ENCODINGS["estban_municipio"]
                ) as csv_path:
                    skip = _preamble_skip(
                        csv_path, ("#DATA_BASE", "#DATA", "DATA_BASE", "#")
                    )
                    lf = _scan(csv_path, skip_rows=skip, schema_overrides=_ESTBAN_TEXTO)
                    if lf.head(1).collect().height == 0:
                        continue
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

                    dim_candidates = {
                        "data_base",
                        "cnpj",
                        "nome_instituicao",
                        "agencia",
                        "codmun",
                        "municipio",
                        "uf",
                        "codmun_ibge",
                    }
                    id_cols = [c for c in cols if c in dim_candidates]
                    verbete_cols = [c for c in cols if c not in dim_candidates]

                    if "data_base" in cols:
                        ano, mes = _extract_year_month(_first_value(lf, "data_base"))
                    else:
                        ano, mes = _extract_year_month(shown)
                    partitions = {"ano": ano, "mes": mes}

                    if verbete_cols:
                        # "verbete_110_disponibilidades" -> ("110", "disponibilidades")
                        # "461+467+468_outras" -> ("461+467+468", "outras")
                        def parse_verbete(col_str: str) -> tuple[str, str]:
                            m = re.search(
                                r"(?:verbete_)?(\d{3}(?:\+\d{3})*)(?:_(.*))?", col_str
                            )
                            if m:
                                return m.group(1), m.group(2) or ""
                            return col_str, ""

                        parsed = {v: parse_verbete(v) for v in verbete_cols}
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
                            pl.lit(ano).cast(pl.Int32).alias("ano"),
                            pl.lit(mes).cast(pl.Int32).alias("mes"),
                        ).drop(["verbete_col", "valor_raw"])
                    else:
                        lf_final = lf.with_columns(
                            pl.lit("").alias("verbete_codigo"),
                            pl.lit("").alias("verbete_nome"),
                            pl.lit(None).cast(pl.Int64).alias("valor"),
                            pl.lit(ano).cast(pl.Int32).alias("ano"),
                            pl.lit(mes).cast(pl.Int32).alias("mes"),
                        )

                    if writer.is_current(
                        raw_file, partitions=partitions, file_key_name=key
                    ):
                        res.skipped += 1
                        continue
                    written = writer.write_polars(
                        lf_final,
                        src=raw_file,
                        partitions=partitions,
                        file_key_name=key,
                    )
                if written.status == "skipped":
                    res.skipped += 1
                else:
                    res.converted += 1
            except Exception as exc:
                res.errors.append(
                    f"Erro ao converter ESTBAN {shown} em {raw_file.name}: {exc}"
                )

    def _convert_cosif(
        self, raw_file: Path, writer: LakeWriter, res: ConvertResult
    ) -> None:
        """Convert COSIF balancetes files into Lake Hive format."""

        def build(csv_path: Path, name: str):
            skip = _preamble_skip(
                csv_path, ("#DATA_BASE", "#DATA", "DATA;", "DATA_BASE", "#")
            )
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
                ano, mes = _extract_year_month(_first_value(lf, "data_base"))
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
            return lf, {"segmento": segmento, "ano": ano}

        _convert_members(raw_file, writer, res, "COSIF", ENCODINGS["cosif"], build)


converter = BcbMicrodadosLakeConverter()
