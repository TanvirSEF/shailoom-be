import resend
from app.core.config import settings
from app.core.logger import app_logger

# Initialize Resend SDK
resend.api_key = settings.resend_api_key

# --- Configurable Defaults ---
# This is the sender email. Typically, you need to verify a domain in Resend to use an email other than 'onboarding@resend.dev'
SENDER_EMAIL = "onboarding@resend.dev"


def send_order_confirmation(user_email: str, order_details: dict):
    """
    Sends a confirmation email to the customer immediately after checkout.
    """
    tracking_id = order_details.get("tracking_id", "Unknown")
    total = order_details.get("total_amount", 0)
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
        <h2 style="color: #333;">Thank You for Your Order!</h2>
        <p>Hi,</p>
        <p>We've successfully received your order at Shailoom.</p>
        
        <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p><strong>Tracking ID:</strong> {tracking_id}</p>
            <p><strong>Total Paid:</strong> ৳{total}</p>
            <p><strong>Status:</strong> Pending</p>
        </div>
        
        <p>We will notify you once your order is shipped.</p>
        <br>
        <p>Warm regards,</p>
        <p><strong>The Shailoom Team</strong></p>
    </div>
    """
    
    try:
        r = resend.Emails.send({
            "from": SENDER_EMAIL,
            "to": user_email,
            "subject": f"Order Confirmation - {tracking_id} | Shailoom",
            "html": html_content
        })
        app_logger.info(f"Order confirmation email sent to {user_email} for order {tracking_id}")
        return r
    except Exception as e:
        app_logger.error(f"Failed to send order confirmation to {user_email}: {e}")


def send_admin_new_order_alert(order_details: dict):
    """
    Sends an alert to the admin email when a new order is placed.
    """
    tracking_id = order_details.get("tracking_id", "Unknown")
    total = order_details.get("total_amount", 0)
    customer = order_details.get("user_email", "Guest")
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif;">
        <h2 style="color: #d9534f;">New Order Alert 🚨</h2>
        <p>You have received a new order on the store.</p>
        <ul>
            <li><strong>Order ID:</strong> {tracking_id}</li>
            <li><strong>Customer:</strong> {customer}</li>
            <li><strong>Total Value:</strong> ৳{total}</li>
        </ul>
        <p>Please log in to the admin dashboard to process this order.</p>
    </div>
    """
    
    try:
        r = resend.Emails.send({
            "from": SENDER_EMAIL,
            "to": settings.admin_email,
            "subject": f"🔥 New Order Received: {tracking_id}",
            "html": html_content
        })
        app_logger.info(f"Admin order alert sent for order {tracking_id}")
        return r
    except Exception as e:
        app_logger.error(f"Failed to send admin order alert: {e}")


def send_order_status_update(user_email: str, tracking_id: str, new_status: str):
    """
    Notifies the customer when an admin changes the status of their order (e.g., shipped, delivered, cancelled).
    """
    status_formatted = new_status.title()
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
        <h2 style="color: #333;">Order Status Update</h2>
        <p>Hi,</p>
        <p>Your Shailoom order <strong>{tracking_id}</strong> has been updated.</p>
        
        <div style="background-color: #f1f8e9; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #7cb342;">
            <p><strong>New Status:</strong> {status_formatted}</p>
        </div>
        
        <p>Thank you for shopping with us!</p>
        <p><strong>The Shailoom Team</strong></p>
    </div>
    """
    
    try:
        r = resend.Emails.send({
            "from": SENDER_EMAIL,
            "to": user_email,
            "subject": f"Update on your Shailoom order: {tracking_id}",
            "html": html_content
        })
        app_logger.info(f"Status update email ({new_status}) sent to {user_email} for order {tracking_id}")
        return r
    except Exception as e:
        app_logger.error(f"Failed to send status update to {user_email}: {e}")
