# create_admin.py
from supabase import create_client
import bcrypt

SUPABASE_URL = "https://epvtsaowyizuhvrwcrmp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVwdnRzYW93eWl6dWh2cndjcm1wIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgyMDM1MDksImV4cCI6MjA5Mzc3OTUwOX0.ml5qsuihROtn5CA1o6PwD_nrRqpv4yX_kPsYiZya264"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

pw = "admin1234".encode()
hashed = bcrypt.hashpw(pw, bcrypt.gensalt()).decode()

sb.table("users").insert({
    "username":      "admin",
    "password_hash": hashed,
    "name":          "관리자",
    "email":         "junyoung70621@gmail.com",
    "phone":         "01055504635",
    "role":          "admin",
    "center":        "자재센터",
    "is_approved":   True
}).execute()

print("관리자 계정 생성 완료!")