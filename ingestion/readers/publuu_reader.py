"""
הקובץ מטפל בקריאה ראשונית של מקורות Publuu

הוא מקבל כתובת ציבורית של חוברת
מאתר קישור שמחזיר את קובץ המקור
ומוריד את הקובץ לצורך המשך עיבוד
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


DEFAULT_TIMEOUT_SECONDS = 30

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
}


class _LinkCollector(
    HTMLParser
):
    """
    אוספת כתובות אפשריות
    מתוך מאפייני תגיות בדף החוברת
    """

    def __init__(
        self,
    ) -> None:
        super().__init__()
        self.values: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """
        שומרת ערכים שיכולים להכיל
        כתובת לקובץ או לפעולת הורדה
        """

        for key, value in attrs:
            if not value:
                continue

            normalized_key = (
                key.strip().lower()
            )

            if (
                normalized_key
                in {
                    "href",
                    "src",
                    "data-src",
                    "data-url",
                    "data-href",
                    "data-download",
                    "content",
                }
            ):
                self.values.append(
                    value.strip()
                )


def _validate_source_url(
    source_url: str,
) -> str:
    """
    בודקת שכתובת המקור היא כתובת רשת תקינה
    של Publuu
    """

    clean_url = source_url.strip()

    parsed = urlparse(
        clean_url
    )

    if (
        parsed.scheme
        not in {
            "http",
            "https",
        }
        or not parsed.netloc
    ):
        raise ValueError(
            "כתובת המקור אינה תקינה"
        )

    host = (
        parsed.hostname
        or ""
    ).lower()

    if not (
        host == "publuu.com"
        or host.endswith(
            ".publuu.com"
        )
    ):
        raise ValueError(
            "הכתובת אינה שייכת ל-Publuu"
        )

    return clean_url


def _fetch_bytes(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    accept: str | None = None,
) -> tuple[bytes, str, str]:
    """
    שולחת בקשת קריאה
    ומחזירה תוכן סוג תוכן וכתובת סופית
    """

    headers = dict(
        _BROWSER_HEADERS
    )

    if accept:
        headers[
            "Accept"
        ] = accept

    request = Request(
        url,
        headers=headers,
        method="GET",
    )

    with urlopen(
        request,
        timeout=timeout,
    ) as response:
        body = response.read()
        content_type = (
            response.headers.get(
                "Content-Type",
                "",
            )
            or ""
        ).lower()
        final_url = response.geturl()

    return (
        body,
        content_type,
        final_url,
    )


def fetch_publuu_page(
    source_url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """
    מורידה את דף החוברת הציבורי
    ומחזירה אותו כטקסט
    """

    clean_url = (
        _validate_source_url(
            source_url
        )
    )

    body, _, _ = _fetch_bytes(
        clean_url,
        timeout=timeout,
    )

    for encoding in (
        "utf-8",
        "utf-16",
        "latin-1",
    ):
        try:
            return body.decode(
                encoding
            )
        except UnicodeDecodeError:
            continue

    raise ValueError(
        "לא ניתן לקרוא את דף המקור"
    )


def _collect_candidate_urls(
    page_html: str,
    *,
    base_url: str,
) -> list[str]:
    """
    מאתרת בדף כתובות אפשריות
    שקשורות לקובץ או לפעולת ההורדה
    """

    decoded_html = html.unescape(
        page_html
    ).replace(
        "\\/",
        "/",
    )

    collector = _LinkCollector()
    collector.feed(
        decoded_html
    )

    raw_values = list(
        collector.values
    )

    raw_values.extend(
        re.findall(
            r"https?://[^\s\"'<>]+",
            decoded_html,
            flags=re.IGNORECASE,
        )
    )

    raw_values.extend(
        re.findall(
            r"[\"']([^\"']*(?:\.pdf|download)[^\"']*)[\"']",
            decoded_html,
            flags=re.IGNORECASE,
        )
    )

    candidates: list[str] = []
    seen: set[str] = set()

    for value in raw_values:
        clean_value = (
            value.strip()
            .replace(
                "\\u0026",
                "&",
            )
        )

        lowered = (
            clean_value.lower()
        )

        if (
            ".pdf"
            not in lowered
            and "download"
            not in lowered
        ):
            continue

        absolute_url = urljoin(
            base_url,
            clean_value,
        )

        if absolute_url in seen:
            continue

        seen.add(
            absolute_url
        )
        candidates.append(
            absolute_url
        )

    candidates.sort(
        key=lambda item: (
            0
            if ".pdf"
            in item.lower()
            else 1,
            len(
                item
            ),
        )
    )

    return candidates


def discover_publuu_download_candidates(
    source_url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[str]:
    """
    מחזירה רשימת כתובות אפשריות
    שמהן ניתן לקבל את קובץ המקור
    """

    clean_url = (
        _validate_source_url(
            source_url
        )
    )

    page_html = fetch_publuu_page(
        clean_url,
        timeout=timeout,
    )

    return _collect_candidate_urls(
        page_html,
        base_url=clean_url,
    )


def download_publuu_pdf(
    source_url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> bytes:
    """
    מנסה להוריד את קובץ המקור
    מתוך חוברת Publuu ציבורית

    כל כתובת אפשרית נבדקת
    עד שנמצא תוכן שהוא קובץ PDF תקין
    """

    candidates = (
        discover_publuu_download_candidates(
            source_url,
            timeout=timeout,
        )
    )

    if not candidates:
        raise ValueError(
            "לא נמצא קישור הורדה בדף Publuu"
        )

    last_error: Exception | None = None

    for candidate in candidates:
        try:
            body, content_type, _ = (
                _fetch_bytes(
                    candidate,
                    timeout=timeout,
                    accept="application/pdf,*/*",
                )
            )

            if (
                body.startswith(
                    b"%PDF"
                )
                or "application/pdf"
                in content_type
            ):
                return body

        except Exception as error:
            last_error = error

    if last_error is not None:
        raise ValueError(
            "נמצא קישור אפשרי אך הורדת ה-PDF נכשלה"
        ) from last_error

    raise ValueError(
        "לא נמצא PDF תקין בין קישורי ההורדה"
    )
