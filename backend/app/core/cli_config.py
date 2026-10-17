# Mapping of engine names to their CLI command templates
# {prompt} will be replaced by the actual prompt string

CLI_ENGINES = {
    # Gemini CLI (Antigravity engine, default)
    "gemini": ["gemini", "--skip-trust", "-p", "{prompt}"],
    
    # Claude Code (Anthropic's official CLI)
    "claude": ["claude", "-p", "{prompt}"],
    
    # Aider (Popular AI pair programming CLI)
    # Using --message to pass the prompt and --no-auto-commits for safety in the pipeline
    "aider": ["aider", "--no-auto-commits", "--message", "{prompt}"],
    
    # codexCLI (OpenAI Codex CLI)
    "codexcli": ["codex", "-p", "{prompt}"],
    
    # deepseekTUI (DeepSeek CLI/TUI)
    "deepseektui": ["deepseek", "-p", "{prompt}"],
    
    # A generic Python Agent fallback
    "python-agent": ["python", "src/agent_wrapper.py", "--prompt", "{prompt}"]
}

def get_cli_command(engine: str, prompt: str) -> list:
    template = CLI_ENGINES.get(engine.lower(), CLI_ENGINES["gemini"])
    # Replace the {prompt} placeholder in the template
    return [arg.replace("{prompt}", prompt) for arg in template]
