"""Two-language support for the public pages, keyed on the English string.

Deliberately not Flask-Babel: this is one extra language and about seventy
strings, so a dict costs nothing at runtime and needs no .mo compilation
step on the server.

Item names, descriptions and units are content the organisers type in, so
they are never translated — only the site's own wording is.

The admin area stays English (see admin/_layout.html forcing dir="ltr").
"""

from flask import session

DEFAULT_LANGUAGE = "en"
LANGUAGES = {"en": "English", "ar": "العربية"}
RTL_LANGUAGES = {"ar"}

TRANSLATIONS = {
    "ar": {
        # ── shell ──
        "Community supply list": "قائمة احتياجات المخيم",
        "Admin": "الإدارة",
        "Organiser sign in": "دخول المنظمين",
        "Thank you for helping out.": "شكراً لمساعدتكم.",
        "Switch to Arabic": "التبديل إلى العربية",
        "Switch to English": "Switch to English",
        # ── overview ──
        "of what the camp needs is covered": "من احتياجات المخيم مُؤمَّن",
        "still need help": "ما زالت بحاجة",
        "items listed": "مادة مدرجة",
        "Nothing listed yet": "لا توجد مواد بعد",
        "The organisers haven't added anything to bring. Please check back soon.":
            "لم يضف المنظمون أي مواد بعد. يرجى العودة قريباً.",
        # ── search ──
        "Search items": "ابحث عن مادة",
        "Search": "بحث",
        "Clear search": "مسح البحث",
        "Nothing matches your search.": "لا توجد نتائج مطابقة لبحثك.",
        "Show all items": "عرض كل المواد",
        # ── item card ──
        "Covered": "مكتمل",
        "to go": "متبقٍ",
        "claimed": "مؤمَّن",
        "Claim": "سأحضره",
        "On your list": "في قائمتك",
        "Quantity": "الكمية",
        "still needed.": "ما زالت مطلوبة.",
        "Note about this item": "ملاحظة على هذه المادة",
        "(optional)": "(اختياري)",
        "e.g. all size L": "مثال: كلها قياس كبير",
        "Add to my list": "أضف إلى قائمتي",
        "Update": "تحديث",
        "Remove from list": "إزالة من القائمة",
        "You'll enter your name once, at the end.": "ستُدخل اسمك مرة واحدة في النهاية.",
        # ── the list bar ──
        "on your list": "في قائمتك",
        "Review & confirm": "المراجعة والتأكيد",
        # ── confirm page ──
        "Confirm your claims": "تأكيد ما ستحضره",
        "Check the amounts, then enter your name once for the whole list.":
            "راجع الكميات، ثم أدخل اسمك مرة واحدة للقائمة كاملة.",
        "Add more": "أضف المزيد",
        "Your list": "قائمتك",
        "still needed": "ما زالت مطلوبة",
        "Only {n} left — lower this to confirm.":
            "المتبقي {n} فقط — قلّل الكمية للتأكيد.",
        "Note about this item (optional)": "ملاحظة على هذه المادة (اختياري)",
        "Your details": "بياناتك",
        "Your name": "اسمك",
        "Shown publicly next to what you're bringing.":
            "يظهر للجميع بجانب ما ستحضره.",
        "Start typing — pick your name if it's already there, so it stays consistent.":
            "ابدأ بالكتابة — اختر اسمك إن كان موجوداً ليبقى موحّداً.",
        "Note about the whole drop-off": "ملاحظة على التسليم كامله",
        "e.g. I can drop everything off on Friday morning":
            "مثال: أستطيع تسليم كل شيء صباح الجمعة",
        "For anything that applies to all of it. Per-item notes go next to each item above.":
            "لأي شيء ينطبق على الكل. ملاحظات كل مادة توضع بجانبها بالأعلى.",
        "Confirm 1 item": "تأكيد مادة واحدة",
        "Confirm {n} items": "تأكيد {n} مواد",
        "Empty my list": "إفراغ قائمتي",
        "Empty your whole list?": "هل تريد إفراغ قائمتك بالكامل؟",
        "item": "مادة",
        "items": "مواد",
        # ── messages ──
        "That item is no longer listed.": "هذه المادة لم تعد مدرجة.",
        "Removed {name} from your list.": "تمت إزالة {name} من قائمتك.",
        "Quantity must be a whole number of at least 1.":
            "يجب أن تكون الكمية رقماً صحيحاً لا يقل عن 1.",
        "{name} has just been fully claimed.": "اكتملت {name} للتو.",
        "Only {n} {unit} of {name} are still needed.":
            "المطلوب من {name} هو {n} {unit} فقط.",
        "Your list is full — please confirm what's on it first.":
            "قائمتك ممتلئة — يرجى تأكيد ما فيها أولاً.",
        "That's more than your list can hold — please confirm what's on it first, or shorten a note.":
            "هذا أكثر مما تتسع له قائمتك — أكّد ما فيها أولاً أو اختصر ملاحظة.",
        "{name} updated.": "تم تحديث {name}.",
        "{name} added to your list.": "تمت إضافة {name} إلى قائمتك.",
        "Your list has been emptied.": "تم إفراغ قائمتك.",
        "Your list is empty — pick something you can bring.":
            "قائمتك فارغة — اختر ما يمكنك إحضاره.",
        "Please enter your name.": "يرجى إدخال اسمك.",
        "That name is too long.": "هذا الاسم طويل جداً.",
        "Please keep the note under {n} characters.":
            "يرجى أن تكون الملاحظة أقل من {n} حرفاً.",
        "Thank you, {name}! 1 item confirmed.": "شكراً {name}! تم تأكيد مادة واحدة.",
        "Thank you, {name}! {n} items confirmed.": "شكراً {name}! تم تأكيد {n} مواد.",
        "{name}: only {n} {unit} left, so your {q} couldn't be recorded. Adjust it below.":
            "{name}: المتبقي {n} {unit} فقط، لذلك لم تُسجَّل كميتك {q}. عدّلها بالأسفل.",
        "{name} was fully claimed by someone else before you confirmed.":
            "اكتملت {name} من شخص آخر قبل أن تؤكد.",
    }
}


def current_language():
    chosen = session.get("lang")
    return chosen if chosen in LANGUAGES else DEFAULT_LANGUAGE


def set_language(code):
    """Store the choice. Unknown codes fall back to the default."""
    session["lang"] = code if code in LANGUAGES else DEFAULT_LANGUAGE


def translate(text, **fields):
    """Look up `text`, falling back to the English source when untranslated."""
    table = TRANSLATIONS.get(current_language(), {})
    result = table.get(text, text)
    return result.format(**fields) if fields else result


def init_app(app):
    app.jinja_env.globals["t"] = translate
    app.jinja_env.globals["LANGUAGES"] = LANGUAGES

    @app.context_processor
    def _inject_language():
        code = current_language()
        return {
            "lang": code,
            "is_rtl": code in RTL_LANGUAGES,
            "other_lang": "en" if code == "ar" else "ar",
        }
