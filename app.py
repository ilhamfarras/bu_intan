import os
import streamlit as st
import schedule
import threading
import time
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from datetime import datetime
from collections import Counter
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
from nltk.tokenize import word_tokenize
import nltk
import pandas as pd
import matplotlib.pyplot as plt
import re

nltk.download('punkt_tab')

# Daftar stopwords tambahan
custom_stopwords = [
    "menjadi", "lebih", "banyak", "memiliki", "dapat", "akan", "dengan",
    "adalah", "karena", "juga", "seperti", "dalam", "yang", "untuk", "oleh",
    "sudah", "masih", "namun", "hingga", "tanpa", "pada", "bahwa", "agar", 
    "berbagai", "orang", "memberikan", "kompasiana", "komentar", "selanjutnya","ن","ا",
]

# Koneksi MongoDB
def get_mongo_client():
    mongo_uri = st.secrets["MONGODB"]["CONNECTION_STRING"]
    return MongoClient(mongo_uri)

def save_to_mongodb(data, db_name="artikel_db", collection_name="test"):
    client = get_mongo_client()
    db = client[db_name]
    collection = db[collection_name]
    data['created_at'] = datetime.now()
    if collection.count_documents({"url": data["url"]}) == 0:
        collection.insert_one(data)
        st.write(f"[✓] Disimpan: {data['title']}")
        return True
    else:
        st.write(f"[=] Sudah ada: {data['title']}")
        return False

# Ambil konten artikel
def crawl_article(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('h1').text if soup.find('h1') else 'No Title'
        paragraphs = soup.find_all('p')
        content = "\n".join([p.text for p in paragraphs])
        return {'url': url, 'title': title, 'content': content}
    except Exception as e:
        st.write(f"[ERROR] Gagal crawling artikel: {e}")
        return None

def clean_text(text):
    # Hanya pertahankan huruf latin, angka, tanda baca umum, dan spasi
    return re.sub(r'[^\x00-\x7F]+', ' ', text)

raw_content = "\n".join([p.text for p in paragraphs])
cleaned_content = clean_text(raw_content)

# Crawl halaman utama kompasiana fashion
def crawl_kompasiana():
    st.write(f"\U0001F680 Memulai crawling tanpa Selenium pada {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    headers = {"User-Agent": "Mozilla/5.0"}
    artikel_terkumpul = 0
    base_url = "https://www.kompasiana.com/tag/fashion"
    
    try:
        for page in range(1, 6):  # Ambil sampai 5 halaman
            page_url = f"{base_url}?page={page}"
            response = requests.get(page_url, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")
            articles = soup.find_all("div", class_="timeline--item")

            if not articles:
                st.write(f"❌ Tidak menemukan artikel di halaman: {page_url}")
                break

            for item in articles:
                content_div = item.find("div", class_="artikel--content")
                if not content_div:
                    continue
                title_tag = content_div.find("h2")
                if title_tag and title_tag.a:
                    url = title_tag.a['href'].strip()
                    detail = crawl_article(url)
                    if detail:
                        baru = save_to_mongodb(detail)
                        if baru:
                            artikel_terkumpul += 1
        st.write(f"✅ Selesai crawling. Artikel baru disimpan: {artikel_terkumpul}")
    except Exception as e:
        st.error(f"[ERROR] Gagal crawling: {e}")

# Thread scheduler
def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Load artikel dari database
def load_articles_from_mongodb(db_name="artikel_db", collection_name="test"):
    client = get_mongo_client()
    db = client[db_name]
    collection = db[collection_name]
    return list(collection.find())

# Statistik jumlah artikel
def get_crawl_stats_by_date(group_by="daily"):
    articles = load_articles_from_mongodb()
    df = pd.DataFrame(articles)
    if 'created_at' not in df:
        return pd.DataFrame()
    df['created_at'] = pd.to_datetime(df['created_at'])
    if group_by == "weekly":
        df['period'] = df['created_at'].dt.to_period("W").apply(lambda r: r.start_time)
    else:
        df['period'] = df['created_at'].dt.date
    count_df = df.groupby('period').size().reset_index(name='jumlah')
    return count_df

# Preprocessing teks
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

# Visualisasi top word
def plot_top_words_bar(top_words):
    words, counts = zip(*top_words)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(words, counts, color='skyblue', edgecolor='black')
    ax.set_xlabel("Kata")
    ax.set_ylabel("Frekuensi")
    ax.set_title("10 Kata Paling Sering Muncul (Diagram Batang)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig

# Grafik artikel per waktu
def plot_article_trend(df):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df['period'], df['jumlah'], marker='o', color='green', linewidth=2)
    ax.set_xlabel("Tanggal")
    ax.set_ylabel("Jumlah Artikel")
    ax.set_title("Tren Jumlah Artikel Dicrawling")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    return fig

# Streamlit UI
st.title("📰 Auto Crawler + Analisis Artikel Kompasiana")
st.write("Crawling artikel dan menganalisis kata yang sering muncul")

st.sidebar.title("⚙ Pengaturan")
interval = st.sidebar.selectbox("⏱ Interval Crawling:", ["1 jam", "2 jam", "5 jam", "12 jam", "24 jam"])

if st.sidebar.button("✅ Aktifkan Jadwal"):
    hours = int(interval.split()[0])
    schedule.every(hours).hours.do(crawl_kompasiana)
    st.sidebar.success(f"Crawling dijadwalkan setiap {hours} jam.")
    st.session_state.run_mode = "jadwal"
    scheduler_thread = threading.Thread(target=run_schedule, daemon=True)
    scheduler_thread.start()

if st.sidebar.button("🚀 Jalankan Sekarang"):
    st.session_state.run_mode = "manual"
    crawl_kompasiana()

# Analisis Kata
st.header("📊 Analisis Kata Paling Sering Muncul")
articles = load_articles_from_mongodb()
st.write(f"📚 Total artikel di database: {len(articles)}")
contents = [article['content'] for article in articles if article.get('content')]

if contents:
    st.info("🔄 Melakukan preprocessing dan analisis...")
    processed_tokens_list = preprocess_text_list(contents)
    all_tokens = [token for tokens in processed_tokens_list for token in tokens]
    word_counts = Counter(all_tokens)
    top_words = word_counts.most_common(10)

    st.subheader("🔍 Top 10 Kata")
    st.write(top_words)

    st.subheader("📈 Visualisasi Frekuensi Kata (Bar Chart)")
    fig_bar = plot_top_words_bar(top_words)
    st.pyplot(fig_bar)

    st.header("📆 Grafik Jumlah Artikel Dicrawling (Line Chart)")
    group_by = st.selectbox("Group berdasarkan:", ["daily", "weekly"])
    stats_df = get_crawl_stats_by_date(group_by=group_by)

    if not stats_df.empty:
        st.write(f"Data dari: {stats_df['period'].min()} sampai {stats_df['period'].max()}")
        fig_line = plot_article_trend(stats_df)
        st.pyplot(fig_line)
    else:
        st.info("Belum ada data crawling dengan timestamp.")
else:
    st.warning("Belum ada konten artikel yang tersedia untuk dianalisis.")
