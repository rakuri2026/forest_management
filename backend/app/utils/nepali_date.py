import re


def is_valid_nepali_date(date_str: str) -> bool:
    if not date_str or not isinstance(date_str, str):
        return False
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", date_str.strip())
    if not m:
        return False
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if year < 2050 or year > 2099:
        return False
    if month < 1 or month > 12:
        return False
    if day < 1 or day > 32:
        return False
    return True


def is_valid_nepali_fiscal_year(fy_str: str) -> bool:
    if not fy_str or not isinstance(fy_str, str):
        return False
    m = re.match(r"^(\d{4})/(\d{4})$", fy_str.strip())
    if not m:
        return False
    start, end = int(m.group(1)), int(m.group(2))
    if start < 2050 or start > 2099:
        return False
    if end != start + 1:
        return False
    return True


def is_valid_nepali_year_only(year_val) -> bool:
    try:
        y = int(year_val)
        return 2050 <= y <= 2099
    except (ValueError, TypeError):
        return False
