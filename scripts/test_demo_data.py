"""
demo_data.py の安全ガードのテスト（実データのある DB・本番では実行しないこと）
"""
import os
import sys

import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../ml"))

from scripts import demo_data
from pipeline.synthetic_data import SYNTHETIC_NAME_PREFIX, synthetic_codes


def _engine():
    e = create_engine("sqlite://")
    with e.begin() as c:
        c.execute(text("CREATE TABLE listed_stocks (code TEXT, company_name TEXT)"))
        c.execute(text('CREATE TABLE daily_quotes ("Code" TEXT, "Date" TEXT)'))
        c.execute(text('CREATE TABLE predictions ("Code" TEXT, "Date" TEXT)'))
    return e


def test_foreign_codes_empty_db_is_safe():
    assert demo_data.foreign_codes(_engine(), set(synthetic_codes(60))) == {}


def test_foreign_codes_only_synthetic_is_safe():
    e = _engine()
    codes = synthetic_codes(10)
    with e.begin() as c:
        for code in codes:
            c.execute(text("INSERT INTO listed_stocks VALUES (:c, :n)"), {"c": code, "n": f"{SYNTHETIC_NAME_PREFIX}1"})
            c.execute(text('INSERT INTO daily_quotes VALUES (:c, "2026-11-06")'), {"c": code})
    assert demo_data.foreign_codes(e, set(synthetic_codes(60))) == {}


@pytest.mark.parametrize("table,col", [("listed_stocks", "code"), ("daily_quotes", '"Code"'), ("predictions", '"Code"')])
def test_foreign_codes_detects_real_data_in_any_table(table, col):
    e = _engine()
    with e.begin() as c:
        c.execute(text(f"INSERT INTO {table} ({col}) VALUES ('72030')"))
    found = demo_data.foreign_codes(e, set(synthetic_codes(60)))
    assert found == {table: ["72030"]}


def test_refuses_in_production(monkeypatch, capsys):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setattr(sys, "argv", ["demo_data.py", "--yes"])
    assert demo_data.main() == 2
    assert "production" in capsys.readouterr().err


def test_refuses_when_real_data_exists(monkeypatch, tmp_path, capsys):
    db = tmp_path / "d.db"
    e = create_engine(f"sqlite:///{db}")
    with e.begin() as c:
        c.execute(text("CREATE TABLE listed_stocks (code TEXT, company_name TEXT)"))
        c.execute(text("INSERT INTO listed_stocks VALUES ('72030','トヨタ')"))
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db}")
    monkeypatch.setattr(sys, "argv", ["demo_data.py", "--yes"])
    assert demo_data.main() == 2
    assert "実データが入っている" in capsys.readouterr().err
    with e.connect() as c:                      # 何も消していない
        assert c.execute(text("SELECT COUNT(*) FROM listed_stocks")).scalar() == 1
