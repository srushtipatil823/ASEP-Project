from email_utils import send_email

result = send_email(
    "ranvirvpatil29@gmail.com",
    "Test Email",
    "This is a test email from Smart Food Rescue Network."
)

print(result)