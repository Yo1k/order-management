import atexit
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar, Optional

from flask import render_template, g, Flask
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

T_co = TypeVar("T_co", covariant=True)


class StorageService(ABC):
    @abstractmethod
    def fetch_data(self, conn: Connection[dict[str, Any]]) -> list[dict[str, Any]]:
        pass


class TransactionManager(ABC):
    @abstractmethod
    def do_in_default_tx(
            self,
            func: Callable[..., T_co],
            *args: Any,
            **kwargs: Any) -> T_co:
        pass


class PgStorageService(StorageService):
    def fetch_data(
            self, conn: Connection[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        data = conn.execute(
                """
                SELECT 
                    order_no as order_no, cost_usd, cost_rub, deliv_date
                FROM orders;
                """
        ).fetchall()
        total_cost = conn.execute(
                """
                SELECT 
                    SUM(cost_usd) as total_cost_usd,
                    SUM(cost_rub) as total_cost_rub
                FROM orders;
                """
        ).fetchone()
        return data, total_cost


class DefaultTransactionManager(TransactionManager):
    def do_in_default_tx(self, func: Callable[..., T_co], *args: Any, **kwargs: Any) -> T_co:
        return func(conn=g.conn, *args, **kwargs)


class DataPage:
    def __init__(
            self,
            db_service: StorageService,
            tx_manager: TransactionManager
    ) -> None:
        self.db_service: StorageService = db_service
        self.tx_manager: TransactionManager = tx_manager

    def request_data(self):
        data, total_cost = self.tx_manager.do_in_default_tx(func=self.db_service.fetch_data)
        context = {
                "data": data,
                "total_cost": total_cost
        }
        # print(f"total_cost{total_cost}")
        return render_template('index.html', **context)


def create_app():
    app = Flask(__name__)
    conn_pool = ConnectionPool(
            conninfo="dbname='postgres'"
                     "user='postgres'"
                     "host='localhost'"
                     "port='5432'",
            open=False,
            kwargs={"row_factory": dict_row}
    )
    tx_manager = DefaultTransactionManager()
    db_service = PgStorageService()
    data_page = DataPage(
            db_service=db_service,
            tx_manager=tx_manager
    )

    with app.app_context():
        conn_pool.open()
        atexit.register(conn_pool.close)

    def get_conn() -> None:
        g.conn = conn_pool.getconn()

    def close_conn(e: Optional[BaseException] = None) -> None:  # pylint: disable=C0103, W0613
        conn = g.pop("conn", None)
        if conn is not None:
            conn.commit()
            conn_pool.putconn(conn)

    app.before_request(get_conn)
    app.add_url_rule(
            rule="/",
            methods=["GET"],
            view_func=data_page.request_data
    )
    app.teardown_request(close_conn)
    return app
