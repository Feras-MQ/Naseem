# Start here / ابدأ من هنا

## Use it now, without parts

1. Download the review branch from [PR #1](https://github.com/Feras-MQ/Naseem/pull/1), or the supplied work-package ZIP. The default `main` branch is older until this PR is merged.
2. Extract the whole folder. Install Python 3.10 or newer if it is not installed.
3. On Windows, double-click **Start-Naseem.cmd**. On Linux/macOS run `python3 scripts/start.py` from the project folder.
4. Open **report.html** at the path printed in the window. It is inside `data/demos/` in a newly created folder.

You get four charts, a status timeline, every reading's explanation, a SQLite
database and CSV/JSONL files. Expected: **72 accepted, 0 rejected**. All values
are **generated demo data**, not measurements. You need no screen, sensor,
database server, login or internet connection for this demo. Each launch creates
a separate folder; earlier demos and recordings are preserved.

## Prepare the recording database

Open a terminal in the extracted project folder:

```powershell
py scripts/start.py doctor
py scripts/start.py init-db --db data/hardware.sqlite3
py scripts/start.py inspect --db data/hardware.sqlite3
```

This prepares the SQLite tables with **zero sessions and zero readings**. The
database is a local file. `doctor` checks Python/SQLite and reports whether the
optional USB dependency is installed; missing USB support does not block a demo.

## Prepare USB software (optional now)

On Windows run **Setup-USB.cmd** once. It uses internet access to install the local
package and pyserial into this project's `.venv`. No administrator or PowerShell
policy change is needed. Then:

```powershell
.\Start-Naseem.cmd ports
```

This only lists available ports. It does not connect, flash firmware or select a
port for you. Do not start hardware recording until the actual boards and wiring
have been confirmed. See [the complete software guide](SOFTWARE_GUIDE.md).

## بالعربي

**تقدرون تبدأون الآن بدون توصيل أي قطعة:**

1. نزّلوا نسخة الفرع الموجود في رابط PR رقم 1 فوق، أو ملف المشروع المضغوط المرسل لكم. نسخة `main` أقدم إلى أن يتم الدمج.
2. فكّوا الضغط عن المجلد كامل، وتأكدوا أن Python إصدار 3.10 أو أحدث موجود.
3. افتحوا **Start-Naseem.cmd**. بيجهّز تجربة جديدة ويكتب لكم مكان ملف **report.html**.
4. افتحوا التقرير في المتصفح. بتشوفون الرسوم، الحالات، أسباب النتائج، والملفات اللي تقدرون تصدّرونها.

التجربة تطلع ٧٢ قراءة، وتحفظها في SQLite وCSV. **هذي بيانات مولدة للتجربة، مو
قياسات من الغرفة.** ما تحتاجون سيرفر قاعدة بيانات؛ SQLite موجودة مع Python.
كل تشغيل يسوي مجلد جديد داخل `data/demos/` وما يستبدل تجاربكم السابقة.

الأوامر في قسم قاعدة البيانات فوق تجهّز ملف `data/hardware.sqlite3` فاضي
للتسجيل لاحقًا. **Setup-USB.cmd** يجهّز مكتبة USB داخل مجلد المشروع فقط،
ويحتاج إنترنت للتنزيل. أمر `ports` يعرض المنافذ بدون ما يتصل بأي جهاز.

## What is needed when the parts arrive

Send clear front/back photographs of the ESP32, the purchased 2.8-inch display
and each sensor, including printed pin labels and the actual model/order for the
soldered sensor. Display size alone does not identify the controller or interface.
The code has a candidate ILI9341 adapter; the delivered display may differ.

قبل التوصيل نحتاج صور واضحة لوجه وظهر القطع وأسماء المنافذ، خصوصًا الشاشة
والحساس الملحوم. منافذ اختبار التجميع في الكود **مو مخطط توصيل**.
نختبر كل حساس لحاله بعد التأكد من الفولتية والتوصيل، ثم USB، ثم الشاشة.
MQ-7 باقي معطل إلى أن تتأكد دائرة التسخين والمعايرة؛ المشروع مو بديل لإنذار معتمد.
