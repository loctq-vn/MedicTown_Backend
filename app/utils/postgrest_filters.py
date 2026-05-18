def parse_eq_filter(value: str | None) -> str | None:
    if not value:
        return None
    return value[3:] if value.startswith("eq.") else value


def parse_ilike_filter(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("ilike."):
        value = value.removeprefix("ilike.")
    return value.replace("*", "%")


def parse_in_filter(value: str | None) -> list[str]:
    if not value:
        return []
    if not (value.startswith("in.(") and value.endswith(")")):
        return []
    value = value[4:-1]
    return [item.strip() for item in value.split(",") if item.strip()]
