"""RWA and private credit interest profile used for ranking."""
"""
Newsletter editorial profile — what Distill's digest is about, used by
the curator to rank articles.

Not a personal profile: the same email goes to every subscriber, so
this represents the newsletter's topic and audience, not one reader's
individual taste.
"""

NEWSLETTER_PROFILE = {
    "name": "Distill readers",
    "background": (
        "A weekly digest for people working in tokenized private credit "
        "and RWA — fund managers, allocators, and researchers who need to "
        "track the sector without reading everything themselves."
    ),
    "interests": [
        "Tokenized private credit protocols and their mechanics",
        "Onchain fund structures — vaults, tranching, curator models",
        "Real-world asset tokenization: treasuries, credit, real estate",
        "Regulatory developments affecting tokenized securities and credit",
        "Institutional adoption of onchain private credit",
    ],
}
