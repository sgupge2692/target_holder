"""
通知システム: メール送信（SendGrid / SMTP）
環境変数で切り替え:
  EMAIL_PROVIDER=sendgrid  → SENDGRID_API_KEY
  EMAIL_PROVIDER=smtp      → SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
  EMAIL_FROM               → 送信元アドレス
"""
import os
import hmac
import hashlib
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)

EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "smtp")  # sendgrid | smtp
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@kabumi.app")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "かぶみ")

# SMTP 設定
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# SendGrid 設定
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")

# 配信停止トークン用シークレット（設定がなければフォールバック）
UNSUBSCRIBE_SECRET = os.getenv("UNSUBSCRIBE_SECRET", "kabumi-unsub-secret-change-me")
SITE_URL = os.getenv("NEXT_PUBLIC_SITE_URL", "https://kabumi.app")


def make_unsubscribe_token(user_id: int, email: str) -> str:
    """HMAC-SHA256 ベースの配信停止トークン生成（DB不要）"""
    msg = f"{user_id}:{email}"
    return hmac.new(UNSUBSCRIBE_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def make_unsubscribe_url(user_id: int, email: str, site_url: str = "") -> str:
    token = make_unsubscribe_token(user_id, email)
    base = site_url or SITE_URL
    return f"{base}/api/notifications/unsubscribe?uid={user_id}&token={token}"


def _send_via_smtp(to: str, subject: str, html: str) -> bool:
    """SMTPでメール送信"""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not set; email skipped")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>"
        msg["To"] = to
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, [to], msg.as_string())
        return True
    except Exception as e:
        logger.error(f"SMTP send failed to {to}: {e}")
        return False


def _send_via_sendgrid(to: str, subject: str, html: str) -> bool:
    """SendGrid APIでメール送信"""
    if not SENDGRID_API_KEY:
        logger.warning("SENDGRID_API_KEY not set; email skipped")
        return False
    try:
        import urllib.request
        import json as _json

        payload = _json.dumps({
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": EMAIL_FROM, "name": EMAIL_FROM_NAME},
            "subject": subject,
            "content": [{"type": "text/html", "value": html}],
        }).encode()

        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=payload,
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 202)
    except Exception as e:
        logger.error(f"SendGrid send failed to {to}: {e}")
        return False


def send_email(to: str, subject: str, html: str) -> bool:
    """メール送信（プロバイダー切り替え）"""
    if EMAIL_PROVIDER == "sendgrid":
        return _send_via_sendgrid(to, subject, html)
    return _send_via_smtp(to, subject, html)


# ─── テンプレート ───────────────────────────────────────────────────────────

def _base_template(content: str, unsubscribe_url: str = "") -> str:
    unsub_html = (
        f'配信停止は <a href="{unsubscribe_url}" style="color:#94a3b8;">こちら</a>'
        if unsubscribe_url
        else "メール設定はダッシュボードから変更できます"
    )
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>かぶみ</title>
<style>
  body {{ margin:0; padding:0; background:#f1f5f9; font-family:-apple-system,sans-serif; }}
  .wrap {{ max-width:600px; margin:40px auto; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 2px 12px rgba(0,0,0,.08); }}
  .header {{ background:#0f172a; padding:28px 32px; }}
  .header h1 {{ color:#fff; margin:0; font-size:20px; letter-spacing:.5px; }}
  .header span {{ color:#22c55e; }}
  .body {{ padding:32px; }}
  .footer {{ background:#f8fafc; padding:16px 32px; font-size:12px; color:#94a3b8; border-top:1px solid #e2e8f0; }}
  .badge-up {{ display:inline-block; background:#dcfce7; color:#166534; border-radius:6px; padding:2px 8px; font-size:12px; font-weight:700; }}
  .badge-down {{ display:inline-block; background:#fee2e2; color:#991b1b; border-radius:6px; padding:2px 8px; font-size:12px; font-weight:700; }}
  .signal-table {{ width:100%; border-collapse:collapse; margin:16px 0; font-size:14px; }}
  .signal-table th {{ text-align:left; padding:8px 12px; background:#f8fafc; color:#64748b; font-weight:600; border-bottom:2px solid #e2e8f0; }}
  .signal-table td {{ padding:10px 12px; border-bottom:1px solid #f1f5f9; }}
  .prob {{ color:#6366f1; font-weight:700; }}
  .btn {{ display:inline-block; background:#22c55e; color:#fff; text-decoration:none; padding:12px 28px; border-radius:8px; font-weight:700; font-size:15px; margin-top:20px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="header"><h1>📈 <span>かぶみ</span></h1></div>
  <div class="body">{content}</div>
  <div class="footer">
    このメールはかぶみから自動送信されています。<br>
    {unsub_html}
  </div>
</div>
</body>
</html>"""


_SIGNAL_LABEL = {"UP": "市場より強い", "DOWN": "市場より弱い", "NEUTRAL": "中立"}


def render_daily_signal_email(
    date: str,
    signals: list[dict],
    accuracy_pct: Optional[float] = None,
    site_url: str = "https://kabumi.app",
    unsubscribe_url: str = "",
    watch_changes: Optional[list[dict]] = None,
    accuracy_n: Optional[int] = None,
) -> str:
    """日次シグナルメール HTML を生成（市場平均との相対予測。ウォッチ銘柄の変化があれば先頭に載せる）"""
    rows = ""
    for s in signals[:10]:
        badge = '<span class="badge-up">市場より強い ↑</span>' if s.get("signal") == "UP" else '<span class="badge-down">市場より弱い ↓</span>'
        prob = s.get("probability_pct", 0)
        rows += f"""<tr>
          <td><strong>{s.get("code", "")}</strong><br><small style="color:#64748b">{s.get("company_name", "")}</small></td>
          <td>{badge}</td>
          <td class="prob">{prob:.1f}%</td>
        </tr>"""

    n_text = f"（n={accuracy_n}）" if accuracy_n else ""
    acc_line = (
        f'<p style="color:#64748b;font-size:13px;">直近30日の的中率（対市場）: <strong>{accuracy_pct:.1f}%</strong>{n_text}</p>'
        if accuracy_pct else ""
    )

    watch_html = ""
    if watch_changes:
        items = ""
        for c in watch_changes:
            prev = _SIGNAL_LABEL.get(c.get("prev_signal"), c.get("prev_signal") or "-")
            now = _SIGNAL_LABEL.get(c.get("signal"), c.get("signal") or "-")
            items += f"""<tr>
          <td><strong>{c.get("code", "")}</strong><br><small style="color:#64748b">{c.get("company_name", "")}</small></td>
          <td>{prev} → <strong>{now}</strong></td>
          <td class="prob">{c.get("probability_pct", 0):.1f}%</td>
        </tr>"""
        watch_html = f"""
<h3 style="color:#0f172a;margin-bottom:0;">ウォッチ中の銘柄に変化があります</h3>
<table class="signal-table">
  <thead><tr><th>銘柄</th><th>前回 → 今回</th><th>確率</th></tr></thead>
  <tbody>{items}</tbody>
</table>
"""

    content = f"""
<h2 style="margin-top:0;color:#0f172a;">{date} のAIシグナル</h2>
<p style="font-size:13px;color:#64748b;">翌営業日に<strong>市場平均を上回る</strong>可能性が高いと予測した銘柄です。株価が上がることを意味するものではありません。</p>
{acc_line}
{watch_html}
<table class="signal-table">
  <thead><tr><th>銘柄</th><th>シグナル</th><th>市場を上回る確率</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
<p style="font-size:13px;color:#64748b;">
  ※ 情報提供を目的としたもので、投資助言・売買の推奨ではありません。予測は外れることがあり、投資判断は自己責任でお願いします。
</p>
<a href="{site_url}" class="btn">シグナル詳細を見る →</a>
"""
    return _base_template(content, unsubscribe_url=unsubscribe_url)


def render_welcome_email(
    username: str,
    site_url: str = "https://kabumi.app",
    unsubscribe_url: str = "",
) -> str:
    """会員登録完了メール HTML を生成"""
    content = f"""
<h2 style="margin-top:0;color:#0f172a;">ご登録ありがとうございます！</h2>
<p>こんにちは、<strong>{username}</strong> さん。</p>
<p>かぶみ へようこそ。AIが毎日、翌日上昇が期待される銘柄をシグナルとしてお届けします。</p>
<h3 style="color:#0f172a;">はじめ方</h3>
<ol style="color:#475569;line-height:2;">
  <li>ダッシュボードで本日のシグナルを確認する</li>
  <li>気になる銘柄の根拠（上位特徴量）をチェック</li>
  <li>バックテスト実績で精度を確認する</li>
</ol>
<p style="font-size:13px;color:#64748b;">
  Proプランにアップグレードすると、全銘柄シグナル + アラートメール配信が利用できます。
</p>
<a href="{site_url}" class="btn">ダッシュボードへ →</a>
"""
    return _base_template(content, unsubscribe_url=unsubscribe_url)


def render_upgrade_reminder_email(
    username: str,
    site_url: str = "https://kabumi.app",
    unsubscribe_url: str = "",
) -> str:
    """Pro アップグレード促進メール HTML を生成"""
    content = f"""
<h2 style="margin-top:0;color:#0f172a;">{username} さん、Proへのアップグレードで全銘柄が解放されます</h2>
<p>現在の無料プランでは、上位10銘柄のみ閲覧可能です。</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;">
  <thead>
    <tr style="background:#f8fafc;">
      <th style="padding:10px 12px;text-align:left;color:#64748b;border-bottom:2px solid #e2e8f0;">機能</th>
      <th style="padding:10px 12px;text-align:center;color:#64748b;border-bottom:2px solid #e2e8f0;">Free</th>
      <th style="padding:10px 12px;text-align:center;color:#166534;border-bottom:2px solid #e2e8f0;">Pro</th>
    </tr>
  </thead>
  <tbody>
    <tr><td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;">シグナル閲覧数</td><td style="text-align:center;padding:10px 12px;border-bottom:1px solid #f1f5f9;">上位10件</td><td style="text-align:center;padding:10px 12px;border-bottom:1px solid #f1f5f9;font-weight:700;color:#166534;">無制限</td></tr>
    <tr><td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;">メールアラート</td><td style="text-align:center;padding:10px 12px;border-bottom:1px solid #f1f5f9;">—</td><td style="text-align:center;padding:10px 12px;border-bottom:1px solid #f1f5f9;font-weight:700;color:#166534;">✓ 毎日配信</td></tr>
    <tr><td style="padding:10px 12px;">バックテスト詳細</td><td style="text-align:center;padding:10px 12px;">3ヶ月</td><td style="text-align:center;padding:10px 12px;font-weight:700;color:#166534;">24ヶ月</td></tr>
  </tbody>
</table>
<p style="font-size:20px;font-weight:700;color:#0f172a;">月額 ¥2,980（税込）</p>
<a href="{site_url}/billing" class="btn">今すぐProにアップグレード →</a>
"""
    return _base_template(content, unsubscribe_url=unsubscribe_url)
