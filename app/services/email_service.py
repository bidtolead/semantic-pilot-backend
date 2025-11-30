"""
Email service using Resend API
"""
import os
import resend

# Initialize Resend with API key from environment
resend.api_key = os.getenv("RESEND_API_KEY")


def send_email(to_email: str, subject: str, html_content: str, from_email: str = None):
    """
    Send an email using Resend.
    
    Args:
        to_email: Recipient email address
        subject: Email subject line
        html_content: HTML content of the email
        from_email: Sender email (defaults to noreply@semanticpilot.com)
    
    Returns:
        dict: Response from Resend API
    
    Raises:
        Exception: If email sending fails
    """
    if not resend.api_key:
        raise ValueError("RESEND_API_KEY not configured")
    
    if not from_email:
        from_email = "Semantic Pilot <noreply@semanticpilot.com>"
    
    try:
        params = {
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
        
        response = resend.Emails.send(params)
        return {"status": "sent", "id": response.get("id")}
    except Exception as e:
        raise Exception(f"Failed to send email: {str(e)}")


def send_bulk_email(to_emails: list[str], subject: str, html_content: str, from_email: str = None):
    """
    Send the same email to multiple recipients.
    
    Args:
        to_emails: List of recipient email addresses
        subject: Email subject line
        html_content: HTML content of the email
        from_email: Sender email (defaults to noreply@semanticpilot.com)
    
    Returns:
        dict: Summary of sent/failed emails
    """
    if not resend.api_key:
        raise ValueError("RESEND_API_KEY not configured")
    
    if not from_email:
        from_email = "Semantic Pilot <noreply@semanticpilot.com>"
    
    results = {"sent": [], "failed": []}
    
    for email in to_emails:
        try:
            params = {
                "from": from_email,
                "to": [email],
                "subject": subject,
                "html": html_content,
            }
            response = resend.Emails.send(params)
            results["sent"].append(email)
        except Exception as e:
            results["failed"].append({"email": email, "error": str(e)})
    
    return results
