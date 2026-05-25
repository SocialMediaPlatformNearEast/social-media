import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

from app_theme import THEME_COLORS

load_dotenv()

sender = os.getenv("MAIL_USERNAME")
password = os.getenv("MAIL_PASSWORD")

print(f"Sender: {sender}")
print(f"Password (first 4 chars): {password[:4] if password else 'NOT FOUND'}...")

# Test email - kendi mailinizi buraya yazın
test_recipient = input("Test gönderilecek e-posta adresinizi girin: ")

msg = MIMEMultipart()
msg['From'] = sender
msg['To'] = test_recipient
msg['Subject'] = "LvL - Test Email Verification"

html = f"<html><body><h1 style='color:{THEME_COLORS['primary']}'>Test Başarılı!</h1><p>LvL mail sistemi çalışıyor.</p></body></html>"
msg.attach(MIMEText(html, 'html', 'utf-8'))

try:
    print("\nGmail SMTP'ye bağlanılıyor...")
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    print("TLS başlatıldı. Giriş yapılıyor...")
    server.login(sender, password)
    print("Giriş başarılı! Mail gönderiliyor...")
    server.sendmail(sender, test_recipient, msg.as_string())
    server.quit()
    print(f"\n✅ BAŞARILI! Mail {test_recipient} adresine gönderildi.")
except Exception as e:
    print(f"\n❌ HATA: {e}")
