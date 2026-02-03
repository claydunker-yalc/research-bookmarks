import resend
from config import RESEND_API_KEY, USER_EMAIL


def send_digest_email(subject: str, html_body: str) -> dict:
    """
    Send the digest email using Resend.

    Args:
        subject: Email subject line
        html_body: HTML content of the email

    Returns:
        dict with send status and id
    """
    if not RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY not configured")
    if not USER_EMAIL:
        raise ValueError("USER_EMAIL not configured")

    resend.api_key = RESEND_API_KEY

    params = {
        "from": "Research Bookmarks <onboarding@resend.dev>",
        "to": [USER_EMAIL],
        "subject": subject,
        "html": html_body,
    }

    result = resend.Emails.send(params)
    return {"success": True, "id": result.get("id")}


def is_email_configured() -> bool:
    """Check if email sending is properly configured."""
    return bool(RESEND_API_KEY and USER_EMAIL)
