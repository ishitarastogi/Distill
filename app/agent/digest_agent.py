"""Digest summarization agent."""
"""
Digest summarization agent.

Takes one relevant article (title + full content — either blog body or
video transcript) and produces a short title and 2-3 sentence summary.
Same shape as RelevanceAgent: one prompt, one structured output, cheap
model since this is summarization, not deep analysis.
"""

from dotenv import load_dotenv
from pydantic import BaseModel, Field
import os
from openai import OpenAI

load_dotenv()


class Digest(BaseModel):
    title: str = Field(
        description="A short, clear title for this digest entry, 5-10 words")
    summary: str = Field(
        description="2-3 sentence summary of the key points and why they matter")


PROMPT = """You are summarizing content for a weekly digest read by fund managers, \
allocators, and researchers working in tokenized private credit and real-world \
assets (RWA).

Write a short title (5-10 words) and a 2-3 sentence summary of the given article \
or video transcript.

Guidelines:
- Focus on concrete facts: what happened, which protocol or entity is involved, \
what changed. Not vague framing.
- If specific numbers are mentioned (TVL, AUM, yield, deal size), include them — \
this audience cares about numbers, not adjectives.
- Skip sponsor content, ad reads, and unrelated tangents even if they appear in \
the source text.
- Write in plain, direct language. No marketing tone, no hype words."""


class DigestAgent:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not set. Add it to your .env file as:\n"
                "OPENAI_API_KEY=sk-...\n"
                "(no quotes around the value)"
            )
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"

    def summarize(self, title: str, content: str) -> Digest:
        # Truncate — long transcripts don't need to be sent in full for a
        # 2-3 sentence summary, and it keeps cost predictable.
        user_prompt = f"Title: {title}\n\nContent: {content[:8000]}"

        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=PROMPT,
                temperature=0.3,
                input=user_prompt,
                text_format=Digest,
            )
            return response.output_parsed
        except Exception as e:
            print(f"Digest generation failed for {title!r}: {e}")
            return Digest(title=title, summary=f"[Summary generation failed: {e}]")


if __name__ == "__main__":
    agent = DigestAgent()

    result = agent.summarize(
        title="PASTE A REAL TITLE FROM YOUR DATABASE HERE",
        content="PASTE THE REAL CONTENT/TRANSCRIPT HERE",
    )
    print(result)
