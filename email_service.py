"""
Gmail OAuth 2.0 Email Service for FreshPlate Co.

Handles:
- OAuth 2.0 authorization flow (consent + token exchange)
- Token storage, refresh, and validation
- Sending branded HTML emails via the Gmail API

Tokens are stored in gmail_token.json alongside gmail_credentials.json
(both must be in .gitignore).
"""

import os
import json
import base64
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'gmail_credentials.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'gmail_token.json')

# We only need the "send" scope — no read access to the mailbox.
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# Human-readable labels for each order status, used in the email body.
STATUS_LABELS = {
    'received': 'Order Received',
    'logged': 'Order Logged',
    'in_preparation': 'In Preparation',
    'ready': 'Ready for Delivery',
    'delivered': 'Delivered'
}

# Color palette for status badges inside the HTML email.
STATUS_COLORS = {
    'received': '#6366f1',
    'logged': '#8b5cf6',
    'in_preparation': '#f59e0b',
    'ready': '#10b981',
    'delivered': '#059669'
}


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def credentials_file_exists():
    """Check if the downloaded Google Cloud OAuth credentials file is present."""
    return os.path.exists(CREDENTIALS_FILE)


def is_email_configured():
    """Return True if we have a valid (possibly refreshable) OAuth token."""
    if not os.path.exists(TOKEN_FILE):
        return False
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds and (creds.valid or creds.refresh_token):
            return True
    except Exception:
        pass
    return False


def get_connected_email():
    """Return the Gmail address that authorised the app, or None."""
    if not is_email_configured():
        return None
    try:
        service = _get_gmail_service()
        profile = service.users().getProfile(userId='me').execute()
        return profile.get('emailAddress')
    except Exception:
        return None


def initiate_oauth_flow(redirect_uri):
    """
    Start the OAuth 2.0 authorization-code flow.

    Returns (authorization_url, state, code_verifier) — the caller must redirect the
    admin's browser to `authorization_url`.
    """
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    code_verifier = getattr(flow, 'code_verifier', None)
    return authorization_url, state, code_verifier


def handle_oauth_callback(authorization_response, redirect_uri, state=None, code_verifier=None):
    """
    Exchange the authorization code for access + refresh tokens and
    persist them to TOKEN_FILE.
    """
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=redirect_uri
    )
    if code_verifier:
        flow.code_verifier = code_verifier
    flow.fetch_token(authorization_response=authorization_response)
    creds = flow.credentials

    # Persist tokens so the app survives restarts.
    with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
        f.write(creds.to_json())

    return True


def disconnect_email():
    """Remove stored tokens, effectively disconnecting the Gmail account."""
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


# ---------------------------------------------------------------------------
# Gmail API client
# ---------------------------------------------------------------------------

def _get_gmail_service():
    """
    Build and return an authorised Gmail API service object.

    Automatically refreshes the access token when expired.
    """
    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError('Gmail not connected. Please authorise via Email Settings.')

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        # Persist the refreshed token.
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            f.write(creds.to_json())

    if not creds.valid:
        raise RuntimeError('Gmail token is invalid. Please reconnect via Email Settings.')

    return build('gmail', 'v1', credentials=creds)


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

def _build_status_email_html(customer_name, order_id, new_status,
                              order_items, delivery_date, sender_name):
    """Return a complete HTML string for the order-status notification."""
    label = STATUS_LABELS.get(new_status, new_status.replace('_', ' ').title())
    color = STATUS_COLORS.get(new_status, '#6366f1')

    # Build the items table rows.
    items_rows = ''
    total = 0.0
    for item in (order_items or []):
        qty = float(item.get('quantity', 0))
        price = float(item.get('unit_price', 0))
        line_total = qty * price
        total += line_total
        items_rows += f'''
        <tr>
            <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:14px;color:#334155;">{item.get('product_name', 'Item')}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:14px;color:#334155;text-align:center;">{qty:g} {item.get('unit', '')}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:14px;color:#334155;text-align:right;">Rs. {price:,.2f}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:14px;color:#334155;text-align:right;">Rs. {line_total:,.2f}</td>
        </tr>'''

    # Status-specific message blurb.
    status_messages = {
        'received': 'We have received your order and it is now being processed. You will be notified as it progresses.',
        'ready': 'Great news! Your order is prepared and ready for delivery. Our delivery team will be on the way shortly.',
        'delivered': 'Your order has been delivered! We hope you enjoy your meal. Thank you for choosing us!'
    }
    blurb = status_messages.get(new_status, f'Your order status has been updated to <strong>{label}</strong>.')

    delivery_str = ''
    if delivery_date:
        if hasattr(delivery_date, 'strftime'):
            delivery_str = delivery_date.strftime('%A, %B %d, %Y')
        else:
            delivery_str = str(delivery_date)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:'Segoe UI',Roboto,Arial,sans-serif;">
<div style="max-width:600px;margin:30px auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,{color} 0%,#1e293b 100%);padding:32px 30px;text-align:center;">
        <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;letter-spacing:-0.5px;">🍽️ {sender_name}</h1>
        <p style="margin:8px 0 0;color:rgba(255,255,255,0.85);font-size:14px;">Order Status Update</p>
    </div>

    <!-- Status Badge -->
    <div style="text-align:center;padding:28px 30px 0;">
        <span style="display:inline-block;background:{color};color:#ffffff;padding:8px 24px;border-radius:50px;font-size:14px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase;">
            {label}
        </span>
    </div>

    <!-- Body -->
    <div style="padding:24px 30px;">
        <p style="color:#334155;font-size:16px;line-height:1.6;margin:0 0 8px;">
            Hi <strong>{customer_name}</strong>,
        </p>
        <p style="color:#64748b;font-size:15px;line-height:1.6;margin:0 0 20px;">
            {blurb}
        </p>

        <!-- Order Info -->
        <div style="background:#f8fafc;border-radius:12px;padding:18px 20px;margin-bottom:20px;">
            <table style="width:100%;border-collapse:collapse;">
                <tr>
                    <td style="padding:4px 0;color:#64748b;font-size:13px;">Order Number</td>
                    <td style="padding:4px 0;color:#0f172a;font-size:14px;font-weight:600;text-align:right;">#{order_id}</td>
                </tr>
                <tr>
                    <td style="padding:4px 0;color:#64748b;font-size:13px;">Delivery Date</td>
                    <td style="padding:4px 0;color:#0f172a;font-size:14px;font-weight:600;text-align:right;">{delivery_str}</td>
                </tr>
                <tr>
                    <td style="padding:4px 0;color:#64748b;font-size:13px;">Status</td>
                    <td style="padding:4px 0;font-size:14px;font-weight:600;text-align:right;">
                        <span style="color:{color};">{label}</span>
                    </td>
                </tr>
            </table>
        </div>

        <!-- Items Table -->
        {f"""
        <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
            <thead>
                <tr style="background:#f8fafc;">
                    <th style="padding:10px 14px;text-align:left;font-size:12px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Item</th>
                    <th style="padding:10px 14px;text-align:center;font-size:12px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Qty</th>
                    <th style="padding:10px 14px;text-align:right;font-size:12px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Price</th>
                    <th style="padding:10px 14px;text-align:right;font-size:12px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Total</th>
                </tr>
            </thead>
            <tbody>
                {items_rows}
            </tbody>
            <tfoot>
                <tr>
                    <td colspan="3" style="padding:12px 14px;text-align:right;font-size:14px;font-weight:700;color:#0f172a;">Grand Total</td>
                    <td style="padding:12px 14px;text-align:right;font-size:16px;font-weight:700;color:{color};">Rs. {total:,.2f}</td>
                </tr>
            </tfoot>
        </table>
        """ if order_items else ""}
    </div>

    <!-- Footer -->
    <div style="background:#f8fafc;padding:20px 30px;text-align:center;border-top:1px solid #e2e8f0;">
        <p style="margin:0 0 4px;color:#94a3b8;font-size:12px;">This is an automated message from {sender_name}.</p>
        <p style="margin:0;color:#94a3b8;font-size:12px;">Please do not reply to this email.</p>
    </div>

</div>
</body>
</html>'''
    return html


def send_order_status_email(to_email, customer_name, order_id, new_status,
                             order_items=None, delivery_date=None,
                             sender_name='FreshPlate Co.'):
    """
    Send a branded HTML email notifying the customer of their order status.

    Returns True on success, raises on failure.
    """
    service = _get_gmail_service()
    label = STATUS_LABELS.get(new_status, new_status.replace('_', ' ').title())
    subject = f'Order #{order_id} — {label} | {sender_name}'

    html_body = _build_status_email_html(
        customer_name, order_id, new_status,
        order_items, delivery_date, sender_name
    )

    message = MIMEMultipart('alternative')
    message['To'] = to_email
    message['Subject'] = subject
    # 'From' is set by Gmail automatically to the authorised account.

    # Plain-text fallback for clients that don't render HTML.
    plain_text = (
        f"Hi {customer_name},\n\n"
        f"Your order #{order_id} status has been updated to: {label}.\n\n"
        f"Thank you,\n{sender_name}"
    )
    message.attach(MIMEText(plain_text, 'plain'))
    message.attach(MIMEText(html_body, 'html'))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    service.users().messages().send(
        userId='me',
        body={'raw': raw}
    ).execute()

    return True


def send_test_email(to_email, sender_name='FreshPlate Co.'):
    """Send a quick test email to verify the Gmail OAuth connection works."""
    service = _get_gmail_service()
    subject = f'✅ Test Email from {sender_name}'

    html = f'''<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Roboto,Arial,sans-serif;">
<div style="max-width:500px;margin:30px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
    <div style="background:linear-gradient(135deg,#10b981 0%,#059669 100%);padding:28px 24px;text-align:center;">
        <h1 style="margin:0;color:#fff;font-size:22px;">✅ Connection Successful!</h1>
    </div>
    <div style="padding:24px;">
        <p style="color:#334155;font-size:15px;line-height:1.6;">
            This is a test email from <strong>{sender_name}</strong>.<br>
            Your Gmail OAuth integration is working correctly.
        </p>
        <p style="color:#64748b;font-size:13px;">
            Order status notifications will be sent from this Gmail account automatically.
        </p>
    </div>
    <div style="background:#f8fafc;padding:16px 24px;text-align:center;border-top:1px solid #e2e8f0;">
        <p style="margin:0;color:#94a3b8;font-size:12px;">Automated message from {sender_name}</p>
    </div>
</div>
</body></html>'''

    message = MIMEMultipart('alternative')
    message['To'] = to_email
    message['Subject'] = subject
    message.attach(MIMEText(f'Test email from {sender_name}. Gmail OAuth is working!', 'plain'))
    message.attach(MIMEText(html, 'html'))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    service.users().messages().send(userId='me', body={'raw': raw}).execute()

    return True


def send_email_in_background(to_email, customer_name, order_id, new_status,
                              order_items=None, delivery_date=None,
                              sender_name='FreshPlate Co.'):
    """
    Fire-and-forget wrapper. Sends the email in a daemon thread so the
    Flask request is not blocked.
    """
    def _worker():
        try:
            send_order_status_email(
                to_email, customer_name, order_id, new_status,
                order_items, delivery_date, sender_name
            )
        except Exception as e:
            # Log but don't crash — email failures must never block the order flow.
            print(f'[EMAIL ERROR] Failed to send status email for order #{order_id}: {e}')

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
