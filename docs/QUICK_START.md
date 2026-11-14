# Start here / ابدأ من هنا

## Run the software now

1. Download the repository ZIP and extract it, or use a Git clone.
2. Install Python 3.10 or newer if needed.
3. Open a terminal inside the folder containing `pyproject.toml`.
4. On Windows, run these commands. On Linux/macOS use `python3` instead of `py`.

```powershell
py -m naseem simulate --scenario mixed --samples 72 --db first_demo.sqlite3 --jsonl first_demo.jsonl --verbose
py -m naseem export --db first_demo.sqlite3 --csv first_demo.csv
py -m unittest discover -s tests -v
```

Expected demo: 72 accepted records and zero rejected records. You will see
UNKNOWN, NORMAL, WATCH and HIGH during the synthetic scenarios. These are
software examples, not air measurements or health/safety conclusions.
If an export already exists, choose another output name; exports are protected
from overwriting. You do not need the ESP32, screen or sensors for these steps.

## What to send before connecting hardware

One clear front/back photo of the ESP32, the purchased 2.8-inch display and each
sensor, including the printed pin labels. Include the actual order/model for the
soldered sensor. Display size alone cannot identify its controller or wiring.
The software has candidate ILI9341 support, but the delivered screen may differ.

## بالعربي

ابدؤوا بتشغيل الأوامر فوق على الكمبيوتر. ما تحتاجون توصيل القطع عشان تجربون
البرنامج. المحاكاة تطلع ٧٢ قراءة تجريبية، تحفظها في قاعدة بيانات، وبعدها تصدرها
لملف CSV يفتح في Excel. هذي بيانات مولدة للتجربة، مو قياسات حقيقية من الغرفة.

قبل التوصيل نحتاج صور واضحة لوجه وظهر كل قطعة مع أسماء المنافذ، خصوصًا الشاشة
٢٫٨ إنش والحساس الملحوم. حجم الشاشة ما يكفي لتحديد نوعها أو طريقة توصيلها.
لا تستخدمون منافذ أمثلة اختبارات البرمجة كمخطط توصيل.

بعد التأكد من القطع والتوصيل نختبر كل حساس لحاله، ثم نقل القراءات للكمبيوتر،
ثم عرض النتيجة على الشاشة. MQ-7 باقي معطل إلى أن نتأكد من دائرة التسخين
والمعايرة. المشروع ما يغني عن جهاز إنذار معتمد.
