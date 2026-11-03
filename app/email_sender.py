from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib


class EmailSender:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str | None,
        smtp_pass: str | None,
        email_from: str,
        logger: logging.Logger | None = None,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.email_from = email_from
        self.logger = logger or logging.getLogger("paper_digest.email")

    def send_html_email(self, recipients: list[str], subject: str, html_body: str) -> None:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.email_from
        message["To"] = ", ".join(recipients)
        message.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=20) as server:
                    self._login_if_needed(server)
                    server.sendmail(self.email_from, recipients, message.as_string())
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=20) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    self._login_if_needed(server)
                    server.sendmail(self.email_from, recipients, message.as_string())
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Failed to send HTML email via SMTP: %s", exc)
            raise

        self.logger.info("Email sent successfully to %s recipient(s)", len(recipients))

    def _login_if_needed(self, server: smtplib.SMTP) -> None:
        if self.smtp_user and self.smtp_pass:
            server.login(self.smtp_user, self.smtp_pass)
