#!/usr/bin/env python3
"""
Standalone script to send the daily curator digest.
Can be run via GitHub Actions or any cron scheduler.
"""

import os
import sys

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from database import get_all_quotes_with_articles
from services.digest_generator import generate_curator_digest
from services.email_sender import send_digest_email, is_email_configured


def main():
    print("Starting curator digest...")

    if not is_email_configured():
        print("ERROR: Email not configured. Set RESEND_API_KEY and USER_EMAIL.")
        sys.exit(1)

    # Get all quotes with article metadata
    quotes = get_all_quotes_with_articles()

    if not quotes:
        print("No quotes available for digest, skipping.")
        sys.exit(0)

    print(f"Found {len(quotes)} quotes")

    # Generate the digest
    digest = generate_curator_digest(quotes)

    if not digest:
        print("No suitable quote cluster found for digest.")
        sys.exit(0)

    # Send the email
    try:
        result = send_digest_email(digest["subject"], digest["html_body"])
        print(f"Curator digest sent successfully!")
        print(f"  Theme: {digest.get('theme')}")
        print(f"  Anchor: {digest.get('anchor_article')}")
        print(f"  Email ID: {result.get('id')}")
    except Exception as e:
        print(f"ERROR: Failed to send email: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
