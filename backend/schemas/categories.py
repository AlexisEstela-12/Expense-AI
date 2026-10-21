from pydantic import BaseModel, Field


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: str = Field(pattern='^(income|expense|reimbursement)$')
