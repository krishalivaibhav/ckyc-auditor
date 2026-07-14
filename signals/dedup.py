"""ADITYA. Three layers. This is the part that was sloppy last time."""


def content_hash(article: dict) -> str:
    raise NotImplementedError("exact dup")


def cluster(articles: list[dict]) -> dict[str, str]:
    raise NotImplementedError("same event, 5 outlets -> ONE signal, 5 source URLs. "
                              "5 alerts for 1 story IS 'drowning compliance staff'.")


def is_rehash(article: dict) -> bool:
    raise NotImplementedError("re-report of an old event != new risk")
