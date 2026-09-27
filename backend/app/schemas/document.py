from pydantic import BaseModel, ConfigDict, Field


class DocumentPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    content: str


class DocumentExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pages: list[DocumentPage] = Field(min_length=1)
