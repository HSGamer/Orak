PROMPT = (
    f"### Last executed action\n"
    f"{{action}}\n\n"
    f"### Current state (text)\n"
    f"{{cur_state_str}}\n\n"
    f"### Current state (image)\n"
    f"<|cur_state_image|>\n\n"
    f"### Level\n"
    f"{{level}}\n\n"
    f"### Game Status\n"
    f"{{game_status}}\n\n"
)
