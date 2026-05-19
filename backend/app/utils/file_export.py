"""
Shared utility for building export filenames with Unicode support (RFC 5987).
"""
from urllib.parse import quote
from datetime import datetime


def build_disposition(
    forest_name: str | None,
    module: str,
    report_type: str,
    ext: str,
) -> tuple[str, str]:
    """
    Returns (filename, Content-Disposition header value).

    Uses dual encoding: ASCII fallback + RFC 5987 UTF-8 for Unicode (Nepali) support.

    Example:
        filename, disposition = build_disposition("बबरमहल", "Fieldbook", "FieldData", "csv")
        # filename = "बबरमहल_Fieldbook_FieldData_20260514.csv"
        # disposition = 'attachment; filename="_________________Fieldbook_FieldData_20260514.csv"; filename*=UTF-8''%E0%A4%AC...'
    """
    safe_name = (forest_name or "Forest").replace(" ", "_")
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{safe_name}_{module}_{report_type}_{date_str}.{ext}"
    ascii_fb = filename.encode("ascii", errors="replace").decode("ascii")
    encoded = quote(filename)
    return filename, f'attachment; filename="{ascii_fb}"; filename*=UTF-8\'\'{encoded}'
