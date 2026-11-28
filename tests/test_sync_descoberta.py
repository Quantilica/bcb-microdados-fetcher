"""Falha de descoberta de um grupo pedido vira erro do ``sync``, não saída 0."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest
from quantilica.cli.sdk import FetcherApp
from typer.testing import CliRunner

from bcb_microdados_fetcher import catalog
from bcb_microdados_fetcher.constants import ESTBAN_IDENTIFICADOR
from bcb_microdados_fetcher.plugin import app, fetcher

from .test_discovery import _api_listagem

runner = CliRunner()


@pytest.fixture(autouse=True)
def _estado_limpo() -> None:
    """O app é um singleton: ``list``/``check`` de outros testes anotam falhas."""
    fetcher._falhas_descoberta.clear()


@pytest.fixture(autouse=True)
def _download_simulado(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Sem rede: o download de cada entrada dá certo e anota o id."""
    baixados: list[str] = []

    def baixa(self: Any, entry: dict, output_dir: Path, **kw: Any) -> Path:
        baixados.append(entry["id"])
        return output_dir / entry["id"]

    monkeypatch.setattr(FetcherApp, "download_entry", baixa)
    return baixados


def _descoberta(monkeypatch: pytest.MonkeyPatch, **kw: Any) -> None:
    monkeypatch.setattr(catalog, "_REPORT", catalog.discover(_api_listagem(**kw)))


def _sync(tmp_path: Path, *grupos: str):
    resumo = tmp_path / "resumo.json"
    saida = str(tmp_path / "bruto")
    res = runner.invoke(
        app, ["sync", *grupos, "-o", saida, "--summary-json", str(resumo)]
    )
    dados = json.loads(resumo.read_text()) if resumo.exists() else None
    return res, dados


def test_falha_de_descoberta_vai_ao_log_em_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _descoberta(monkeypatch, no_conteudo={ESTBAN_IDENTIFICADOR})
    with caplog.at_level(logging.ERROR, logger="bcb_microdados_fetcher.plugin"):
        fetcher.listar_grupo("estban")
    (registro,) = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert "grupo estban" in registro.getMessage()
    assert "503" in registro.getMessage()


def test_estban_fora_do_ar_sozinho_sai_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _descoberta(monkeypatch, no_conteudo={ESTBAN_IDENTIFICADOR})
    res, resumo = _sync(tmp_path, "estban")
    assert res.exit_code == 1
    assert resumo is not None
    assert resumo["exit_code"] == 1
    (erro,) = resumo["errors"]
    assert erro["id"] == "descoberta:estban"
    assert "conteudosite" in erro["message"] and "503" in erro["message"]


def test_estban_fora_do_ar_com_scr_baixando_sai_3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _download_simulado: list[str],
) -> None:
    _descoberta(monkeypatch, no_conteudo={ESTBAN_IDENTIFICADOR})
    res, resumo = _sync(tmp_path, "scr", "estban")
    assert res.exit_code == 3
    assert _download_simulado  # o SCR baixou
    assert resumo is not None
    assert [e["id"] for e in resumo["errors"]] == ["descoberta:estban"]
    assert resumo["failed"] == 1
    assert resumo["total"] == resumo["succeeded"] + 1


def test_falha_so_vale_para_o_grupo_pedido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _descoberta(monkeypatch, no_conteudo={ESTBAN_IDENTIFICADOR})
    res, resumo = _sync(tmp_path, "cosif")  # o ESTBAN, fora do ar, não foi pedido
    assert res.exit_code == 0
    assert resumo is not None and resumo["errors"] == []


def test_apelido_do_grupo_tambem_conta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _descoberta(monkeypatch, no_conteudo={"cosif"})
    res, resumo = _sync(tmp_path, "balancetes")
    assert res.exit_code == 1
    assert resumo is not None
    assert [e["id"] for e in resumo["errors"]] == ["descoberta:cosif"]


def test_pasta_vazia_valida_nao_quebra_o_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _download_simulado: list[str]
) -> None:
    _descoberta(monkeypatch)  # 6 pastas do COSIF respondem vazio, as outras têm arquivo
    res, resumo = _sync(tmp_path, "cosif")
    assert res.exit_code == 0
    assert _download_simulado
    assert resumo is not None and resumo["errors"] == []


def test_grupo_inteiro_sem_arquivo_sai_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _descoberta(monkeypatch, todas_vazias=True)
    res, resumo = _sync(tmp_path, "estban")
    assert res.exit_code == 1
    assert resumo is not None
    assert [e["id"] for e in resumo["errors"]] == ["descoberta:estban"]


def test_descoberta_desligada_nao_deixa_estban_sair_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalog, "_REPORT", None)  # BCB_DISCOVER=0 nos testes
    res, resumo = _sync(tmp_path, "estban")
    assert res.exit_code == 1
    assert resumo is not None
    assert "descoberta desligada" in resumo["errors"][0]["message"]


def test_falha_nao_vaza_para_o_download_seguinte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _descoberta(monkeypatch, no_conteudo={ESTBAN_IDENTIFICADOR})
    fetcher.listar_grupo("estban")
    assert fetcher._falhas_descoberta
    fetcher.download_datasets([], tmp_path)
    assert fetcher._falhas_descoberta == {}
    assert fetcher.download_datasets([], tmp_path) == (0, 0, [])


def test_check_com_falha_de_descoberta_sai_1_e_nao_grava_plano(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Modo de plano: sem isto o ``check`` saía 0 e o ``sync --from-plan`` também."""
    _descoberta(monkeypatch, no_conteudo={ESTBAN_IDENTIFICADOR})
    plano = tmp_path / "plano.json"
    res = runner.invoke(
        app, ["check", "-o", str(tmp_path / "bruto"), "--out", str(plano)]
    )
    assert res.exit_code == 1
    assert not plano.exists()
    assert fetcher._falhas_descoberta == {}  # consumidas


def test_dois_processos_check_e_sync_from_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _download_simulado: list[str]
) -> None:
    """``check --out`` (processo 1) e ``sync --from-plan`` (processo 2) sem falha."""
    from quantilica.cli.sdk import CheckPlanItem

    def verifica(self: Any, entry: dict, output_dir: Path) -> CheckPlanItem:
        return CheckPlanItem(
            dataset=entry["group"], id=entry["id"], url=entry["url"], partition=None,
            local_path=str(output_dir / entry["id"]), remote_etag=None,
            remote_last_modified=None, remote_size=None, local_exists=False,
            action="download", reason="not-present", entry=dict(entry),
        )  # fmt: skip

    monkeypatch.setattr(FetcherApp, "check_entry", verifica)
    _descoberta(monkeypatch)
    plano = tmp_path / "plano.json"
    res = runner.invoke(
        app, ["check", "estban", "-o", str(tmp_path), "--out", str(plano)]
    )
    assert res.exit_code == 0 and plano.exists()

    fetcher._falhas_descoberta.clear()  # outro processo: estado novo
    monkeypatch.setattr(catalog, "_REPORT", None)
    res = runner.invoke(
        app, ["sync", "--from-plan", str(plano), "--force", "-o", str(tmp_path)]
    )
    assert res.exit_code == 0
    assert _download_simulado  # as entradas do plano baixaram


def test_check_so_olha_os_grupos_pedidos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from quantilica.cli.sdk import CheckPlan

    monkeypatch.setattr(
        FetcherApp,
        "check_datasets",
        lambda self, entries, output_dir, workers=4: CheckPlan(
            fetcher="bcb-microdados",
            output_dir=str(output_dir),
            generated_at="",
            items=[],
        ),
    )
    _descoberta(monkeypatch, no_conteudo={ESTBAN_IDENTIFICADOR})
    res = runner.invoke(app, ["check", "cosif", "-o", str(tmp_path)])
    assert res.exit_code == 0
