import dns.resolver
import smtplib
import socket
import logging

logger = logging.getLogger(__name__)

def verify_email(email: str) -> bool:
    """
    Verifies an email address by checking its MX records and performing
    a simulated SMTP handshake. Returns True if likely valid, False otherwise.
    """
    if not email or "@" not in email:
        return False
        
    domain = email.split('@')[1]
    
    # 1. DNS MX Record Check
    try:
        records = dns.resolver.resolve(domain, 'MX')
        mx_record = str(records[0].exchange)
    except Exception as e:
        logger.warning(f"DNS MX lookup failed for {domain}: {e}")
        return False

    # 2. SMTP Handshake (optional, best effort)
    try:
        # Some servers might block connections if not from a reputable IP.
        # We'll use a short timeout.
        server = smtplib.SMTP(timeout=3)
        server.set_debuglevel(0)
        
        # SMTP Conversation
        server.connect(mx_record)
        server.helo(server.local_hostname) 
        server.mail('test@example.com')
        code, message = server.rcpt(str(email))
        server.quit()
        
        # Assume 250 is Success
        if code == 250:
            return True
        else:
            logger.warning(f"SMTP verification failed for {email} with code {code}: {message}")
            return False
    except smtplib.SMTPServerDisconnected:
        logger.warning(f"SMTP disconnected abruptly for {domain}.")
        return True # Fallback to true if server doesn't allow probing
    except smtplib.SMTPConnectError:
        logger.warning(f"Failed to connect to SMTP server for {domain}.")
        return False
    except socket.timeout:
        logger.warning(f"SMTP connection timed out for {domain}.")
        return True # Timeout means server exists but is slow/blocking, assume valid
    except Exception as e:
        logger.warning(f"SMTP validation exception for {email}: {e}")
        return True # Fallback to true if we hit a generic error to avoid false negatives

if __name__ == "__main__":
    test_email = "test@sonictch.com"
    print(f"Verifying {test_email}: {verify_email(test_email)}")
