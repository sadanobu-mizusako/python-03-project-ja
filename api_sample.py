# ライブラリ
import pandas as pd
import requests
import configparser

# API情報
con = configparser.ConfigParser()
con.read("../../config.ini") # config情報を格納しているpathを指定してください。
API_KEY_RESAS = con["RESAS"]["API_KEY"]
API_URL_RESAS = "https://opendata.resas-portal.go.jp/api/v1/tourism/hotelAnalysis/groupStack"

API_URL_HOLIDAYS = "https://date.nager.at/api/v2/PublicHolidays"

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
    res.raise_for_status()
    res_json = res.json()
    res_df = pd.DataFrame(res_json["result"]["data"])
    res_df["prefCode"] = prefCode
    res_df["prefName"] = res_json["result"]["prefName"]
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
    df = pd.concat([get_guests_for_prefcode(prefCode) for prefCode in range(1, 48)])
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
    res.raise_for_status()
    res_json = res.json()
    res_df = pd.DataFrame(res_json)[["date", "localName"]].rename(columns={"localName":"holiday_name"})

    res_df = res_df.assign(
        date = lambda df: pd.to_datetime(df["date"]),
        year_month = lambda df: df["date"].dt.year.astype(str) + "-" + df["date"].dt.month.astype(str)
    )[["date", "year_month", "holiday_name"]]
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

# print(get_guests_in_japan())
print(get_holidays_for_year(2022))