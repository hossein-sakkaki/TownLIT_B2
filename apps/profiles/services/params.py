# apps/friendship/services/params.py

TRUE_SET = {"1", "true", "True", "yes", "on"}

def parse_bool(qs_value: str | None, default: bool = False) -> bool:
    if qs_value is None:
        return default
    return qs_value in TRUE_SET

def parse_int(qs_value: str | None, default: int | None = None) -> int | None:
    if qs_value is None:
        return default
    try:
        return int(qs_value)
    except (TypeError, ValueError):
        return default

def resolve_randomization_params(query_params) -> dict:
    """
    Returns:
      {
        "random": bool,
        "daily": bool,
        "seed": str | None,
        "limit": int | None,
      }
    """
    random_enabled = parse_bool(query_params.get("random"), default=True)
    daily = parse_bool(query_params.get("daily"), default=False)
    seed = query_params.get("seed")
    limit = parse_int(query_params.get("limit"), default=None)
    return {"random": random_enabled, "daily": daily, "seed": seed, "limit": limit}
