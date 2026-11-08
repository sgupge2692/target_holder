"""
scripts/post_twitter.py のテスト（文面・文字数・DB取得・スキップ条件）
"""
import importlib.util
import os
import sqlite3
from datetime import date, timedelta

import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "post_twitter.py")


@pytest.fixture()
def pt():
    spec = importlib.util.spec_from_file_location("post_twitter", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SIGNALS = [
    {"code": "7203", "name": "トヨタ自動車", "prob": 58.2},
    {"code": "6758", "name": "ソニーグル", "prob": 57.1},
    {"code": "9984", "name": "ソフトバン", "prob": 56.4},
]


# ── 文字数 ──────────────────────────────────────────────────────────────

def test_tweet_weight_counts_japanese_double_and_urls_as_23(pt):
    assert pt.tweet_weight("abc") == 3
    assert pt.tweet_weight("あいう") == 6
    assert pt.tweet_weight("https://example.com/very/long/path?x=1") == 23
    assert pt.tweet_weight("見て https://example.com") == 4 + 1 + 23


def test_build_tweet_fits_limit_and_has_disclaimer(pt):
    acc = {"rate": 53.4, "n": 412}
    tweet = pt.build_tweet(SIGNALS, acc, "11/09", site_url="https://kabumi.app")
    assert pt.tweet_weight(tweet) <= pt.TWEET_LIMIT
    assert "市場平均を上回る" in tweet
    assert "投資助言・売買の推奨ではありません" in tweet
    assert "対市場" in tweet and "n=412" in tweet
    assert "7203" in tweet and "超過確率58%" in tweet


def test_build_tweet_drops_stocks_instead_of_exceeding_limit(pt):
    many = [{"code": f"{1000 + i}", "name": "あ" * 6, "prob": 55.0} for i in range(20)]
    tweet = pt.build_tweet(many, {"rate": 52.0, "n": 100}, "11/09")
    assert pt.tweet_weight(tweet) <= pt.TWEET_LIMIT
    assert "1000" in tweet                      # 先頭（確度の高い順）は残る
    assert "1019" not in tweet


def test_build_tweet_omits_accuracy_when_unknown(pt):
    tweet = pt.build_tweet(SIGNALS, None, "11/09")
    assert "的中率" not in tweet


# ── DB取得（SQLite で代用） ─────────────────────────────────────────────

def _make_db(path, rows, days_ago=0):
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE listed_stocks (code TEXT, company_name TEXT);
        CREATE TABLE predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, "Code" TEXT, "Date" TEXT,
            up_probability REAL, signal TEXT, is_correct INTEGER
        );
    """)
    d = (date.today() - timedelta(days=days_ago)).isoformat()
    for code, name, p, sig in rows:
        con.execute("INSERT INTO listed_stocks VALUES (?, ?)", (code, name))
        con.execute('INSERT INTO predictions ("Code","Date",up_probability,signal) VALUES (?,?,?,?)',
                    (code, d, p, sig))
    con.commit()
    return con


@pytest.mark.asyncio
async def test_fetch_signals_returns_top_up_by_probability(pt, tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    rows = [("1001", "あ", 0.55, "UP"), ("1002", "い", 0.61, "UP"), ("1003", "う", 0.58, "UP"),
            ("1004", "え", 0.57, "UP"), ("1005", "お", 0.30, "DOWN")]
    _make_db(db, rows)
    monkeypatch.setattr(pt, "DATABASE_URL", f"sqlite+aiosqlite:///{db}")

    signals, accuracy, d = await pt.fetch_signals()
    assert [s["code"] for s in signals] == ["1002", "1003", "1004"]      # 確度順・DOWN除外・上位3件
    assert signals[0]["prob"] == pytest.approx(61.0)
    assert accuracy is None                                               # 母数不足は載せない
    assert d == date.today()


@pytest.mark.asyncio
async def test_fetch_signals_accuracy_uses_is_correct_with_min_samples(pt, tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    con = _make_db(db, [("1001", "あ", 0.6, "UP")])
    old = (date.today() - timedelta(days=5)).isoformat()
    for i in range(40):                                 # 40 件中 24 件的中 → 60%
        con.execute('INSERT INTO predictions ("Code","Date",up_probability,signal,is_correct) VALUES (?,?,?,?,?)',
                    (f"2{i:03d}", old, 0.6, "UP", 1 if i < 24 else 0))
    con.commit()
    monkeypatch.setattr(pt, "DATABASE_URL", f"sqlite+aiosqlite:///{db}")

    _, accuracy, _ = await pt.fetch_signals()
    assert accuracy == {"rate": pytest.approx(60.0), "n": 40}


# ── main の分岐 ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_main_skips_stale_data_and_dry_run_never_posts(pt, tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    _make_db(db, [("1001", "あ", 0.6, "UP")], days_ago=10)
    monkeypatch.setattr(pt, "DATABASE_URL", f"sqlite+aiosqlite:///{db}")
    posted = []
    monkeypatch.setattr(pt, "post_tweet", lambda t: posted.append(t) or True)
    monkeypatch.setattr(pt, "credentials_set", lambda: True)

    assert await pt.main() == 0 and posted == []        # 古いデータは投稿しない

    db2 = tmp_path / "t2.db"
    _make_db(db2, [("1001", "あ", 0.6, "UP")], days_ago=0)
    monkeypatch.setattr(pt, "DATABASE_URL", f"sqlite+aiosqlite:///{db2}")
    assert await pt.main(dry_run=True) == 0 and posted == []   # dry-run は投稿しない
    assert await pt.main() == 0 and len(posted) == 1           # 通常は投稿する


@pytest.mark.asyncio
async def test_main_returns_nonzero_on_db_failure_and_post_failure(pt, tmp_path, monkeypatch):
    monkeypatch.setattr(pt, "DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/missing/none.db")
    assert await pt.main() == 1                          # DB失敗を握りつぶさない

    db = tmp_path / "t.db"
    _make_db(db, [("1001", "あ", 0.6, "UP")])
    monkeypatch.setattr(pt, "DATABASE_URL", f"sqlite+aiosqlite:///{db}")
    monkeypatch.setattr(pt, "credentials_set", lambda: True)
    monkeypatch.setattr(pt, "post_tweet", lambda t: False)
    assert await pt.main() == 1                          # 投稿失敗は非ゼロ
