# Competitor Intelligence Dashboard v4

لوحة ثنائية اللغة متوافقة مع ملف:

`competitor_campaigns_all_competitors_social_verified_2026-08-06_updated.xlsx`

## أساس التصنيف

تصنيفات الحملات مطابقة للملف المعتمد:

- Remittance
- Musaned
- SADAD
- Card
- Engagement
- Other

سجلات `Merchant` محفوظة في **Merchant Offers Portfolio** كمرجع مستقل، ولا تدخل في مؤشرات وعدد الحملات.

## أساس الملخص

الملخص يحسب **جميع الحملات النشطة الحالية** الموجودة في `inventory.json`، وليس فقط العناصر الجديدة منذ آخر زيارة. يتضمن المخزون الأولي 48 سجلًا من Excel: 24 حملة نشطة، 15 عرض شريك نشط، و9 سجلات منتهية محفوظة للسجل التحليلي.

## ملفات البيانات

- `inventory.json`: المخزون المستورد من Excel.
- `data.json`: الناتج النهائي الذي تقرأه الواجهة.
- `state.json`: سجل العناصر الحية المكتشفة من المواقع وRSS.
- `manual_overrides.json`: التعديلات اليدوية الدائمة التي ترفعها للمستودع.

## التعديل اليدوي من الموقع

يمكن تعديل التصنيف والاسم والملخص والحالة والروابط من زر **تعديل**.

التعديل يحفظ فورًا في المتصفح الحالي. لجعله دائمًا لجميع المستخدمين:

1. اضغط **تصدير التعديلات**.
2. سينزل ملف `manual_overrides.json`.
3. استبدل الملف الذي يحمل الاسم نفسه في مستودع GitHub.
4. شغّل GitHub Actions من جديد.

## فحص المصادر

افتح مربع **سلامة المصادر** في الصفحة الرئيسية. كل مصدر يعرض:

- يعمل / متعثر / يعمل بدون عناصر.
- عدد العناصر المستخرجة.
- وقت آخر فحص.
- وقت آخر نجاح.
- نص الخطأ.
- رابط فتح المصدر مباشرة.

`يعمل بدون عناصر` لا يعني أن المصدر متعطل؛ يعني أن الاتصال نجح لكن المحلل لم يجد عناصر، وقد يحتاج رابط RSS أو بنية الصفحة إلى مراجعة.

## النشر

1. ارفع جميع الملفات مع الحفاظ على المسار `.github/workflows/monitor.yml`.
2. اختر `Settings → Pages → Source → GitHub Actions`.
3. شغّل `Actions → Competitor Intelligence Monitor → Run workflow`.
4. بعد نجاح `build` و`deploy` افتح موقع GitHub Pages.

## v5 — Priority offers and AI executive summary

This version adds two presentation improvements:

- The two explanatory hero notes (Calculation basis / Excel aligned) are removed.
- Each competitor page now places **Current Offers** directly below the competitor header, before KPIs and charts.
- The home page and each competitor page include a concise bilingual **AI Executive Summary** (one paragraph + three bullets).

### Enable automatic OpenAI summaries

The website itself is static GitHub Pages, so the OpenAI API key must **not** be placed in JavaScript or committed to the repository. The included GitHub Action runs `generate_ai_summary.py` securely and publishes only `ai_summary.json`.

1. Create an OpenAI API key in the OpenAI Platform.
2. In GitHub open the repository, then go to **Settings → Secrets and variables → Actions**.
3. Choose **New repository secret**.
4. Name it exactly `OPENAI_API_KEY` and paste the key as the value.
5. Go to **Actions → Competitor Intelligence Monitor → Run workflow** once.

The default AI model is `gpt-5.6-terra`. The model can be changed in `.github/workflows/monitor.yml`.

`generate_ai_summary.py` creates a material snapshot hash and skips the OpenAI call when relevant campaign/social data has not changed. This prevents an API call on every scheduled RSS check.


## V8 intelligence layer

This version keeps AI cost controlled by separating counting/scoring from interpretation:

- `build_intelligence_metrics.py` runs locally in GitHub Actions with no AI/API cost. It creates `intelligence.json` and maintains `market_history.json` (up to 180 daily snapshots).
- Competitive Activity Score is deterministic (0–100): campaign intensity 35%, priority-category breadth 25%, 7-day social activity 20%, and multi-channel coverage 20%. It is an activity indicator only — not market share or commercial performance.
- Expiry Watch, category intensity and historical trends are also deterministic and free.
- `generate_ai_summary.py` uses one GPT-5.6 Sol Responses API call with `xhigh` reasoning only when tracked campaigns/offers materially change (or after an AI schema/prompt upgrade). Routine RSS/social-post churn does not trigger a paid call.
- The single AI response contains the market summary, what changed, why it matters, management takeaway, opportunity gaps, category insights, a 7-day executive brief, plus analysis for every competitor.
- `OPENAI_API_KEY` is read only from GitHub Actions secrets.
- If the AI call fails, the last good AI output remains in place and the zero-cost metrics continue to update.

The Pages build publishes `data.json`, `ai_summary.json`, `intelligence.json`, and `market_history.json`. Existing `CNAME` is preserved automatically when present.
