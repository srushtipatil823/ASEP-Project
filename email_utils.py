import smtplib
from email.message import EmailMessage

EMAIL_ADDRESS = "smartfoodrescue@gmail.com"
EMAIL_PASSWORD = "qxrigbdfumbjcbjy"


def send_email(to_email, subject, message):

    msg = EmailMessage()

    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email

    msg.set_content(message)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)

        return True

    except Exception as e:
        print("Email Error:", e)
        return False