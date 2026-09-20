"""
Service for dispatching emails via AWS SES.
"""

import logging
from botocore.exceptions import ClientError
from models.circular import CanonicalCircular
from lib.aws import get_ses_client
from config import get_settings

logger = logging.getLogger(__name__)


def send_urgent_circular_email(circular: CanonicalCircular, recipients: list[str]) -> bool:
    """
    Constructs and sends an email for an urgent circular using AWS SES.
    Returns True if successfully sent, False otherwise.
    """
    settings = get_settings()
    
    if not settings.aws_enabled:
        logger.warning("AWS is disabled. Skipping email dispatch.")
        return False
        
    sender = settings.ses_sender_email
    
    if not sender:
        logger.warning("SES sender not configured. Skipping email dispatch.")
        return False
        
    if not recipients:
        logger.warning("No valid recipients provided. Skipping email dispatch.")
        return False

    title = circular.simplification.simplified_title or circular.source_metadata.title
    summary = circular.simplification.summary or "No summary available."
    
    # Construct the subject and body
    subject = f"URGENT: {title}"
    body_text = (
        f"A new urgent circular has been published.\n\n"
        f"Title: {title}\n"
        f"Source: {circular.source_metadata.department_name}\n"
        f"Summary: {summary}\n\n"
        f"Read more on the JanVaani portal."
    )
    
    body_html = f"""
    <html>
    <head></head>
    <body>
      <h2>URGENT: {title}</h2>
      <p><strong>Source:</strong> {circular.source_metadata.department_name}</p>
      <p><strong>Summary:</strong> {summary}</p>
      <br>
      <p>Please check the <a href="https://janvaani.in">JanVaani portal</a> for more details.</p>
    </body>
    </html>
    """

    try:
        client = get_ses_client()
        
        # SES limits recipients to 50 per call
        chunk_size = 50
        for i in range(0, len(recipients), chunk_size):
            chunk = recipients[i:i + chunk_size]
            response = client.send_email(
                Destination={
                    'BccAddresses': chunk,
                },
                Message={
                    'Body': {
                        'Html': {
                            'Charset': "UTF-8",
                            'Data': body_html,
                        },
                        'Text': {
                            'Charset': "UTF-8",
                            'Data': body_text,
                        },
                    },
                    'Subject': {
                        'Charset': "UTF-8",
                        'Data': subject,
                    },
                },
                Source=sender,
            )
            logger.info(f"Email sent! Message ID: {response['MessageId']}")
    except ClientError as e:
        logger.error(f"Failed to send email via SES: {e.response['Error']['Message']}")
        return False
    return True
