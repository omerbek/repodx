# RepoDx

[![tests](https://github.com/omerbek/repodx/actions/workflows/tests.yml/badge.svg)](https://github.com/omerbek/repodx/actions/workflows/tests.yml)
[![repodx](https://img.shields.io/badge/repodx-A%20100%2F100-brightgreen)](https://github.com/omerbek/repodx)
[![Sponsor](https://img.shields.io/github/sponsors/omerbek?label=Sponsor&logo=GitHub)](https://github.com/sponsors/omerbek)

🇬🇧 [English](../README.md) · Bu, İngilizce README'nin çevirisidir. Güncel ve esas
sürüm [README.md](../README.md) dosyasıdır.

**Yapay zekâyla yazdığın projeyi push etmeden önce kontrol et.**
Tek komut, sıfır bağımlılık. Hiçbir veri bilgisayarından çıkmaz.

Cursor, Claude Code, Lovable, Bolt ve Replit gibi kodlama ajanları uygulamaları
hızla çıkarıyor. Ama API anahtarlarını kaynak koda yapıştırıyor, `.env`
dosyalarını commit'liyor, Supabase tablolarını Row Level Security (RLS) olmadan
oluşturuyor ve Firebase kurallarını herkese açık bırakıyorlar. 2025'te herkese
açık GitHub commit'lerinde yaklaşık 28,6 milyon yeni gizli anahtar sızdı. Sızan
yapay zekâ servis anahtarları bir yılda %81 arttı
([GitGuardian, State of Secrets Sprawl 2026](https://blog.gitguardian.com/the-state-of-secrets-sprawl-2026/)).
Botlar sızan bir anahtarı dakikalar içinde bulur.

RepoDx proje klasörünü tarar, projeye bir puan verir ve her sorunun nasıl
düzeltileceğini sade bir dille anlatır.

![RepoDx örnek bir projeyi tarıyor](demo.svg)

## Kurulum

PyPI'dan, izole bir araç yöneticisiyle kur:

```bash
pipx install repodx
# or
uv tool install repodx
```

Hiçbir şey kurmadan bir kez çalıştır (tek gereksinim Python 3.9+):

```bash
curl -sSL https://github.com/omerbek/repodx/releases/latest/download/repodx.py | python3 - .
```

Etiketli GitHub sürümünü doğrudan kur:

```bash
pipx install git+https://github.com/omerbek/repodx@v0.5.0
# or
uv tool install git+https://github.com/omerbek/repodx@v0.5.0
```

Windows'ta `repodx.py` dosyasını indirip `python repodx.py .` ile de
çalıştırabilirsin.

## Kullanım

```bash
repodx                    # scan the current folder
repodx path/to/project    # scan another folder
repodx --fix              # apply safe fixes, then scan again
repodx --prompt           # prompt to paste into Cursor, Claude Code or Lovable
repodx --install-hook     # block commits with critical findings
repodx --json             # machine-readable output
repodx --quiet            # one-line score for scripts and hooks
repodx --format markdown  # report for PR comments or CI summaries
repodx --badge            # print a README badge with your score
repodx --fail-on critical # only fail on critical findings (default: warning)
```

Çıkış kodları:

- `0`: `--fail-on` seviyesinde veya üstünde bir sorun bulunmadı.
- `1`: böyle bir sorun bulundu.
- `2`: verilen yol bir klasör değil.

### Düzelt

**`repodx --fix`** her zaman güvenli olan düzeltmeleri uygular ve sonra projeyi
yeniden tarar:

- `.gitignore` dosyasına eksik satırları ekler (`.env`, `node_modules/`,
  `*.log`, ...). Dosya yoksa oluşturur.
- `.env` dosyalarındaki ve koddaki değişken adlarıyla, değerleri boş bırakılmış
  bir `.env.example` oluşturur.

Hiçbir dosyayı silmez, Git geçmişine dokunmaz ve kodunu değiştirmez. Geri
kalanlar için ne yapman gerektiğini yazar: Git'in zaten takip ettiği dosyalar
için `git rm -r --cached`, sızan anahtarlar için de anahtarı yenilemek gibi.
İki kez çalıştırmak hiçbir şeyi değiştirmez.

**`repodx --prompt`**, yapay zekâ kodlama aracın için bir prompt yazdırır. Prompt'ta
her sorun konumu ve düzeltmesiyle birlikte yer alır. Ayrıca "gizli değerleri
asla yazdırma veya commit'leme" ve "işin bitince `repodx .` çalıştır" gibi
kurallar da içerir. Cursor, Claude Code, Lovable veya Bolt'a yapıştırabilirsin.

**`repodx --install-hook`** bir Git `pre-commit` hook'u kurar. Hook, stage'e
alınmış (staged) içeriği kontrol eder. Bu sayede stage'e alınmış bir anahtarı,
commit'ten önce çalışma dizininden silsen bile yakalar. Stage'e alınmamış
alakasız dosyaları yok sayar. Sızmış bir anahtar veya ignore edilmemiş bir
`.env` dosyası gibi kritik bir bulgu varsa commit engellenir. Kontrolü bir
kereliğine atlamak için `git commit --no-verify` kullan. RepoDx, kendisinin
kurmadığı bir `pre-commit` hook'unun üzerine yazmaz.

Stage'e alınmış içeriği elle taramak için **`repodx --staged`** çalıştır. Bu
mod dosya içeriklerini ve boyutlarını kontrol eder. Depo genelindeki README,
lisans ve `.gitignore` kontrollerini çalıştırmaz.

### GitHub Action

```yaml
# .github/workflows/repodx.yml
name: repodx
on: [push, pull_request]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: omerbek/repodx@v0.5.0
        with:
          fail-on: warning # critical, warning, info or never
```

Action, raporu job özetine yazar ve sorun bulursa job'u başarısız sayar.

### pre-commit hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/omerbek/repodx
    rev: v0.5.0
    hooks:
      - id: repodx
```

### Rozet

`repodx --badge` çalıştır ve çıktıyı README'ne yapıştır:

```markdown
[![repodx](https://img.shields.io/badge/repodx-A%2094%2F100-brightgreen)](https://github.com/omerbek/repodx)
```

## Neleri kontrol eder

| Önem | Kontrol |
| --- | --- |
| kritik | API anahtarları ve token'lar: OpenAI, Anthropic, OpenRouter, Perplexity, Replicate, Groq, Hugging Face, AWS, GitHub, GitLab, npm, PyPI, Stripe, Supabase gizli anahtarları, Shopify, DigitalOcean, Slack, SendGrid, Telegram botları, özel anahtarlar (private key) |
| kritik | Slack ve Discord webhook URL'leri |
| kritik / uyarı | Tarayıcıya giden public önekli, gizli anahtar gibi görünen değişken adları (`NEXT_PUBLIC_OPENAI_API_KEY`, `VITE_STRIPE_SECRET_KEY`, `EXPO_PUBLIC_..._SERVICE_ROLE_KEY`), değerleri boş olsa bile |
| kritik | Supabase `service_role` JWT'leri (rolü kontrol etmek için JWT çözülür; herkese açık `anon` anahtarları raporlanmaz) |
| kritik | Gerçek parola içeren veritabanı URL'leri (`postgres://`, `mysql://`, `mongodb+srv://`, `redis://` ...). Yerel adresler ve yer tutucular hariçtir. |
| kritik | Ignore edilmemiş `.env` ve `.env.local` dosyaları (`.env.production` gibi diğer varyantlar ve yalnızca `NEXT_PUBLIC_`/`VITE_` değişkenleri içeren dosyalar uyarıdır) |
| kritik | Herkesin yazmasına izin veren Firebase `firestore.rules`, `storage.rules` veya `database.rules.json` (herkese açık okuma bilgi olarak raporlanır) |
| kritik / uyarı | 100 MB'tan büyük dosyalar (GitHub bunları reddeder) ve 50 MB'tan büyük dosyalar |
| uyarı | Google API anahtarları (Firebase web anahtarıysa herkese açıktır; Gemini, Maps veya Cloud anahtarıysa gizlidir) |
| uyarı | `enable row level security` olmadan tablo oluşturan Supabase migration'ları |
| uyarı | Commit'lenmiş gereksiz dosyalar: `node_modules/`, `__pycache__/`, sanal ortamlar, `dist/`, `.next/`, `coverage/`, `.log`, `.tmp`, `.DS_Store` |
| uyarı | Eksik `.gitignore` ya da eksik `.env`, `node_modules/` ve `__pycache__/` satırları |
| uyarı | Eksik README veya LICENSE |
| bilgi | Kod ortam değişkeni okuyor ama `.env.example` yok |
| bilgi | Installation veya Usage bölümü olmayan README (İngilizce ve Türkçe başlıklar tanınır) |
| bilgi | 300 satırı aşan `AGENTS.md` veya `CLAUDE.md` (kodlama ajanları uzun talimat dosyalarını göz ardı etme eğilimindedir) |

Yanlış alarmları az tutmak için RepoDx:

- dokümantasyon yer tutucusu gibi görünen değerleri (`AKIAIOSFODNN7EXAMPLE`,
  `[YOUR-PASSWORD]`, `xoxb-0000...`, `-----BEGIN PRIVATE KEY-----\n...`) ve yerel
  Supabase CLI'ın herkese açık demo anahtarlarını atlar
- test ve örnek klasörlerindeki anahtarları ve `.env` dosyalarını kritik değil
  uyarı olarak raporlar
- `.gitignore` içinde `node_modules/` satırını yalnızca `package.json` varsa,
  `__pycache__/` satırını da yalnızca Python dosyaları varsa bekler

RepoDx, `!` ile başlayan geri dahil etme kuralları da dahil olmak üzere
`.gitignore` dosyanı okur. Git'in commit'lemeyeceği dosyalar raporlanmaz,
ignore edilen klasörler taranmaz. Bulunan anahtarlar çıktıda maskelenir
(`sk-pro...l2`).

Puan 100'den başlar. Her kritik bulgu 25, her uyarı 8, her bilgi 2 puan düşürür.
Her sorun türü en fazla üç kez sayılır.
Notlar: A ≥ 90, B ≥ 80, C ≥ 65, D ≥ 50, F 50'nin altı.

## Gerçek projelerde test edildi

Her sürümden önce RepoDx, yanlış alarmları yakalamak için büyük açık kaynak
depolarda çalıştırılır. 0.3.0 sonuçları:

| Depo | Dosya | Süre | Kritik | Sonuç |
| --- | ---: | ---: | ---: | --- |
| vercel/ai-chatbot | 181 | 0,1 sn | 0 | 100 (A) |
| langchain-ai/langchain | 3.165 | 2,3 sn | 0 | 98 (A) |
| fastapi/fastapi | 3.139 | 1,6 sn | 0 | 90 (A) |
| openai/openai-cookbook | 3.601 | 3,1 sn | 0 | 50 MB'ı aşan dört veri dosyası |
| psf/requests | 128 | 0,2 sn | 0 | test sertifikalarının özel anahtarları (uyarı) |
| supabase/supabase | 17.564 | 6,9 sn | 0 | RLS'siz örnek tablolar, örnek `.env` dosyaları |
| vercel/next.js | 32.215 | 7,5 sn | 0 | örnek `.env` dosyaları, test sertifikaları |
| firebase/quickstart-js | 436 | 0,3 sn | 1 | `database.rules.json` içinde `".write": true` (gerçek bulgu) |

Bu kontrollerin ilk sürümü aynı depolarda 136 kritik alarm vermişti. Neredeyse
hepsi dokümantasyon yer tutucuları ve test verileriydi. Onları elemek için
yukarıdaki kurallar eklendi.

## Yanlış alarmları susturma

- O satırı atlamak için satırdaki bir yoruma `repodx:ignore` ekle.
- Test verileri gibi bütün yolları atlamak için bir `.repodxignore` dosyası
  ekle (gitignore sözdizimi):

  ```gitignore
  tests/fixtures/
  docs/examples/*.md
  ```

## RepoDx'in yapmadıkları

- Git geçmişini değil, klasördeki dosyaları tarar. Bir anahtar bir kez bile
  push edildiyse onu yenile. Dosyayı silmek anahtarı geçmişten kaldırmaz.
  Geçmişi taramak için [Gitleaks](https://github.com/gitleaks/gitleaks) veya
  [TruffleHog](https://github.com/trufflesecurity/trufflehog) kullan.
- Canlı Supabase veya Firebase projene bağlanmaz. RLS ve kural kontrolleri
  yalnızca depondaki dosyaları okur.
- Hızlı bir ilk kontroldür, tam bir güvenlik denetimi değildir.

## Katkıda bulunma

İlk kez katkı verenleri memnuniyetle bekliyoruz. Her
[good first issue](https://github.com/omerbek/repodx/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
küçük ve kendi içinde tamamlanan bir iştir. Genellikle testiyle birlikte tek
bir anahtar sağlayıcısı eklemektir ve hangi satırların değişeceğini tam olarak
anlatır. Üstlenmek için issue'ya yorum yaz, sonra PR aç. Ayrıntılar için
[CONTRIBUTING.md](../CONTRIBUTING.md) dosyasına bak.

Yanlış alarm veya gözden kaçan bir anahtar mı buldun? İlgili satırla birlikte
(anahtarı değiştirerek) [bir issue aç](https://github.com/omerbek/repodx/issues/new/choose).

### Katkıda bulunanlar

RepoDx'i daha iyi yapan herkese teşekkürler:

[![Contributors](https://contrib.rocks/image?repo=omerbek/repodx)](https://github.com/omerbek/repodx/graphs/contributors)

## Destek

RepoDx ücretsizdir ve MIT lisanslıdır. Seni sızmış bir anahtardan kurtardıysa:

- Depoya yıldız ver. Başkalarının bulmasına yardımcı olur.
- Yanlış alarmları ve gözden kaçan sorunları [issue](https://github.com/omerbek/repodx/issues) olarak bildir.
- GitHub'da sponsor ol: https://github.com/sponsors/omerbek
- Bu Ethereum adresine bağış yapabilirsin (Ethereum ana ağında ETH veya ERC-20 token):

  ```text
  0xb74e0A471bC60BB52067353C024e9bBA5a123F48
  ```

## Geliştirme

RepoDx bağımlılığı olmayan tek bir Python dosyasıdır, bu yüzden okuması ve
genişletmesi kolaydır. Her kontrol, `repodx.py` içinde bulgu döndüren küçük
bir fonksiyondur.

`sample_repo/` klasörü bilerek bozuk bırakılmıştır ve içindeki bütün anahtarlar
sahtedir. Testlerde ve yukarıdaki örnekte kullanılır.

Testleri çalıştır:

```bash
python3 -m unittest discover
```

Yeni bir kontrol eklemek için:

1. `make_finding(...)` sonuçları döndüren bir fonksiyon yaz.
2. Düzeltme metnini `FIXES` sözlüğüne ekle.
3. Fonksiyonu `build_report` içinden çağır.
4. `tests/test_repodx.py` içine bir test ekle.
