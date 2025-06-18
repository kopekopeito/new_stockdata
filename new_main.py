# main.py (デバッグ強化版)

import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
import time

# --- 設定項目 ---
NIKKEI_CSV_PATH = 'nikkei_225_data.csv'
GROWTH_CSV_PATH = 'growth_core_data.csv'

# === Webスクレイピング関数 (ログ出力強化) ===
def get_nikkei_225_tickers():
    print("--- [DEBUG] 日経225スクレイピング開始 ---")
    tickers = []
    try:
        url = "https://indexes.nikkei.co.jp/nkave/index/component?idx=nk225"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        
        print(f"[DEBUG] URLにアクセスします: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        print("[DEBUG] HTML取得成功。解析を開始します。")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        rows = soup.find_all('tr')
        print(f"[DEBUG] trタグを {len(rows)} 個見つけました。")
        
        for row in rows:
            code_cell = row.find('div', class_='component-list-item_code')
            if code_cell:
                code = code_cell.text.strip()
                if code.isdigit() and len(code) == 4:
                    tickers.append(f"{code}.T")
        
        if not tickers: print("★[警告] 日経225の銘柄リストが取得できませんでした。0件です。")
        else: print(f"✅ 日経225から {len(tickers)} 銘柄を取得しました。")
            
    except Exception as e:
        print(f"❌[エラー] 日経225の銘柄リスト取得中に問題が発生しました: {e}")
    
    print("--- [DEBUG] 日経225スクレイピング終了 ---")
    return tickers

def get_growth_core_tickers():
    print("\n--- [DEBUG] グロース指数スクレイピング開始 ---")
    tickers = []
    try:
        url = "https://minkabu.jp/financial_item/tse_growth_core_index"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

        print(f"[DEBUG] URLにアクセスします: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        print("[DEBUG] HTML取得成功。解析を開始します。")

        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.select('td > a[href*="/stock/"]')
        print(f"[DEBUG] 銘柄リンクらしきものを {len(links)} 個見つけました。")
        
        for link in links:
            href = link.get('href', '')
            parts = href.split('/')
            if len(parts) > 2 and parts[-1].isdigit() and len(parts[-1]) == 4:
                tickers.append(f"{parts[-1]}.T")
        
        tickers = sorted(list(set(tickers)))

        if not tickers: print("★[警告] グロース指数の銘柄リストが取得できませんでした。0件です。")
        else: print(f"✅ グロース指数から {len(tickers)} 銘柄を取得しました。")

    except Exception as e:
        print(f"❌[エラー] グロース指数の銘柄リスト取得中に問題が発生しました: {e}")
    
    print("--- [DEBUG] グロース指数スクレイピング終了 ---")
    return tickers

# === 株価取得関数（変更なし） ===
def get_stock_data(tickers, file_path):
    # (この関数の内容は変更ありません)
    if not tickers:
        print(f"★[警告] {file_path} の対象銘柄リストが空のため、株価取得処理をスキップします。")
        return
    print(f"\n--- {file_path} の処理を開始 ---")
    start_fetch_date = "2025-01-01"
    existing_df = None
    if os.path.exists(file_path):
        try:
            existing_df = pd.read_csv(file_path)
            if not existing_df.empty:
                last_date = pd.to_datetime(existing_df['Date']).max()
                start_fetch_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
                print(f"既存ファイルを発見。最終取得日: {last_date.strftime('%Y-%m-%d')}")
        except Exception:
            print(f"既存ファイル {file_path} が空または読み込めないため、最初から取得します。")
    today = date.today().strftime("%Y-%m-%d")
    if start_fetch_date > today:
        print("データは最新です。取得をスキップします。")
        return
    print(f"{len(tickers)} 銘柄のデータを {start_fetch_date} から取得します...")
    df_new = yf.download(tickers, start=start_fetch_date, end=today, auto_adjust=False, group_by='ticker')
    if df_new.empty:
        print("★[情報] yfinanceから新規データをダウンロードできませんでした（0件）。")
        return
    all_data_list = []
    for ticker in tickers:
        try:
            df_ticker = df_new.loc[:, (ticker, slice(None))].copy()
            df_ticker.columns = df_ticker.columns.droplevel(0)
            if not df_ticker.dropna(how='all').empty:
                df_ticker['Ticker'] = ticker.replace('.T', '')
                all_data_list.append(df_ticker)
        except KeyError: pass
    if not all_data_list:
        print("★[警告] 整形後の有効なデータはありませんでした。")
        return
    new_data_df = pd.concat(all_data_list).reset_index()
    final_columns = ['Date', 'Ticker', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
    new_data_df = new_data_df[[col for col in final_columns if col in new_data_df.columns]]
    new_data_df['Date'] = pd.to_datetime(new_data_df['Date']).dt.strftime('%Y-%m-%d')
    if existing_df is not None and not existing_df.empty:
        combined_df = pd.concat([existing_df, new_data_df]).drop_duplicates(subset=['Date', 'Ticker'], keep='last')
    else:
        combined_df = new_data_df
    combined_df.sort_values(by=['Ticker', 'Date'], inplace=True)
    combined_df.to_csv(file_path, index=False, encoding='utf-8-sig')
    print(f"✅ データを {file_path} に保存しました。")

# === メイン処理 ===
if __name__ == "__main__":
    print("======= 全自動処理を開始します =======")
    nikkei_tickers = get_nikkei_225_tickers()
    time.sleep(1)
    growth_tickers = get_growth_core_tickers()
    
    get_stock_data(nikkei_tickers, NIKKEI_CSV_PATH)
    time.sleep(1)
    get_stock_data(growth_tickers, GROWTH_CSV_PATH)
    
    print("\n======= 全自動処理が完了しました =======")
