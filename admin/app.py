"""
ממשק ניהול מקומי לקובצי המקור של המערכת

הממשק מאפשר למנהל לצפות בקבצים
להוריד קובץ קיים להעלות קובץ חדש
להחליף קובץ קיים ולמחוק קובץ

הפעולות מתבצעות מול מאגר הקבצים הקיים
ואינן משנות את לוגיקת הסוכן או את תהליך הקליטה
"""

from __future__ import annotations

import hmac
import mimetypes
import os
import secrets
from datetime import datetime
from functools import wraps
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from database.external_sources_repository import (
    create_external_source,
    delete_external_source,
    get_all_external_sources,
    get_external_source_by_id,
    update_external_source,
    update_external_source_sync_status,
)
from database.supabase_client import (
    get_supabase_client,
)
from ingestion.readers.publuu_activity_extractor import (
    extract_activities_from_publuu,
)
from database.activities_repository import (
    delete_activities_by_source_file,
    get_activities_by_source_file,
    insert_new_activities,
)
from ingestion.source_adapter import (
    adapt_activity_record,
)
from ingestion.storage_source import (
    SUPPORTED_SOURCE_SUFFIXES,
    list_source_files,
)
from ingestion.validation import (
    validate_activities,
)


load_dotenv()


MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024


def _get_required_environment_value(
    name: str,
) -> str:
    """
    קוראת ערך חובה ממשתני הסביבה

    אם הערך חסר התהליך נעצר כדי למנוע
    הפעלה לא מאובטחת של ממשק הניהול
    """

    value = (
        os.getenv(
            name
        )
        or ""
    ).strip()

    if not value:
        raise RuntimeError(
            f"{name} לא נמצא "
            "יש לבדוק את קובץ .env"
        )

    return value


def _get_source_bucket_name() -> str:
    """
    מחזירה את שם מאגר קובצי המקור
    שמוגדר במשתני הסביבה
    """

    return _get_required_environment_value(
        "SOURCE_BUCKET"
    )


def _get_admin_password() -> str:
    """
    מחזירה את סיסמת מנהל המערכת
    שמוגדרת במשתני הסביבה
    """

    return _get_required_environment_value(
        "ADMIN_PASSWORD"
    )


def _create_application() -> Flask:
    """
    בונה את אפליקציית הניהול
    ומגדירה את מפתח ההפעלה המוגנת ואת מגבלת גודל הקובץ
    """

    application = Flask(
        __name__
    )

    application.secret_key = (
        _get_required_environment_value(
            "ADMIN_SESSION_SECRET"
        )
    )

    application.config[
        "MAX_CONTENT_LENGTH"
    ] = MAX_FILE_SIZE_BYTES

    return application


app = _create_application()


def _get_storage_bucket() -> Any:
    """
    מחזירה חיבור למאגר קובצי המקור
    באמצעות החיבור הקיים של המערכת למסד הנתונים
    """

    client = (
        get_supabase_client()
    )

    return (
        client.storage
        .from_(
            _get_source_bucket_name()
        )
    )


def _clean_uploaded_file_name(
    raw_name: str,
) -> str:
    """
    מנקה את שם הקובץ שהתקבל מהדפדפן

    נשמר רק שם הקובץ עצמו ללא נתיב
    ונבדק שסוג הקובץ נתמך במערכת
    """

    normalized = (
        raw_name
        .replace(
            "\\",
            "/",
        )
        .strip()
    )

    file_name = (
        normalized
        .rsplit(
            "/",
            1,
        )[-1]
        .strip()
    )

    if not file_name:
        raise ValueError(
            "לא נבחר קובץ"
        )

    suffix = (
        Path(
            file_name
        )
        .suffix
        .lower()
    )

    if (
        suffix
        not in SUPPORTED_SOURCE_SUFFIXES
    ):
        supported = ", ".join(
            sorted(
                SUPPORTED_SOURCE_SUFFIXES
            )
        )

        raise ValueError(
            "סוג הקובץ אינו נתמך. "
            f"הסוגים הנתמכים הם: {supported}"
        )

    return file_name


def _validate_existing_file_name(
    file_name: str,
) -> str:
    """
    מוודאת ששם הקובץ מתייחס לקובץ קיים
    ואינו מכיל נתיב חיצוני
    """

    clean_name = (
        file_name
        .replace(
            "\\",
            "/",
        )
        .rsplit(
            "/",
            1,
        )[-1]
        .strip()
    )

    if (
        not clean_name
        or clean_name != file_name
    ):
        raise ValueError(
            "שם הקובץ אינו תקין"
        )

    if (
        clean_name
        not in list_source_files()
    ):
        raise ValueError(
            "הקובץ לא נמצא במאגר"
        )

    return clean_name


def _get_file_type_label(
    file_name: str,
) -> str:
    """
    מחזירה תיאור קצר של סוג הקובץ
    לצורך הצגה ברורה בממשק הניהול
    """

    suffix = (
        Path(
            file_name
        )
        .suffix
        .lower()
    )

    if suffix == ".docx":
        return "מסמך וורד"

    if suffix in {
        ".xlsx",
        ".xlsm",
    }:
        return "גיליון נתונים"

    return "קובץ מקור"


def _format_file_size(
    value: Any,
) -> str:
    """
    ממירה את גודל הקובץ לתצוגה קריאה
    כאשר המידע קיים במאגר הקבצים
    """

    try:
        size = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return "לא זמין"

    units = (
        "בתים",
        "קילובתים",
        "מגה־בתים",
        "גיגה־בתים",
    )

    unit_index = 0

    while (
        size >= 1024
        and unit_index
        < len(
            units
        ) - 1
    ):
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return (
            f"{int(size)} "
            f"{units[unit_index]}"
        )

    return (
        f"{size:.1f} "
        f"{units[unit_index]}"
    )


def _format_updated_at(
    value: Any,
) -> str:
    """
    ממירה את זמן העדכון לתצוגה קצרה וברורה
    כאשר המידע קיים במאגר הקבצים
    """

    if not value:
        return "לא זמין"

    raw_value = str(
        value
    ).strip()

    try:
        parsed = datetime.fromisoformat(
            raw_value.replace(
                "Z",
                "+00:00",
            )
        )

        return parsed.strftime(
            "%d/%m/%Y %H:%M"
        )

    except ValueError:
        return raw_value


def _list_source_file_details() -> list[
    dict[str, str]
]:
    """
    קוראת את פרטי קובצי המקור ממאגר הקבצים

    לכל קובץ מוחזרים שם סוג גודל
    וזמן העדכון האחרון לצורך תצוגה בממשק
    """

    items = (
        _get_storage_bucket()
        .list()
    )

    files: list[
        dict[str, str]
    ] = []

    for item in items:
        file_name = str(
            item.get(
                "name",
                "",
            )
            or ""
        ).strip()

        if not file_name:
            continue

        suffix = (
            Path(
                file_name
            )
            .suffix
            .lower()
        )

        if (
            suffix
            not in SUPPORTED_SOURCE_SUFFIXES
        ):
            continue

        metadata = (
            item.get(
                "metadata"
            )
            or {}
        )

        size_value = None

        if isinstance(
            metadata,
            dict,
        ):
            size_value = (
                metadata.get(
                    "size"
                )
                or metadata.get(
                    "contentLength"
                )
            )

        updated_at = (
            item.get(
                "updated_at"
            )
            or item.get(
                "created_at"
            )
        )

        files.append(
            {
                "name":
                    file_name,
                "type_label":
                    _get_file_type_label(
                        file_name
                    ),
                "size":
                    _format_file_size(
                        size_value
                    ),
                "updated_at":
                    _format_updated_at(
                        updated_at
                    ),
            }
        )

    return sorted(
        files,
        key=lambda item: (
            item[
                "name"
            ].casefold()
        ),
    )



def _validate_external_source_url(
    raw_url: str,
) -> str:
    """
    בודקת שכתובת המקור החיצוני היא כתובת רשת תקינה
    שניתן להעביר בהמשך לשכבת הקריאה של המערכת
    """

    clean_url = raw_url.strip()

    if not clean_url:
        raise ValueError(
            "כתובת המקור אינה יכולה להיות ריקה"
        )

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

    return clean_url


DAY_LETTER_TO_NAME = {
    "א": "ראשון",
    "א'": "ראשון",
    "א׳": "ראשון",
    "ב": "שני",
    "ב'": "שני",
    "ב׳": "שני",
    "ג": "שלישי",
    "ג'": "שלישי",
    "ג׳": "שלישי",
    "ד": "רביעי",
    "ד'": "רביעי",
    "ד׳": "רביעי",
    "ה": "חמישי",
    "ה'": "חמישי",
    "ה׳": "חמישי",
    "ו": "שישי",
    "ו'": "שישי",
    "ו׳": "שישי",
    "שבת": "שבת",
}


def _optional_form_text(
    name: str,
) -> str | None:
    """
    קוראת שדה טקסט מהטופס

    ערך ריק מוחזר כערך חסר
    כדי לא לשמור מחרוזות ריקות במסד הנתונים
    """

    value = (
        request.form.get(
            name,
            "",
        )
        or ""
    ).strip()

    return value or None


def _optional_form_int(
    name: str,
) -> int | None:
    """
    קוראת מספר שלם אופציונלי מהטופס

    שדה ריק מוחזר כערך חסר
    וערך שאינו מספר שלם גורם לעצירת השמירה
    """

    value = _optional_form_text(
        name
    )

    if value is None:
        return None

    try:
        return int(
            value
        )

    except ValueError as error:
        raise ValueError(
            f"השדה {name} חייב להכיל מספר שלם"
        ) from error


def _external_source_file_name(
    source: dict[str, Any],
) -> str:
    """
    יוצרת מזהה קבוע לפעילויות
    שנשמרות ממקור חיצוני

    המזהה מבוסס על סוג המקור והמזהה שלו
    ולכן נשאר יציב גם אם שם המקור משתנה
    """

    source_type = str(
        source.get(
            "source_type",
            "external",
        )
        or "external"
    ).strip().lower()

    source_id = int(
        source[
            "id"
        ]
    )

    return (
        f"external:{source_type}:{source_id}"
    )


def _day_name_for_storage(
    value: str | None,
) -> str | None:
    """
    ממירה סימון יום באות עברית
    לשם היום המלא שבו משתמשת שכבת הנתונים
    """

    if value is None:
        return None

    clean_value = value.strip()

    if not clean_value:
        return None

    return DAY_LETTER_TO_NAME.get(
        clean_value,
        clean_value,
    )


def _build_external_notes(
    monthly_cost: str | None,
    additional_costs: str | None,
) -> str | None:
    """
    בונה הערה קצרה
    שמכילה רק מחיר חודשי ותשלומים נוספים
    """

    parts: list[str] = []

    if monthly_cost:
        parts.append(
            f"עלות חודשית: {monthly_cost}"
        )

    if additional_costs:
        parts.append(
            f"תשלומים נוספים: {additional_costs}"
        )

    if not parts:
        return None

    return "; ".join(
        parts
    )


def _read_edited_external_activities() -> list[
    dict[str, Any]
]:
    """
    קוראת את כל הפעילויות
    לאחר שהמנהל ערך אותן בתצוגה המקדימה
    """

    raw_count = (
        request.form.get(
            "activity_count",
            "0",
        )
        or "0"
    ).strip()

    try:
        activity_count = int(
            raw_count
        )

    except ValueError as error:
        raise ValueError(
            "מספר הפעילויות בטופס אינו תקין"
        ) from error

    if (
        activity_count <= 0
        or activity_count > 100
    ):
        raise ValueError(
            "מספר הפעילויות בטופס אינו תקין"
        )

    activities: list[
        dict[str, Any]
    ] = []

    for index in range(
        activity_count
    ):
        prefix = (
            f"activity_{index}_"
        )

        monthly_cost = (
            _optional_form_text(
                prefix
                + "monthly_cost"
            )
        )

        additional_costs = (
            _optional_form_text(
                prefix
                + "additional_costs"
            )
        )

        activities.append(
            {
                "page_number":
                    _optional_form_int(
                        prefix
                        + "page_number"
                    ),
                "section_title":
                    _optional_form_text(
                        prefix
                        + "section_title"
                    ),
                "name":
                    _optional_form_text(
                        prefix
                        + "name"
                    ),
                "center_name":
                    _optional_form_text(
                        prefix
                        + "center_name"
                    ),
                "branch":
                    _optional_form_text(
                        prefix
                        + "branch"
                    ),
                "day":
                    _optional_form_text(
                        prefix
                        + "day"
                    ),
                "start_time":
                    _optional_form_text(
                        prefix
                        + "start_time"
                    ),
                "end_time":
                    _optional_form_text(
                        prefix
                        + "end_time"
                    ),
                "target_audience":
                    _optional_form_text(
                        prefix
                        + "target_audience"
                    ),
                "min_age":
                    _optional_form_int(
                        prefix
                        + "min_age"
                    ),
                "max_age":
                    _optional_form_int(
                        prefix
                        + "max_age"
                    ),
                "instructor":
                    _optional_form_text(
                        prefix
                        + "instructor"
                    ),
                "location":
                    _optional_form_text(
                        prefix
                        + "location"
                    ),
                "monthly_cost":
                    monthly_cost,
                "additional_costs":
                    additional_costs,
                "notes":
                    _build_external_notes(
                        monthly_cost,
                        additional_costs,
                    ),
            }
        )

    return activities


def _adapt_external_activities(
    activities: list[
        dict[str, Any]
    ],
    *,
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    מעבירה את הפעילויות הערוכות
    דרך שכבת ההתאמה הכללית של המערכת

    כך גם מקור חיצוני משתמש
    באותו מבנה נתונים של שאר מקורות המערכת
    """

    source_name = (
        _external_source_file_name(
            source
        )
    )

    adapted: list[
        dict[str, Any]
    ] = []

    for activity in activities:
        original_day = activity.get(
            "day"
        )

        record = dict(
            activity
        )

        record[
            "day"
        ] = _day_name_for_storage(
            original_day
        )

        converted = (
            adapt_activity_record(
                record,
                source_name=
                    source_name,
            )
        )

        if original_day:
            converted[
                "raw_day"
            ] = original_day

        adapted.append(
            converted
        )

    return adapted


def _validate_external_source_name(
    raw_name: str,
) -> str:
    """
    בודקת שלמקור החיצוני יש שם ברור
    לצורך זיהויו בממשק הניהול
    """

    clean_name = raw_name.strip()

    if not clean_name:
        raise ValueError(
            "שם המקור אינו יכול להיות ריק"
        )

    return clean_name

def _get_csrf_token() -> str:
    """
    מחזירה אסימון הגנה לטופסי הניהול

    האסימון נשמר במצב ההפעלה של המנהל
    ומשמש לבדיקה לפני פעולות שמשנות קבצים
    """

    token = session.get(
        "csrf_token"
    )

    if not token:
        token = secrets.token_urlsafe(
            32
        )

        session[
            "csrf_token"
        ] = token

    return str(
        token
    )


app.jinja_env.globals[
    "csrf_token"
] = _get_csrf_token


def _validate_csrf_token() -> None:
    """
    בודקת שהטופס נשלח מתוך מצב ההפעלה הנוכחי
    ולא מתוך בקשה חיצונית לא מורשית
    """

    expected = str(
        session.get(
            "csrf_token",
            "",
        )
    )

    received = (
        request.form.get(
            "csrf_token",
            "",
        )
        or ""
    )

    if (
        not expected
        or not received
        or not hmac.compare_digest(
            expected,
            received,
        )
    ):
        abort(
            400
        )


def _admin_required(
    function: Callable[..., Any],
) -> Callable[..., Any]:
    """
    מגינה על דפי הניהול

    משתמש שלא עבר אימות מועבר למסך הכניסה
    """

    @wraps(
        function
    )
    def wrapped(
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if not session.get(
            "admin_authenticated",
            False,
        ):
            return redirect(
                url_for(
                    "login"
                )
            )

        return function(
            *args,
            **kwargs,
        )

    return wrapped


@app.route(
    "/login",
    methods=[
        "GET",
        "POST",
    ],
)
def login() -> Any:
    """
    מציגה את מסך הכניסה
    ומאמתת את סיסמת מנהל המערכת
    """

    if request.method == "POST":
        _validate_csrf_token()

        password = (
            request.form.get(
                "password",
                "",
            )
            or ""
        )

        if hmac.compare_digest(
            password,
            _get_admin_password(),
        ):
            session[
                "admin_authenticated"
            ] = True

            flash(
                "הכניסה בוצעה בהצלחה",
                "success",
            )

            return redirect(
                url_for(
                    "index"
                )
            )

        flash(
            "הסיסמה אינה נכונה",
            "error",
        )

    return render_template(
        "login.html"
    )


@app.post(
    "/logout"
)
@_admin_required
def logout() -> Any:
    """
    מסיימת את מצב ההפעלה של מנהל המערכת
    ומחזירה למסך הכניסה
    """

    _validate_csrf_token()

    session.clear()

    return redirect(
        url_for(
            "login"
        )
    )


@app.get(
    "/"
)
@_admin_required
def index() -> Any:
    """
    מציגה את קובצי המקור הקיימים
    ואת פעולות הניהול הזמינות
    """

    try:
        files = (
            _list_source_file_details()
        )

    except Exception as error:
        files = []

        flash(
            "לא ניתן לקרוא את קובצי המקור: "
            f"{error}",
            "error",
        )

    try:
        external_sources = (
            get_all_external_sources()
        )

    except Exception as error:
        external_sources = []

        flash(
            "לא ניתן לקרוא את המקורות החיצוניים: "
            f"{error}",
            "error",
        )

    return render_template(
        "index.html",
        files=
            files,
        external_sources=
            external_sources,
        supported_suffixes=
            sorted(
                SUPPORTED_SOURCE_SUFFIXES
            ),
    )


@app.get(
    "/download/<path:file_name>"
)
@_admin_required
def download_file(
    file_name: str,
) -> Any:
    """
    מורידה קובץ מקור קיים מהמאגר
    ושולחת אותו למנהל כקובץ להורדה
    """

    try:
        target_name = (
            _validate_existing_file_name(
                file_name
            )
        )

        file_bytes = (
            _get_storage_bucket()
            .download(
                target_name
            )
        )

        content_type = (
            mimetypes.guess_type(
                target_name
            )[0]
            or "application/octet-stream"
        )

        return send_file(
            BytesIO(
                file_bytes
            ),
            mimetype=
                content_type,
            as_attachment=
                True,
            download_name=
                target_name,
        )

    except Exception as error:
        flash(
            f"הורדת הקובץ נכשלה: {error}",
            "error",
        )

        return redirect(
            url_for(
                "index"
            )
        )


@app.post(
    "/upload"
)
@_admin_required
def upload_file() -> Any:
    """
    מעלה קובץ מקור חדש למאגר הקבצים

    אם כבר קיים קובץ באותו שם
    המנהל מתבקש להשתמש בפעולת ההחלפה
    """

    _validate_csrf_token()

    uploaded_file = request.files.get(
        "file"
    )

    if uploaded_file is None:
        flash(
            "לא נבחר קובץ",
            "error",
        )

        return redirect(
            url_for(
                "index"
            )
        )

    try:
        file_name = (
            _clean_uploaded_file_name(
                uploaded_file.filename
                or ""
            )
        )

        if (
            file_name
            in list_source_files()
        ):
            raise ValueError(
                "כבר קיים קובץ בשם הזה. "
                "יש להשתמש בפעולת ההחלפה"
            )

        file_bytes = (
            uploaded_file.read()
        )

        if not file_bytes:
            raise ValueError(
                "הקובץ ריק"
            )

        content_type = (
            uploaded_file.mimetype
            or mimetypes.guess_type(
                file_name
            )[0]
            or "application/octet-stream"
        )

        _get_storage_bucket().upload(
            file_name,
            file_bytes,
            {
                "content-type":
                    content_type,
            },
        )

        flash(
            f"הקובץ {file_name} הועלה בהצלחה. "
            "הסנכרון האוטומטי יטפל בו",
            "success",
        )

    except Exception as error:
        flash(
            f"העלאת הקובץ נכשלה: {error}",
            "error",
        )

    return redirect(
        url_for(
            "index"
        )
    )


@app.post(
    "/replace/<path:file_name>"
)
@_admin_required
def replace_file(
    file_name: str,
) -> Any:
    """
    מחליפה קובץ קיים בתוכן חדש
    תוך שמירה על אותו שם במאגר הקבצים
    """

    _validate_csrf_token()

    uploaded_file = request.files.get(
        "file"
    )

    if uploaded_file is None:
        flash(
            "לא נבחר קובץ חלופי",
            "error",
        )

        return redirect(
            url_for(
                "index"
            )
        )

    try:
        target_name = (
            _validate_existing_file_name(
                file_name
            )
        )

        uploaded_name = (
            _clean_uploaded_file_name(
                uploaded_file.filename
                or ""
            )
        )

        target_suffix = (
            Path(
                target_name
            )
            .suffix
            .lower()
        )

        uploaded_suffix = (
            Path(
                uploaded_name
            )
            .suffix
            .lower()
        )

        if (
            target_suffix
            != uploaded_suffix
        ):
            raise ValueError(
                "סוג הקובץ החלופי חייב להתאים "
                "לסוג הקובץ הקיים"
            )

        file_bytes = (
            uploaded_file.read()
        )

        if not file_bytes:
            raise ValueError(
                "הקובץ החלופי ריק"
            )

        content_type = (
            uploaded_file.mimetype
            or mimetypes.guess_type(
                target_name
            )[0]
            or "application/octet-stream"
        )

        _get_storage_bucket().update(
            target_name,
            file_bytes,
            {
                "content-type":
                    content_type,
            },
        )

        flash(
            f"הקובץ {target_name} הוחלף בהצלחה. "
            "הסנכרון האוטומטי יעדכן את הנתונים",
            "success",
        )

    except Exception as error:
        flash(
            f"החלפת הקובץ נכשלה: {error}",
            "error",
        )

    return redirect(
        url_for(
            "index"
        )
    )


@app.post(
    "/delete/<path:file_name>"
)
@_admin_required
def delete_file(
    file_name: str,
) -> Any:
    """
    מוחקת קובץ מקור קיים ממאגר הקבצים

    תהליך הסנכרון האוטומטי יזהה את המחיקה
    ויעדכן את נתוני המערכת
    """

    _validate_csrf_token()

    try:
        target_name = (
            _validate_existing_file_name(
                file_name
            )
        )

        _get_storage_bucket().remove(
            [
                target_name
            ]
        )

        flash(
            f"הקובץ {target_name} נמחק בהצלחה. "
            "הסנכרון האוטומטי יעדכן את הנתונים",
            "success",
        )

    except Exception as error:
        flash(
            f"מחיקת הקובץ נכשלה: {error}",
            "error",
        )

    return redirect(
        url_for(
            "index"
        )
    )


@app.post(
    "/external-sources/add"
)
@_admin_required
def add_external_source() -> Any:
    """
    מוסיפה מקור חיצוני חדש מרשימת הניהול

    בשלב זה נשמרים פרטי המקור בלבד
    והקריאה מהתוכן תחובר בשכבת הסנכרון
    """

    _validate_csrf_token()

    try:
        name = (
            _validate_external_source_name(
                request.form.get(
                    "name",
                    "",
                )
                or ""
            )
        )

        url = (
            _validate_external_source_url(
                request.form.get(
                    "url",
                    "",
                )
                or ""
            )
        )

        create_external_source(
            name=name,
            url=url,
            source_type="publuu",
            is_active=True,
        )

        flash(
            f"המקור {name} נוסף בהצלחה",
            "success",
        )

    except Exception as error:
        flash(
            f"הוספת המקור נכשלה: {error}",
            "error",
        )

    return redirect(
        url_for(
            "index"
        )
    )


@app.post(
    "/external-sources/<int:source_id>/update"
)
@_admin_required
def edit_external_source(
    source_id: int,
) -> Any:
    """
    מעדכנת שם כתובת ומצב פעילות
    של מקור חיצוני שכבר קיים במערכת
    """

    _validate_csrf_token()

    try:
        name = (
            _validate_external_source_name(
                request.form.get(
                    "name",
                    "",
                )
                or ""
            )
        )

        url = (
            _validate_external_source_url(
                request.form.get(
                    "url",
                    "",
                )
                or ""
            )
        )

        is_active = (
            request.form.get(
                "is_active"
            )
            == "on"
        )

        update_external_source(
            source_id,
            name=name,
            url=url,
            source_type="publuu",
            is_active=is_active,
        )

        flash(
            f"המקור {name} עודכן בהצלחה",
            "success",
        )

    except Exception as error:
        flash(
            f"עדכון המקור נכשל: {error}",
            "error",
        )

    return redirect(
        url_for(
            "index"
        )
    )


@app.post(
    "/external-sources/<int:source_id>/test"
)
@_admin_required
def test_external_source(
    source_id: int,
) -> Any:
    """
    קוראת מקור חיצוני
    ומציגה את הפעילויות לעריכה לפני שמירה
    """

    _validate_csrf_token()

    try:
        source = (
            get_external_source_by_id(
                source_id
            )
        )

        if source is None:
            raise ValueError(
                "המקור החיצוני לא נמצא"
            )

        activities = (
            extract_activities_from_publuu(
                str(
                    source.get(
                        "url",
                        "",
                    )
                )
            )
        )

        if not activities:
            raise ValueError(
                "לא נמצאו פעילויות במקור"
            )

        return render_template(
            "external_preview.html",
            source=source,
            activities=activities,
            validation_errors=[],
        )

    except Exception as error:
        flash(
            f"בדיקת המקור נכשלה: {error}",
            "error",
        )

        return redirect(
            url_for(
                "index"
            )
        )


@app.post(
    "/external-sources/<int:source_id>/save-preview"
)
@_admin_required
def save_external_source_preview(
    source_id: int,
) -> Any:
    """
    שומרת את הפעילויות
    לאחר שהמנהל בדק וערך אותן

    לפני השמירה הפעילויות עוברות
    התאמה למבנה האחיד ובדיקת תקינות
    """

    _validate_csrf_token()

    try:
        source = (
            get_external_source_by_id(
                source_id
            )
        )

        if source is None:
            raise ValueError(
                "המקור החיצוני לא נמצא"
            )

        edited_activities = (
            _read_edited_external_activities()
        )

        adapted_activities = (
            _adapt_external_activities(
                edited_activities,
                source=source,
            )
        )

        report = validate_activities(
            adapted_activities
        )

        if not report.passed:
            return render_template(
                "external_preview.html",
                source=source,
                activities=edited_activities,
                validation_errors=
                    report.critical_errors,
            )

        source_file = (
            _external_source_file_name(
                source
            )
        )

        previous_activities = (
            get_activities_by_source_file(
                source_file
            )
        )

        deleted_count = 0

        try:
            if previous_activities:
                deleted_count = (
                    delete_activities_by_source_file(
                        source_file
                    )
                )

            result = insert_new_activities(
                adapted_activities
            )

            handled_count = (
                result["inserted"]
                + result["duplicates"]
            )

            if handled_count != len(
                adapted_activities
            ):
                raise RuntimeError(
                    "לא כל הפעילויות החדשות טופלו בזמן השמירה"
                )

        except Exception:
            if previous_activities:
                delete_activities_by_source_file(
                    source_file
                )

                insert_new_activities(
                    previous_activities
                )

            raise

        update_external_source_sync_status(
            source_id,
            status="saved",
            error_message=None,
        )

        flash(
            (
                "שמירת המקור הסתיימה בהצלחה. "
                f"נמחקו {deleted_count} פעילויות ישנות, "
                f"נשמרו {result['inserted']} פעילויות חדשות "
                f"ו-{result['duplicates']} כבר היו קיימות"
            ),
            "success",
        )

        return redirect(
            url_for(
                "index"
            )
        )

    except Exception as error:
        try:
            update_external_source_sync_status(
                source_id,
                status="error",
                error_message=str(
                    error
                ),
            )
        except Exception:
            pass

        flash(
            f"שמירת הפעילויות נכשלה: {error}",
            "error",
        )

        return redirect(
            url_for(
                "index"
            )
        )


@app.post(
    "/external-sources/<int:source_id>/delete"
)
@_admin_required
def remove_external_source(
    source_id: int,
) -> Any:
    """
    מוחקת מקור חיצוני מרשימת הניהול

    מחיקת נתונים שכבר נקלטו מהמקור
    תחובר בשלב הסנכרון של המקורות החיצוניים
    """

    _validate_csrf_token()

    try:
        deleted = (
            delete_external_source(
                source_id
            )
        )

        if not deleted:
            raise ValueError(
                "המקור החיצוני לא נמצא"
            )

        flash(
            "המקור החיצוני נמחק בהצלחה",
            "success",
        )

    except Exception as error:
        flash(
            f"מחיקת המקור נכשלה: {error}",
            "error",
        )

    return redirect(
        url_for(
            "index"
        )
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
    )