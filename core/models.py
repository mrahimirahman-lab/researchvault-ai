from typing import Literal
from pydantic import BaseModel, Field

Classification = Literal['Supporting', 'Contradicting', 'Mixed', 'Inconclusive', 'Background / Conceptual']

class PassageAssessment(BaseModel):
    chunk_id: str
    quote: str
    classification: Classification
    interpretation: str
    construct_name: str = Field(default='', alias='construct')

class Relevance(BaseModel):
    category: Literal['High', 'Moderate', 'Low']
    score: int = Field(ge=0, le=100)
    explanation: str
    constructs: list[str]
    thesis_sections: list[str]
    contributions: list[str]
    limitations: list[str]
    supporting_passages: list[PassageAssessment]

class Synthesis(BaseModel):
    draft: str
    similarities: list[str]
    differences: list[str]
    limitations: list[str]
    cited_evidence_ids: list[str]
