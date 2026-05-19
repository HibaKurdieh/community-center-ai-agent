# מתנ״ס דיגיטלי חכם — Sprint 0

פרויקט הוכחת יכולת (POC) לסוכן מידע על בסיס נתונים סינטטי בעברית: חוגים שבועיים, אירועים חד-פעמיים והזדמנויות התנדבות.

## מה כבר קיים ב-repo

| רכיב | תיאור |
|--------|--------|
| `data/raw/community_center_data.xlsx` | שלושה גיליונות: `activities`, `events`, `volunteer_opportunities` |
| `data/raw/community_center_booklet.docx` | חוברת שנתית בעברית |
| `data/processed/*.json` | פלט ה-ingestion (ניתן לייצר מחדש מהפקודה למטה) |
| `ingestion/ingest.py` | קריאת Excel ויצירת JSON |
| `agent/tools.py` | פונקציות חיפוש לפי שדות (ללא LLM) |
| `agent/run_agent.py` | הדגמה: שלוש שאלות בעברית ותשובות מתוך הנתונים בלבד |
| `agent/graph.py` | שמור לשלבים הבאים (LangGraph) — ריק מתוכן לוגי בספרינט 0 |

**מספרי רשומות בנתונים:** 30 חוגים, 10 אירועים, 8 הזדמנויות התנדבות.

## דרישת ליבה: תשובות רק מהנתונים

בספרינט 0 הסוכן אינו מפיק טקסט חופשי ממודל שפה. התשובות נבנות רק מסינון רשומות ב-JSON (מחרוזות בעברית מתוך הקבצים).

## התקנה

מתיקיית השורש של הפרויקט:

```bash
pip install -r requirements.txt
```

נדרש Python 3.10 ומעלה (מומלץ 3.11+).

## הרצת Ingestion (Excel → JSON)

```bash
python ingestion/ingest.py
```

הסקריפט:

1. קורא את `data/raw/community_center_data.xlsx` (שלושת הגיליונות).
2. מנרמל תאריכים/שעות למחרוזות יציבות.
3. כותב ל-`data/processed/activities.json`, `events.json`, `volunteer_opportunities.json`.

ניתן להריץ את הפקודה מכל תיקייה — הנתיבים מחושבים לפי מיקום הקובץ.

## הרצת POC (שלוש שאלות בעברית)

```bash
python agent/run_agent.py
```

ברירת המחדל מדפיסה שלוש שאלות קבועות מראש ואת התשובות מהנתונים:

1. חיפוש חוגים (כולל שילוב מסננים: קטגוריה, גיל, יום, שעה).
2. חיפוש אירועים לפי קהל יעד.
3. חיפוש התנדבות לפי גיל המתנדב.

מצב אינטראקטיבי (אופציונלי):

```bash
python agent/run_agent.py --interactive
```

## בדיקת פונקציות החיפוש ישירות

```bash
python agent/tools.py
```

## מבנה גיליון Excel

- **activities:** `id`, `name`, `category`, `age_group`, `day`, `start_time`, `end_time`, `min_age`, `max_age`, `price`, `instructor`, `location`
- **events:** `id`, `name`, `date`, `day`, `start_time`, `end_time`, `target_age_group`, `price`, `location`
- **volunteer_opportunities:** `id`, `title`, `day`, `start_time`, `end_time`, `min_age`, `location`, `contact_person`

## מבנה קוד (אנגלית)

```text
community-center-ai-agent/
├── data/raw/…
├── data/processed/…
├── ingestion/ingest.py
├── agent/paths.py
├── agent/tools.py
├── agent/run_agent.py
├── agent/graph.py
├── requirements.txt
└── README.md
```

## Smart Digital Community Center — Sprint 0 (English summary)

Synthetic Hebrew community-center data in Excel is ingested into JSON. The POC agent (`agent/run_agent.py`) answers three fixed Hebrew questions by filtering those JSON files only—no free-form LLM generation. Run `pip install -r requirements.txt`, then `python ingestion/ingest.py`, then `python agent/run_agent.py` from the project root.

## הערות ל-Windows

אם בעברית בקונסול מופיעות סימני שאלה, הפעילו טרמינל עם UTF-8 (למשל Windows Terminal) או הגדירו `PYTHONUTF8=1` לפני ההרצה.

## Git / הגשה

לדרישת ״קוד ב-Git״: יש לאתחל מאגר (`git init`), להוסיף `.gitignore` בסיסי (למשל `__pycache__/`, `.env`) ולדחוף ל-remote של הקורס.