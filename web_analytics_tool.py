import os
import re
import time
import threading
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
from urllib.parse import urlparse, urljoin
from requests_html import HTMLSession
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime

try:
    from nltk.corpus import stopwords
    STOPWORDS = set(stopwords.words('indonesian')) | set(stopwords.words('english'))
except Exception:
    STOPWORDS = set()

BASE_OUTPUT = "web_analytics_output"
os.makedirs(BASE_OUTPUT, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WebAnalyticsTool/3.0)"}

def fetch_url_js(url, timeout=20):
    """Ambil halaman dan render JavaScript"""
    session = HTMLSession()
    t0 = time.time()
    resp = session.get(url, headers=HEADERS, timeout=timeout)
    try:
        resp.html.render(timeout=30, sleep=2)
    except Exception as e:
        print("Render gagal:", e)
    t1 = time.time()
    return resp, t1 - t0, len(resp.content)

def extract_onpage_info(resp, base_url):
    """Ambil info struktural & SEO"""
    html = resp.html.html
    soup = resp.html
    title = soup.find("title", first=True)
    meta_desc = soup.find("meta[name='description']", first=True)
    meta_kw = soup.find("meta[name='keywords']", first=True)

    links = [a.attrs.get("href") for a in soup.find("a") if "href" in a.attrs]
    onclick_links = re.findall(r"onclick=[\"'].*?(https?://[^\s\"']+)", html)
    links += onclick_links
    links = [l for l in links if l]

    imgs = soup.find("img")
    scripts = soup.find("script")
    css_links = soup.find("link[rel*='stylesheet']")

    texts = soup.text
    words = re.findall(r"\b[\w']+\b", texts.lower())
    if STOPWORDS:
        words = [w for w in words if w not in STOPWORDS and len(w) > 2]
    freq = Counter(words)
    top_words = freq.most_common(20)

    return {
        "title": title.text if title else "",
        "meta_description": meta_desc.attrs.get("content", "") if meta_desc else "",
        "meta_keywords": meta_kw.attrs.get("content", "") if meta_kw else "",
        "n_links": len(links),
        "n_internal_links": sum(1 for l in links if l and (l.startswith("/") or base_url in l)),
        "n_external_links": sum(1 for l in links if l and not (l.startswith("/") or base_url in l)),
        "n_images": len(imgs),
        "n_scripts": len(scripts),
        "n_css_files": len(css_links),
        "top_words": top_words,
        "all_links": links[:200],
    }

def crawl(url, max_pages=10, max_depth=1, timeout=20, log_callback=None):
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    visited = set()
    queue = [(url, 0)]
    results = []

    while queue and len(visited) < max_pages:
        cur, depth = queue.pop(0)
        if cur in visited or depth > max_depth:
            continue

        try:
            resp, resp_time, size = fetch_url_js(cur, timeout=timeout)
        except Exception as e:
            if log_callback:
                log_callback(f"Gagal mengambil {cur}: {e}")
            visited.add(cur)
            continue

        visited.add(cur)
        info = extract_onpage_info(resp, base)
        info.update({
            "url": cur,
            "status_code": resp.status_code,
            "response_time_s": resp_time,
            "size_bytes": size,
        })
        results.append(info)

        if log_callback:
            log_callback(f"Analisis {cur} | {resp.status_code} | {resp_time:.2f}s | {size} bytes")

        if depth < max_depth:
            for link in info["all_links"]:
                if not link:
                    continue
                if link.startswith("//"):
                    link = parsed.scheme + ":" + link
                if link.startswith("/"):
                    link = urljoin(base, link)
                if link.startswith(base) and link not in visited:
                    queue.append((link, depth + 1))

    return results

def save_results(results, output_dir):
    df = pd.DataFrame(results)
    csv_path = os.path.join(output_dir, "web_analytics_results.csv")
    df.to_csv(csv_path, index=False)

    # Grafik
    if not df.empty:
        for col, title, xlabel in [
            ("response_time_s", "Response Time per Page", "Waktu response (s)"),
            ("size_bytes", "Ukuran Halaman per Page", "Ukuran halaman (bytes)"),
            ("n_links", "Jumlah Link per Page", "Jumlah link"),
        ]:
            plt.figure(figsize=(8, 4))
            df_sorted = df.sort_values(col, ascending=False)
            plt.barh(df_sorted["url"], df_sorted[col])
            plt.title(title)
            plt.xlabel(xlabel)
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, f"{col}.png"))
            plt.close()

    summary_path = os.path.join(output_dir, "summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"Total halaman dianalisis: {len(df)}\n")
        if not df.empty:
            f.write(f"Rata-rata waktu respons: {df['response_time_s'].mean():.2f} detik\n")
            f.write(f"Rata-rata ukuran halaman: {df['size_bytes'].mean():.0f} bytes\n")
            f.write(f"Rata-rata jumlah link per halaman: {df['n_links'].mean():.0f}\n")
        f.write("\n=== Rekomendasi ===\n")
        f.write("• Gunakan meta description untuk SEO.\n")
        f.write("• Optimalkan waktu respons halaman.\n")
        f.write("• Pastikan struktur internal link mudah diakses.\n")

    return csv_path, summary_path

class WebAnalyticsApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Web Analytics Tool - Final Version")
        self.geometry("730x650")
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="URL Website:").pack()
        self.url_entry = tk.Entry(self, width=60)
        self.url_entry.pack(pady=3)

        tk.Label(self, text="Tanggal Awal (YYYY-MM-DD):").pack()
        self.start_date = tk.Entry(self, width=20)
        self.start_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.start_date.pack()

        tk.Label(self, text="Tanggal Akhir (YYYY-MM-DD):").pack()
        self.end_date = tk.Entry(self, width=20)
        self.end_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.end_date.pack()

        tk.Label(self, text="Maksimal Halaman:").pack()
        self.max_pages = tk.Entry(self, width=10)
        self.max_pages.insert(0, "10")
        self.max_pages.pack()

        tk.Label(self, text="Depth Crawl:").pack()
        self.max_depth = tk.Entry(self, width=10)
        self.max_depth.insert(0, "1")
        self.max_depth.pack()

        tk.Label(self, text="Timeout per Halaman (detik):").pack()
        self.timeout_entry = tk.Entry(self, width=10)
        self.timeout_entry.insert(0, "20")
        self.timeout_entry.pack()

        self.start_btn = tk.Button(self, text="Mulai Analisis", command=self.start_analysis)
        self.start_btn.pack(pady=10)

        self.log_area = scrolledtext.ScrolledText(self, height=20, width=90, state="disabled")
        self.log_area.pack(padx=10, pady=5)

    def log(self, msg):
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.config(state="disabled")
        self.log_area.see(tk.END)

    def start_analysis(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Masukkan URL website dulu!")
            return
        if not url.startswith("http"):
            url = "https://" + url

        try:
            pages = int(self.max_pages.get())
            depth = int(self.max_depth.get())
            timeout = int(self.timeout_entry.get())
            start_date = self.start_date.get().strip()
            end_date = self.end_date.get().strip()
        except:
            messagebox.showerror("Error", "Input numerik/tanggal tidak valid!")
            return

        folder_name = f"{BASE_OUTPUT}_{start_date}_to_{end_date}"
        os.makedirs(folder_name, exist_ok=True)

        self.start_btn.config(state="disabled")
        threading.Thread(target=self.run_analysis, args=(url, pages, depth, timeout, folder_name)).start()

    def run_analysis(self, url, pages, depth, timeout, folder_name):
        self.log(f"Memulai analisis {url} (periode hasil: {folder_name}) ...")
        try:
            results = crawl(url, pages, depth, timeout, log_callback=self.log)
            if not results:
                messagebox.showwarning("Selesai", "Tidak ada hasil ditemukan.")
                self.start_btn.config(state="normal")
                return
            csv_path, summary = save_results(results, folder_name)
            self.log(f"\nHasil disimpan di folder '{folder_name}'")
            self.log(f"File CSV: {csv_path}")
            self.log(f"Ringkasan: {summary}")
            messagebox.showinfo("Selesai", "Analisis selesai! Hasil tersimpan di folder output.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            self.start_btn.config(state="normal")

if __name__ == "__main__":
    app = WebAnalyticsApp()
    app.mainloop()
