"""Universal Hive Parquet Lake converter for bcb-microdados-fetcher."""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

try:
    import polars as pl
    from quantilica.analytics.lake import ConvertResult, LakeWriter
    from quantilica.core.lake import (
        DatasetDescriptor,
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
DATASETS = ["scr", "estban_municipio", "estban_agencia", "cosif"]


def _norm_col(col_name: str) -> str:
    s = unicodedata.normalize("NFKD", col_name)
    s = s.encode("ascii", "ignore").decode("ascii")
    # Preserve '+' for compound verbetes like '461+467+468'
    return re.sub(r"[^a-z0-9+]+", "_", s.lower()).strip("_")


def _read_csv_members(path: Path) -> list[tuple[str, bytes]]:
    """Return list of (member_name, bytes) for CSVs in file (or ZIP archive)."""
    suffix = path.suffix.lower()
    # Check if file has PK header (ZIP signature)
    try:
        with open(path, "rb") as f:
            header = f.read(4)
        if header.startswith(b"PK"):
            results = []
            with zipfile.ZipFile(path) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".csv") or ".csv" in name.lower():
                        results.append((name, zf.read(name)))
            return results
    except Exception:
        pass

    if suffix in (".csv", ".txt") or path.name.lower().endswith((".csv", ".txt")):
        return [(path.name, path.read_bytes())]
    return []


def _skip_preamble_lines(text: str, prefixes: tuple[str, ...]) -> str:
    """Skip preamble lines until a line starting with one of ``prefixes`` is found."""
    lines = text.splitlines()
    for idx, line in enumerate(lines[:15]):
        line_s = line.strip()
        if any(line_s.startswith(p) for p in prefixes):
            return "\n".join(lines[idx:])
    return text


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

            # 1. SCR files
            if "scr" in fname or "scr" in parent or "scrdata" in fname:
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

    def _convert_scr(
        self, raw_file: Path, writer: LakeWriter, res: ConvertResult
    ) -> None:
        """Convert SCR.data files (annual ZIP or monthly CSV)."""
        members = _read_csv_members(raw_file)
        if not members:
            return

        for name, data_bytes in members:
            try:
                # UTF-8 with BOM
                text = data_bytes.decode("utf-8-sig", errors="replace")
                df = pl.read_csv(
                    io.StringIO(text),
                    separator=";",
                    decimal_comma=True,
                    infer_schema_length=5000,
                )
                if df.height == 0:
                    continue

                # Normalize column names
                df = df.rename({c: _norm_col(c) for c in df.columns})

                # Determine year and month
                if "data_base" in df.columns:
                    first_date = df["data_base"][0]
                    ano, mes = _extract_year_month(first_date)
                else:
                    ano, mes = _extract_year_month(name)

                # Statistical secrecy: numero_de_operacoes == -1
                if "numero_de_operacoes" in df.columns:
                    # Cast to float or numeric if string
                    df = df.with_columns(
                        pl.col("numero_de_operacoes")
                        .cast(pl.Float64, strict=False)
                        .alias("numero_de_operacoes")
                    )
                    sigilo_expr = pl.col("numero_de_operacoes") == -1
                    num_ops_expr = (
                        pl.when(sigilo_expr)
                        .then(None)
                        .otherwise(pl.col("numero_de_operacoes"))
                    )
                    df = df.with_columns(
                        sigilo_expr.alias("sigilo"),
                        num_ops_expr.alias("numero_de_operacoes"),
                    )
                else:
                    df = df.with_columns(pl.lit(False).alias("sigilo"))

                # Add partition columns
                df = df.with_columns(
                    pl.lit(ano).cast(pl.Int32).alias("ano"),
                    pl.lit(mes).cast(pl.Int32).alias("mes"),
                )

                writer.write_polars(
                    df, src=raw_file, partitions={"ano": ano, "mes": mes}
                )
                res.converted += 1
            except Exception as exc:
                res.errors.append(
                    f"Erro ao converter SCR {name} em {raw_file.name}: {exc}"
                )

    def _convert_estban(
        self, raw_file: Path, writers: dict[str, LakeWriter], res: ConvertResult
    ) -> None:
        """Convert ESTBAN files (município e agência) into long format."""
        members = _read_csv_members(raw_file)
        if not members:
            return

        for name, data_bytes in members:
            try:
                # latin-1 or cp1252
                text = data_bytes.decode("latin-1", errors="replace")
                cleaned = _skip_preamble_lines(
                    text, ("#DATA_BASE", "#DATA", "DATA_BASE", "#")
                )

                df = pl.read_csv(
                    io.StringIO(cleaned),
                    separator=";",
                    infer_schema_length=5000,
                )
                if df.height == 0:
                    continue

                # Clean column names (strip leading # and normalize)
                col_map = {}
                for c in df.columns:
                    c_clean = c.lstrip("#").strip()
                    col_map[c] = _norm_col(c_clean)
                df = df.rename(col_map)

                # Determine if agencia or municipio
                is_agencia = (
                    "agencia" in df.columns
                    or "_ag" in name.lower()
                    or "_ag" in raw_file.name.lower()
                )
                target_ds = "estban_agencia" if is_agencia else "estban_municipio"

                if target_ds not in writers:
                    continue

                writer = writers[target_ds]

                # Strip leading apostrophe from agencia if present
                if "agencia" in df.columns:
                    df = df.with_columns(
                        pl.col("agencia")
                        .cast(pl.Utf8)
                        .str.strip_prefix("'")
                        .alias("agencia")
                    )

                # Identify base dimension columns vs verbete columns
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
                id_cols = [c for c in df.columns if c in dim_candidates]
                verbete_cols = [c for c in df.columns if c not in dim_candidates]

                # Extract year and month
                if "data_base" in df.columns:
                    first_date = df["data_base"][0]
                    ano, mes = _extract_year_month(first_date)
                else:
                    ano, mes = _extract_year_month(name)

                # Reshape to long format
                if verbete_cols:
                    # Melt / unpivot
                    df_long = df.unpivot(
                        index=id_cols,
                        on=verbete_cols,
                        variable_name="verbete_col",
                        value_name="valor_raw",
                    )

                    # Parse verbete_codigo and verbete_nome from verbete_col
                    # E.g. "verbete_110_disponibilidades" -> ("110", "disponibilidades")
                    # E.g. "461+467+468_outras" -> ("461+467+468", "outras")
                    def parse_verbete(col_str: str) -> tuple[str, str]:
                        m = re.search(
                            r"(?:verbete_)?(\d{3}(?:\+\d{3})*)(?:_(.*))?", col_str
                        )
                        if m:
                            return m.group(1), m.group(2) or ""
                        return col_str, ""

                    codigos: list[str] = []
                    nomes: list[str] = []
                    for v_col in df_long["verbete_col"].to_list():
                        cod, nom = parse_verbete(v_col)
                        codigos.append(cod)
                        nomes.append(nom)

                    df_final = df_long.with_columns(
                        pl.Series("verbete_codigo", codigos, dtype=pl.Utf8),
                        pl.Series("verbete_nome", nomes, dtype=pl.Utf8),
                        pl.col("valor_raw").cast(pl.Int64, strict=False).alias("valor"),
                        pl.lit(ano).cast(pl.Int32).alias("ano"),
                        pl.lit(mes).cast(pl.Int32).alias("mes"),
                    ).drop(["verbete_col", "valor_raw"])
                else:
                    df_final = df.with_columns(
                        pl.lit("").alias("verbete_codigo"),
                        pl.lit("").alias("verbete_nome"),
                        pl.lit(None).cast(pl.Int64).alias("valor"),
                        pl.lit(ano).cast(pl.Int32).alias("ano"),
                        pl.lit(mes).cast(pl.Int32).alias("mes"),
                    )

                writer.write_polars(
                    df_final, src=raw_file, partitions={"ano": ano, "mes": mes}
                )
                res.converted += 1
            except Exception as exc:
                res.errors.append(
                    f"Erro ao converter ESTBAN {name} em {raw_file.name}: {exc}"
                )

    def _convert_cosif(
        self, raw_file: Path, writer: LakeWriter, res: ConvertResult
    ) -> None:
        """Convert COSIF balancetes files into Lake Hive format."""
        members = _read_csv_members(raw_file)
        if not members:
            return

        for name, data_bytes in members:
            try:
                # cp1252
                text = data_bytes.decode("cp1252", errors="replace")
                cleaned = _skip_preamble_lines(
                    text, ("#DATA_BASE", "#DATA", "DATA;", "DATA_BASE", "#")
                )

                df = pl.read_csv(
                    io.StringIO(cleaned),
                    separator=";",
                    decimal_comma=True,
                    infer_schema_length=5000,
                )
                if df.height == 0:
                    continue

                # Clean and map column names
                col_map = {}
                for c in df.columns:
                    c_clean = c.lstrip("#").strip()
                    norm = _norm_col(c_clean)
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

                df = df.rename(col_map)

                # Identify segment
                segmento = _identify_cosif_segmento(name)

                # Extract year and month
                if "data_base" in df.columns:
                    first_date = df["data_base"][0]
                    ano, mes = _extract_year_month(first_date)
                else:
                    ano, mes = _extract_year_month(name)

                # Account plan and account string cleaning
                plano = "cosif_2025" if ano >= 2025 else "cosif_1988"
                if "conta" in df.columns:
                    # If L8 format (starts with '00' and length 10 in plano antigo)
                    df = df.with_columns(
                        pl.col("conta").cast(pl.Utf8).str.strip_chars().alias("conta")
                    )
                    if plano == "cosif_1988":
                        df = df.with_columns(
                            pl.when(
                                pl.col("conta").str.starts_with("00")
                                & (pl.col("conta").str.len_chars() == 10)
                            )
                            .then(pl.col("conta").str.slice(2))
                            .otherwise(pl.col("conta"))
                            .alias("conta")
                        )

                # Add metadata columns: moeda, plano, segmento, ano
                moeda = moeda_for_date(ano, mes)
                df = df.with_columns(
                    pl.lit(moeda).alias("moeda"),
                    pl.lit(plano).alias("plano"),
                    pl.lit(segmento).alias("segmento"),
                    pl.lit(ano).cast(pl.Int32).alias("ano"),
                )

                writer.write_polars(
                    df,
                    src=raw_file,
                    partitions={"segmento": segmento, "ano": ano},
                )
                res.converted += 1
            except Exception as exc:
                res.errors.append(
                    f"Erro ao converter COSIF {name} em {raw_file.name}: {exc}"
                )


converter = BcbMicrodadosLakeConverter()
