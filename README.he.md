# morning-cli

**כלי שורת פקודה ידידותי-סוכן (agent-native) ל-[morning by Green Invoice](https://www.greeninvoice.co.il)** — ממשק הנפקת החשבוניות המוביל בישראל.

נבנה על-ידי [JangoAI](https://jango-ai.com) במתודולוגיית [cli-anything](https://github.com/HKUDS/CLI-Anything). גרסה באנגלית: [README.md](README.md).

## מה זה

`morning-cli` עוטף את כל ה-API של morning (לשעבר Green Invoice) ב-CLI נקי שאפשר להשתמש בו משורת הפקודה, מסקריפטים, או מתוך סוכני AI (Claude Code, Cursor, וכו'). הכלי לא מממש חשבוניות בפייתון — הוא קורא ישר ל-API האמיתי של morning.

**מה יש בארסנל:**
- ✅ 66 endpoints ב-10 קבוצות (עסקים, לקוחות, ספקים, פריטים, מסמכים, הוצאות, תשלומים, פרטנרים, כלים)
- ✅ אשף התחברות אינטראקטיבי (`morning-cli auth init`) שמעביר אותך שלב-אחר-שלב ביצירת מפתחות API
- ✅ REPL אינטראקטיבי כמצב ברירת מחדל — הרץ `morning-cli` בלי פרמטרים
- ✅ פלט JSON עקבי (`--json`) לצריכה על-ידי AI agents, עם מבנה מתועד
- ✅ חידוש JWT אוטומטי על 401 — לא צריך לחשוב על תוקף טוקנים
- ✅ ברירת מחדל: sandbox — תקלות לא פוגעות בנתונים אמיתיים
- ✅ קובץ session נעול ב-`~/.greeninvoice/session.json` (הרשאות 0600)
- ✅ 55 טסטים, מתוכם 22 רצים מול ה-sandbox החי האמיתי
- ✅ הודעות שגיאה בעברית נשמרות end-to-end (`errorCode` + `errorMessage`)

## התקנה

```bash
pip install morning-cli
```

דורש Python 3.10 ומעלה.

## התחלה מהירה

```bash
# 1. הרץ את אשף ההתחברות האינטראקטיבי
morning-cli auth init
```

האשף ידריך אותך:
1. לבחור בין sandbox ל-production
2. לפתוח את העמוד של morning ליצירת מפתח API
3. להדביק את ה-`id` וה-`secret`
4. לאמת את המפתחות מול ה-API האמיתי
5. לשמור אותם ב-`~/.greeninvoice/credentials.json` (הרשאות 0600)

**לאחר מכן:**

```bash
# REPL אינטראקטיבי (מצב ברירת מחדל)
morning-cli

# או פקודות חד-פעמיות
morning-cli --json business current         # פרטי העסק שלך
morning-cli --json document types --lang he  # כל סוגי המסמכים הנתמכים
morning-cli --json client search              # כל הלקוחות
```

## דוגמה — יצירת חשבון עסקה (Proforma Invoice)

```bash
cat > /tmp/proforma.json <<'JSON'
{
  "description": "ריטיינר חודשי",
  "type": 300,
  "lang": "he",
  "currency": "ILS",
  "vatType": 0,
  "client": {"name": "חברת אקמה בע\"מ", "emails": ["ap@acme.co.il"], "country": "IL"},
  "income": [
    {"description": "שירותי ייעוץ", "quantity": 10, "price": 300, "currency": "ILS", "vatType": 0}
  ]
}
JSON

# תצוגה מקדימה (לא יוצרת מסמך אמיתי)
morning-cli --json document preview --file /tmp/proforma.json

# יצירה בפועל
morning-cli --json document create --file /tmp/proforma.json
```

## סוגי מסמכים נתמכים

| קוד | סוג |
|---|---|
| 10 | הצעת מחיר |
| 20 | דרישת תשלום / אישור תשלום |
| 100 | הזמנה |
| 200 | תעודת משלוח |
| 300 | **חשבון עסקה** (עובד לכל סוגי העסקים) |
| 305 | חשבונית מס (לא זמין לעוסק פטור) |
| 320 | חשבונית מס / קבלה |
| 330 | חשבונית זיכוי |
| 400 | קבלה |
| 405 | קבלה לתרומה |

הרשימה המלאה: `morning-cli --json document types --lang he`

## פקודות לפי קבוצה

| קבוצה | endpoints | פקודות עיקריות |
|---|---|---|
| `auth` | מקומי | `init` (אשף), `login`, `logout`, `whoami`, `refresh` |
| `session` | מקומי | `show`, `reset`, `history` |
| `business` | 10 | `list`, `current`, `get`, `update`, ניהול מספור ולוגו |
| `client` | 8 | `add`, `get`, `update`, `delete`, `search`, `merge` |
| `supplier` | 6 | כמו client אבל לספקים |
| `item` | 5 | ניהול פריטי קטלוג (מוצרים/שירותים) |
| `document` | 13 | יצירה, חיפוש, הורדת PDF, סגירה/פתיחה |
| `expense` | 13 | הוצאות + מנגנון העלאת קבלות |
| `payment` | 3 | טפסי תשלום וחיוב כרטיסי אשראי שמורים |
| `partner` | 4 | חיבורי בין-חשבונות של morning |
| `tools` | 4 | רשימות עזר: עיסוקים, מדינות, ערים, מטבעות |

## שגיאות נפוצות

| קוד | משמעות | מה לעשות |
|---|---|---|
| 401 | טוקן פג | ה-CLI מחדש אוטומטית — אם זה עדיין נכשל, הרץ `morning-cli auth init` שוב |
| 1003 | אין עסק פעיל בחשבון | צור עסק ב-UI של morning תחילה |
| 1006 | המינוי פג | חדש את המינוי בהגדרות morning |
| 1007 | חסרה הרשאה | מפתח ה-API שלך בסקופ מוגבל מדי |
| 1012 | הפעולה דורשת מסלול גבוה יותר | שדרג את המינוי |
| 1110 | מחיר לא תקין | בדוק את שדה `price` ב-`income[]` |
| 2102 | אי-אפשר להוסיף עוד עסקים במסלול הזה | שדרג או מחק עסק קיים |
| 2403 | סוג מסמך לא נתמך עבור סוג העסק | עוסק פטור למשל לא יכול להנפיק חשבונית מס (305) |

## משתני סביבה

```bash
export MORNING_API_KEY_ID=<ה-id-שלך>
export MORNING_API_KEY_SECRET=<הסוד-שלך>
export MORNING_ENV=sandbox   # או production
```

*(התחילית הישנה `GREENINVOICE_*` עדיין נתמכת.)*

## שאלות נפוצות

**איך אני יוצר מפתחות API?**
היכנס ל-morning → Settings → Advanced → Developers → "יצירת מפתח API". שים לב: הסוד מוצג פעם אחת בלבד. הרץ `morning-cli auth init` והאשף יפתח את הדף הנכון בשבילך.

**מה ההבדל בין sandbox ל-production?**
Sandbox הוא סביבת בדיקות עם בסיס נתונים נפרד. מפתחות sandbox לא עובדים ב-production ולהפך. ה-sandbox משתמש בכרטיס אשראי דמו לתשלומים. הרשמה ל-sandbox: [lp.sandbox.d.greeninvoice.co.il/join](https://lp.sandbox.d.greeninvoice.co.il/join).

**האם צריך מסלול מסוים של morning?**
כן — ה-API נעול מאחורי מסלולים מסוימים (כמו "Best"). אם אתה רואה "ForbiddenException: Product is not included in your subscription" — המסלול שלך לא כולל את מודול ה-API.

**אני עוסק פטור — אילו מסמכים אני יכול להנפיק?**
עוסק פטור יכול להנפיק: הצעות מחיר (10), הזמנות (100), תעודות משלוח (200), **חשבונות עסקה (300)**, קבלות (400). לא ניתן להנפיק חשבוניות מס (305) — זה מוגבל לעוסק מורשה/חברה.

**איך אני מוחק חשבונית שיצרתי בטעות?**
אי-אפשר — מסמכים שהונפקו לא ניתנים למחיקה מסיבות רגולטוריות. מה שכן: אפשר לבטל ב-`document close` או להנפיק חשבונית זיכוי (330).

## AI Agents

יש לחבילה קובץ [SKILL.md](cli_anything/greeninvoice/skills/SKILL.md) שמתגלה אוטומטית על-ידי Claude Code / Cursor. אם אתה סוכן AI שקורא את זה — תתחיל שם, יש שם דוגמאות מוכנות ורשימה מלאה של קודי השגיאה של morning.

## תרומה לפרויקט

PRs ברוכים ב-[github.com/jango-ai-com/morning-cli](https://github.com/jango-ai-com/morning-cli). לפני שליחה:

```bash
pip install -e ".[test]"
pytest cli_anything/greeninvoice/tests/test_core.py -v
```

## על JangoAI

[JangoAI](https://jango-ai.com) היא סטודיו ישראלי לאוטומציה וכלי AI לעסקים. אנחנו בונים אינטגרציות עם n8n, Monday.com, Supabase, ו-CLIs כמו זה — כולם עם דגש על להיות שימושיים לסוכני AI ולא רק לבני אדם.

**היי, אם השתמשת בכלי ועזר לך — בוא נכיר!** צור קשר דרך [jango-ai.com](https://jango-ai.com) או פתח issue ב-GitHub.

## רישיון

MIT. ראה [LICENSE](LICENSE).

---

*נבנה על-ידי JangoAI · [jango-ai.com](https://jango-ai.com) · [@jango-ai-com ב-GitHub](https://github.com/jango-ai-com)*
