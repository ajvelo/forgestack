"""ForgeStack prompts module."""

from pathlib import Path


def get_prompts_dir() -> Path:
    """Get the prompts directory path.

    Returns:
        Path to the prompts directory
    """
    return Path(__file__).parent


def load_prompt(prompt_name: str) -> str:
    """Load a prompt template by name.

    Args:
        prompt_name: Name of the prompt (without .md extension)

    Returns:
        Contents of the prompt template

    Raises:
        FileNotFoundError: If prompt template doesn't exist
    """
    prompts_dir = get_prompts_dir()
    prompt_path = prompts_dir / f"{prompt_name}.md"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_name}")

    return prompt_path.read_text()


def load_task_prompt(filename: str) -> str:
    """Load a task prompt from a file in the prompts directory.

    Args:
        filename: Name of the prompt file (e.g., '.prompt.txt' or 'my_prompt.txt')

    Returns:
        Contents of the prompt file

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    prompts_dir = get_prompts_dir()
    prompt_path = prompts_dir / filename

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_path}\n"
            f"Create the file or provide a description directly."
        )

    content = prompt_path.read_text().strip()
    if not content:
        raise ValueError(f"Prompt file is empty: {prompt_path}")

    return content


def get_master_prompt() -> str:
    """Get the master prompt that defines ForgeStack's behavior.

    Returns:
        Contents of master_prompt.md
    """
    return load_prompt("master_prompt")


__all__ = [
    "get_prompts_dir",
    "load_prompt",
    "load_task_prompt",
    "get_master_prompt",
]
