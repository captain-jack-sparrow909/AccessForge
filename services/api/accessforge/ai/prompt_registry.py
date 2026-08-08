import hashlib
from dataclasses import dataclass
from importlib import resources


@dataclass(frozen=True)
class PromptTemplate:
    identifier: str
    version: str
    content: str
    content_hash: str


PROMPT_FILES = {
    "requirements_extractor": "requirements-extractor.v1.md",
    "clarification_planner": "clarification-planner.v1.md",
}


def get_prompt(identifier: str) -> PromptTemplate:
    try:
        filename = PROMPT_FILES[identifier]
    except KeyError as exc:
        raise ValueError(f"Unknown prompt identifier: {identifier}") from exc
    prompt_file = resources.files("accessforge.ai.prompts").joinpath(filename)
    content = prompt_file.read_text(encoding="utf-8")
    return PromptTemplate(
        identifier=identifier,
        version="v1",
        content=content.strip(),
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )
