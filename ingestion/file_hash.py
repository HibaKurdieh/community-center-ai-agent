"""
הקובץ אחראי על יצירת טביעת תוכן קבועה לקובץ

טביעת התוכן מחושבת מתוך תוכן הקובץ עצמו
ולא מתוך שם הקובץ

כך ניתן לזהות אם קובץ כבר עובד בעבר
וגם לזהות שינוי בתוכן של קובץ בעל אותו שם
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def calculate_file_hash(
    file_path: Path,
) -> str:
    """
    מחשבת טביעת תוכן ייחודית לקובץ

    הקובץ נקרא בחלקים
    כדי לא לטעון את כולו לזיכרון בבת אחת
    """

    if not file_path.exists():
        raise FileNotFoundError(
            file_path
        )

    if not file_path.is_file():
        raise ValueError(
            "הנתיב חייב להצביע על קובץ"
        )

    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        while True:
            chunk = file.read(
                8192
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()