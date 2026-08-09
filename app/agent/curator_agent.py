"""Curator agent for ranking articles against the user profile."""
"""
Curator agent for ranking articles against the user profile.

Takes a batch of digest summaries and scores each one for relevance
against the reader's stated interests. Same shape as the other two
agents — one prompt, one structured output — but operates on the whole
batch in a single call rather than one call per article, since ranking
is inherently a comparison across items.
"""

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from openai import OpenAI
import os
from typing import List

load_dotenv()


class RankedItem(BaseModel):
    article_id: str = Field(description="The article's id, exactly as given")
    score: float = Field(
        description="Relevance score 0.0-10.0", ge=0.0, le=10.0)
    rank: int = Field(description="Rank position, 1 = most relevant", ge=1)


class RankedList(BaseModel):
    ranked: List[RankedItem]


PROMPT_TEMPLATE = """You rank digest summaries for a weekly email read by this person:

Name: {name}
Background: {background}

Interests:
{interests}

Score each item 0.0-10.0 based on how well it matches these interests, then rank from
most relevant (1) to least relevant. Prioritize concrete, protocol-specific content
with real numbers over generic market commentary."""


class CuratorAgent:
    def __init__(self, profile: dict):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not set. Add it to your .env file as:\n"
                "OPENAI_API_KEY=sk-...\n"
                "(no quotes around the value)"
            )
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        self.profile = profile
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        interests = "\n".join(f"- {i}" for i in self.profile["interests"])
        return PROMPT_TEMPLATE.format(
            name=self.profile["name"],
            background=self.profile["background"],
            interests=interests,
        )

    def rank(self, digests: List[dict]) -> List[RankedItem]:
        """
        digests: list of dicts with keys 'id', 'title', 'summary'.
        Returns items ranked most to least relevant.
        """
        if not digests:
            return []

        items_text = "\n\n".join(
            f"ID: {d['id']}\nTitle: {d['title']}\nSummary: {d['summary']}"
            for d in digests
        )
        user_prompt = f"Rank these {len(digests)} items:\n\n{items_text}"

        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=self.system_prompt,
                temperature=0.2,
                input=user_prompt,
                text_format=RankedList,
            )
            result = response.output_parsed
            return sorted(result.ranked, key=lambda x: x.rank)
        except Exception as e:
            print(f"Ranking failed: {e}")
            return []


if __name__ == "__main__":
    from app.profiles.user_profile import USER_PROFILE

    agent = CuratorAgent(USER_PROFILE)
    sample = [
        {"id": "1", "title": "Maple TVL up 20%",
            "summary": "Maple Finance saw TVL grow 20% this week."},
        {"id": "2", "title": "Bitcoin hits new high",
            "summary": "BTC price surged past $100k."},
    ]
    print(agent.rank(sample))
