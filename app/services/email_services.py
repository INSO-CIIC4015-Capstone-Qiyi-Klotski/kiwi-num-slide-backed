# app/services/email_service.py
import os
import re
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
SES_SENDER_EMAIL = os.getenv("SES_SENDER_EMAIL")

_ses = boto3.client("sesv2", region_name=AWS_REGION)

def _html_to_text(html: str) -> str:
    """
    Fallback muy simple para convertir HTML a texto.
    NO perfecto, pero suficiente para cuerpo de texto plano.
    """
    # Quita tags HTML
    text = re.sub(r"<[^>]+>", "", html)
    # Reemplaza múltiples espacios/saltos
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def send_simple_email(to_email: str, subject: str, html_body: str, text_body: str | None = None) -> str:
    if not text_body:
        text_body = _html_to_text(html_body)
    try:
        resp = _ses.send_email(
            FromEmailAddress=SES_SENDER_EMAIL,
            Destination={"ToAddresses": [to_email]},
            Content={
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                        "Text": {"Data": text_body, "Charset": "UTF-8"},
                    },
                }
            },
            ReplyToAddresses=[SES_SENDER_EMAIL],
        )
        return resp["MessageId"]
    except NoCredentialsError as e:
        # NO HAY CREDENCIALES DENTRO DEL CONTENEDOR
        raise RuntimeError("AWS credentials not found inside container") from e
    except ClientError as e:
        # Ver exactamente qué dijo SES (MessageRejected, etc.)
        msg = e.response.get("Error", {}).get("Message", str(e))
        raise RuntimeError(f"SES ClientError: {msg}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error sending email: {e}") from e
