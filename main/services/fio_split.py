def split_fio(full_name: str):
    """
    To‘liq FIO → last / first / father
    """

    parts = (full_name or "").split()

    last = parts[0].title() if len(parts) > 0 else ""
    first = parts[1].title() if len(parts) > 1 else ""
    father = " ".join(parts[2:]).title() if len(parts) > 2 else ""

    return last, first, father
