"""Short, model-independent prompt construction with a hard character cap."""

from dataclasses import dataclass


MAX_CONTEXT_CHARS = 2000
MAX_PROMPT_CHARS = 3000
SYSTEM_INSTRUCTION = (
    "Choose one next action for a simulated person. "
    "Return JSON only. Do not explain."
)
USER_INSTRUCTION = (
    "In the context, a lists allowed actions and targets lists allowed MOVE ids. "
    "Return exactly an object with action and target. "
    "For MOVE use one listed target; for WAIT or REST use target:null.\n"
)


@dataclass(frozen=True)
class DecisionPrompt:
    system: str
    user: str
    context_chars: int

    @property
    def prompt_chars(self) -> int:
        return len(self.system) + len(self.user)


def build_decision_prompt(compact_context: str) -> DecisionPrompt:
    if not isinstance(compact_context, str):
        raise TypeError("compact_context must be a string")
    if len(compact_context) > MAX_CONTEXT_CHARS:
        raise ValueError("Decision context exceeds MAX_CONTEXT_CHARS")
    prompt = DecisionPrompt(
        system=SYSTEM_INSTRUCTION,
        user=f"{USER_INSTRUCTION}Context:{compact_context}",
        context_chars=len(compact_context),
    )
    if prompt.prompt_chars >= MAX_PROMPT_CHARS:
        raise ValueError("Decision prompt exceeds MAX_PROMPT_CHARS")
    return prompt
