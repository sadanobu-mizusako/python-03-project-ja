# ライブラリ
import pandas as pd
import sqlite3
import requests
import configparser
import os

# API情報
con = configparser.ConfigParser()
con.read("../../config.ini") # config情報を格納しているpathを指定してください。
API_KEY_RESAS = con["RESAS"]["API_KEY"]
API_URL_RESAS = "https://opendata.resas-portal.go.jp/api/v1/tourism/hotelAnalysis/groupStack"

API_URL_HOLIDAYS = "https://date.nager.at/api/v2/PublicHolidays"

# DB情報
DB_NAME = "./tourism.db"
TABLE_HOLIDAY = "holidays"
TABLE_GUEST = "guests"

SCHEMA_HOLIDAY = """
(
    holiday_id integer primary key autoincrement,
    date date,
    year_month text,
    holiday_name text
)
"""

SCHEMA_GUEST = """
(
    year_month text primary key,
    total_guests integer,
    foreign key(year_month) references holidays(year_month)
)
"""

# 国内の宿泊者数を求めるための関数群
def get_guests_for_prefcode(prefCode):
    """
    prefCodeに対応する件の月ごとの宿泊者数を取得する関数
    出力データのサンプル：value0~4は事業者規模ごとの宿泊者数を表す
     year  month   value0  value1  value2  value3  value4  prefCode prefName
     2011      1  2148210  261260  431010  651780  804160         1      北海道
     2011      2  2320620  288580  500450  721060  810530         1      北海道
     …
     2021     12  2320620  288580  500450  721060  810530         1      北海道

    参考リンク：https://opendata.resas-portal.go.jp/docs/api/v1/tourism/hotelAnalysis/groupStack.html
    """
    headers = {"X-API-KEY":API_KEY_RESAS}
    res = requests.get(f"{API_URL_RESAS}?matter=1&display=1&unit=1&prefCode={prefCode}", headers=headers)
    try:
        res.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("エラー : ",e)
        raise Exception
    
    try:
        res_json = res.json()
        res_df = pd.DataFrame(res_json["result"]["data"])
        res_df["prefCode"] = prefCode
        res_df["prefName"] = res_json["result"]["prefName"]
    except:
        print("宿泊者数のデータ加工でエラーが発生しました。APIから想定外の形式のデータが提供されている可能性があります。")
        raise Exception
    
    return res_df

def get_guests_for_all_prefs():
    """
    47都道府県の月ごとの宿泊者数を取得する関数
    出力データのサンプル：value0~4は事業者規模ごとの宿泊者数を表す
     year  month   value0  value1  value2  value3  value4  prefCode prefName
     2011      1  2148210  261260  431010  651780  804160         1      北海道
     2011      2  2320620  288580  500450  721060  810530         1      北海道
     …
     2021     12  2320620  288580  500450  721060  810530        47      沖縄県
    """
    dfs = [get_guests_for_prefcode(prefCode) for prefCode in range(1, 48)]
    df = pd.concat(dfs)
    return df

def get_guests_in_japan():
    """
    全国の月ごとの宿泊者数を取得する関数
    year_month  total_guests
    2011-1      61817780
    2011-2      64307300
    …
    2021-12     78372070
    """
    df_by_pref = get_guests_for_all_prefs()
    df_japan =  df_by_pref.groupby(["year", "month"], as_index=False).agg(
        value0 = ("value0", "sum"),
        value1 = ("value1", "sum"),
        value2 = ("value2", "sum"),
        value3 = ("value3", "sum"),
        value4 = ("value4", "sum"),
    ).assign(
        #value0~4は事業者規模ごとの宿泊者数なので、合算して合計宿泊者数を計算する
        total_guests = lambda df: df.value0+df.value1+df.value2+df.value3+df.value4, 
        year_month = lambda df: df.year.astype(str) + "-" + df.month.astype(str)
    )[["year_month", "total_guests"]]
    return df_japan

# 日本の祝日を取得するための関数群
def get_holidays_for_year(year):
    """
    ある年の日本の祝日を返す関数
    出力データのサンプル：
    date            year_month  holiday_name
    2022-01-01      2022-1      元日
    2022-01-10      2022-1      成人の日
    …
    2022-11-23      2022-11     勤労感謝の日

    参考リンク：https://date.nager.at/Api
    """
    res = requests.get(f"{API_URL_HOLIDAYS}/{year}/JP")
    try:
        res.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("エラー : ",e)
        raise Exception

    try: 
        res_json = res.json()
        res_df = pd.DataFrame(res_json)[["date", "localName"]].rename(columns={"localName":"holiday_name"})

        res_df = res_df.assign(
            date = lambda df: pd.to_datetime(df["date"]),
            year_month = lambda df: df["date"].dt.year.astype(str) + "-" + df["date"].dt.month.astype(str)
        )[["date", "year_month", "holiday_name"]]
    except:
        print("祝日のデータ加工でエラーが発生しました。APIから想定外の形式のデータが提供されている可能性があります。")
        raise Exception
    
    return res_df

def get_holidays_for_years(years):
    """
    指定された年（複数）の日本の祝日を返す関数
    出力データのサンプル：
    date            year_month  holiday_name
    2022-01-01      2022-1      元日
    2022-01-10      2022-1      成人の日
    …
    2022-11-23      2022-11     勤労感謝の日
    """
    df = pd.concat([get_holidays_for_year(year) for year in years])
    return df

# 複数のデータソースを統合して扱う関数群
def load_multi_data_sources():
    """
    複数のデータソースからデータを取得する関数
    """
    df_guests = get_guests_in_japan() # 取得可能な全ての期間の宿泊者数データを取得
    years = df_guests.year_month.apply(lambda x: x[:4]).unique() # データ取得した年をリストアップ
    df_holidays = get_holidays_for_years(years) # 宿泊者数データが取得できている年だけ祝日情報を取得
    return df_guests, df_holidays

def store_data_db(df_guests, df_holidays, con):
    """
    データフレームをdbに保存する関数
    """
    cur = con.cursor()

    # HOLIDAYS
    sql = f"drop table if exists {TABLE_HOLIDAY};"
    cur.execute(sql)
    con.commit()

    sql = f"create table if not exists {TABLE_HOLIDAY} {SCHEMA_HOLIDAY};"
    cur.execute(sql)
    con.commit()

    df_holidays.to_sql(TABLE_HOLIDAY,con,if_exists='append',index=None)

    # GUESTS
    sql = f"drop table if exists {TABLE_GUEST};"
    cur.execute(sql)
    con.commit()

    sql = f"create table {TABLE_GUEST} {SCHEMA_GUEST};"
    cur.execute(sql)
    con.commit()

    df_guests.to_sql(TABLE_GUEST,con,if_exists='append',index=None)

def join_data_db(con):
    """
    あらかじめデータをジョインして作成しておく    
    """
    sql = """
        with holiday_cnt_tbl as (
            select year_month, count(holiday_name) as holiday_cnt
            from holidays
            group by year_month
        )
        select a.year_month, a.total_guests, b.holiday_cnt
        from guests as a
        left join holiday_cnt_tbl as b
        on a.year_month==b.year_month
    """
    df_by_month = pd.read_sql_query(sql=sql, con=con)
    df_by_month = df_by_month.fillna(0).assign(holiday_cnt=lambda df: df.holiday_cnt.astype(int))
    # print(df_by_month)

    sql = """
        with holiday_cnt_tbl as (
            select substr(year_month, 1, 4) as year, count(holiday_name) as holiday_cnt
            from holidays
            group by 1
        ),
        guests_cnt_tbl as (
            select substr(year_month, 1, 4) as year, sum(total_guests) as total_guests
            from guests
            group by 1
        )
        select a.year, a.total_guests, b.holiday_cnt
        from guests_cnt_tbl as a
        left join holiday_cnt_tbl as b
        on a.year==b.year
    """
    df_by_year = pd.read_sql_query(sql=sql, con=con)
    df_by_year = df_by_year.fillna(0).assign(holiday_cnt=lambda df: df.holiday_cnt.astype(int))
    return df_by_month, df_by_year

# UI関連の関数
def get_option_or_query():
    ng_commands = ["delete", "insert", "update", "drop"]
    while True:
        message = "\n実行したい処理を選択してください。"
        message += "\n 1:月毎の祝日数と宿泊者数を出力する"
        message += "\n 2:年毎の祝日数と宿泊者数を出力する"
        message += "\n 9:処理を終了する"
        message += "\n DBに対してクエリを実行したい場合は、直接クエリを記述してください。ただし、delete / insert / update / dropは禁止します"
        message += "\n"
        option = input(message)

        contains_ng_command = 0
        for ng_command in ng_commands:
            if ng_command in option.lower():
                contains_ng_command += 1

        if contains_ng_command>0:
            print("このクエリは禁止されています。")
        else:
            break
    
    return option
        
if __name__ == "__main__":
    # pandasデータフレームの表示設定
    pd.set_option('display.max_rows',1000)

    # DBの準備
    con = sqlite3.connect(DB_NAME)
    df_guests, df_holidays = load_multi_data_sources()
    store_data_db(df_guests, df_holidays, con)
    df_by_month, df_by_year = join_data_db(con)

    while True:
        option = get_option_or_query()
        if option=="1":
            print(df_by_month)
        elif option=="2":
            print(df_by_year)
        elif option=="9":
            break
        else:
            try:
                print(pd.read_sql_query(sql=option, con=con))
            except:
                print("クエリが正しくありません。")

    con.close