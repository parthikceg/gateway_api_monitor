"""Email service using Zoho SMTP"""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)


class EmailService:
    """Send email alerts via Zoho SMTP"""

    def __init__(self):
        self.smtp_host = os.environ.get("SMTP_HOST", "smtp.zoho.com")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_username = os.environ.get("SMTP_USERNAME", "")
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "")
        self.from_email = os.environ.get("ALERT_FROM_EMAIL", "")
        self.from_name = os.environ.get("ALERT_FROM_NAME", "Gateway Monitor")

        self.enabled = bool(self.smtp_username and self.smtp_password and self.from_email)
        if self.enabled:
            logger.info("Email service enabled")
        else:
            logger.warning("Email service disabled - missing SMTP credentials")

    def send_email(self, to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> bool:
        """Send a single email"""
        if not self.enabled:
            logger.warning("Email service not configured, skipping email send")
            return False

        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email

            # Add plain text version (fallback)
            if text_content:
                part1 = MIMEText(text_content, "plain")
                message.attach(part1)

            # Add HTML version
            part2 = MIMEText(html_content, "html")
            message.attach(part2)

            # Connect and send
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                server.sendmail(self.from_email, to_email, message.as_string())

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def send_change_alert(self, to_email: str, to_name: str, changes: List[Dict[str, Any]]) -> bool:
        """Send alert email when new API changes are detected"""
        if not changes:
            return False

        subject = f"🚨 {len(changes)} New Stripe API Change{'s' if len(changes) > 1 else ''} Detected"

        # Build HTML content
        changes_html = ""
        for change in changes:
            severity_color = {
                "high": "#dc2626",
                "medium": "#f59e0b",
                "low": "#3b82f6",
                "info": "#6b7280"
            }.get(change.get("severity", "info"), "#6b7280")

            changes_html += f"""
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                    <span style="background-color: {severity_color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; text-transform: uppercase;">
                        {change.get('severity', 'info')}
                    </span>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                    <strong>{change.get('type', 'Unknown')}</strong>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                    <code style="background-color: #f3f4f6; padding: 2px 6px; border-radius: 4px;">{change.get('field', 'N/A')}</code>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                    <code style="background-color: #e0e7ff; padding: 2px 6px; border-radius: 4px; font-size: 11px;">{change.get('endpoint', 'N/A')}</code>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                    {change.get('tier', 'stable').capitalize()}
                </td>
            </tr>
            <tr>
                <td colspan="5" style="padding: 8px 12px 16px 12px; color: #6b7280; font-size: 14px;">
                    {change.get('summary', 'No summary available')}
                </td>
            </tr>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); padding: 24px; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Gateway Monitor</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0;">Stripe API Change Alert</p>
            </div>

            <div style="background-color: #ffffff; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p>Hi {to_name},</p>

                <p>We detected <strong>{len(changes)} new change{'s' if len(changes) > 1 else ''}</strong> in the Stripe API:</p>

                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <thead>
                        <tr style="background-color: #f9fafb;">
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb;">Severity</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb;">Type</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb;">Field</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb;">Endpoint</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb;">Tier</th>
                        </tr>
                    </thead>
                    <tbody>
                        {changes_html}
                    </tbody>
                </table>

                <p style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 14px;">
                    You're receiving this because you subscribed to Gateway Monitor alerts.
                </p>
            </div>
        </body>
        </html>
        """

        text_content = f"""
Gateway Monitor - Stripe API Change Alert

Hi {to_name},

We detected {len(changes)} new change{'s' if len(changes) > 1 else ''} in the Stripe API:

""" + "\n".join([
            f"- [{c.get('severity', 'info').upper()}] {c.get('type', 'Unknown')}: {c.get('field', 'N/A')}\n  Endpoint: {c.get('endpoint', 'N/A')} | Tier: {c.get('tier', 'stable')}\n  {c.get('summary', 'No summary')}"
            for c in changes
        ])

        return self.send_email(to_email, subject, html_content, text_content)

    def send_welcome_email(self, to_email: str, to_name: str, recent_changes: List[Dict[str, Any]]) -> bool:
        """Send welcome email to a new subscriber with a snapshot of recent changes"""
        subject = "Welcome to Gateway Monitor — You're subscribed to Stripe API alerts"

        if recent_changes:
            changes_html = ""
            for change in recent_changes[:10]:
                severity_color = {
                    "high": "#dc2626",
                    "medium": "#f59e0b",
                    "low": "#3b82f6",
                    "info": "#6b7280"
                }.get(change.get("severity", "info"), "#6b7280")
                tier_label = change.get("tier", "stable").replace("_", " ").title()
                changes_html += f"""
                <div style="padding: 14px; margin-bottom: 10px; background-color: #f9fafb; border-radius: 8px; border-left: 4px solid {severity_color};">
                    <div style="margin-bottom: 6px;">
                        <span style="background-color: {severity_color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; text-transform: uppercase; margin-right: 8px;">{change.get('severity', 'info')}</span>
                        <strong style="font-size: 14px;">{change.get('type', 'Unknown').replace('_', ' ').title()}</strong>
                        <span style="color: #6b7280; font-size: 12px; margin-left: 8px;">· {tier_label}</span>
                    </div>
                    <code style="background-color: #e5e7eb; padding: 2px 6px; border-radius: 4px; font-size: 12px;">{change.get('field', 'N/A')}</code>
                    <code style="background-color: #e0e7ff; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 6px;">{change.get('endpoint', 'N/A')}</code>
                    <p style="margin: 8px 0 0 0; color: #4b5563; font-size: 13px;">{change.get('summary', '')}</p>
                </div>
                """
            if len(recent_changes) > 10:
                changes_html += f'<p style="color: #6b7280; font-size: 13px; text-align: center;">...and {len(recent_changes) - 10} more changes on the dashboard.</p>'
            recent_section = f"<p>Here's a snapshot of the most recent Stripe API changes we're tracking:</p><div style='margin: 20px 0;'>{changes_html}</div>"
        else:
            recent_section = "<p>No changes have been detected yet. You'll be the first to know when Stripe updates their API.</p>"

        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); padding: 24px; border-radius: 12px 12px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">Gateway Monitor</h1>
        <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0;">You're now subscribed to Stripe API alerts</p>
    </div>
    <div style="background-color: #ffffff; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
        <p>Hi {to_name},</p>
        <p>Welcome to <strong>Gateway Monitor</strong>! You'll receive email alerts whenever Stripe's API changes — new fields, removed parameters, updated types, and more across all tiers (Stable, Preview, Beta).</p>
        <div style="background-color: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 16px; margin: 20px 0;">
            <p style="margin: 0; font-size: 14px; color: #0369a1;">
                <strong>What you'll receive:</strong><br>
                · <strong>Instant alerts</strong> when new API changes are detected (daily monitoring)<br>
                · <strong>Weekly digest</strong> every Monday summarising the week's changes
            </p>
        </div>
        {recent_section}
        <p style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;">
            You subscribed with this email address. To unsubscribe, reply to this email.
        </p>
    </div>
</body>
</html>"""

        text_content = f"""Gateway Monitor — Welcome, {to_name}!

You're subscribed to Stripe API change alerts.

What you'll receive:
- Instant alerts when new API changes are detected
- Weekly digest every Monday

{'Recent changes:\n' + chr(10).join([f"- [{c.get('severity','info').upper()}] {c.get('type','Unknown')}: {c.get('field','N/A')} ({c.get('endpoint','N/A')}, {c.get('tier','stable')})" for c in recent_changes[:10]]) if recent_changes else 'No changes yet — you will be the first to know!'}
"""
        return self.send_email(to_email, subject, html_content, text_content)

    def send_weekly_digest(self, to_email: str, to_name: str, changes: List[Dict[str, Any]], week_start: str, week_end: str) -> bool:
        """Send weekly digest email"""

        if changes:
            subject = f"📊 Weekly Digest: {len(changes)} Stripe API Change{'s' if len(changes) > 1 else ''}"
            intro_text = f"Here's your weekly summary of Stripe API changes ({week_start} - {week_end}):"
        else:
            subject = "📊 Weekly Digest: No Changes This Week"
            intro_text = f"Good news! No Stripe API changes were detected this week ({week_start} - {week_end})."

        # Build changes HTML
        changes_html = ""
        if changes:
            for change in changes:
                severity_color = {
                    "high": "#dc2626",
                    "medium": "#f59e0b",
                    "low": "#3b82f6",
                    "info": "#6b7280"
                }.get(change.get("severity", "info"), "#6b7280")

                changes_html += f"""
                <div style="padding: 16px; margin-bottom: 12px; background-color: #f9fafb; border-radius: 8px; border-left: 4px solid {severity_color};">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="font-weight: 600;">{change.get('type', 'Unknown')}</span>
                        <span style="background-color: {severity_color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">
                            {change.get('severity', 'info').upper()}
                        </span>
                    </div>
                    <code style="background-color: #e5e7eb; padding: 2px 6px; border-radius: 4px; font-size: 13px;">{change.get('field', 'N/A')}</code>
                    <code style="background-color: #e0e7ff; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 8px;">{change.get('endpoint', 'N/A')}</code>
                    <span style="color: #6b7280; font-size: 13px; margin-left: 8px;">({change.get('tier', 'stable').capitalize()})</span>
                    <p style="margin: 8px 0 0 0; color: #4b5563; font-size: 14px;">{change.get('summary', 'No summary available')}</p>
                </div>
                """
        else:
            changes_html = """
            <div style="padding: 24px; text-align: center; background-color: #f0fdf4; border-radius: 8px; border: 1px solid #bbf7d0;">
                <p style="margin: 0; color: #166534; font-size: 16px;">✅ No API changes detected this week</p>
                <p style="margin: 8px 0 0 0; color: #4ade80; font-size: 14px;">Your integration remains stable</p>
            </div>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%); padding: 24px; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Gateway Monitor</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0;">Weekly Digest</p>
            </div>

            <div style="background-color: #ffffff; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p>Hi {to_name},</p>

                <p>{intro_text}</p>

                <div style="margin: 20px 0;">
                    {changes_html}
                </div>

                <p style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 14px;">
                    You're receiving this weekly digest because you subscribed to Gateway Monitor.
                </p>
            </div>
        </body>
        </html>
        """

        text_content = f"""
Gateway Monitor - Weekly Digest

Hi {to_name},

{intro_text}

""" + ("\n".join([
            f"- [{c.get('severity', 'info').upper()}] {c.get('type', 'Unknown')}: {c.get('field', 'N/A')}\n  Endpoint: {c.get('endpoint', 'N/A')} | Tier: {c.get('tier', 'stable')}\n  {c.get('summary', 'No summary')}"
            for c in changes
        ]) if changes else "No changes detected this week.")

        return self.send_email(to_email, subject, html_content, text_content)
