import os
from typing import Dict

import sendgrid
from sendgrid.helpers.mail import Email, Mail, Content, To
from agents import Agent, Runner, function_tool


@function_tool
def send_email(subject: str, html_body: str, email: str) -> Dict[str, str]:
    """Send an email with the given subject and HTML body"""
    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    from_email_address = os.environ.get("SENDGRID_FROM_EMAIL")

    if not sendgrid_api_key:
        raise RuntimeError("SENDGRID_API_KEY is not configured.")

    if not from_email_address:
        raise RuntimeError("SENDGRID_FROM_EMAIL is not configured.")

    sg = sendgrid.SendGridAPIClient(api_key=sendgrid_api_key)
    from_email = Email(from_email_address)
    to_email = To(email)
    content = Content("text/html", html_body)
    mail = Mail(from_email, to_email, subject, content).get()
    response = sg.client.mail.send.post(request_body=mail)
    print("Email response", response.status_code)
    return {"status": "success"}


subject_instructions = "You can write a subject for a cold sales email. \
You are given a message and you need to write a subject for an email that is likely to get a response."

html_instructions = "You can convert a text email body to an HTML email body. \
You are given a text email body which might have some markdown \
and you need to convert it to an HTML email body with simple, clear, compelling layout and design."

subject_writer = Agent(
    name="Email subject writer", instructions=subject_instructions, model="gpt-4o-mini"
)
subject_tool = subject_writer.as_tool(
    tool_name="subject_writer",
    tool_description="Write a subject for a cold sales email",
)

html_converter = Agent(
    name="HTML email body converter",
    instructions=html_instructions,
    model="gpt-4o-mini",
)
html_tool = html_converter.as_tool(
    tool_name="html_converter",
    tool_description="Convert a text email body to an HTML email body",
)

email_agent = Agent(
    name="Email Agent",
    instructions=(
        "You are an email formatter and sender. You receive the body of an email to be sent.\n"
        "You first use the subject_writer tool to write a subject for the email.\n"
        "Then use the html_converter tool to convert the body to HTML.\n"
        "Finally, you use the send_email tool to send the email with the subject and HTML body."
    ),
    tools=[subject_tool, html_tool, send_email],
    model="gpt-4o-mini",
    handoff_description="Convert an email to HTML and send it",
)


async def send_report_email(
    *,
    recipient_email: str,
    report_title: str,
    report_markdown: str,
) -> None:
    await Runner.run(
        email_agent,
        (
            f"Send this research report to {recipient_email}.\n\n"
            f"Report title: {report_title}\n\n"
            f"Report body:\n{report_markdown}"
        ),
    )
