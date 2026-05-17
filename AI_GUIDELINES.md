# LvL Social Media Platform - Technical Guidelines & AI Context

Bu doküman, projeye sonradan dahil olacak geliştiriciler ve onlara asistanlık yapacak Yapay Zeka (AI) araçları (Cursor, Windsurf, GitHub Copilot vb.) için bir **"Sistem Bağlamı" (System Context)** olarak hazırlanmıştır. Projede herhangi bir değişiklik yapmadan önce bu kuralların eksiksiz okunması ve benimsenmesi zorunludur.

---

## 1. Teknoloji Yığını (Tech Stack) ve Gerekçeler
Proje, eski "PHP/MySQL + XAMPP" mimarisinden tamamen kopartılmış ve Serverless (Sunucusuz) mimariye geçirilmiştir.

*   **Backend:** `Python 3.9+` ve `Flask`. Hızlı prototipleme, temiz kod dizilimi ve zengin kütüphane desteği nedeniyle seçildi.
*   **Veritabanı (BaaS):** `Supabase` (PostgreSQL tabanlı). Eski XAMPP bağımlılığını yok etmek, ölçeklenebilir veritabanı yönetimi ve entegre RLS (Satır Seviyesi Güvenlik) sunması sebebiyle tercih edildi. İletişim `supabase-py` SDK'sı üzerinden sağlanır.
*   **Hosting/Deployment:** `Vercel`. Sitenin 7/24 ayakta kalması, sıfır sunucu bakımı gerektirmesi ve otomatik GitHub CI/CD süreçleri için kullanılıyor.
*   **Frontend:** HTML5, Jinja2 (Template Engine), Vanilla CSS ve Vanilla JavaScript. Ağır frontend frameworklerinden (React, Vue vb.) kaçınılarak performans ve sadelik hedeflendi.

---

## 2. Vercel & Supabase Standartları
*   **XAMPP Devri Kapandı:** Projede hiçbir şekilde `localhost:3306`, `mysqli`, `PDO` veya yerel veritabanı mantığı yoktur.
*   **Çevre Değişkenleri (Environment Variables):** Şifreler ve API anahtarları asla koda gömülmez (Hardcode edilmez). Her şey `os.getenv()` üzerinden çekilir. Gerekli Vercel değişkenleri:
    *   `SUPABASE_URL`
    *   `SUPABASE_KEY` (Anon Key - İsteğe bağlı)
    *   `SUPABASE_SECRET` (Service Role Key - Required)
    *   `FLASK_SECRET_KEY` (Oturum yönetimi için)
*   **RLS (Row Level Security) Aşımı:** Backend `app.py` dosyası Supabase'e bağlanırken `SUPABASE_SECRET` (Service Role) anahtarını kullanır. Bunun amacı Supabase RLS politikalarına takılmadan (Admin yetkisiyle) Python'un CRUD işlemlerini serbestçe yapabilmesini sağlamaktır. Bu bağlantı mantığı *değiştirilmemelidir*.

---

## 3. Dosya ve Mimari Kuralları
Flask mimarisinin Vercel üzerinde doğru çalışabilmesi için dosya konumu kuralları katıdır:
*   `templates/`: Tüm `.html` dosyaları sadece burada yer almalıdır. Alt klasör kabul edilmez.
*   `static/`: Tüm CSS (`.css`), JavaScript (`.js`), görseller (`.svg`, `.png`) ve Fontlar sadece burada yer almalıdır.
*   `vercel.json`: Vercel'in uygulamayı nasıl çalıştıracağını (Gunicorn entegrasyonu) ve tüm trafiklerin `app.py` üzerine yönlendirilmesini sağlayan kritik dosyadır. İçeriği kurcalanmamalıdır.
*   `requirements.txt`: Tüm Python kütüphaneleri burada güncel tutulmalıdır. Aksi halde Vercel Build esnasında çöker.

---

## 4. Özel Mekanizmalar ve Bilinmeyen Detaylar (Kritik)

Yeni geliştiricilerin bilmesi gereken, projeye özel yazılmış spesifik motorlar:

### A. XP ve Oyunlaştırma (Gamification) Motoru
`app.py` içerisindeki `award_xp` fonksiyonu, sistemin kalbidir. Kullanıcı her post attığında, yorum yaptığında veya beğeni attığında bu fonksiyon çağrılır.
*   Sistem `xp_events` tablosuna benzersiz bir log atar (aynı işlemden defalarca XP kazanılmasını engeller).
*   Kazanılan XP, kullanıcının `total_xp`'sini artırır ve `level_for_xp()` algoritması ile yeni seviyesi hesaplanır.
*   Seviye atlandığında otomatik olarak `badge_color` (Rozet Rengi) ve `activity_title` (Platform Legend vb. unvanlar) güncellenir.
**Kural:** Sisteme yeni bir etkileşim (örneğin "Hikaye paylaşma") eklerseniz, mutlaka arkasından `award_xp(user_id, 'story_created', 15)` fonksiyonunu tetiklemelisiniz.

### B. Vercel Serverless Timeout Koruması (Count Joins)
Vercel'in ücretsiz sürümünde Python fonksiyonları 10 saniye içinde yanıt vermelidir. Bir post listesi çekerken her post için ayrı ayrı "kaç like var, kaç yorum var" sorgusu atarsanız N+1 probleminden dolayı sunucu Timeout yer (504 hatası).
**Kural:** Veri çekerken her zaman PostgREST Count yapısını kullanın:
`select('*, user:users!posts_user_id_fkey(*), likes(count), comments(count), reposts(count)')`

### C. Global Error Handler
Projede herhangi bir Python hatası oluştuğunda beyaz bir "500 Internal Server Error" sayfası gelmemesi için `app.py` içinde bir traceback motoru bulunur. Hata anında ekrana hatanın *hangi satırda* ve *hangi Python dosyası sebebiyle* yaşandığı yazdırılır. Bu blok production'da hayat kurtarır, asla silmeyin.

---

## 5. AI ile Geliştirme İçin Prompt (İstem) Anahtar Kelimeleri

Bu projede başka bir AI (Örn: Cursor, Copilot) kullanacaksanız, promptlarınızın başına/sonuna (veya `.cursorrules` dosyasına) şu kuralları mutlaka ekleyin:

> **[PROMPT SYSTEM CONTEXT]**
> 1. Sen bir Python/Flask uzmanısın. Projede PHP veya MySQL yoktur, her şey `supabase-py` ile çalışır.
> 2. Asla statik dosyalara `<link href="/static/style.css">` şeklinde hardcode yol verme. Her zaman Jinja tagı kullan: `{{ url_for('static', filename='style.css') }}`.
> 3. Veritabanı sorgularında Supabase Client yapısını (`supabase.table('...').select('...').execute()`) kullan. Saf SQL sorguları üretme.
> 4. `app.py` üzerindeki bağlantı bloğuna (`SUPABASE_SECRET` arayan kısıma) dokunma, bu RLS bypass etmek için kritiktir.
> 5. Yeni bir HTML formu ekliyorsan, geri bildirim için her zaman Flask `flash()` mesajlarını kullan ve `redirect()` döndür, asla düz HTML döndürme.
> 6. Bir listeleme yapacaksan (Örn: Postlar), `users` tablosuyla olan yabancı anahtar ilişkisini joinlerken ambiguiti (belirsizlik) olmaması için her zaman belirteç kullan: `user:users!posts_user_id_fkey(*)`.
> 7. Yaptığın güncellemeler sonrasında `app.py` syntax'ının geçerli olup olmadığını daima kontrol et.
