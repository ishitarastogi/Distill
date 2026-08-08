import os
from openai import OpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class RelevanceCheck(BaseModel):
    is_relevant: bool = Field(
        description="True if this is genuinely about tokenized RWA or private credit")
    reason: str = Field(
        description="One short sentence explaining the decision")


PROMPT = """You classify whether a video is genuinely about tokenized real-world assets \
(RWA) or private credit, based on its title and description.

Say relevant only if the CONTENT of the video is actually about:
- tokenization of real-world assets (treasuries, credit, real estate, funds)
- onchain private credit protocols or mechanics
- RWA market structure, regulation, or infrastructure

Do NOT mark it relevant just because a sponsor blurb or ad copy in the description \
happens to mention "tokenized" in passing (e.g. "230 tokenized stocks" as a sponsor \
plug). Read for what the video is actually about, not for keyword presence.

If the title and description are about something else entirely (Bitcoin price, \
general market commentary, an unrelated hack, a different DeFi topic) and RWA/private \
credit is not the actual subject, mark it not relevant."""


class RelevanceAgent:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not set. Add it to your .env file as:\n"
                "OPENAI_API_KEY=sk-...\n"
                "(no quotes around the value)"
            )
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"  # cheap model — this is a yes/no check, not a summary

    def classify(self, title: str, description: str) -> RelevanceCheck:
        user_prompt = f"Title: {title}\n\nDescription: {description[:1500]}"

        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=PROMPT,
                temperature=0,
                input=user_prompt,
                text_format=RelevanceCheck,
            )
            return response.output_parsed
        except Exception as e:
            print(f"Relevance check failed, defaulting to not relevant: {e}")
            # fail closed — an API error should not let junk through
            return RelevanceCheck(is_relevant=False, reason=f"classification failed: {e}")


if __name__ == "__main__":
    agent = RelevanceAgent()

    # Replace title/description below with a REAL video from your own scraper output.
    result = agent.classify(
        title="PASTE A REAL TITLE FROM YOUR SCRAPER OUTPUT HERE",
        description="PASTE THE REAL DESCRIPTION FROM YOUR SCRAPER OUTPUT HERE",
    )
    print(result)
