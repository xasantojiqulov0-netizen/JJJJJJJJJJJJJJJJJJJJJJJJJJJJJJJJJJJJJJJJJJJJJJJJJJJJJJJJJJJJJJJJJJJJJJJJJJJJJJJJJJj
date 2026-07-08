# 🕵️ Stalker Bot

Telegram bot — kim sizning profilingizga kirganini bilib oling.

## ⚙️ Imkoniyatlar

| Funksiya | Tavsif |
|---|---|
| 🪤 Tuzoq havola | Unikal havola, uni bosgan odam haqida darhol xabar olasiz |
| 👥 Kim bosdi | Havolangizni bosganlar ro'yxati (20 tasi) |
| ✏️ Tuzoq xabari | Bosgan odamga ko'rsatiladigan xabarni o'zingiz yozasiz |
| 💳 Obuna tizimi | 5 xil tarif, to'lov cheki orqali tasdiqlash |
| 👨‍💼 Admin panel | Statistika, karta, obuna berish, blok, reklama, Excel |

---

## 🚀 Railway'ga Deploy qilish

### 1. GitHub'ga yuklash

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/username/havolabot.git
git push -u origin main
```

> ⚠️ `.env` faylini commit qilmang — `.gitignore` da allaqachon bor.

### 2. Railway'da yangi project ochish

1. [railway.app](https://railway.app) ga kiring
2. **New Project → Deploy from GitHub repo** bosing
3. Repozitoriyangizni tanlang

### 3. PostgreSQL qo'shish

1. Project ichida **+ New → Database → PostgreSQL** bosing
2. Railway `DATABASE_URL` o'zgaruvchisini avtomatik qo'shadi

### 4. Environment Variables qo'shish

Railway project → **Variables** bo'limiga quyidagilarni qo'shing:

```
BOT_TOKEN=your_bot_token
ADMIN_ID=your_telegram_id
CARD_NUMBER=8600 1234 5678 9012
CARD_OWNER=Ism Familiya
PRICE_1_MONTH=30000
PRICE_3_MONTH=80000
PRICE_6_MONTH=150000
PRICE_9_MONTH=210000
PRICE_12_MONTH=270000
```

> `DATABASE_URL` ni qo'shmang — PostgreSQL plugin avtomatik qo'shadi.

### 5. Deploy

Variables saqlangandan so'ng Railway avtomatik deploy qiladi.  
**Logs** bo'limida `Bot starting... 🤖` ko'rsangiz — ishlayapti!

---

## 💻 Lokal ishlatish

```bash
# Virtual muhit yaratish
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac

# Kutubxonalarni o'rnatish
pip install -r requirements.txt

# .env faylni sozlash
copy .env.example .env
# .env ni oching va qiymatlarni to'ldiring

# Botni ishga tushirish
python main.py
```

---

## 📁 Loyiha tuzilmasi

```
havolabot/
├── main.py           — Asosiy fayl, bot va dispatcherni ishga tushiradi
├── config.py         — Environment o'zgaruvchilari
├── database.py       — SQLAlchemy modellari va yordamchi funksiyalar
├── keyboards.py      — InlineKeyboard'lar
├── middlewares.py    — DB session va obuna tekshiruvi
├── scheduler.py      — Obuna eslatma scheduler'i
├── handlers/
│   ├── user.py       — Foydalanuvchi handlerlari
│   └── admin.py      — Admin handlerlari
├── requirements.txt
├── Procfile          — Railway/Heroku uchun
└── runtime.txt       — Python versiyasi
```

---

## 🗄️ Ma'lumotlar bazasi

| Jadval | Tavsif |
|---|---|
| `users` | Foydalanuvchilar, obuna ma'lumotlari |
| `payments` | To'lovlar va ularning holati |
| `admin_cards` | To'lov kartalari |
| `trap_logs` | Tuzoqqa tushganlar tarixi |

---

## 👨‍💼 Admin buyruqlari

- `/admin` — Admin panelni ochish

**Admin panel imkoniyatlari:**
- 📊 Statistika — jami foydalanuvchilar, obunalar, daromad
- 💳 Karta qo'shish — yangi to'lov kartasini belgilash
- ⏳ Kutayotgan to'lovlar — tasdiqlash yoki rad etish
- 📋 Obuna berish — qo'lda ID va oylar orqali
- 🚫 Blok — foydalanuvchini bloklash/ochish
- 📢 Reklama — barcha foydalanuvchilarga xabar
- 📥 Excel — foydalanuvchilar ro'yxatini yuklab olish
