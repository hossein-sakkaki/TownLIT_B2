from django.template.loader import render_to_string
from django.utils.html import strip_tags
from utils.common.utils import send_email
import logging

logger = logging.getLogger(__name__)

def send_custom_email(to, subject, template_path, context=None, text_template_path=None):
    """
    رندر و ارسال یک ایمیل HTML (و اختیاری: متن ساده) به کاربر یا کاربران.

    :param to: آدرس ایمیل گیرنده (str یا list)
    :param subject: موضوع ایمیل
    :param template_path: مسیر قالب HTML برای رندر (مثال: 'emails/account/verify.html')
    :param context: دیکشنری اطلاعات مورد نیاز قالب
    :param text_template_path: (اختیاری) مسیر قالب متن ساده، در صورت نیاز
    :return: True در صورت موفقیت، False در صورت خطا
    """

    context = context or {}

    try:
        # HTML content
        html_content = render_to_string(template_path, context)

        # Plain text fallback
        if text_template_path:
            text_content = render_to_string(text_template_path, context)
        else:
            text_content = strip_tags(html_content)  # استخراج متن ساده از HTML

        # ارسال واقعی
        success = send_email(subject, text_content, html_content, to)

        if not success:
            logger.warning(f"❌ Email not sent to {to}. Check SES or SMTP logs.")
        return success

    except Exception as e:
        logger.error(f"❌ Failed to send email to {to}: {e}", exc_info=True)
        return False
