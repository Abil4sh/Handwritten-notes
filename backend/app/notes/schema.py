"""The structured note schema.

This is the contract between the AI and the renderer. The AI produces one of
these; the renderer consumes one. Neither knows anything else about the other.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1


class BaseBlock(BaseModel):
    id: str = Field(min_length=1)


class HeadingBlock(BaseBlock):
    type: Literal["heading"]
    level: int = Field(default=1, ge=1, le=3)
    text: str


class ParagraphBlock(BaseBlock):
    type: Literal["paragraph"]
    text: str


class BulletBlock(BaseBlock):
    type: Literal["bullet"]
    depth: int = Field(default=0, ge=0, le=2)
    text: str


class NumberedBlock(BaseBlock):
    type: Literal["numbered"]
    depth: int = Field(default=0, ge=0, le=2)
    index: int = Field(ge=1)
    text: str


class DefinitionBlock(BaseBlock):
    type: Literal["definition"]
    term: str
    text: str


class ExampleBlock(BaseBlock):
    type: Literal["example"]
    text: str


class FormulaBlock(BaseBlock):
    type: Literal["formula"]
    text: str
    notation: Literal["plain"] = "plain"


class CalloutBlock(BaseBlock):
    type: Literal["callout"]
    variant: Literal["note", "warning", "key"] = "note"
    text: str


class QuoteBlock(BaseBlock):
    type: Literal["quote"]
    text: str
    attribution: str | None = None


class DividerBlock(BaseBlock):
    type: Literal["divider"]


Block = Annotated[
    Union[
        HeadingBlock,
        ParagraphBlock,
        BulletBlock,
        NumberedBlock,
        DefinitionBlock,
        ExampleBlock,
        FormulaBlock,
        CalloutBlock,
        QuoteBlock,
        DividerBlock,
    ],
    Field(discriminator="type"),
]


class Note(BaseModel):
    schema_version: Literal[1] = SCHEMA_VERSION
    title: str = Field(min_length=1)
    blocks: list[Block] = Field(min_length=1)