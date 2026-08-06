# Competitor Intelligence Monitor | رصد وتحليل المنافسين

لوحة تحليلية ثنائية اللغة لمراقبة عروض وحملات منافسي المدفوعات الرقمية. تعمل بالكامل على GitHub Pages، ويقوم GitHub Actions بفحص المواقع الرسمية وروابط RSS كل 20 دقيقة.

A bilingual analytical dashboard for monitoring digital-payment competitor offers and campaigns. It runs on GitHub Pages, while GitHub Actions checks official websites and RSS feeds every 20 minutes.

## ما الذي يعرضه الموقع؟ | What does the site show?

- نظرة عامة ومؤشرات رئيسية لجميع المنافسين.
- صفحة تحليلية مستقلة لكل منافس.
- العروض النشطة، والتحديثات الجديدة، والسجل التاريخي.
- رسوم حسب المنافس، والتصنيف، والمنصة، والنشاط خلال آخر 30 يومًا.
- فلاتر حسب التصنيف والمصدر والحالة والكلمات المفتاحية.
- مفتاح للتبديل بين العربية والإنجليزية.
- حفظ حالة المقروء داخل متصفح المستخدم.
- الاحتفاظ بآخر بيانات ناجحة عند تعطل أحد المصادر.

## التصنيفات الاستراتيجية | Strategic categories

يبدأ الموقع افتراضيًا بعرض الفئات المرتبطة بمنتجاتنا:

- التحويل الدولي | International Transfer
- السفر والسياحة | Travel & Tourism
- الرسوم والإنفاق الدولي | International Fees & Spending
- البطاقات | Cards
- مساند ورواتب العمالة | Masaned & Payroll
- سداد والفواتير | SADAD & Bills
- التحويل المحلي | Local Transfer
- الكاش باك والمكافآت | Cashback & Rewards

عروض التجار والمحتوى العام محفوظة كمرجع، لكنها غير داخلة افتراضيًا في مؤشرات العروض الاستراتيجية.

## بنية الملفات | File structure

```text
competitor-monitor/
├── .github/
│   └── workflows/
│       └── monitor.yml
├── assets/
│   ├── common.js
│   ├── competitor.js
│   ├── index.js
│   └── styles.css
├── .nojekyll
├── competitor.html
├── config.json
├── data.json
├── index.html
├── monitor.py
├── README.md
├── requirements.txt
└── state.json
```

## التثبيت على GitHub | GitHub setup

### 1. استبدال الملفات

ارفع جميع الملفات والمجلدات إلى جذر المستودع. تأكد خصوصًا من وجود الملف في المسار التالي بالضبط:

```text
.github/workflows/monitor.yml
```

لا تضع `monitor.yml` في جذر المستودع.

### 2. تفعيل GitHub Pages

من المستودع افتح:

```text
Settings → Pages → Build and deployment → Source → GitHub Actions
```

### 3. التشغيل الأول

افتح:

```text
Actions → Competitor Intelligence Monitor → Run workflow
```

انتظر حتى تنجح وظيفتا `build` و`deploy` باللون الأخضر.

### 4. رابط الموقع

```text
https://YOUR-USERNAME.github.io/YOUR-REPOSITORY/
```

مثال هذا المستودع:

```text
https://mjmj777.github.io/competitor-monitor/
```

## تعديل المنافسين وروابط RSS

كل الإعدادات موجودة في `config.json`:

- `competitors`: أسماء المنافسين وروابط مواقعهم.
- `website_sources`: صفحات العروض الرسمية.
- `social_feeds`: روابط RSS لكل منصة.
- `categories`: التصنيفات والكلمات المفتاحية.
- `category_overrides`: تصنيف رابط محدد يدويًا عند الحاجة.

مثال لتصنيف رابط محدد يدويًا:

```json
{
  "link_contains": "special-remittance-offer",
  "category_id": "international_transfer"
}
```

ضعه داخل مصفوفة `category_overrides`.

## طريقة اكتشاف التحديثات

- المعرف ثابت ويعتمد على المنافس والمنصة والرابط.
- إذا تغيّر عنوان العرض أو وصفه، يزيد رقم الإصدار ويُسجل `last_changed`.
- العرض لا يصبح غير نشط إلا بعد غيابه في عدة فحوصات ناجحة متتالية.
- إذا فشل المصدر، لا تُحذف بياناته السابقة.
- جميع البيانات التاريخية تحفظ في `state.json`، بينما تقرأ الصفحة `data.json`.

## التشغيل محليًا

```bash
python -m pip install -r requirements.txt
python monitor.py --validate-only
python monitor.py
python -m http.server 8000
```

ثم افتح:

```text
http://localhost:8000/
```

لا تفتح `index.html` مباشرة بصيغة `file://` لأن المتصفح قد يمنع تحميل `data.json`.

## ملاحظات

- بعض المواقع تعتمد على JavaScript بشكل كامل؛ في هذه الحالة قد يكون RSS هو المصدر الأكثر استقرارًا.
- التصنيف آلي وقابل للتحسين من `config.json` دون تعديل كود Python.
- أوقات GitHub Actions تعمل بتوقيت UTC، لكن الصفحة تعرض التاريخ حسب لغة ومتصفح المستخدم.
