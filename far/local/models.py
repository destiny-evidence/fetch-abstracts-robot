"""Define the data models for the local abstract retrieval process."""

from pydantic import BaseModel, Field


class LocalAbstractRetrievalOutput(BaseModel):
    """Define a common output model for the local abstract retrieval process."""

    abstracts: list[dict[str, str]] | None = Field(
        None,
        description="List of abstracts retrieved locally.",
    )
    dois_with_abstracts: list[str] | None = Field(
        None,
        description="List of DOIs for which abstracts were successfully retrieved.",
    )
    dois_without_abstracts: list[str] | None = Field(
        None, description="List of DOIs for which abstracts were not found."
    )
