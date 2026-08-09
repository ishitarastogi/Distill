"""
Build and send the digest email.

Pulls recent digest summaries, ranks them against the newsletter
profile, groups them into video and written coverage, formats a
designed HTML email, shows a preview for approval, and sends it.

Video items get a real YouTube thumbnail — the video ID is already
the article's id (see build_youtube_article in runner.py), so no
extra lookup is needed. Written items get a colored monogram instead,
since there's no equivalent image source for blog posts.
"""

from app.database.connection import get_session
from app.database.repository import Repository
from app.agent.curator_agent import CuratorAgent
from app.profiles.user_profile import NEWSLETTER_PROFILE
from app.services.email import send_email


def get_youtube_thumbnail(video_id: str) -> str:
    return f"https://i3.ytimg.com/vi/{video_id}/hqdefault.jpg"


def monogram_color(source_name: str) -> str:
    palette = ["#0c447c", "#3c3489", "#996039", "#085041", "#712b13"]
    return palette[sum(ord(c) for c in source_name) % len(palette)]


def build_html(ranked_items: list, digests_by_id: dict) -> str:
    video_rows, blog_rows = [], []

    for item in ranked_items:
        digest = digests_by_id.get(item.article_id)
        if not digest:
            continue

        if digest["source_type"].startswith("youtube"):
            thumb_url = get_youtube_thumbnail(item.article_id)
            video_rows.append(f"""
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px;">
              <tr>
                <td style="background-color:#ffffff;border:1px solid #e8e6e1;border-radius:10px;padding:16px;">
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td width="140" valign="top">
                        <img src="{thumb_url}" width="140" height="79" style="display:block;border-radius:6px;object-fit:cover;background-color:#e8e6e1;" alt="" />
                        <div style="text-align:center;margin-top:6px;">
                          <span style="display:inline-block;background-color:#712b13;color:#ffffff;font-size:10px;font-weight:700;letter-spacing:0.5px;padding:3px 8px;border-radius:20px;font-family:Arial,sans-serif;">&#9654; WATCH</span>
                        </div>
                      </td>
                      <td style="padding-left:16px;" valign="top">
                        <div style="font-size:16px;font-weight:600;color:#1a1a1a;line-height:1.35;margin-bottom:6px;font-family:Georgia,serif;">{digest['title']}</div>
                        <div style="font-size:13px;color:#55524d;line-height:1.55;margin-bottom:10px;font-family:Arial,sans-serif;">{digest['summary']}</div>
                        <a href="{digest['url']}" style="font-size:12px;font-weight:600;color:#712b13;text-decoration:none;border-bottom:1px solid #712b13;font-family:Arial,sans-serif;">Watch on YouTube &rarr;</a>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
            """)
        else:
            initial = digest["source_name"][0].upper()
            color = monogram_color(digest["source_name"])
            blog_rows.append(f"""
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px;">
              <tr>
                <td style="background-color:#ffffff;border:1px solid #e8e6e1;border-radius:10px;padding:20px;">
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td width="48" valign="top">
                        <div style="width:44px;height:44px;background-color:{color};border-radius:8px;color:#ffffff;font-size:18px;font-weight:700;text-align:center;line-height:44px;font-family:Georgia,serif;">{initial}</div>
                      </td>
                      <td style="padding-left:16px;" valign="top">
                        <div style="font-size:10px;font-weight:700;letter-spacing:0.8px;color:{color};text-transform:uppercase;margin-bottom:5px;font-family:Arial,sans-serif;">{digest['source_name']}</div>
                        <div style="font-size:16px;font-weight:600;color:#1a1a1a;line-height:1.35;margin-bottom:8px;font-family:Georgia,serif;">{digest['title']}</div>
                        <div style="font-size:13px;color:#55524d;line-height:1.6;margin-bottom:10px;font-family:Arial,sans-serif;">{digest['summary']}</div>
                        <a href="{digest['url']}" style="font-size:12px;font-weight:600;color:{color};text-decoration:none;border-bottom:1px solid {color};font-family:Arial,sans-serif;">Read the full story &rarr;</a>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
            """)

    def section_label(text: str, color: str) -> str:
        return f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:28px 0 14px 0;">
          <tr>
            <td width="4" style="background-color:{color};"></td>
            <td style="padding-left:10px;">
              <span style="font-size:11px;font-weight:700;letter-spacing:1.2px;color:#1a1a1a;text-transform:uppercase;font-family:Arial,sans-serif;">{text}</span>
            </td>
          </tr>
        </table>
        """

    sections = ""
    if video_rows:
        sections += section_label(
            f"On video &middot; {len(video_rows)}", "#712b13")
        sections += "".join(video_rows)
    if blog_rows:
        sections += section_label(
            f"From the protocols &middot; {len(blog_rows)}", "#0c447c")
        sections += "".join(blog_rows)

    total = len(video_rows) + len(blog_rows)

    return f"""
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background-color:#f4f3ef;font-family:Arial,sans-serif;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f3ef;">
        <tr>
          <td align="center" style="padding:0 0 40px 0;">
            <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

              <tr>
                <td style="background-color:#1a1815;padding:32px 32px 28px 32px;border-radius:0 0 12px 12px;">
                  <div style="font-size:26px;font-weight:700;color:#ffffff;letter-spacing:-0.3px;font-family:Georgia,serif;">Distill</div>
                  <div style="width:36px;height:3px;background-color:#d4a843;margin:10px 0 12px 0;"></div>
                  <div style="font-size:12px;color:#b8b4a8;letter-spacing:0.6px;text-transform:uppercase;font-family:Arial,sans-serif;">Tokenized Private Credit &amp; RWA &mdash; Weekly Digest</div>
                </td>
              </tr>

              <tr>
                <td style="padding:24px 16px 0 16px;">
                  <div style="font-size:14px;color:#55524d;line-height:1.6;font-family:Georgia,serif;font-style:italic;">
                    {total} stories on tokenized private credit and RWA, filtered from protocol blogs and YouTube this week.
                  </div>
                </td>
              </tr>

              <tr>
                <td style="padding:0 16px;">
                  {sections}
                </td>
              </tr>

              <tr>
                <td style="padding:20px 16px 0 16px;border-top:1px solid #e8e6e1;margin-top:8px;">
                  <div style="font-size:11px;color:#a8a59c;line-height:1.6;padding-top:16px;font-family:Arial,sans-serif;">
                    You're receiving this because you subscribed to Distill.<br/>
                    Sourced from protocol blogs and YouTube, filtered for relevance, curated weekly.
                  </div>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """


def run_email_stage(hours: int = 24 * 7, top_n: int = 10, require_approval: bool = True) -> dict:
    session = get_session()
    repo = Repository(session)

    articles = repo.get_recent_digests(hours=hours)
    print(f"Found {len(articles)} digested articles in the last {hours} hours")

    if not articles:
        print("Nothing to send — no digests in the time window.")
        return {"sent": False, "count": 0}

    digests_by_id = {
        str(a.id): {
            "title": a.digest_title or a.title,
            "summary": a.summary,
            "url": a.url,
            "source_type": a.source_type,
            "source_name": a.source_name,
        }
        for a in articles
    }

    curator = CuratorAgent(NEWSLETTER_PROFILE)
    ranked = curator.rank([
        {"id": str(a.id), "title": a.digest_title or a.title,
         "summary": a.summary}
        for a in articles
    ])

    top_items = ranked[:top_n]
    print(f"\nRanked {len(ranked)} items, top {len(top_items)} selected:\n")
    for i, item in enumerate(top_items, 1):
        d = digests_by_id[item.article_id]
        print(f"  {i}. [{d['source_name']}] {d['title']}")

    if require_approval:
        confirm = input("\nSend this email? (y/n): ").strip().lower()
        if confirm != "y":
            print("Cancelled — email not sent.")
            return {"sent": False, "count": len(top_items)}

    html = build_html(top_items, digests_by_id)
    success = send_email(
        subject=f"Distill Weekly Digest — {len(top_items)} items",
        html_body=html,
    )

    print("Email sent" if success else "Email failed to send")
    return {"sent": success, "count": len(top_items)}


if __name__ == "__main__":
    run_email_stage()
