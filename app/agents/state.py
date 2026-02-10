from typing import Optional, TypedDict, Annotated, List
import operator
from langchain_core.messages import BaseMessage


def _keep_last_non_none(existing: Optional[int], new: Optional[int]) -> Optional[int]:
    return new if new is not None else existing


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

    intent: str

    context: str

    active_property_id: Annotated[Optional[int], _keep_last_non_none]