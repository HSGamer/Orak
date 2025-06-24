PROMPT = (
    f"### Last executed action\n"
    f"{{action}}\n\n"
    f"### Previous state (text)\n"
    f"{{prev_state_str}}\n\n"
    f"### Previous state (image)\n"
    f"<|prev_state_image|>\n\n"
    f"### Current state (text)\n"
    f"{{cur_state_str}}\n\n"
    f"### Current state (image)\n"
    f"<|cur_state_image|>\n\n"
)
