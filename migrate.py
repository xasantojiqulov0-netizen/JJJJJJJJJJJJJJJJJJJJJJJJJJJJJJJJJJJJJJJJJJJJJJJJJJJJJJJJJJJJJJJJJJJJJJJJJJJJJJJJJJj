import sqlite3

conn = sqlite3.connect("stalker.db")
cur = conn.cursor()

# users jadvalidagi ustunlarni tekshirish
cur.execute("PRAGMA table_info(users)")
cols = [row[1] for row in cur.fetchall()]
print("users ustunlari:", cols)

if "decoy_message" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN decoy_message TEXT")
    print("✅ decoy_message qo'shildi")

if "is_blocked" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN is_blocked BOOLEAN NOT NULL DEFAULT 0")
    print("✅ is_blocked qo'shildi")

# trap_logs jadvali
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trap_logs'")
if not cur.fetchone():
    cur.execute("""
        CREATE TABLE trap_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id BIGINT NOT NULL,
            visitor_id BIGINT NOT NULL,
            visitor_name VARCHAR(128) NOT NULL,
            visitor_username VARCHAR(64),
            clicked_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ trap_logs jadvali yaratildi")
else:
    print("ℹ️  trap_logs allaqachon mavjud")

# tariffs jadvali
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tariffs'")
if not cur.fetchone():
    cur.execute("""
        CREATE TABLE tariffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label VARCHAR(64) NOT NULL,
            months INTEGER NOT NULL,
            price INTEGER NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
    """)
    print("✅ tariffs jadvali yaratildi")
else:
    print("ℹ️  tariffs allaqachon mavjud")

# payments.tariff_id — eski qiymatlarga tegmaymiz (string edi, endi int)
# Eski DB bo'lsa payments jadvalini qayta yaratishga hojat yo'q,
# yangi payment'lar tariff.id (int) saqlanadi.

conn.commit()
conn.close()
print("\n✅ Migration tugadi!")
