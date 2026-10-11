def generate_subtitle_html(script_text: str, total_duration: float) -> str:
    """Split script into words and assign staggered CSS animation delays for karaoke effect."""
    words = script_text.split()
    if not words:
        return ""

    # Distribute total audio duration evenly across words
    time_per_word = total_duration / len(words)
    spans = []
    cumulative_time = 0.0

    for word in words:
        # Inject custom CSS animation delay corresponding to the word's spoken timestamp
        span = f'<span class="word" style="animation-delay: {cumulative_time:.2f}s; animation-duration: {time_per_word:.2f}s;">{word}</span>'
        spans.append(span)
        cumulative_time += time_per_word

    return " ".join(spans)
