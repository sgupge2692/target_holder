"""
予想バトルのテスト
純粋関数（判定・連勝・ランキング）と、実際の SQL を通した API の挙動を確認する。
"""
import pytest
from sqlalchemy import text

from app.routers import battle as b


# ── 純粋関数 ─────────────────────────────────────────────────────────────────

def test_is_pick_correct_matches_backtest_rule():
    assert b.is_pick_correct("UP", 0.01) is True
    assert b.is_pick_correct("UP", -0.01) is False
    assert b.is_pick_correct("DOWN", -0.01) is True
    assert b.is_pick_correct("DOWN", 0.01) is False
    assert b.is_pick_correct("UP", 0.0) is False      # 0 はどちらも外れ
    assert b.is_pick_correct("DOWN", 0.0) is False
    assert b.is_pick_correct("UP", None) is None      # 未確定


def test_duel_outcome():
    assert b.duel_outcome(True, False) == "win"
    assert b.duel_outcome(False, True) == "lose"
    assert b.duel_outcome(True, True) == "draw"
    assert b.duel_outcome(False, False) == "draw"
    assert b.duel_outcome(None, True) is None


def test_choose_round_is_deterministic_and_date_dependent():
    cands = [{"Code": f"{1000 + i}"} for i in range(40)]
    a = b.choose_round(cands, "2026-11-10")
    assert a == b.choose_round(list(reversed(cands)), "2026-11-10")   # 入力順に依存しない
    assert len(a) == b.BATTLE_ROUND_SIZE
    assert a != b.choose_round(cands, "2026-11-11")                    # 日が変われば別の出題
    assert len(b.choose_round(cands[:2], "2026-11-10")) == 2          # 候補が少なければあるだけ


def test_streaks():
    assert b.streaks([]) == (0, 0)
    assert b.streaks([True, True, False, True]) == (1, 2)
    assert b.streaks([True, True, True]) == (3, 3)
    assert b.streaks([True, False]) == (0, 1)


def test_wilson_lower_penalizes_small_samples():
    assert b.wilson_lower(0, 0) == 0.0
    assert b.wilson_lower(3, 3) < b.wilson_lower(60, 80)   # 3戦3勝より 80戦60勝のほうが上
    assert 0 < b.wilson_lower(60, 80) < 60 / 80


def test_handle_does_not_leak_identity():
    h = b.handle_for(7)
    assert h.startswith("投資家#") and "@" not in h
    assert h == b.handle_for(7) and h != b.handle_for(8)


def test_title_needs_enough_samples():
    assert b.title_for(5, 1.0, 5) == "ビギナーズラック?"   # 少数では腕と言わない
    assert b.title_for(5, 0.2, 0) == "見習いトレーダー"
    assert b.title_for(30, 0.65, 4) == "株の仙人"
    assert b.title_for(30, 0.50, 4) == "ふつうの投資家"


# ── API（実 SQL） ─────────────────────────────────────────────────────────────

async def _token(client, email):
    res = await client.post("/api/auth/register", json={"email": email, "password": "pass1234"})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def _seed(db_session, date="2026-11-10", n=8, excess=None):
    """n 銘柄の予測を入れる。excess は {code: 超過リターン}（未指定なら未確定）"""
    excess = excess or {}
    for i in range(n):
        code = f"{2000 + i}"
        await db_session.execute(text("INSERT INTO listed_stocks (code, company_name, sector_code) VALUES (:c, :n, '3650')"),
                                 {"c": code, "n": f"テスト{i}"})
        await db_session.execute(text("""
            INSERT INTO predictions ("Code","Date",up_probability,signal,excess_return,is_correct)
            VALUES (:c,:d,:p,:s,:e,NULL)
        """), {"c": code, "d": date, "p": 0.6 if i % 2 == 0 else 0.4,
               "s": "UP" if i % 2 == 0 else "DOWN", "e": excess.get(code)})
    await db_session.commit()


async def _round_codes(client, headers):
    res = await client.get("/api/battle/today", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.asyncio
async def test_requires_auth(client):
    assert (await client.get("/api/battle/today")).status_code == 401
    assert (await client.post("/api/battle/pick", json={"code": "2000", "pick": "UP"})).status_code == 401
    assert (await client.get("/api/battle/me")).status_code == 401


@pytest.mark.asyncio
async def test_today_empty_without_predictions(client):
    h = await _token(client, "b_empty@example.com")
    data = await _round_codes(client, h)
    assert data["stocks"] == [] and data["round_date"] is None


@pytest.mark.asyncio
async def test_today_is_same_for_everyone_and_hides_ai(client, db_session):
    await _seed(db_session)
    h1, h2 = await _token(client, "b1@example.com"), await _token(client, "b2@example.com")
    d1, d2 = await _round_codes(client, h1), await _round_codes(client, h2)
    assert [s["code"] for s in d1["stocks"]] == [s["code"] for s in d2["stocks"]]
    assert len(d1["stocks"]) == b.BATTLE_ROUND_SIZE
    for s in d1["stocks"]:                       # AI の予想は出題時には含まれない
        assert "signal" not in s and "up_probability" not in s and "ai_signal" not in s


@pytest.mark.asyncio
async def test_pick_flow_and_duplicate_rejected(client, db_session):
    await _seed(db_session)
    h = await _token(client, "b_pick@example.com")
    code = (await _round_codes(client, h))["stocks"][0]["code"]
    res = await client.post("/api/battle/pick", json={"code": code, "pick": "UP"}, headers=h)
    assert res.status_code == 201, res.text
    dup = await client.post("/api/battle/pick", json={"code": code, "pick": "DOWN"}, headers=h)
    assert dup.status_code == 409                              # 変更不可
    data = await _round_codes(client, h)
    assert data["answered"] == 1
    assert next(s for s in data["stocks"] if s["code"] == code)["my_pick"] == "UP"


@pytest.mark.asyncio
async def test_pick_validation(client, db_session):
    await _seed(db_session)
    h = await _token(client, "b_val@example.com")
    in_round = {s["code"] for s in (await _round_codes(client, h))["stocks"]}
    outside = next(f"{2000 + i}" for i in range(8) if f"{2000 + i}" not in in_round)
    assert (await client.post("/api/battle/pick", json={"code": outside, "pick": "UP"}, headers=h)).status_code == 404
    assert (await client.post("/api/battle/pick", json={"code": "2000", "pick": "SIDEWAYS"}, headers=h)).status_code == 422


@pytest.mark.asyncio
async def test_pick_closed_after_results(client, db_session):
    """結果が出た出題には、結果を見てからの後出し回答をさせない"""
    await _seed(db_session, excess={f"{2000 + i}": 0.01 for i in range(8)})
    h = await _token(client, "b_closed@example.com")
    data = await _round_codes(client, h)
    assert data["closed"] is True
    res = await client.post("/api/battle/pick", json={"code": data["stocks"][0]["code"], "pick": "UP"}, headers=h)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_me_reveals_ai_only_after_settlement(client, db_session):
    await _seed(db_session)
    h = await _token(client, "b_me@example.com")
    code = (await _round_codes(client, h))["stocks"][0]["code"]
    await client.post("/api/battle/pick", json={"code": code, "pick": "UP"}, headers=h)

    me = (await client.get("/api/battle/me", headers=h)).json()
    assert me["summary"]["settled"] == 0 and me["summary"]["pending"] == 1
    assert me["recent"][0]["ai_signal"] is None and me["recent"][0]["outcome"] is None   # 未確定は伏せる

    await db_session.execute(text('UPDATE predictions SET excess_return = 0.02 WHERE "Code" = :c'), {"c": code})
    await db_session.commit()
    me = (await client.get("/api/battle/me", headers=h)).json()
    d = me["recent"][0]
    assert d["settled"] and d["user_correct"] is True and d["excess_return_pct"] == 2.0
    assert d["ai_signal"] in ("UP", "DOWN") and d["outcome"] in ("win", "draw")
    assert me["summary"]["settled"] == 1 and me["summary"]["current_streak"] == 1


@pytest.mark.asyncio
async def test_summary_counts_wins_and_losses_vs_ai(client, db_session):
    """全銘柄で UP と答えた人 vs AI（偶数 index=UP / 奇数=DOWN）。超過リターンはすべてプラス"""
    await _seed(db_session)
    h = await _token(client, "b_vs@example.com")
    stocks = (await _round_codes(client, h))["stocks"]
    for s in stocks:
        assert (await client.post("/api/battle/pick", json={"code": s["code"], "pick": "UP"}, headers=h)).status_code == 201
    await db_session.execute(text('UPDATE predictions SET excess_return = 0.01'))
    await db_session.commit()
    sm = (await client.get("/api/battle/me", headers=h)).json()["summary"]
    ups = sum(1 for s in stocks if int(s["code"]) % 2 == 0)       # AI が UP の銘柄数 = 両方正解（引き分け）
    assert sm["settled"] == len(stocks) and sm["user_correct"] == len(stocks)
    assert sm["ai_correct"] == ups
    assert sm["duel_draws"] == ups and sm["duel_wins"] == len(stocks) - ups and sm["duel_losses"] == 0
    assert sm["current_streak"] == len(stocks)


@pytest.mark.asyncio
async def test_users_are_isolated(client, db_session):
    await _seed(db_session)
    h1, h2 = await _token(client, "b_iso1@example.com"), await _token(client, "b_iso2@example.com")
    code = (await _round_codes(client, h1))["stocks"][0]["code"]
    await client.post("/api/battle/pick", json={"code": code, "pick": "UP"}, headers=h1)
    me2 = (await client.get("/api/battle/me", headers=h2)).json()
    assert me2["recent"] == [] and me2["summary"]["pending"] == 0


@pytest.mark.asyncio
async def test_leaderboard_min_picks_and_anonymous(client, db_session):
    await _seed(db_session, n=8)
    h = await _token(client, "b_lb@example.com")
    # 10 日分の出題に全部答えて確定させる
    for day in range(1, 11):
        d = f"2026-10-{day:02d}"
        await _seed_day(db_session, d)
        # 出題日を最新にするため、その日を最大日付として扱う
        await db_session.execute(text('DELETE FROM predictions WHERE "Date" > :d'), {"d": d})
        await db_session.commit()
        s = (await _round_codes(client, h))["stocks"][0]
        assert (await client.post("/api/battle/pick", json={"code": s["code"], "pick": "UP"}, headers=h)).status_code == 201, d
        await db_session.execute(text('UPDATE predictions SET excess_return = 0.01 WHERE "Date" = :d'), {"d": d})
        await db_session.commit()
    res = await client.get("/api/battle/leaderboard")
    assert res.status_code == 200
    entries = res.json()["entries"]
    assert len(entries) == 1 and entries[0]["settled"] == 10 and entries[0]["rank"] == 1
    assert "@" not in entries[0]["handle"] and "user_id" not in entries[0] and "email" not in entries[0]


async def _seed_day(db_session, date):
    for i in range(6):
        await db_session.execute(text("""
            INSERT INTO predictions ("Code","Date",up_probability,signal,excess_return,is_correct)
            VALUES (:c,:d,0.6,'UP',NULL,NULL)
        """), {"c": f"{3000 + i}", "d": date})
    await db_session.commit()


@pytest.mark.asyncio
async def test_leaderboard_hides_users_with_few_picks(client, db_session):
    await _seed(db_session)
    h = await _token(client, "b_few@example.com")
    code = (await _round_codes(client, h))["stocks"][0]["code"]
    await client.post("/api/battle/pick", json={"code": code, "pick": "UP"}, headers=h)
    await db_session.execute(text("UPDATE predictions SET excess_return = 0.01"))
    await db_session.commit()
    assert (await client.get("/api/battle/leaderboard")).json()["entries"] == []


@pytest.mark.asyncio
async def test_leaderboard_returns_same_result_via_cache(client, db_session, monkeypatch):
    """1回目の結果が cache_set で保存され、2回目はキャッシュ経由で同じ結果を返す"""
    await _seed(db_session, n=8)
    h = await _token(client, "b_cache@example.com")
    # 10 日分の出題に全部答えて確定させる（ランキングに載る最低数）
    for day in range(1, 11):
        d = f"2026-10-{day:02d}"
        await _seed_day(db_session, d)
        await db_session.execute(text('DELETE FROM predictions WHERE "Date" > :d'), {"d": d})
        await db_session.commit()
        s = (await _round_codes(client, h))["stocks"][0]
        assert (await client.post("/api/battle/pick", json={"code": s["code"], "pick": "UP"}, headers=h)).status_code == 201, d
        await db_session.execute(text('UPDATE predictions SET excess_return = 0.01 WHERE "Date" = :d'), {"d": d})
        await db_session.commit()

    # Redis が無い環境でもキャッシュ経路を試せるよう、in-memory のフェイクに差し替え
    store: dict[str, dict] = {}
    set_keys: list[str] = []

    async def fake_cache_get(key):
        return store.get(key)

    async def fake_cache_set(key, value, ttl=300):
        set_keys.append(key)
        store[key] = value
        return True

    monkeypatch.setattr(b, "cache_get", fake_cache_get)
    monkeypatch.setattr(b, "cache_set", fake_cache_set)

    first = (await client.get("/api/battle/leaderboard")).json()
    assert set_keys == [b.cache_key("battle", "leaderboard")]     # 1回目でキャッシュに保存される
    assert len(first["entries"]) == 1 and first["entries"][0]["settled"] == 10

    # 再計算すれば結果が変わる状態にしてから 2 回目 → キャッシュ経由で 1 回目と同じ結果
    await db_session.execute(text("UPDATE predictions SET excess_return = 0.9"))
    await db_session.commit()
    second = (await client.get("/api/battle/leaderboard")).json()
    assert second == first


@pytest.mark.asyncio
async def test_today_returns_my_pick_after_closed(client, db_session):
    """締め切り後も /today は自分の回答（my_pick）を正しく返す"""
    await _seed(db_session)
    h = await _token(client, "b_closed_pick@example.com")
    data = await _round_codes(client, h)
    assert data["closed"] is False
    targets = {s["code"] for s in data["stocks"][:2]}
    for code in targets:
        assert (await client.post("/api/battle/pick", json={"code": code, "pick": "UP"}, headers=h)).status_code == 201

    # 出題日の結果が確定 → 締め切り。以後 /today でも自分の回答が見えること
    await db_session.execute(text("UPDATE predictions SET excess_return = 0.01"))
    await db_session.commit()
    after = await _round_codes(client, h)
    assert after["closed"] is True
    assert after["answered"] == 2
    for s in after["stocks"]:
        assert s["my_pick"] == ("UP" if s["code"] in targets else None)
