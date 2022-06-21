from __future__ import print_function

from abc import ABC
from decimal import Decimal
import time
from datetime import datetime, timedelta
import bisect
import urllib.request
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
import sys
from typing import NamedTuple, MutableSequence, Optional

import telegram
from googleapiclient.discovery import build
import googleapiclient.errors
import google.auth.exceptions
import httplib2.error

import psycopg


class Data(NamedTuple):
    sec_no: MutableSequence[int]
    order_no: MutableSequence[int]
    cost_usd: MutableSequence[Optional[Decimal]]
    cost_rub: MutableSequence[Optional[Decimal]]
    deliv_date: MutableSequence[Optional[datetime.date]]


class DataService(ABC):
    def get_data(self) -> Data:
        pass


class StorageService(ABC):
    def insert_data(self, data: Data) -> None:
        pass

    def missed_deadlines_orders(self, now_date, min_interval):
        pass

    def update_notification_date(self, missed_order_no, notif_date):
        pass

    def finalize(self) -> None:
        pass


class BotService(ABC):
    def send_notification(self, information):
        pass


class PgStorageService(StorageService):
    def __init__(self, schema="./orders_schema.sql"):
        self.__schema = schema
        self.conn = psycopg.connect(
                dbname="postgres",
                user="postgres",
                password="postgres",
                # host="db",  # uncomment in case running docker container
                host="127.0.0.1",  # comment in case running docker container
                port="5432")
        self.__create_table()

    def __create_table(self):
        """Creates a connection to PostgreSQL DBMS.

        Creates table `orders` in DB in case it does not exist.
        """
        with self.conn.transaction():
            with self.conn.cursor() as cur:
                with open(self.__schema) as schema:
                    cur.execute(schema.read())

    def insert_data(self, data: Data) -> None:
        """Inserts all data to the DB within a single transaction within a single SQL command.

        On conflict with `order_no`,which is a primary key, it updates other
        attributes in the row.
        """
        with self.conn.transaction():
            with self.conn.cursor() as cur:
                cur.execute(
                        """
                        INSERT INTO orders
                        (SELECT * from unnest(
                            %s::int[],
                            %s::int[],
                            %s::numeric[],
                            %s::numeric[],
                            %s::date[]))
                        ON CONFLICT (order_no) DO UPDATE SET
                            sec_no = excluded.sec_no,
                            cost_usd = excluded.cost_usd,
                            cost_rub = excluded.cost_rub,
                            deliv_date = excluded.deliv_date;
                        """,
                        data)

    def missed_deadlines_orders(self, now_date, min_interval):
        with self.conn.transaction():
            with self.conn.cursor() as cur:
                cur.execute(
                        """
                        SELECT
                            orders.order_no,
                            orders.deliv_date
                        FROM
                            orders
                        LEFT JOIN missed_deadlines
                            ON orders.order_no = missed_deadlines.order_no
                        WHERE
                            deliv_date <= %(now)s::date - '1 day'::interval
                            AND (notif_date is NULL
                                OR (notif_date <= %(now)s::timestamptz - %(interval)s::interval))
                        ORDER BY
                            deliv_date ASC;
                        """,
                        ({"now": now_date, "interval": min_interval}))
                missed_orders = cur.fetchall()
        return missed_orders #PgStorageService.__get_column_from_query(missed_orders)

    def update_notification_date(self, missed_order_no, notif_date):
        data = PgStorageService.__prepare_data(missed_order_no, notif_date)
        with self.conn.transaction():
            with self.conn.cursor() as cur:
                cur.execute(
                        """
                        INSERT INTO missed_deadlines
                        (SELECT * from unnest(%s::int[], %s::timestamptz[]))
                        ON CONFLICT (order_no) DO UPDATE SET
                            notif_date = excluded.notif_date;
                        """,
                        data)

    # @staticmethod
    # def __get_column_from_query(res_query):
    #     return [row[0] for row in res_query]

    @staticmethod
    def __prepare_data(missed_order_no, notif_date: datetime):
        return missed_order_no, [notif_date for _ in range(len(missed_order_no))]

    def finalize(self) -> None:
        self.conn.close()


class USDQuotes:
    """Cache of daily use quotes for different years from CBR."""
    def __init__(self):
        self.__cache = {}
        self.__keys = []

    def get(self, date_quote):
        """Returns usd quote for a specific date.

        If the USDQuotes object does not contain information for a particular date,
        it updates usd quotes for the entire year from that date.
        """
        if date_quote not in self.__keys \
                and self.__floor_key(date_quote) is None:
            self.__update_cache(date_quote.year)

        if date_quote in self.__keys:
            return self.__cache.get(date_quote)
        else:
            floor_date_quote = self.__floor_key(date_quote)
            if floor_date_quote:
                return self.__cache.get(floor_date_quote)
            else:
                return None

    def __update_cache(self, year):
        self.__fetch_year_usd_quotes(year)
        self.__keys = sorted(self.__cache)

    def __fetch_year_usd_quotes(self, year):
        """Fetches from CBR daily usd quotes for the whole year."""
        with urllib.request.urlopen(
                url=(
                        f"https://www.cbr.ru/scripts/XML_dynamic.asp?"
                        f"date_req1=01/12/{year-1}"
                        f"&date_req2=31/12/{year}"
                        f"&VAL_NM_RQ=R01235")) as response:
            root = ET.parse(response).getroot()

            for record in root.findall("Record"):
                date_quote = record.attrib.get("Date")

                nominal = record.find("Nominal").text
                value = record.find("Value").text.replace(",", ".")
                usd_quote = Decimal(value) / Decimal(nominal)

                self.__cache[convert_to_date(date_quote)] = usd_quote

    def __floor_key(self, key):
        """Find the highest value less than key."""
        idx = bisect.bisect_left(self.__keys, key)
        if idx:
            return self.__keys[idx - 1]
        return None


class SheetsDataService(DataService):
    def __init__(self, usd_quotes: USDQuotes):
        self.__data = Data([], [], [], [], [])
        self.__raw_data = None
        self.__usd_quotes = usd_quotes

    def get_data(self) -> Data:
        self.__get_sheets_data()
        self.__convert_data()
        return self.__data

    def __get_sheets_data(self):
        """Reads and returns the whole google spreadsheet file."""
        # The ID and range of a source spreadsheet
        source_spreadsheet_id = "1uqzyZbTDQWjVCbGiFlr2pS8GbUQpyW-3bJ3WqCwMz7E"
        source_range_name = "Sheet1!A2:D"

        with open("developer_key", "r") as file:
            dev_key = file.read()

        service = build('sheets', 'v4', developerKey=dev_key)
        # Calls the Sheets API
        sheet = service.spreadsheets()
        result = sheet.values().get(
                spreadsheetId=source_spreadsheet_id,
                range=source_range_name,
                majorDimension="COLUMNS").execute()
        self.__raw_data = result.get('values')

    def __convert_usd_rub(self, usd_value, date_quote):
        if date_quote > datetime.now().date():
            return None

        usd_quote = self.__usd_quotes.get(date_quote)
        if usd_quote is None:
            return None
        else:
            return usd_value * usd_quote

    def __convert_data(self):
        """Prepares data for storage to DB from raw spreadsheet data."""
        if self.__raw_data:
            sec_no, order_no, cost_usd, deliv_date = self.__raw_data
            assert len(sec_no) == len(order_no) == len(cost_usd) == len(deliv_date), \
                f"len(sec_no_lst)={len(sec_no)}," \
                f"len(order_no_lst)={len(order_no)}," \
                f"len(cost_usd_lst)={len(cost_usd)}," \
                f"len(deliv_date_lst)={len(deliv_date)}"

            for i in range(len(self.__raw_data[0])):
                cnvt_cost_usd = Decimal(cost_usd[i])
                cnvt_deliv_date = convert_to_date(deliv_date[i])
                cnvt_cost_rub = self.__convert_usd_rub(cnvt_cost_usd, cnvt_deliv_date)

                self.__data.sec_no.append(int(sec_no[i]))
                self.__data.order_no.append(int(order_no[i]))
                self.__data.cost_usd.append(cnvt_cost_usd)
                self.__data.cost_rub.append(cnvt_cost_rub)
                self.__data.deliv_date.append(cnvt_deliv_date)


class TgBotService(BotService):
    def __init__(self, api_token, db: PgStorageService):
        self.__bot = telegram.Bot(token=api_token)
        self.__db = db
        self.__user_chat_id_cache = set()
        self.__unsubscrube_user_chat_id = set()
        self.__cache_user_chat_id()


    def join_db(self, db):
        self.__db = db

    def __cache_user_chat_id(self):
        with self.__db.conn.transaction():
            with self.__db.conn.cursor() as cur:
                cur.execute("SELECT * FROM tg_information;")
                res_query = cur.fetchall()
        self.__user_chat_id_cache.update([row[0] for row in res_query])

    def send_notification(self, information):
        if information:
            message_header = "Список заказов с пропущенными сроками поставки\n" \
                             "(в порядке от самого старого срока поставки):\n\n" \
                             "заказ №: срок поставки\n"
            str_information = TgBotService.__convert_to_string(information)

            self.__update_user_chat_id()
            for chat_id in self.__user_chat_id_cache:
                if chat_id:
                    self.__bot.send_message(
                            text=f"{message_header}{str_information}",
                            chat_id=chat_id)
            notif_time = datetime.now()
            self.__update_db_user_chat_id()
            self.__db.update_notification_date(
                    missed_order_no=[row[0] for row in information],
                    notif_date=notif_time)

    def __update_user_chat_id(self):
        for upd in self.__bot.get_updates():
            if not upd.my_chat_member:
                self.__user_chat_id_cache.add(upd.message.from_user.id)
            else:
                self.__unsubscrube_user_chat_id.add(upd.my_chat_member.chat.id)
        self.__user_chat_id_cache = self.__user_chat_id_cache.difference(
                self.__unsubscrube_user_chat_id)

    def __update_db_user_chat_id(self):
        with self.__db.conn.transaction():
            with self.__db.conn.cursor() as cur:
                cur.execute(
                        """
                        INSERT INTO tg_information
                        (SELECT * from unnest(%s::int[]))
                        ON CONFLICT (user_chat_id) DO NOTHING;
                        """,
                        [list(self.__user_chat_id_cache)])

            with self.__db.conn.cursor() as cur:
                cur.execute(
                        """
                        DELETE from tg_information
                        WHERE user_chat_id IN
                            (SELECT * from unnest(%s::int[]));
                        """,
                        [list(self.__unsubscrube_user_chat_id)])


    @staticmethod
    def __convert_to_string(information):
        return "\n".join(f"{row[0]: >10d}: {row[1]}" for row in information)


def convert_to_date(str_date):
    return datetime.strptime(str_date, "%d.%m.%Y").date()


if __name__ == "__main__":
    # Parameters:

    # Idle time before the next synchronisation of PgStorageService database
    # and a specific Google Spreadsheet (sleep_time: int
    sleep_time: int = 5  # value in seconds

    # Minimal time interval between notifications with missed deadlines orders
    time_delta = timedelta(days=1)  # for testing try `seconds=60`

    with open("telegram_api_token", "r") as file:
        telegram_api_token = file.read().strip()
    usd_quotes: Optional[USDQuotes] = None
    tg_bot: Optional[TgBotService] = None

    # Main loop of the `data_flow` service
    while True:
        try:
            if usd_quotes is None:
                usd_quotes = USDQuotes()

            # Service creation
            sheets_service = SheetsDataService(usd_quotes)
            db = PgStorageService()
            if tg_bot is None:
                tg_bot = TgBotService(telegram_api_token, db)
            else:
                tg_bot.join_db(db)

            # Services usage
            prep_data = sheets_service.get_data()
            db.insert_data(prep_data)

            # now_date = datetime.now()
            missed_orders = db.missed_deadlines_orders(
                    now_date=datetime.now(),
                    min_interval=time_delta)
            tg_bot.send_notification(information=missed_orders)

            db.finalize()

        except googleapiclient.errors.Error as e:
            print(f"googleapiclient.errors.Error: {e}", file=sys.stderr)

        except google.auth.exceptions.GoogleAuthError as e:
            print(f"google.auth.exceptions.GoogleAuthError: {e}", file=sys.stderr)

        except httplib2.error.HttpLib2Error as e:
            print(f"httplib2.error.HttpLib2Error: {e}", file=sys.stderr)

        except urllib.error.URLError as e:
            print(f"urllib.error.URLError: {e.reason}", file=sys.stderr)

        except psycopg.Error as e:
            print(f"psycopg.Error: {e}", file=sys.stderr)

        except telegram.error.TelegramError as e:
            print(f"telegram.error.TelegramError: {e}", file=sys.stderr)

        time.sleep(sleep_time)
