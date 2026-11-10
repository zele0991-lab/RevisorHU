"""Pruebas de la traza: formato JSONL, enmascarado de secretos y hashes."""

import hashlib

from revisor.agente.traza import Traza, enmascarar, estado_git, leer_eventos, sha256_archivos


def test_escribe_un_evento_por_linea_con_t_y_tipo(tmp_path):
    with Traza(tmp_path, "run1") as t:
        t.evento("inicio", caso="HU-1")
        t.evento("fin", motivo="x")
    ev = leer_eventos(tmp_path / "run1.jsonl")
    assert [e["tipo"] for e in ev] == ["inicio", "fin"] and all("t" in e for e in ev)


def test_enmascara_los_secretos_del_entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-PRUEBA-1234567890")
    monkeypatch.setenv("AZDO_PAT", "pat-secreto-azdo-987")
    with Traza(tmp_path, "run2") as t:
        t.evento("herramienta", salida="la clave es sk-ant-PRUEBA-1234567890",
                 argumentos={"lista": ["pat-secreto-azdo-987"]})
    texto = (tmp_path / "run2.jsonl").read_text(encoding="utf-8")
    assert "sk-ant-PRUEBA" not in texto and "pat-secreto" not in texto and texto.count("***") == 2


def test_no_enmascara_valores_cortos_o_ausentes(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "abc")
    monkeypatch.delenv("AZDO_PAT", raising=False)
    assert enmascarar("abc def") == "abc def"


def test_hash_de_archivos(tmp_path):
    a = tmp_path / "a.txt"
    a.write_bytes(b"hola")
    h = hashlib.sha256(b"a.txt\0hola").hexdigest()
    assert sha256_archivos(a) == h
    assert sha256_archivos(a, tmp_path / "no_existe") is None


def test_estado_git_del_repositorio():
    g = estado_git(".")
    assert g["commit"] and len(g["commit"]) == 40 and isinstance(g["cambios_sin_confirmar"], bool)
