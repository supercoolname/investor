def fmt_b(v):
    return f"${v / 1e9:.2f}B" if v is not None else "N/A"


def fmt_x(v):
    return f"{v:.2f}x" if v is not None else "N/A"
