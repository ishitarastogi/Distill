"""
YouTube ingestion — Data API v3 for listing a channel's uploads.

Three stages, same shape as the rest of the pipeline:
  1. get_channel_videos() — metadata only, no transcript fetched yet.
     Costs quota, not money.
  2. Relevance classification (in runner.py) — cheap LLM check per
     candidate, filters out sponsor-boilerplate false positives that
     pure keyword matching misses.
  3. add_transcripts() — only called on videos that survive step 2.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import yaml
from googleapiclient.discovery import build
from pydantic import BaseModel
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.proxies import WebshareProxyConfig

load_dotenv()


CONFIG_PATH = "app/config/sources.yaml"


def load_channels() -> dict[str, str]:
    """Reads the youtube_channels list from sources.yaml."""
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    return {
        source["name"]: source["channel_id"]
        for source in config.get("youtube_channels", [])
    }


CHANNELS = load_channels()


class Transcript(BaseModel):
    text: str


class Video(BaseModel):
    title: str
    url: str
    video_id: str
    channel_id: str
    channel_title: str
    published_at: datetime
    description: str
    transcript: Optional[str] = None


class YouTubeScraper:
    def __init__(self):
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY not set in .env")
        self.youtube = build("youtube", "v3", developerKey=api_key)

        proxy_config = None
        proxy_username = os.getenv("PROXY_USERNAME")
        proxy_password = os.getenv("PROXY_PASSWORD")
        if proxy_username and proxy_password:
            proxy_config = WebshareProxyConfig(
                proxy_username=proxy_username, proxy_password=proxy_password
            )
        self.transcript_api = YouTubeTranscriptApi(proxy_config=proxy_config)

    # ---------- Stage 1: list a channel's recent uploads ----------

    def get_channel_videos(self, channel_id: str, channel_title: str, hours: int = 24 * 7) -> List[Video]:
        """
        search.list with channelId set — official API equivalent of
        reading a channel's RSS feed. Costs 100 quota units per call.
        """
        published_after = (
            datetime.now(timezone.utc) - timedelta(hours=hours)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        request = self.youtube.search().list(
            channelId=channel_id,
            part="snippet",
            type="video",
            order="date",
            publishedAfter=published_after,
            maxResults=25,
        )
        response = request.execute()

        videos = []
        for item in response.get("items", []):
            snippet = item["snippet"]
            video_id = item["id"]["videoId"]
            videos.append(Video(
                title=snippet["title"],
                url=f"https://www.youtube.com/watch?v={video_id}",
                video_id=video_id,
                channel_id=channel_id,
                channel_title=channel_title,
                published_at=datetime.strptime(
                    snippet["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc),
                description=snippet.get("description", ""),
            ))

        return self._filter_shorts(videos)

    def _filter_shorts(self, videos: List[Video]) -> List[Video]:
        """
        The Data API doesn't flag Shorts directly the way RSS links did.
        Real duration requires a separate videos.list call (1 unit each) —
        worth adding once volume justifies the extra quota cost. For now
        this is a pass-through; Shorts get caught downstream by the
        relevance classifier instead, since a Short's description is
        usually too thin to pass anyway.
        """
        return videos

    # ---------- Stage 3: transcripts, only for confirmed-relevant videos ----------

    def get_transcript(self, video_id: str) -> Optional[Transcript]:
        try:
            transcript = self.transcript_api.fetch(video_id)
            text = " ".join([snippet.text for snippet in transcript.snippets])
            return Transcript(text=text)
        except (TranscriptsDisabled, NoTranscriptFound):
            return None
        except Exception:
            return None

    def add_transcripts(self, videos: List[Video]) -> List[Video]:
        result = []
        for video in videos:
            transcript = self.get_transcript(video.video_id)
            result.append(video.model_copy(
                update={"transcript": transcript.text if transcript else None}
            ))
        return result


if __name__ == "__main__":
    from app.agent.relevance_agent import RelevanceAgent

    scraper = YouTubeScraper()
    classifier = RelevanceAgent()

    all_confirmed = []

    for name, channel_id in CHANNELS.items():
        candidates = scraper.get_channel_videos(channel_id, name, hours=24 * 7)
        print(f"\n{name}: {len(candidates)} candidates")

        confirmed = []
        for video in candidates:
            check = classifier.classify(video.title, video.description)
            if check.is_relevant:
                confirmed.append(video)
            else:
                print(f"  rejected: {video.title[:60]}  — {check.reason}")

        print(f"{name}: {len(confirmed)} confirmed relevant")
        for v in confirmed:
            print(f"  ✓ {v.title}")
        all_confirmed.extend(confirmed)

    print(f"\n{'='*50}")
    print(
        f"Total confirmed relevant across all channels: {len(all_confirmed)}")
    print("Quota used: ~" + str(len(CHANNELS) * 100) + " units (channel search)")
