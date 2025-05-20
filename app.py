import streamlit as st
import schedule
import threading
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from pymongo import MongoClient
from datetime import datetime
from collections import Counter
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
from nltk.tokenize import word_tokenize
import nltk
import pandas as pd
import matplotlib.pyplot as plt
from wordcloud import WordCloud


custom_stopwords = [
    "menjadi", "lebih", "banyak", "memiliki", "dapat", "akan", "dengan",
    "adalah", "karena", "juga", "seperti", "dalam", "yang", "untuk", "oleh",
    "sudah", "masih", "namun", "hingga", "tanpa", "pada", "bahwa", "agar", "berbagai", "orang", 
    "memberikan", "kompasiana", "komentar", "selanjutnya"
]

nltk.download('punkt_tab')

# Fungsi MongoDB
def save_to_mongodb(data, db_name="artikel_db", collection_name="test"):
    client = MongoClient("mongodb+srv://test:test123@cluster1.bv983sn.mongodb.net/?retryWrites=true&w=majority&appName=Cluster1")
    db = client[db_name]
    collection = db[collection_name]
    if collection.count_documents({"url": data["url"]}) == 0:
        collection.insert_one(data)
        st.write(f"[\u2713] Disimpan: {data['title']}")
        return True
    else:
        st.write(f"[=] Sudah ada: {data['title']}")
        return False

# Fungsi ambil artikel
def crawl_article(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('h1').text if soup.find('h1') else 'No Title'
        paragraphs = soup.find_all('p')
        content = "\n".join([p.text for p in paragraphs])
        return {'url': url, 'title': title, 'content': content}
    except Exception as e:
        st.write(f"[ERROR] Gagal crawling artikel: {e}")
        return None

# Fungsi utama crawling
def crawl_kompasiana():
    st.write(f"\U0001F680 Memulai crawling pada {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    url = "https://www.kompasiana.com/tag/fashion"
    driver.get(url)
    time.sleep(2)

    max_click = 50
    for i in range(max_click):
        try:
            load_more = driver.find_element(By.ID, "load-more-index-tag")
            driver.execute_script("arguments[0].click();", load_more)
            time.sleep(3)
        except:
            break

    soup = BeautifulSoup(driver.page_source, "html.parser")
    articles = soup.find_all("div", class_="timeline--item")
    st.write(f"📄 Artikel ditemukan: {len(articles)}")

    for item in articles:
        try:
            content_div = item.find("div", class_="artikel--content")
            if not content_div:
                continue
            title_tag = content_div.find("h2")
            if title_tag and title_tag.a:
                url = title_tag.a['href'].strip()
                detail = crawl_article(url)
                if detail:
                    baru = save_to_mongodb(detail)
                    if not baru:
                        continue
        except Exception as e:
            st.write(f"[ERROR] {e}")

    driver.quit()
    st.write("\u2705 Selesai crawling.\n")

# Scheduler
def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Fungsi load dan analisis artikel dari MongoDB
def load_articles_from_mongodb(db_name="artikel_db", collection_name="test"):
    client = MongoClient("mongodb+srv://test:test123@cluster1.bv983sn.mongodb.net/?retryWrites=true&w=majority&appName=Cluster1")
    db = client[db_name]
    collection = db[collection_name]
    return list(collection.find())

# Fungsi untuk preprocessing teks
def preprocess_text_list(text_list):
    factory = StopWordRemoverFactory()
    default_stopwords = factory.get_stop_words()
    stopword_list = set(default_stopwords + custom_stopwords)

    data_casefolding = pd.Series([text.lower() for text in text_list])
    filtering = data_casefolding.str.replace(r'[\W_]+', ' ', regex=True)
    data_tokens = [word_tokenize(line) for line in filtering]

    def stopword_filter(line):
        return [word for word in line if word not in stopword_list]

    data_stopremoved = [stopword_filter(tokens) for tokens in data_tokens]
    return data_stopremoved

# visualisasi
def plot_top_words_line(top_words):
    words, counts = zip(*top_words)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(words, counts, color='black', marker='o', linewidth=2)
    ax.set_xlabel("Kata")
    ax.set_ylabel("Frekuensi")
    ax.set_title("10 Kata Paling Sering Muncul (Line Chart)")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    return fig

def plot_top_words_bar(top_words):
    words, counts = zip(*top_words)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(words, counts, color='skyblue')
    ax.set_xlabel("Frekuensi")
    ax.set_title("10 Kata Paling Sering Muncul (Bar Chart Horizontal)")
    plt.tight_layout()
    return fig

def plot_wordcloud(word_counts):
    wc = WordCloud(width=800, height=400, background_color='white')
    wc.generate_from_frequencies(dict(word_counts))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wc, interpolation='bilinear')
    ax.axis("off")
    plt.tight_layout()
    return fig


# Streamlit App UI
st.title("📰 Auto Crawler + Analisis Artikel Kompasiana")
st.write("Crawling artikel dan menganalisis kata yang sering muncul")

st.sidebar.title("⚙ Pengaturan")
interval = st.sidebar.selectbox("⏱ Interval Crawling:", ["1 jam", "2 jam", "5 jam", "12 jam", "24 jam"])

if st.sidebar.button("✅ Aktifkan Jadwal"):
    hours = int(interval.split()[0])
    schedule.every(hours).hours.do(crawl_kompasiana)
    st.sidebar.success(f"Crawling dijadwalkan setiap {hours} jam.")
    scheduler_thread = threading.Thread(target=run_schedule, daemon=True)
    scheduler_thread.start()

if st.sidebar.button("🚀 Jalankan Sekarang"):
    crawl_kompasiana()

# Analisis kata
st.header("📊 Analisis Kata Paling Sering Muncul")
articles = load_articles_from_mongodb()
st.write(f"📚 Total artikel di database: {len(articles)}")
contents = [article['content'] for article in articles if article.get('content')]

if contents:
    factory = StopWordRemoverFactory()
    ind_stopword = factory.get_stop_words()
    st.info("🔄 Melakukan preprocessing dan analisis...")
    processed_tokens_list = preprocess_text_list(contents)
    all_tokens = [token for tokens in processed_tokens_list for token in tokens]
    word_counts = Counter(all_tokens)
    top_words = word_counts.most_common(10)

    st.subheader("🔍 Top 10 Kata")
    st.write(top_words)

    st.subheader("📈 Visualisasi Frekuensi Kata (Line Chart)")
    fig_line = plot_top_words_line(top_words)
    st.pyplot(fig_line)

    st.subheader("📊 Visualisasi Bar Chart Horizontal")
    fig_bar = plot_top_words_bar(top_words)
    st.pyplot(fig_bar)

    st.subheader("☁️ Word Cloud")
    fig_wc = plot_wordcloud(word_counts)
    st.pyplot(fig_wc)

else:
    st.warning("Belum ada konten artikel yang tersedia untuk dianalisis.")
