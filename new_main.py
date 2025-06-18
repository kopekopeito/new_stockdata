# main.py

import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
import time

# --- 設定項目 ---
# 保存するCSVファイル名
NIKKEI_CSV_PATH = 'nikkei_225_data.csv'
GROWTH_CSV_PATH = 'growth_core_data.csv' # グロース市場Core指数に変更

# === Webスクレイピングで銘柄リストを取得する関数群 ===

def get_nikkei_225_tickers():
    """
    日経プロファイルサイトから日経225の構成銘柄コードをスクレイピングする関数
    """
    print("日経225の構成銘柄リストを取得中...")
    tickers = []
    try:
        url = "https://indexes.nikkei.co.jp/nkave/index/component?idx=nk225"
        headers = { # PCからのアクセスを装うためのヘッダー
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # エラーがあれば例外を発生させる
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 銘柄コードが含まれるテーブルの要素を特定
        # サイト構造の変更に対応できるよう、柔軟なセレクタを使用
        rows = soup.find_all('tr')
        for row in rows:
            code_cell = row.find('div', class_='component-list-item_code')
            if code_cell:
                code = code_cell.text.strip()
                if code.isdigit() and len(code) == 4:
                    tickers.append(f"{code}.T")
        
        if not tickers:
            print("警告: 日経225の銘柄リストが取得できませんでした。サイト構造が変更された可能性があります。")
        else:
            print(f"日経225から {len(tickers)} 銘柄を取得しました。")
            
    except Exception as e:
        print(f"エラー: 日経225の銘柄リスト取得中に問題が発生しました: {e}")
        
    return tickers

def get_growth_core_tickers():
    """
    みんなの株式(minkabu)から東証グロース市場Core指数の構成銘柄をスクレイピングする関数
    """
    print("東証グロース市場Core指数の構成銘柄リストを取得中...")
    tickers = []
    try:
        url = "https://minkabu.jp/financial_item/tse_growth_core_index"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 銘柄コードが含まれるリンク要素を特定
        links = soup.select('td > a[href*="/stock/"]')
        for link in links:
            href = link.get('href', '')
            parts = href.split('/')
            if len(parts) > 2 and parts[-1].isdigit() and len(parts[-1]) == 4:
                code = parts[-1]
                tickers.append(f"{code}.T")

        # 重複を削除
        tickers = sorted(list(set(tickers)))

        if not tickers:
            print("警告: グロース指数の銘柄リストが取得できませんでした。サイト構造が変更された可能性があります。")
        else:
            print(f"グロース指数から {len(tickers)} 銘柄を取得しました。")

    except Exception as e:
        print(f"エラー: グロース指数の銘柄リスト取得中に問題が発生しました: {e}")

    return tickers

# === 株価データを取得・保存する関数（変更なし） ===
def get_stock_data(tickers, file_path):
    if not tickers:
        print(f"{file_path} の対象銘柄リストが空のため、処理をスキップします。")
        return

    print(f"--- {file_path} の処理を開始 ---")
    start_fetch_date = "2025-01-01"
    if os.path.exists(file_path):
        try:
            existing_df = pd.read_csv(file_path)
            last_date = pd.to_datetime(existing_df['Date']).max()
            start_fetch_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"既存ファイルを発見。最終取得日: {last_date.strftime('%Y-%m-%d')}")
        except Exception:
            print(f"既存ファイル {file_path} が空または読み込めないため、最初から取得します。")
            
    today = date.today().strftime("%Y-%m-%d")
    if start_fetch_date > today:
        print(f"データは最新です（{start_fetch_date}）。取得をスキップします。")
        return

    print(f"{len(tickers)} 銘柄のデータを {start_fetch_date} から取得します...")
    df_new = yf.download(tickers, start=start_fetch_date, end=today, auto_adjust=False, group_by='ticker')

    if df_new.empty:
        print("新規データはありませんでした。")
        return

    all_data_list = []
    for ticker in tickers:
        try:
            df_ticker = df_new.loc[:, (ticker, slice(None))].copy()
            df_ticker.columns = df_ticker.columns.droplevel(0)
            if not df_ticker.dropna(how='all').empty:
                df_ticker['Ticker'] = ticker.replace('.T', '')
                all_data_list.append(df_ticker)
        except KeyError:
            pass

    if not all_data_list:
        print("整形後の有効なデータはありませんでした。")
        return

    new_data_df = pd.concat(all_data_list).reset_index()
    final_columns = ['Date', 'Ticker', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
    new_data_df = new_data_df[[col for col in final_columns if col in new_data_df.columns]]
    new_data_df['Date'] = pd.to_datetime(new_data_df['Date']).dt.strftime('%Y-%m-%d')

    if 'existing_df' in locals() and not existing_df.empty:
        combined_df = pd.concat([existing_df, new_data_df]).drop_duplicates(subset=['Date', 'Ticker'], keep='last')
    else:
        combined_df = new_data_df

    combined_df.sort_values(by=['Ticker', 'Date'], inplace=True)
    combined_df.to_csv(file_path, index=False, encoding='utf-8-sig')
    print(f"データを {file_path} に保存しました。")

# === メイン処理 ===
if __name__ == "__main__":
    # 1. 銘柄リストをスクレイピングで動的に取得
    nikkei_tickers = get_nikkei_225_tickers()
    time.sleep(1) # サーバーに配慮して1秒待機
    growth_tickers = get_growth_core_tickers()
    
    # 2. 取得したリストを元に株価データを取得・保存
    get_stock_data(nikkei_tickers, NIKKEI_CSV_PATH)
    get_stock_data(growth_tickers, GROWTH_CSV_PATH)
    
    print("\nすべての処理が完了しました。")