import logging
from abc import ABC, abstractmethod
from typing import Optional
from core.llm_client import LLMClient
from core.schemas import MultiAgentState

class BaseAgent(ABC):
    """Abstract base class for all specialized agents in the multi-agent system."""

    def __init__(self, name: str, role: str, llm_client: Optional[LLMClient] = None):
        self.name = name
        self.role = role
        self.llm_client = llm_client or LLMClient()
        self.logger = logging.getLogger(f"Agent.{self.name}")

    @abstractmethod
    def process(self, state: MultiAgentState) -> MultiAgentState:
        """Process the shared pipeline state and update it with agent findings."""
        pass

    def log(self, state: MultiAgentState, message: str) -> None:
        formatted = f"[{self.name}] {message}"
        self.logger.info(formatted)
        state.log(formatted)
