/* Competitor Monitor v5.10.0 full review reconciliation and dated report download */
(() => {
  "use strict";
  const LANG_KEY="cm_v54_language", ALERT_KEY="cm_v5_alert_ack", OVERRIDE_KEY="cm_v5_manual_overrides", DELTA_KEY="cm_v5_last_delta_export", REFRESH_KEY="cm_v573_refresh";
  const COLORS=["#0f766e","#2563eb","#7c3aed","#d97706","#dc2626","#475569"];
  const COMPETITOR_COLORS={
    "stc-bank":"#4f008c",
    "barq":"#e59b00",
    "mobily-pay":"#008c95",
    "tiqmo":"#d94676",
    "urpay":"#2563eb",
    "alinma-pay":"#16a34a"
  };
  const I18N={
    ar:{
      appTitle:"لوحة ذكاء المنافسين",appSubtitle:"متابعة الحملات والعروض والنشاط التسويقي للمنافسين",overview:"النظرة العامة",marketAnalysis:"تحليل السوق",competitors:"المنافسون",inventory:"سجل المنافسين",campaigns:"الحملات والعروض",merchantOffers:"عروض الشركاء",posts:"المنشورات",review:"بحاجة إلى مراجعة",all:"الكل",
      activeCampaigns:"الحملات النشطة",activeCampaignsDetail:"الحملات الحالية — عروض الشركاء مستبعدة من مؤشرات الحملات",merchantPortfolio:"محفظة عروض الشركاء",merchantPortfolioDetail:"مرجع مستقل ولا يدخل في Campaign KPIs",remittanceCampaigns:"حملات التحويل الدولي",expiring30d:"تنتهي خلال 30 يومًا",socialPosts7d:"منشورات آخر 7 أيام",reviewRequired:"عناصر تحتاج مراجعة",
      alerts:"التنبيهات",alertsHint:"التغييرات منذ آخر مراجعة",markReviewed:"تحديد الكل كمراجع",noAlerts:"لا توجد تنبيهات جديدة",sourceHealth:"حالة المصادر",sourceHealthHint:"افتح التفاصيل لمعرفة المصدر المتعثر وآخر فحص ونجاح",healthy:"يعمل",failed:"متعثر",noItems:"يعمل بدون عناصر",lastCheck:"آخر فحص",lastSuccess:"آخر نجاح",extracted:"العناصر",openSource:"فتح المصدر",zeroItemsMeaning:"الاتصال نجح لكن لم يتم استخراج عناصر؛ راجع رابط RSS أو بنية الصفحة.",sourceVerification:"التحقق من المصدر",verified:"تم التحقق",sourceChanged:"المصدر تغيّر",couldNotVerify:"تعذر التحقق",evidence:"دليل المصدر",sourceConflict:"تعارض المصادر",verificationTiming:"وقت التحقق",networkChecks:"فحوصات الشبكة",
      campaignsByCompetitor:"الحملات الحالية حسب المنافس",categoryMix:"توزيع تصنيفات الحملات",remittanceComparison:"مقارنة التحويل الدولي",merchantComparison:"عروض الشركاء حسب المنافس",expiryRisk:"العروض القريبة من الانتهاء",mechanicsMix:"آليات العروض",channelActivity7d:"نشاط القنوات خلال 7 أيام",competitiveMatrix:"مصفوفة التغطية حسب الفئة",latestMedia:"أحدث محتوى اجتماعي",marketingSignals:"إشارات التسويق",
      exportEdits:"تصدير التعديلات",importEdits:"استيراد التعديلات",excelExport:"تحميل Excel",downloadFullReport:"تحميل التقرير الكامل",adminTools:"أدوات الإدارة",deltaExport:"تصدير التغييرات",addCampaign:"إضافة عرض",analyzeAfterUpload:"سيتم تحليل الرابط واستخراج التواريخ بعد رفع manual_overrides.json وتشغيل GitHub Action.",saveLocal:"حفظ",resetEdit:"إلغاء تعديلي",edit:"تعديل",editItem:"تعديل السجل",deleteCampaign:"حذف الحملة",deleteConfirm:"هل أنت متأكد من حذف هذه الحملة؟ سيتم تنزيل manual_overrides.json لتثبيت الحذف في GitHub.",deleteDownloaded:"تم حذف الحملة محليًا وتنزيل ملف التعديلات. ارفع manual_overrides.json إلى GitHub لتثبيت الحذف.",editsNote:"التعديل يظهر فورًا في متصفحك. لتثبيته للجميع صدّر manual_overrides.json وارفعه للمستودع.",
      noData:"لا توجد بيانات",search:"بحث",searchPlaceholder:"ابحث باسم العرض أو المحتوى",category:"التصنيف",source:"المصدر",status:"الحالة",clear:"مسح",results:"نتيجة",loading:"جاري تحميل البيانات…",loadError:"تعذر تحميل البيانات",retry:"إعادة المحاولة",back:"رجوع",officialWebsite:"الموقع الرسمي",officialOffers:"العروض الرسمية",openAnalysis:"فتح التفاصيل",openOfficial:"فتح المصدر الرسمي",openPost:"فتح المنشور",inventorySource:"Excel Master",website:"الموقع",instagram:"Instagram",facebook:"Facebook",x:"X",tiktok:"TikTok",
      contentType:"نوع السجل",title:"الاسم",summary:"الملخص",active:"نشط",currentStatus:"الحالة الحالية",officialCampaignUrl:"رابط العرض الرسمي التفصيلي",primarySourceUrl:"المصدر الرسمي الأساسي",instagramUrl:"رابط Instagram",xUrl:"رابط X",facebookUrl:"رابط Facebook",tiktokUrl:"رابط TikTok",published:"تاريخ النشر",startDate:"تاريخ البداية",endDate:"تاريخ النهاية",operationType:"نوع العملية",mechanic:"آلية العرض",eligibility:"الأهلية / المنتج",terms:"الشروط والتوقيت",lastReviewed:"آخر مراجعة",recordId:"Record ID",socialLinks:"روابط السوشيال",sourcesAndLinks:"المصادر والروابط الرسمية",verifiedOfficialWebsite:"تم التحقق — الموقع الرسمي",verifiedOfficialSocial:"تم التحقق — منشور اجتماعي رسمي",needsReview:"بحاجة إلى مراجعة",
      campaign:"حملة أو عرض",merchant_offer:"عرض شريك",social_post:"منشور اجتماعي",awareness:"محتوى توعوي",review_type:"بحاجة إلى مراجعة",remittance:"التحويل الدولي",
      dataBasis:"أساس الحساب",dataBasisText:"المؤشرات تحسب جميع الحملات النشطة الحالية، وليس فقط ما اكتُشف منذ آخر زيارة.",excelAligned:"متوافق مع Excel",excelAlignedText:"التصنيفات والحقول تتبع ملف Excel المعتمد.",
      newCampaign:"حملة جديدة",updatedCampaign:"حملة تم تحديثها",newMerchant:"عرض شريك جديد",newPost:"منشور جديد",reviewAlert:"عنصر يحتاج تصنيفًا",
      offerIntelligence:"بيانات العرض",corridors:"الدول / الممرات",offerValues:"قيمة العرض",socialAnalysis:"تحليل السوشيال",totalPosts:"إجمالي المنشورات",platformsUsed:"المنصات المستخدمة",posts7d:"منشورات 7 أيام",posts30d:"منشورات 30 يومًا",firstPost:"أول منشور",latestPost:"آخر منشور",linkedPosts:"المنشورات المرتبطة",campaignTimeline:"سجل تغييرات العرض",classification:"التصنيف",media:"الوسائط",linkedCampaign:"العرض المرتبط",
      linkToCampaign:"ربط بعرض",createCampaignFromPost:"إنشاء عرض من المنشور",noCampaign:"بدون ربط",bulkReview:"مراجعة جماعية",linkSelected:"ربط المحدد",selectItems:"حدد عناصر أولًا",
      featuredCampaigns:"الحملات الحالية",viewAllCampaigns:"عرض جميع الحملات",noCurrentCampaigns:"لا توجد حملات حالية",aiSummary:"الملخص الإداري",whatChanged:"ما الذي تغير؟",whyMatters:"لماذا يهم؟",managementTakeaway:"الخلاصة للإدارة",categorySnapshot:"ملخص التصنيفات",noMedia:"لا توجد وسائط متاحة",checkNow:"تحديث الآن",checkAllNow:"تحديث جميع المنافسين",refreshRunning:"جاري طلب التحديث…",refreshQueued:"تم إرسال الفحص",refreshWaiting:"جاري فحص المصادر…",refreshComplete:"اكتمل التحديث",refreshFailed:"فشل التحديث",refreshBusy:"يوجد فحص آخر قيد التنفيذ",refreshTimedOut:"استغرق الفحص وقتًا أطول من المتوقع؛ راجع GitHub Actions",newOffersCount:"عروض جديدة",updatedOffersCount:"عروض محدثة",unchangedOffersCount:"عروض بدون تغيير",newPostsCount:"منشورات جديدة",failedSourcesCount:"مصادر متعثرة",zeroSourcesCount:"مصادر لم ترجع عناصر",refreshHistory:"سجل التحديثات",noRefreshHistory:"لا توجد تحديثات مسجلة",retryFailed:"إعادة فحص المنافس",lastNewOffer:"آخر عرض جديد",loadMore:"تحميل المزيد",reviewReason:"سبب المراجعة",signOut:"تسجيل الخروج",language:"English"
    },
    en:{
      appTitle:"Competitor Intelligence Dashboard",appSubtitle:"Competitor campaign, offer and marketing activity monitoring",overview:"Overview",marketAnalysis:"Market analysis",competitors:"Competitors",inventory:"Inventory",campaigns:"Campaigns & offers",merchantOffers:"Merchant offers",posts:"Posts",review:"Needs review",all:"All",
      activeCampaigns:"Active campaigns",activeCampaignsDetail:"Current campaigns — merchant offers excluded from campaign KPIs",merchantPortfolio:"Merchant offers portfolio",merchantPortfolioDetail:"Separate reference portfolio, excluded from Campaign KPIs",remittanceCampaigns:"Remittance campaigns",expiring30d:"Expiring within 30 days",socialPosts7d:"Social posts in 7 days",reviewRequired:"Items needing review",
      alerts:"Alerts",alertsHint:"Changes since last review",markReviewed:"Mark all reviewed",noAlerts:"No new alerts",sourceHealth:"Source health",sourceHealthHint:"Open details to see failed sources, last check and last success",healthy:"Working",failed:"Failed",noItems:"Working, no items",lastCheck:"Last check",lastSuccess:"Last success",extracted:"Items",openSource:"Open source",zeroItemsMeaning:"Connection succeeded but no items were extracted; review the RSS URL or page structure.",sourceVerification:"Source verification",verified:"Verified",sourceChanged:"Source changed",couldNotVerify:"Could not verify",evidence:"Source evidence",sourceConflict:"Source conflict",verificationTiming:"Verification time",networkChecks:"network checks",
      campaignsByCompetitor:"Current campaigns by competitor",categoryMix:"Campaign category mix",remittanceComparison:"Remittance comparison",merchantComparison:"Merchant offers by competitor",expiryRisk:"Campaign expiry watch",mechanicsMix:"Offer mechanics",channelActivity7d:"Channel activity over 7 days",competitiveMatrix:"Category coverage matrix",latestMedia:"Latest social content",marketingSignals:"Marketing signals",
      exportEdits:"Export edits",importEdits:"Import edits",excelExport:"Download Excel",downloadFullReport:"Download Full Report",adminTools:"Admin Tools",deltaExport:"Export changes",addCampaign:"Add campaign",analyzeAfterUpload:"The URL will be analyzed and dates extracted after you upload manual_overrides.json and run GitHub Actions.",saveLocal:"Save",resetEdit:"Reset my edit",edit:"Edit",editItem:"Edit record",deleteCampaign:"Delete campaign",deleteConfirm:"Delete this campaign? manual_overrides.json will be downloaded so the deletion can be made permanent in GitHub.",deleteDownloaded:"Campaign deleted locally and the overrides file was downloaded. Upload manual_overrides.json to GitHub to make the deletion permanent.",editsNote:"The edit appears immediately in this browser. Export manual_overrides.json and upload it to the repository to make it persistent.",
      noData:"No data",search:"Search",searchPlaceholder:"Search campaign or content",category:"Category",source:"Source",status:"Status",clear:"Clear",results:"results",loading:"Loading data…",loadError:"Could not load data",retry:"Retry",back:"Back",officialWebsite:"Official website",officialOffers:"Official offers",openAnalysis:"Open details",openOfficial:"Open official source",openPost:"Open post",inventorySource:"Excel Master",website:"Website",instagram:"Instagram",facebook:"Facebook",x:"X",tiktok:"TikTok",
      contentType:"Record type",title:"Title",summary:"Summary",active:"Active",currentStatus:"Current status",officialCampaignUrl:"Specific official campaign URL",primarySourceUrl:"Primary official source",instagramUrl:"Instagram URL",xUrl:"X URL",facebookUrl:"Facebook URL",tiktokUrl:"TikTok URL",published:"Published date",startDate:"Start date",endDate:"End date",operationType:"Operation type",mechanic:"Mechanic / offer",eligibility:"Eligibility / product",terms:"Terms / timing",lastReviewed:"Last reviewed",recordId:"Record ID",socialLinks:"Social links",sourcesAndLinks:"Official & Social Sources",verifiedOfficialWebsite:"Verified — Official Website",verifiedOfficialSocial:"Verified — Official Social Post",needsReview:"Needs Review",
      campaign:"Campaign / offer",merchant_offer:"Merchant offer",social_post:"Social post",awareness:"Awareness",review_type:"Needs review",remittance:"Remittance",
      dataBasis:"Calculation basis",dataBasisText:"KPIs use the full current active campaign inventory, not only items detected since the previous visit.",excelAligned:"Excel aligned",excelAlignedText:"Categories and fields follow the approved Excel master.",
      newCampaign:"New campaign",updatedCampaign:"Campaign updated",newMerchant:"New merchant offer",newPost:"New post",reviewAlert:"Item needs classification",
      offerIntelligence:"Offer intelligence",corridors:"Corridors",offerValues:"Offer value",socialAnalysis:"Social analysis",totalPosts:"Total posts",platformsUsed:"Platforms used",posts7d:"Posts in 7 days",posts30d:"Posts in 30 days",firstPost:"First post",latestPost:"Latest post",linkedPosts:"Linked posts",campaignTimeline:"Campaign change history",classification:"Classification",media:"Media",linkedCampaign:"Linked campaign",
      linkToCampaign:"Link to campaign",createCampaignFromPost:"Create campaign from post",noCampaign:"No link",bulkReview:"Bulk review",linkSelected:"Link selected",selectItems:"Select items first",
      featuredCampaigns:"Current campaigns",viewAllCampaigns:"View all campaigns",noCurrentCampaigns:"No current campaigns",aiSummary:"Management summary",whatChanged:"What changed?",whyMatters:"Why it matters",managementTakeaway:"Management takeaway",categorySnapshot:"Category snapshot",noMedia:"No media available",checkNow:"Check now",checkAllNow:"Check all competitors",refreshRunning:"Requesting refresh…",refreshQueued:"Check queued",refreshWaiting:"Checking sources…",refreshComplete:"Refresh completed",refreshFailed:"Refresh failed",refreshBusy:"Another refresh is already running",refreshTimedOut:"The refresh took longer than expected; review GitHub Actions",newOffersCount:"New offers",updatedOffersCount:"Updated offers",unchangedOffersCount:"Unchanged offers",newPostsCount:"New posts",failedSourcesCount:"Failed sources",zeroSourcesCount:"Sources with no items",refreshHistory:"Refresh history",noRefreshHistory:"No refreshes recorded",retryFailed:"Retry competitor",lastNewOffer:"Latest new offer",loadMore:"Load more",reviewReason:"Review reason",signOut:"Sign out",language:"العربية"
    }
  };
  Object.assign(I18N.ar,{
    marketAnalytics:"تحليلات السوق",
    executiveView:"النظرة التنفيذية",
    keyMarketDevelopments:"أبرز تطورات السوق",
    managementAttention:"نقاط تتطلب انتباه الإدارة",
    recommendedActions:"الإجراءات المقترحة",
    portfolioInsight:"قراءة محفظة الحملات",
    campaignsByCompetitorNote:"ترتيب تنازلي للحملات النشطة الحالية. اضغط على المنافس لعرض سجلاته.",
    campaignChanges30d:"تغيّرات الحملات خلال 30 يومًا",
    campaignChangesNote:"أحداث سوقية موثقة خلال آخر 30 يومًا؛ لا تشمل المراجعات البشرية أو استكمال البيانات الناقصة.",
    campaignMixByCompetitor:"مزيج الحملات حسب المنافس",
    campaignMixNote:"توزيع نسبي للحملات النشطة على التصنيفات الرئيسية.",
    coverageMatrixNote:"شدة اللون تعكس عدد الحملات. اضغط على الخلية لتصفية السجل.",
    offersAndRisk:"العروض ومخاطر الانتهاء",
    remittanceComparisonNote:"عدد حملات التحويل الدولي النشطة لكل منافس.",
    merchantComparisonNote:"عروض الشركاء منفصلة عن مؤشرات الحملات.",
    mechanicsMixNote:"أكثر آليات العروض استخدامًا في الحملات النشطة.",
    expiryRiskNote:"الحملات القريبة من الانتهاء، بدون تاريخ نهاية، والمنتهية حديثًا.",
    socialMediaActivity:"نشاط السوشيال ميديا",
    socialActivityNote:"مقارنة الفترة الحالية بالفترة السابقة المماثلة حسب المنافس والمنصة.",
    last7Days:"آخر 7 أيام",
    last30Days:"آخر 30 يومًا",
    currentPeriod:"الفترة الحالية",
    previousPeriod:"الفترة السابقة",
    allPlatforms:"جميع المنصات",
    platform:"المنصة",
    newStatus:"جديد / أول نشر",
    updatedStatus:"محدّث",
    expiredStatus:"منتهي",
    expiring7:"≤7 أيام",
    expiring30:"8–30 يومًا",
    noEndDate:"بدون تاريخ نهاية",
    chartTotal:"الإجمالي",
    chartPeriod:"الفترة",
    comparisonUp:"ارتفاع",
    comparisonDown:"انخفاض",
    comparisonFlat:"بدون تغيير"
  });
  Object.assign(I18N.en,{
    marketAnalytics:"Market analytics",
    executiveView:"Executive view",
    keyMarketDevelopments:"Key market developments",
    managementAttention:"Management attention",
    recommendedActions:"Recommended actions",
    portfolioInsight:"Portfolio insight",
    campaignsByCompetitorNote:"Active campaigns sorted from highest to lowest. Select a competitor to filter the inventory.",
    campaignChanges30d:"Campaign changes over 30 days",
    campaignChangesNote:"Verified market events during the last 30 days; Admin reviews and data backfills are excluded.",
    campaignMixByCompetitor:"Campaign mix by competitor",
    campaignMixNote:"Relative distribution of active campaigns across the main categories.",
    coverageMatrixNote:"Darker cells indicate more campaigns. Select a cell to filter the inventory.",
    offersAndRisk:"Offers and expiry risk",
    remittanceComparisonNote:"Active remittance campaigns by competitor.",
    merchantComparisonNote:"Merchant offers remain separate from campaign KPIs.",
    mechanicsMixNote:"Most-used offer mechanics across active campaigns.",
    expiryRiskNote:"Campaigns nearing expiry, missing an end date, or recently expired.",
    socialMediaActivity:"Social media activity",
    socialActivityNote:"Current period versus the equivalent previous period by competitor and platform.",
    last7Days:"Last 7 days",
    last30Days:"Last 30 days",
    currentPeriod:"Current period",
    previousPeriod:"Previous period",
    allPlatforms:"All platforms",
    platform:"Platform",
    newStatus:"New / first published",
    updatedStatus:"Updated",
    expiredStatus:"Expired",
    expiring7:"≤7 days",
    expiring30:"8–30 days",
    noEndDate:"No end date",
    chartTotal:"Total",
    chartPeriod:"Period",
    comparisonUp:"Increase",
    comparisonDown:"Decrease",
    comparisonFlat:"No change"
  });
  Object.assign(I18N.ar,{
    reviewCenter:"مركز مراجعة الحملات وعروض الشركاء",reviewCenterHint:"راجع الحملات وعروض الشركاء المحتملة. يمكن اعتماد كل عرض شريك محدد كسجل مستقل، أو تجميع عدة أدلة في حملة واحدة.",
    selectedCount:"العناصر المحددة",groupAsCampaign:"تجميع المحدد كحملة واحدة",confirmSeparateMerchants:"اعتماد المحدد كعروض شريك منفصلة",linkExisting:"ربط بحملة موجودة",markNotCampaign:"ليست حملة",markAwareness:"محتوى توعوي",confirmCampaign:"اعتماد كحملة",confirmMerchant:"اعتماد كعرض شريك",clearSelection:"إلغاء التحديد",
    suggestedType:"التصنيف المقترح",reviewReasons:"أسباب المراجعة",officialEvidence:"الدليل الرسمي",selectAllVisible:"تحديد النتائج الظاهرة",sameCompetitorRequired:"لا يمكن تجميع عناصر منافسين مختلفين. اختر عناصر لمنافس واحد.",
    createOneCampaign:"إنشاء سجل حملة واحد",recordType:"نوع السجل",campaignTitle:"اسم الحملة",campaignSummary:"ملخص الحملة",officialSourceRequired:"رابط رسمي تفصيلي",saveDecision:"حفظ القرار",cancel:"إلغاء",chooseCampaign:"اختر الحملة",accessDenied:"هذه الصفحة متاحة للأدمن فقط.",
    reviewSaving:"جاري إرسال القرار…",reviewQueued:"تم إرسال القرار، جاري الحفظ…",reviewSaved:"تم حفظ القرار وتحديث الموقع.",reviewSaveFailed:"تعذر حفظ قرار المراجعة",reviewBusy:"يوجد قرار مراجعة آخر قيد الحفظ",noReviewItems:"لا توجد عناصر تحتاج مراجعة حاليًا.",allReasons:"كل الأسباب",allSources:"كل المصادر",openReviewCenter:"فتح مركز المراجعة",
    merchantCandidates:"عروض شريك محتملة",suggestedCampaign:"حملات محتملة",suggestedUnclassified:"بدون تصنيف مقترح",merchantBulkWebsiteOnly:"الاعتماد الجماعي المنفصل متاح فقط للعناصر المصنفة كعروض شريك محتملة والمكتشفة من صفحات رسمية. استخدم ربط بحملة للمنشورات الاجتماعية.",bulkMerchantConfirm:"سيتم اعتماد {count} عنصر كعروض شريك مستقلة، ولن يتم دمجها في عرض واحد. هل تريد المتابعة؟",
    fullReviewScan:"تشغيل فحص شامل للمراجعة",fullReviewScanConfirm:"سيتم تحديث جميع المنافسين ومقارنة كل عناصر Needs Review بالحملات وعروض الشركاء الموجودة. قد يستغرق ذلك عدة دقائق. هل تريد المتابعة؟",lastFullReviewScan:"آخر فحص شامل",reviewCleaned:"تم تنظيف",autoLinked:"تم الربط تلقائيًا",duplicatesRemoved:"تكرارات أزيلت"
  });
  Object.assign(I18N.en,{
    reviewCenter:"Campaign & Merchant Review Center",reviewCenterHint:"Review potential campaigns and merchant offers. Approve each selected merchant offer as a separate record, or group several evidence items into one campaign.",
    selectedCount:"Selected items",groupAsCampaign:"Group selected as one campaign",confirmSeparateMerchants:"Confirm selected as separate merchant offers",linkExisting:"Link to existing campaign",markNotCampaign:"Not a campaign",markAwareness:"Awareness",confirmCampaign:"Confirm campaign",confirmMerchant:"Confirm merchant offer",clearSelection:"Clear selection",
    suggestedType:"Suggested type",reviewReasons:"Review reasons",officialEvidence:"Official evidence",selectAllVisible:"Select visible results",sameCompetitorRequired:"Items from different competitors cannot be grouped. Select one competitor only.",
    createOneCampaign:"Create one campaign record",recordType:"Record type",campaignTitle:"Campaign title",campaignSummary:"Campaign summary",officialSourceRequired:"Specific official source URL",saveDecision:"Save decision",cancel:"Cancel",chooseCampaign:"Choose campaign",accessDenied:"This page is available to Admin users only.",
    reviewSaving:"Sending decision…",reviewQueued:"Decision queued; saving…",reviewSaved:"Decision saved and site updated.",reviewSaveFailed:"Could not save review decision",reviewBusy:"Another review decision is being saved",noReviewItems:"No items currently need review.",allReasons:"All reasons",allSources:"All sources",openReviewCenter:"Open review center",
    merchantCandidates:"Potential merchant offers",suggestedCampaign:"Potential campaigns",suggestedUnclassified:"No suggested type",merchantBulkWebsiteOnly:"Separate bulk approval is only available for items classified as potential Merchant Offers and discovered from official offer pages. Use Link to existing campaign for social posts.",bulkMerchantConfirm:"Confirm {count} items as separate Merchant Offer records? They will not be merged into one offer.",
    fullReviewScan:"Run full review scan",fullReviewScanConfirm:"This will refresh all competitors and compare every Needs Review item with existing campaigns and merchant offers. It may take several minutes. Continue?",lastFullReviewScan:"Last full review scan",reviewCleaned:"Cleaned",autoLinked:"Auto-linked",duplicatesRemoved:"Duplicates removed"
  });
  let AUTH={authenticated:false,role:"viewer",user:""};
  async function loadAuth(){try{const r=await fetch("/__session",{cache:"no-store",credentials:"same-origin"});if(r.ok){const v=await r.json();AUTH={authenticated:!!v.authenticated,role:v.role||"viewer",user:v.username||v.user||""};}}catch{}return AUTH;}
  const auth=()=>({...AUTH});
  const isAdmin=()=>AUTH.role==="admin";
  const language=()=>localStorage.getItem(LANG_KEY)||"en"; const t=k=>I18N[language()]?.[k]??I18N.en[k]??k;
  function setLanguage(v){localStorage.setItem(LANG_KEY,v);applyLanguage();window.dispatchEvent(new CustomEvent("cm:language"));}
  function applyLanguage(){const l=language();document.documentElement.lang=l;document.documentElement.dir=l==="ar"?"rtl":"ltr";document.querySelectorAll("[data-i18n]").forEach(n=>n.textContent=t(n.dataset.i18n));document.querySelectorAll("[data-i18n-placeholder]").forEach(n=>n.placeholder=t(n.dataset.i18nPlaceholder));document.querySelectorAll("[data-language-toggle]").forEach(n=>{n.textContent=t("language");n.onclick=()=>setLanguage(l==="ar"?"en":"ar");});}
  const initLanguage=applyLanguage;
  function el(tag,attrs={},...children){const n=document.createElement(tag);Object.entries(attrs||{}).forEach(([k,v])=>{if(v===null||v===undefined||v===false)return;if(k==="class")n.className=v;else if(k.startsWith("on")&&typeof v==="function")n.addEventListener(k.slice(2).toLowerCase(),v);else if(k==="checked")n.checked=!!v;else if(k==="selected")n.selected=!!v;else n.setAttribute(k,String(v));});children.flat(Infinity).filter(v=>v!==null&&v!==undefined&&v!==false).forEach(c=>n.append(c instanceof Node?c:document.createTextNode(String(c))));return n;}
  function clear(n){while(n?.firstChild)n.removeChild(n.firstChild);} const byId=rows=>Object.fromEntries((rows||[]).map(r=>[r.id,r])); const competitorName=r=>r?.name_en||"—"; const taxonomyName=r=>language()==="ar"?r?.name_ar:r?.name_en;
  function formatDate(v,time=false){if(!v)return"—";const d=new Date(v);if(Number.isNaN(d.getTime()))return String(v);return new Intl.DateTimeFormat(language()==="ar"?"ar-SA":"en-GB",time?{dateStyle:"medium",timeStyle:"short"}:{dateStyle:"medium"}).format(d);}
  const dateInput=v=>{if(!v)return"";const d=new Date(v);return Number.isNaN(d.getTime())?"":d.toISOString().slice(0,10);}; const toIsoDate=v=>v?`${v}T00:00:00+00:00`:null;
  function timeAgo(v){if(!v)return"—";const ms=Date.now()-new Date(v).getTime();if(ms<60000)return"now";if(ms<3600000)return`${Math.floor(ms/60000)}m`;if(ms<86400000)return`${Math.floor(ms/3600000)}h`;return`${Math.floor(ms/86400000)}d`;}
  const withinDays=(i,d)=>{const x=new Date(i.published_at||i.last_changed||0);return!Number.isNaN(x.getTime())&&x>=new Date(Date.now()-d*86400000);};
  function countBy(items,getter){const m=new Map();items.forEach(i=>{const raw=getter(i);(Array.isArray(raw)?raw:[raw]).filter(Boolean).forEach(k=>m.set(k,(m.get(k)||0)+1));});return m;}
  const blankOverrides=()=>({schema_version:3,items:{},new_items:[],review_history:[]});
  function getOverrides(){try{const v=JSON.parse(localStorage.getItem(OVERRIDE_KEY)||"null")||blankOverrides();v.items||={};v.new_items||=[];v.review_history||=[];return v;}catch{return blankOverrides();}}
  const setOverrides=v=>localStorage.setItem(OVERRIDE_KEY,JSON.stringify(v));
  function dateOnly(v){const m=String(v||"").match(/^(\d{4})-(\d{2})-(\d{2})/);return m?`${m[1]}-${m[2]}-${m[3]}`:"";}
  function todayDateOnly(){const d=new Date(),y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,"0"),day=String(d.getDate()).padStart(2,"0");return `${y}-${m}-${day}`;}
  function setupReportDownloads(){const stamp=todayDateOnly(),nonce=Date.now();document.querySelectorAll("[data-report-download]").forEach(link=>{const url=new URL("competitor_campaigns_latest.xlsx",location.href);url.searchParams.set("download",String(nonce));link.href=url.href;link.download=`Competitor-Analysis-${stamp}.xlsx`;});}
  function dayDiff(a,b){const ad=new Date(`${a}T00:00:00Z`),bd=new Date(`${b}T00:00:00Z`);return Math.round((ad-bd)/86400000);}
  function lifecycleFor(item){const today=todayDateOnly(),start=dateOnly(item?.start_date),end=dateOnly(item?.end_date);if(start&&start>today)return{status:"Upcoming",active:true};if(end){const days=dayDiff(end,today);if(days<0)return{status:"Expired",active:false};if(days<=7)return{status:"Expiring ≤7 Days",active:true};if(days<=30)return{status:"Expiring 8–30 Days",active:true};return{status:"Active",active:true};}return{status:"End Date Not Stated",active:true};}
  function staleNoEndNote(v){const x=String(v||"").trim().toLowerCase();return !!x&&(x.includes("end date is not stated")||x.includes("end date not stated")||x.includes("no end date")||x.includes("تاريخ الانتهاء غير")||x.includes("تاريخ انتهاء غير")||x.includes("لم يتم ذكر تاريخ الانتهاء")||x.includes("لم يذكر تاريخ الانتهاء"));}
  function normalizeLifecycle(item){const r={...item};if(["campaign","merchant_offer"].includes(r.content_type)){const life=lifecycleFor(r);r.current_status=life.status;r.active=life.active;if(r.end_date&&staleNoEndNote(r.terms_note))r.terms_note="";}return r;}
  function applyOverride(i,p){const r={...i,...(p||{}),...(p?{manual_override:true}:{})};if(p?.campaign_category){r.primary_category=p.campaign_category;r.categories=[p.campaign_category];}r.social_links=Object.fromEntries(Object.entries(r.social_links||{}).filter(([,u])=>u));return normalizeLifecycle(r);}
  function applyOverrides(data){const o=getOverrides();const items=(data.items||[]).map(i=>applyOverride(i,o.items[i.id])).filter(i=>!i.deleted);const ids=new Set(items.map(i=>i.id));(o.new_items||[]).forEach(i=>{if(o.items?.[i.id]?.deleted)return;if(!ids.has(i.id))items.push({...i,source_type:"manual",platform:"website",manual_override:true,review_required:true,current_status:i.current_status||"Needs Review",social_links:i.social_links||{},active:i.active!==false});});return{...data,items};}
  function publicTitleKey(v){return String(v||"").normalize("NFKC").toLowerCase().replace(/[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]/gu,"").replace(/ـ/gu,"").replace(/[®™©]/gu," ").replace(/[^\p{L}\p{N}%]+/gu," ").split(/\s+/).filter(Boolean).filter(x=>!["offer","offers","campaign","campaigns","promotion","promotions","promo","deal","deals","عرض","عروض","حملة","حملات"].includes(x)).join(" ");}
  function publicUrlKey(v){if(!v)return"";try{const u=new URL(v,location.href);const host=u.hostname.toLowerCase().replace(/^www\./,"");let path=u.pathname.replace(/\/{2,}/g,"/").replace(/\/$/,"").toLowerCase()||"/";path=path.replace(/^\/(ar|en)(?=\/)/,"");const q=[...u.searchParams.entries()].filter(([k])=>!k.toLowerCase().startsWith("utm_")).sort().map(([k,val])=>`${k.toLowerCase()}=${val}`).join("&");return`${host}${path}${q?`?${q}`:""}`;}catch{return String(v).toLowerCase().replace(/\/$/,"");}}
  function publicCampaignRank(i){if(i.source_type==="inventory"&&i.manual_override)return 70;if(i.source_type==="inventory")return 60;if(i.source_type==="manual")return 50;if(i.manual_override)return 45;if(i.verified&&i.official_campaign_page_url)return 30;if(i.source_type==="website")return 20;return 10;}
  function dedupePublicItems(data){const campaigns=(data.items||[]).filter(i=>i.content_type==="campaign").sort((a,b)=>publicCampaignRank(b)-publicCampaignRank(a)),others=(data.items||[]).filter(i=>i.content_type!=="campaign"),kept=[],byTitle=new Map(),byUrl=new Map();for(const item of campaigns){const comp=item.competitor_id||"",tk=publicTitleKey(item.title),urls=[item.official_campaign_page_url,item.primary_official_source_url,item.link].map(publicUrlKey).filter(Boolean);let keep=urls.map(u=>byUrl.get(`${comp}|${u}`)).find(Boolean)||(tk?byTitle.get(`${comp}|${tk}`):null);if(!keep){kept.push(item);if(tk)byTitle.set(`${comp}|${tk}`,item);urls.forEach(u=>byUrl.set(`${comp}|${u}`,item));continue;}keep.social_links={...(keep.social_links||{}),...(item.social_links||{})};keep.social_link_count=Object.keys(keep.social_links).length;if(item.official_campaign_page_url){keep.official_campaign_page_url=item.official_campaign_page_url;keep.primary_official_source_url=item.official_campaign_page_url;keep.link=item.official_campaign_page_url;}for(const f of ["summary","snippet","start_date","end_date","published_at","mechanic","eligibility","terms_note"]){if(!keep[f]&&item[f])keep[f]=item[f];}if(tk)byTitle.set(`${comp}|${tk}`,keep);urls.forEach(u=>byUrl.set(`${comp}|${u}`,keep));}data.items=[...kept,...others];if(data.stats){const cs=kept.filter(i=>i.active!==false);data.stats.active_campaigns=cs.length;data.stats.remittance_campaigns=cs.filter(i=>i.campaign_category==="remittance").length;}return data;}
  async function loadData(){const r=await fetch(`data.json?_=${Date.now()}`,{cache:"no-store"});if(!r.ok)throw new Error(`HTTP ${r.status}`);return dedupePublicItems(applyOverrides(await r.json()));}
  const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  function refreshLock(){try{return JSON.parse(localStorage.getItem(REFRESH_KEY)||"null");}catch{return null;}}
  function saveRefreshLock(value){try{value?localStorage.setItem(REFRESH_KEY,JSON.stringify(value)):localStorage.removeItem(REFRESH_KEY);}catch{}}
  function setRefreshControls(disabled,label=""){document.querySelectorAll("[data-refresh-control],#refresh-all,#refresh-competitor").forEach(button=>{if(!button.dataset.refreshLabel)button.dataset.refreshLabel=button.textContent||"";button.disabled=disabled;if(label)button.textContent=label;else button.textContent=button.dataset.refreshLabel;});}
  function refreshSummaryText(summary,scan=null){const lines=[
    t("refreshComplete"),
    `${t("newOffersCount")}: ${Number(summary?.new_offers||0)}`,
    `${t("updatedOffersCount")}: ${Number(summary?.updated_offers||0)}`,
    `${t("unchangedOffersCount")}: ${Number(summary?.unchanged_offers||0)}`,
    `${t("newPostsCount")}: ${Number(summary?.new_posts||0)}`,
    `${t("needsReview")}: ${Number(summary?.needs_review||0)}`,
    `${t("failedSourcesCount")}: ${Number(summary?.failed_sources||0)}`,
    `${t("zeroSourcesCount")}: ${Number(summary?.zero_item_sources||0)}`,
  ];if(scan)lines.push(`${t("reviewCleaned")}: ${Number(scan.cleaned||0)}`,`${t("autoLinked")}: ${Number(scan.linked_social||0)}`,`${t("duplicatesRemoved")}: ${Number(scan.counted_duplicates_removed||0)+Number(scan.review_duplicates_removed||0)}`);return lines.join("\n");}
  async function refreshStatus(requestId){const r=await fetch(`/__refresh-status?request_id=${encodeURIComponent(requestId)}`,{cache:"no-store",credentials:"same-origin"});let payload={};try{payload=await r.json();}catch{}if(!r.ok&&r.status!==202)throw new Error(payload.message||payload.error||`HTTP ${r.status}`);return payload;}
  async function completedRefreshData(requestId){for(let attempt=0;attempt<24;attempt+=1){try{const data=await loadData();if(data.refresh_summary?.request_id===requestId)return data;}catch{}await sleep(5000);}return null;}
  async function waitForRefresh(lock,button=null){if(!lock?.requestId)return false;setRefreshControls(true,t("refreshWaiting"));if(button)button.textContent=t("refreshWaiting");const started=Number(lock.startedAt||Date.now());try{while(Date.now()-started<30*60*1000){const status=await refreshStatus(lock.requestId);if(status.status==="completed"){if(status.conclusion!=="success")throw new Error(status.conclusion||t("refreshFailed"));const data=await completedRefreshData(lock.requestId);saveRefreshLock(null);alert(data?refreshSummaryText(data.refresh_summary,data.full_review_scan):t("refreshComplete"));location.reload();return true;}await sleep(8000);}throw new Error(t("refreshTimedOut"));}catch(error){saveRefreshLock(null);setRefreshControls(false);if(button)button.title=String(error?.message||error);alert(`${t("refreshFailed")}: ${error?.message||error}`);return false;}}
  async function resumeRefresh(){if(!isAdmin())return false;const lock=refreshLock();if(!lock)return false;if(Date.now()-Number(lock.startedAt||0)>35*60*1000){saveRefreshLock(null);return false;}return waitForRefresh(lock);}
  async function triggerRefresh(competitor="all",button=null){if(!isAdmin())return false;const existing=refreshLock();if(existing&&Date.now()-Number(existing.startedAt||0)<35*60*1000)return waitForRefresh(existing,button);setRefreshControls(true,t("refreshRunning"));try{const r=await fetch("/__refresh",{method:"POST",credentials:"same-origin",cache:"no-store",headers:{"Content-Type":"application/json","X-Requested-With":"competitor-monitor"},body:JSON.stringify({competitor})});let payload={};try{payload=await r.json();}catch{}if(!r.ok){if(r.status===409)throw new Error(t("refreshBusy"));throw new Error(payload.message||payload.error||`HTTP ${r.status}`);}if(!payload.request_id)throw new Error("Refresh request ID missing");const lock={requestId:payload.request_id,competitor,startedAt:Date.now()};saveRefreshLock(lock);if(button)button.textContent=t("refreshQueued");return waitForRefresh(lock,button);}catch(error){saveRefreshLock(null);setRefreshControls(false);if(button)button.title=String(error?.message||error);alert(`${t("refreshFailed")}: ${error?.message||error}`);return false;}}
  function saveItemOverride(id,patch){if(!isAdmin())return;const v=getOverrides();v.updated_at=new Date().toISOString();v.items[id]={...(v.items[id]||{}),...patch};setOverrides(v);}
  function resetItemOverride(id){if(!isAdmin())return;const v=getOverrides();delete v.items[id];v.updated_at=new Date().toISOString();setOverrides(v);}
  function addNewItem(row){if(!isAdmin())return;const v=getOverrides();v.updated_at=new Date().toISOString();v.new_items.push(row);setOverrides(v);}
  function downloadBlob(name,text,type){const blob=new Blob([text],{type});const a=el("a",{href:URL.createObjectURL(blob),download:name});document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove();},500);}
  function exportOverrides(){if(!isAdmin())return;const v=getOverrides();v.updated_at=new Date().toISOString();downloadBlob("manual_overrides.json",JSON.stringify(v,null,2),"application/json");}
  function deleteCampaign(item,options={}){if(!isAdmin()||!item||item.content_type!=="campaign")return false;if(!confirm(t("deleteConfirm")))return false;saveItemOverride(item.id,{deleted:true,active:false,current_status:"Deleted",deleted_at:new Date().toISOString(),deleted_title:item.title||"",deleted_competitor_id:item.competitor_id||"",deleted_url:item.official_campaign_page_url||item.primary_official_source_url||item.link||""});exportOverrides();if(options.redirect){location.href=options.redirect;}else{location.reload();}return true;}
  function importOverrides(file){if(!isAdmin())return;const reader=new FileReader();reader.onload=()=>{try{const v=JSON.parse(reader.result);setOverrides({...blankOverrides(),...v,items:v.items||{},new_items:v.new_items||[],review_history:v.review_history||[]});location.reload();}catch(e){alert(String(e));}};reader.readAsText(file);}
  const activeCampaigns=items=>items.filter(i=>i.active!==false&&i.content_type==="campaign"); const activeMerchants=items=>items.filter(i=>i.active!==false&&i.content_type==="merchant_offer"); const socialPosts=(items,days=null)=>items.filter(i=>i.active!==false&&i.source_type==="social"&&(!days||withinDays(i,days)));
  function alerts(items){const cutoff=new Date(localStorage.getItem(ALERT_KEY)||"1970-01-01T00:00:00Z");return[...new Map(items.filter(i=>{const d=new Date(i.last_changed||i.first_seen||0);return((!i.baseline_import&&d>cutoff)||(i.review_required&&d>cutoff));}).map(i=>[i.id,i])).values()].sort((a,b)=>new Date(b.last_changed||0)-new Date(a.last_changed||0));}
  const acknowledgeAlerts=()=>localStorage.setItem(ALERT_KEY,new Date().toISOString()); const alertLabel=i=>i.review_required?t("reviewAlert"):i.content_type==="campaign"?(Number(i.version||1)>1?t("updatedCampaign"):t("newCampaign")):i.content_type==="merchant_offer"?t("newMerchant"):t("newPost");
  const pill=(text,kind="neutral")=>el("span",{class:`pill pill--${kind}`},text);
  const competitorColor=id=>COMPETITOR_COLORS[id]||COLORS[0];
  const prefersReducedMotion=()=>window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  let chartObserver=null;
  function countUp(node){
    const target=Number(node.dataset.countTarget||0);
    if(!Number.isFinite(target)||prefersReducedMotion()){node.textContent=String(target);return;}
    const started=performance.now(),duration=650;
    const step=now=>{const progress=Math.min(1,(now-started)/duration),eased=1-Math.pow(1-progress,3);node.textContent=String(Math.round(target*eased));if(progress<1)requestAnimationFrame(step);};
    requestAnimationFrame(step);
  }
  function observeChart(container){
    if(!container)return;
    container.classList.remove("is-chart-visible");
    container.querySelectorAll("[data-count-target]").forEach(n=>n.textContent=prefersReducedMotion()?n.dataset.countTarget:"0");
    if(prefersReducedMotion()){container.classList.add("is-chart-visible");return;}
    if(!("IntersectionObserver" in window)){container.classList.add("is-chart-visible");container.querySelectorAll("[data-count-target]").forEach(countUp);return;}
    chartObserver??=new IntersectionObserver(entries=>entries.forEach(entry=>{if(!entry.isIntersecting)return;const node=entry.target;node.classList.add("is-chart-visible");node.querySelectorAll("[data-count-target]").forEach(countUp);chartObserver.unobserve(node);}),{threshold:.18,rootMargin:"0px 0px -8% 0px"});
    chartObserver.unobserve(container);
    chartObserver.observe(container);
  }
  function chartTarget(tag,row,children){
    const attrs={class:`bar-row${row.onClick||row.href?" bar-row--interactive":""}`,title:row.tooltip||`${row.label}: ${row.value??0}`};
    if(row.href){attrs.href=row.href;return el("a",attrs,...children);}
    if(row.onClick){attrs.type="button";attrs.onclick=row.onClick;return el("button",attrs,...children);}
    return el(tag,attrs,...children);
  }
  function renderBarChart(container,rows,options={}){
    clear(container);
    let vals=options.keepZero?[...rows]:rows.filter(r=>Number(r.value)>0);
    if(options.sort!==false)vals.sort((a,b)=>Number(b.value||0)-Number(a.value||0));
    if(!vals.length){container.appendChild(el("div",{class:"empty-state"},t("noData")));return;}
    const max=Math.max(1,...vals.map(r=>Number(r.value)||0));
    vals.forEach((r,i)=>{
      const value=Number(r.value)||0,pct=value?Math.max(2.5,value/max*100):0,color=r.color||COLORS[i%COLORS.length];
      const label=el("span",{class:"bar-row__label"},r.label);
      const track=el("span",{class:"bar-row__track","aria-hidden":"true"},el("span",{class:"bar-row__fill",style:`width:${pct}%;--bar-color:${color};--chart-delay:${i*70}ms`}));
      const number=el("strong",{class:"bar-row__value","data-count-target":value},String(value));
      container.appendChild(chartTarget("div",r,[label,track,number]));
    });
    observeChart(container);
  }
  function renderStackedBarChart(container,rowDefs,series,options={}){
    clear(container);
    const normalizedRows=rowDefs.map(row=>({...row,values:Object.fromEntries(series.map(s=>[s.id,Number(row.values?.[s.id]||0)]))}));
    const maxTotal=Math.max(1,...normalizedRows.map(row=>series.reduce((sum,s)=>sum+row.values[s.id],0)));
    const legend=el("div",{class:"chart-legend"},series.map(s=>el("span",{},el("i",{style:`--legend-color:${s.color}`}),s.label)));
    container.appendChild(legend);
    normalizedRows.forEach((row,rowIndex)=>{
      const total=series.reduce((sum,s)=>sum+row.values[s.id],0),outerWidth=options.normalize?100:(total?Math.max(3,total/maxTotal*100):0);
      const segments=series.map(s=>{
        const value=row.values[s.id],width=total?value/total*100:0,pct=total?Math.round(value/total*100):0;
        const attrs={class:"stacked-bar__segment",style:`width:${width}%;--segment-color:${s.color}`,title:`${row.label} · ${s.label}: ${value}${options.normalize?` (${pct}%)`:""}`};
        if(options.onSegmentClick&&value){attrs.type="button";attrs.onclick=()=>options.onSegmentClick(row,s,value);return el("button",attrs);}
        return el("span",attrs);
      });
      const rowNode=el("div",{class:"stacked-row"},row.href?el("a",{class:"stacked-row__label",href:row.href},row.label):el("span",{class:"stacked-row__label"},row.label),el("div",{class:"stacked-bar__rail"},el("div",{class:"stacked-bar__track",style:`width:${outerWidth}%;--chart-delay:${rowIndex*75}ms`},segments)),el("strong",{class:"stacked-row__total","data-count-target":total},String(total)));
      container.appendChild(rowNode);
    });
    observeChart(container);
  }
  function renderGroupedBarChart(container,rowDefs,series,options={}){
    clear(container);
    const max=Math.max(1,...rowDefs.flatMap(row=>series.map(s=>Number(row.values?.[s.id]||0))));
    container.appendChild(el("div",{class:"chart-legend"},series.map(s=>el("span",{},el("i",{style:`--legend-color:${s.color}`}),s.label))));
    rowDefs.forEach((row,rowIndex)=>{
      const bars=series.map((s,seriesIndex)=>{const value=Number(row.values?.[s.id]||0),pct=value?Math.max(2.5,value/max*100):0,color=row.colors?.[s.id]||s.color;return el("div",{class:"grouped-bar",title:`${row.label} · ${s.label}: ${value}`},el("span",{class:"grouped-bar__track"},el("span",{class:"grouped-bar__fill",style:`width:${pct}%;--bar-color:${color};--chart-delay:${rowIndex*70+seriesIndex*45}ms`})),el("strong",{"data-count-target":value},String(value)));});
      const attrs={class:`grouped-row${row.onClick?" grouped-row--interactive":""}`};
      let node;
      if(row.onClick){attrs.type="button";attrs.onclick=row.onClick;node=el("button",attrs,el("span",{class:"grouped-row__label"},row.label),el("div",{class:"grouped-row__bars"},bars));}
      else node=el("div",attrs,el("span",{class:"grouped-row__label"},row.label),el("div",{class:"grouped-row__bars"},bars));
      container.appendChild(node);
    });
    observeChart(container);
  }
  function renderMatrix(container,rowDefs,colDefs,valueFn,options={}){
    clear(container);
    const values=rowDefs.flatMap(r=>colDefs.map(c=>Number(valueFn(r,c))||0)),max=Math.max(1,...values);
    const table=el("div",{class:"matrix heatmap-table",style:`--matrix-columns:${colDefs.length}`});
    table.appendChild(el("div",{class:"matrix__row matrix__row--head"},el("strong",{},""),...colDefs.map(c=>el("strong",{},c.label))));
    rowDefs.forEach((r,rowIndex)=>{
      const cells=colDefs.map((c,colIndex)=>{const value=Number(valueFn(r,c))||0,intensity=value/max,attrs={class:`matrix__cell heatmap-cell${options.onCellClick&&value?" heatmap-cell--interactive":""}`,style:`--heat:${intensity};--chart-delay:${(rowIndex*colDefs.length+colIndex)*24}ms`,title:`${r.label} · ${c.label}: ${value}`,"aria-label":`${r.label}, ${c.label}: ${value}`};if(options.onCellClick&&value){attrs.type="button";attrs.onclick=()=>options.onCellClick(r,c,value);return el("button",attrs,el("span",{"data-count-target":value},String(value)));}return el("span",attrs,el("span",{"data-count-target":value},String(value)));});
      table.appendChild(el("div",{class:"matrix__row"},r.href?el("a",{href:r.href},r.label):el("strong",{},r.label),cells));
    });
    container.appendChild(table);
    observeChart(container);
  }
  function renderMedia(item,compact=false){const m=item.media;if(!m?.url)return null;if(m.type==="video"){if(/\.(mp4|webm|mov)(\?|$)/i.test(m.url))return el("video",{class:compact?"media media--compact":"media",controls:true,preload:"metadata",poster:m.thumbnail_url||""},el("source",{src:m.url}));if(m.thumbnail_url)return el("div",{class:"media-link"},el("img",{src:m.thumbnail_url,alt:"",loading:"lazy"}),el("span",{class:"media-play"},"▶"));return el("div",{class:"media-placeholder"},"▶");}return el("img",{class:compact?"media media--compact":"media",src:m.thumbnail_url||m.url,alt:item.title||"",loading:"lazy",referrerpolicy:"no-referrer"});}
  const contentLabel=i=>i.content_type==="review"?t("review_type"):t(i.content_type); const categoryLabel=(i,data)=>{const r=byId(data.categories)[i.campaign_category||i.primary_category];return r?taxonomyName(r):"—";};
  function socialIdentity(value){if(!value)return"";try{const u=new URL(value,location.href);let h=u.hostname.toLowerCase().replace(/^www\./,"");if(h==="twitter.com")h="x.com";if(h==="m.facebook.com")h="facebook.com";const p=(u.pathname||"/").replace(/\/{2,}/g,"/").replace(/\/$/,"").toLowerCase()||"/";return`${h}${p}`;}catch{return String(value).trim().toLowerCase().replace(/\/$/,"");}}
  function knownSocialCount(item){const ids=new Set();Object.values(item.social_links||{}).forEach(raw=>(Array.isArray(raw)?raw:[raw]).filter(Boolean).forEach(u=>ids.add(socialIdentity(u))));(item.linked_posts||[]).forEach(p=>p?.link&&ids.add(socialIdentity(p.link)));return ids.size;}
  function renderItemCard(item,data,options={}){const comp=byId(data.competitors)[item.competitor_id],card=el("article",{class:`item-card item-card--${item.content_type||"review"}`});if(options.selectable&&isAdmin())card.appendChild(el("input",{type:"checkbox",class:"review-select","data-item-id":item.id}));const total=Math.max(Number(item.social_posts_total||0),knownSocialCount(item));card.appendChild(el("div",{class:"item-card__body"},el("div",{class:"item-card__top"},el("strong",{},competitorName(comp)),el("span",{},item.source_type==="inventory"?t("inventorySource"):t(item.platform||item.source_type||"website"))),el("div",{class:"pill-row"},pill(contentLabel(item),item.content_type==="merchant_offer"?"gold":item.review_required?"warning":"info"),pill(categoryLabel(item,data),"neutral"),total?pill(`${total} ${t("posts")}`,"success"):null),el("h3",{},item.title||"—"),item.snippet?el("p",{},item.snippet):null,el("div",{class:"item-card__meta"},item.current_status?el("span",{},item.current_status):null,item.end_date?el("span",{},`${t("endDate")}: ${formatDate(item.end_date)}`):null),el("div",{class:"item-card__actions"},el("a",{class:"button button--primary",href:`item.html?id=${encodeURIComponent(item.id)}`},t("openAnalysis")),item.link?el("a",{class:"button button--ghost",href:item.link,target:"_blank",rel:"noopener noreferrer"},item.source_type==="social"?t("openPost"):t("openOfficial")):null,(isAdmin()?el("button",{class:"button button--secondary",onclick:()=>openEditor(item,data)},t("edit")):null),(isAdmin()&&item.content_type==="campaign"?el("button",{class:"button button--danger",onclick:()=>deleteCampaign(item)},t("deleteCampaign")):null))));return card;}
  function renderMediaCard(item,data){const media=renderMedia(item);if(!media)return null;const comp=byId(data.competitors)[item.competitor_id];return el("article",{class:"media-card"},el("a",{class:"media-card__visual",href:item.link||"#",target:"_blank",rel:"noopener noreferrer"},media),el("div",{class:"media-card__body"},el("div",{class:"media-card__meta"},`${competitorName(comp)} · ${t(item.platform||"website")}`),el("h3",{},item.title||"—"),el("a",{href:`item.html?id=${encodeURIComponent(item.id)}`},t("openAnalysis"))));}
  const field=(label,input)=>el("label",{class:"editor-field"},el("span",{},label),input); const campaignsFor=(item,data)=>(data.items||[]).filter(i=>i.competitor_id===item.competitor_id&&["campaign","merchant_offer"].includes(i.content_type)&&i.id!==item.id);
  function openEditor(item,data){if(!isAdmin())return;document.getElementById("cm-editor")?.remove();const showPublished=item.source_type==="social";const content=el("select",{},["campaign","merchant_offer","social_post","awareness","review"].map(v=>el("option",{value:v,selected:item.content_type===v},t(v==="review"?"review_type":v)))),category=el("select",{},data.categories.map(r=>el("option",{value:r.id,selected:(item.campaign_category||item.primary_category)===r.id},taxonomyName(r)))),title=el("input",{value:item.title||""}),summary=el("textarea",{rows:4},item.snippet||item.summary||""),status=el("input",{value:item.current_status||"",readonly:true,title:"Calculated automatically from campaign dates"}),active=el("input",{type:"checkbox",checked:item.active!==false,disabled:true,title:"Calculated automatically from campaign dates"}),pub=el("input",{type:"date",value:dateInput(item.published_at)}),start=el("input",{type:"date",value:dateInput(item.start_date)}),end=el("input",{type:"date",value:dateInput(item.end_date)}),official=el("input",{value:item.official_campaign_page_url||"",type:"url"}),primary=el("input",{value:item.primary_official_source_url||"",type:"url"}),mechanic=el("textarea",{rows:2},item.mechanic||""),eligibility=el("textarea",{rows:2},item.eligibility||""),terms=el("textarea",{rows:3},item.terms_note||"");const social=Object.fromEntries(["instagram","x","facebook","tiktok"].map(p=>[p,el("input",{value:item.social_links?.[p]||"",type:"url"})]));const linkSelect=el("select",{},el("option",{value:""},t("noCampaign")),...campaignsFor(item,data).map(c=>el("option",{value:c.id,selected:item.campaign_id===c.id||item.suggested_campaign_id===c.id},c.title||c.id)));
    const createFromPost=item.source_type==="social"?el("button",{class:"button button--ghost",onclick:()=>{const row={id:`manual:${item.competitor_id}:${Date.now()}`,competitor_id:item.competitor_id,content_type:"campaign",campaign_category:item.campaign_category||"other",title:item.title||"New campaign",summary:item.snippet||"",social_links:{[item.platform]:item.link},created_at:new Date().toISOString(),active:true};addNewItem(row);saveItemOverride(item.id,{linked_campaign_id:row.id,campaign_id:row.id,review_required:false});exportOverrides();location.reload();}},t("createCampaignFromPost")):null;
    const modal=el("div",{id:"cm-editor",class:"modal-backdrop"},el("section",{class:"modal"},el("header",{class:"modal__header"},el("h2",{},t("editItem")),el("button",{class:"icon-button",onclick:()=>modal.remove()},"×")),el("div",{class:"modal__body"},el("p",{class:"editor-note"},t("editsNote")),el("div",{class:"editor-grid"},field(t("contentType"),content),field(t("category"),category),field(t("title"),title),field(t("currentStatus"),status),field(t("summary"),summary),field(t("active"),active),showPublished?field(t("published"),pub):null,field(t("startDate"),start),field(t("endDate"),end),field(t("officialCampaignUrl"),official),field(t("primarySourceUrl"),primary),field(t("mechanic"),mechanic),field(t("eligibility"),eligibility),field(t("terms"),terms),item.source_type==="social"?field(t("linkToCampaign"),linkSelect):null,field(t("instagramUrl"),social.instagram),field(t("xUrl"),social.x),field(t("facebookUrl"),social.facebook),field(t("tiktokUrl"),social.tiktok))),el("footer",{class:"modal__footer"},createFromPost,el("button",{class:"button button--ghost",onclick:()=>{resetItemOverride(item.id);location.reload();}},t("resetEdit")),el("button",{class:"button button--secondary",onclick:exportOverrides},t("exportEdits")),item.content_type==="campaign"?el("button",{class:"button button--danger",onclick:()=>deleteCampaign(item)},t("deleteCampaign")):null,el("button",{class:"button button--primary",onclick:()=>{const cat=category.value,ctype=cat==="merchant"?"merchant_offer":content.value,links=Object.fromEntries(Object.entries(social).map(([k,input])=>[k,input.value.trim()]).filter(([,v])=>v));const nextStart=toIsoDate(start.value),nextEnd=toIsoDate(end.value),life=lifecycleFor({start_date:nextStart,end_date:nextEnd}),nextTerms=(nextEnd&&staleNoEndNote(terms.value))?"":terms.value.trim();saveItemOverride(item.id,{title:title.value.trim(),snippet:summary.value.trim(),summary:summary.value.trim(),content_type:ctype,campaign_category:cat,current_status:life.status,active:life.active,...(showPublished?{published_at:toIsoDate(pub.value)}:{}),start_date:nextStart,end_date:nextEnd,official_campaign_page_url:official.value.trim(),primary_official_source_url:primary.value.trim(),link:official.value.trim()||primary.value.trim()||item.link,mechanic:mechanic.value.trim(),eligibility:eligibility.value.trim(),terms_note:nextTerms,social_links:links,linked_campaign_id:linkSelect.value||null,campaign_id:linkSelect.value||item.campaign_id||null,review_required:ctype==="review"||(item.source_type==="social"&&!linkSelect.value&&item.review_required),review_reasons:ctype==="review"?["manual_review_required"]:[]});location.reload();}},t("saveLocal")))));document.body.appendChild(modal);modal.addEventListener("click",e=>{if(e.target===modal)modal.remove();});}
  function openAddCampaign(data,presetComp=""){if(!isAdmin())return;document.getElementById("cm-add")?.remove();const competitor=el("select",{},data.competitors.map(c=>el("option",{value:c.id,selected:c.id===presetComp},competitorName(c)))),category=el("select",{},data.categories.filter(c=>c.id!=="merchant").map(c=>el("option",{value:c.id},taxonomyName(c)))),url=el("input",{type:"url",placeholder:"https://..."}),title=el("input",{});const modal=el("div",{id:"cm-add",class:"modal-backdrop"},el("section",{class:"modal modal--compact"},el("header",{class:"modal__header"},el("h2",{},t("addCampaign")),el("button",{class:"icon-button",onclick:()=>modal.remove()},"×")),el("div",{class:"modal__body"},el("p",{class:"editor-note"},t("analyzeAfterUpload")),el("div",{class:"editor-grid"},field(t("competitors"),competitor),field(t("category"),category),field(t("officialCampaignUrl"),url),field(t("title"),title))),el("footer",{class:"modal__footer"},el("button",{class:"button button--primary",onclick:()=>{if(!url.value.trim())return;addNewItem({id:`manual:${competitor.value}:${Date.now()}`,competitor_id:competitor.value,content_type:"campaign",campaign_category:category.value,title:title.value.trim()||"New campaign pending source analysis",summary:"",official_campaign_page_url:url.value.trim(),primary_official_source_url:url.value.trim(),link:url.value.trim(),social_links:{},active:true,review_required:true,created_at:new Date().toISOString()});exportOverrides();modal.remove();location.reload();}},t("saveLocal")))));document.body.appendChild(modal);}
  function refreshHistoryRow(row,data){const comp=row.competitor==="all"?t("all"):competitorName(byId(data.competitors)[row.competitor]);return el("article",{class:"refresh-history-row"},el("div",{},el("strong",{},comp),el("span",{},formatDate(row.completed_at,true))),el("div",{class:"refresh-history-metrics"},el("span",{},`${t("newOffersCount")}: ${Number(row.new_offers||0)}`),el("span",{},`${t("updatedOffersCount")}: ${Number(row.updated_offers||0)}`),el("span",{},`${t("newPostsCount")}: ${Number(row.new_posts||0)}`),el("span",{},`${t("failedSourcesCount")}: ${Number(row.failed_sources||0)}`)));}
  function sourceRow(status,data){const comp=byId(data.competitors)[status.competitor_id],state=status.success?(status.item_count?t("healthy"):t("noItems")):t("failed"),retry=isAdmin()&&status.competitor_id&&status.source_type!=="campaign_detail"&&(!status.success||!status.item_count)?el("button",{type:"button",class:"button button--secondary","data-refresh-control":"true",onclick:e=>triggerRefresh(status.competitor_id,e.currentTarget)},t("retryFailed")):null;return el("article",{class:`source-card ${status.success?"source-card--ok":"source-card--failed"}`},el("div",{},el("strong",{},`${competitorName(comp)} · ${status.source_type==="campaign_detail"?t("sourceVerification"):t(status.platform||"website")}`),el("span",{class:"source-state"},state)),el("dl",{},el("div",{},el("dt",{},t("lastCheck")),el("dd",{},formatDate(status.checked_at,true))),el("div",{},el("dt",{},t("lastSuccess")),el("dd",{},formatDate(status.last_success_at,true))),el("div",{},el("dt",{},t("extracted")),el("dd",{},String(status.item_count||0)))),status.error?el("code",{},status.error):status.success&&!status.item_count?el("p",{class:"source-note"},t("zeroItemsMeaning")):null,el("div",{class:"source-actions"},el("a",{href:status.url,target:"_blank",rel:"noopener noreferrer"},t("openSource")),retry));}
  function showError(container,error){clear(container);container.appendChild(el("div",{class:"error-state"},el("strong",{},t("loadError")),el("code",{},String(error)),el("button",{class:"button button--primary",onclick:()=>location.reload()},t("retry"))));}
  function csvEscape(v){const s=v==null?"":String(v);return/[",\n]/.test(s)?`"${s.replaceAll('"','""')}"`:s;}
  function exportDelta(data){if(!isAdmin())return;const since=new Date(localStorage.getItem(DELTA_KEY)||data.inventory_source?.review_date||"1970-01-01"),comps=byId(data.competitors),cats=byId(data.categories),rows=(data.items||[]).filter(i=>!i.baseline_import&&new Date(i.last_changed||i.first_seen||0)>since),head=["Competitor","Record Type","Category","Title","Status","Start Date","End Date","Changed At","Official URL"],body=rows.map(i=>[competitorName(comps[i.competitor_id]),i.content_type,taxonomyName(cats[i.campaign_category]),i.title,i.current_status,i.start_date,i.end_date,i.last_changed||i.first_seen,i.official_campaign_page_url||i.link]);downloadBlob(`competitor_delta_${new Date().toISOString().slice(0,10)}.csv`,[head,...body].map(r=>r.map(csvEscape).join(",")).join("\n"),"text/csv;charset=utf-8");localStorage.setItem(DELTA_KEY,new Date().toISOString());}
  setupReportDownloads();
  window.CM={lifecycleFor,normalizeLifecycle,t,language,setLanguage,initLanguage,loadAuth,auth,isAdmin,loadData,triggerRefresh,resumeRefresh,el,clear,byId,competitorName,taxonomyName,formatDate,timeAgo,withinDays,countBy,getOverrides,exportOverrides,importOverrides,saveItemOverride,addNewItem,deleteCampaign,activeCampaigns,activeMerchants,socialPosts,alerts,acknowledgeAlerts,alertLabel,pill,competitorColor,renderBarChart,renderStackedBarChart,renderGroupedBarChart,renderMatrix,renderMedia,renderItemCard,renderMediaCard,openEditor,openAddCampaign,sourceRow,refreshHistoryRow,showError,categoryLabel,contentLabel,exportDelta};
})();
