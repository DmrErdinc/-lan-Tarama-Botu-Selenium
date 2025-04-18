import asyncio
import time
import re
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from telegram import Bot
from config import TELEGRAM_TOKEN, CHAT_ID, SAHIBINDEN_URL, FİYAT_MIN, FİYAT_MAX

bot = Bot(token=TELEGRAM_TOKEN)
bildirilenler = set()

async def telegram_mesaj_gonder(mesaj):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=mesaj)
        print("📤 Telegram mesajı gönderildi.")
    except Exception as e:
        print("❌ Telegram mesajı gönderilemedi:", e)

async def telegram_dosya_gonder(dosya_yolu, mesaj):
    try:
        with open(dosya_yolu, "rb") as f:
            await bot.send_document(chat_id=CHAT_ID, document=f, caption=mesaj)
    except Exception as e:
        print("❌ Telegram'a dosya gönderilemedi:", e)

def sahibinden_ilanlari_tar():
    options = Options()
    #options.add_argument("--headless")  # Gerekirse aç kapat
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=options)
    driver.get(SAHIBINDEN_URL)

    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ekran_path = f"screenshot_{now}.png"
    html_path = f"sayfa_kodu_{now}.html"

    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tbody.searchResultsTable tr.searchResultsItem"))
        )
        time.sleep(1)

        # Debug log: ekran görüntüsü ve sayfa kaynağı
        driver.save_screenshot(ekran_path)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)

    except Exception as e:
        print("❌ Sayfa yüklenemedi:", e)
        driver.save_screenshot(ekran_path)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        driver.quit()
        return [], ekran_path, html_path

    sayfa = 1
    ilanlar = []

    while True:
        print(f"📄 Sayfa {sayfa} taranıyor...")
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, "tbody.searchResultsTable tr.searchResultsItem")
            if not rows:
                print("🚫 İlan bulunamadı.")
                break

            for row in rows:
                try:
                    fiyat_raw = row.find_element(By.XPATH, './/td[5]/div/span').text.strip()
                    fiyat_numbers = re.findall(r"[\\d\\.]+", fiyat_raw)
                    if not fiyat_numbers:
                        continue
                    fiyat_str = "".join(fiyat_numbers)
                    fiyat = float(fiyat_str.replace(".", ""))

                    if FİYAT_MIN <= fiyat <= FİYAT_MAX:
                        link_el = row.find_element(By.CSS_SELECTOR, "td.searchResultsTitleValue a")
                        link = link_el.get_attribute("href")
                        if not link or link in bildirilenler:
                            continue
                        aciklama = row.find_element(By.CSS_SELECTOR, "td.searchResultsTitleValue").text.strip()
                        ilanlar.append((aciklama, fiyat, link, sayfa))
                        bildirilenler.add(link)
                except Exception as e:
                    continue

            try:
                next_button = driver.find_element(By.CSS_SELECTOR, "a.next")
                if "disabled" in next_button.get_attribute("class"):
                    break
                next_button.click()
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "tbody.searchResultsTable tr.searchResultsItem"))
                )
                time.sleep(2)
                sayfa += 1
            except:
                break
        except Exception as e:
            print("⚠️ Sayfa hatası:", e)
            break

    driver.quit()
    return ilanlar, ekran_path, html_path

async def main():
    await telegram_mesaj_gonder("✅ Sahibinden ilan botu başlatıldı. Full debug açık patron...")

    while True:
        ilanlar, ekran_path, html_path = sahibinden_ilanlari_tar()

        await telegram_dosya_gonder(ekran_path, "🖼️ Sayfa ekran görüntüsü")
        await telegram_dosya_gonder(html_path, "📄 Sayfa HTML içeriği")

        if not ilanlar:
            await telegram_mesaj_gonder("🔍 Hiçbir uygun ilan bulunamadı patron.")
        else:
            for aciklama, fiyat, link, sayfa in ilanlar:
                mesaj = (
                    f"📄 Sayfa: {sayfa}\n"
                    f"💬 Açıklama: {aciklama}\n"
                    f"💰 Fiyat: {fiyat:,.0f} TL\n"
                    f"🔗 Link: {link}"
                )
                await telegram_mesaj_gonder(mesaj)

        print("⏳ 1 saat bekleniyor...\n")
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
