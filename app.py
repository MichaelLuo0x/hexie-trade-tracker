import base64
import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

    return MARKET_SESSIONS[market][-1][1]


def time_to_text(value: time) -> str:
    return value.strftime("%H:%M")


def text_to_time(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def parse_quantity(value: str) -> int | None:
    cleaned = str(value).replace(",", "").strip()
    if not cleaned.isdigit():
    }


def encode_orders(orders):
    serializable_orders = []
    for order in orders:
        serializable_orders.append(
            {
                "stock": order.get("stock", ""),
                "market": order.get("market", "港股"),
                "direction": order.get("direction", "买入"),
                "limit_price": float(order.get("limit_price", 0)),
                "quantity": int(order.get("quantity", 0)),
                "order_time": time_to_text(order.get("order_time", time(9, 30))),
                "end_time": time_to_text(
                    order.get("end_time", market_close_time(order.get("market", "港股")))
                ),
            }
        )
    payload = json.dumps(serializable_orders, ensure_ascii=False, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_orders(value: str):
    try:
        payload = base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")
        raw_orders = json.loads(payload)
    except (ValueError, json.JSONDecodeError):
        return []

    restored_orders = []
    for order in raw_orders:
        market = order.get("market", "港股")
        if market not in MARKET_SESSIONS:
            market = "港股"
        try:
            restored_orders.append(
                {
                    "stock": str(order.get("stock", "")),
                    "market": market,
                    "direction": order.get("direction", "买入"),
                    "limit_price": float(order.get("limit_price", 0)),
                    "quantity": int(order.get("quantity", 0)),
                    "order_time": text_to_time(order.get("order_time", "09:30")),
                    "end_time": text_to_time(
                        order.get("end_time", time_to_text(market_close_time(market)))
                    ),
                }
            )
        except (TypeError, ValueError):
            continue
    return restored_orders


def load_orders_from_url():
    encoded_orders = st.query_params.get("orders")
    if isinstance(encoded_orders, list):
        encoded_orders = encoded_orders[0] if encoded_orders else None
    return decode_orders(encoded_orders) if encoded_orders else []


def persist_orders():
    if st.session_state.orders:
        st.query_params["orders"] = encode_orders(st.session_state.orders)
    elif "orders" in st.query_params:
        del st.query_params["orders"]


st.set_page_config(page_title="交易进度跟踪", page_icon="📈", layout="wide")
st.title("交易进度跟踪")
st.caption(
)

if "orders" not in st.session_state:
    st.session_state.orders = []
    st.session_state.orders = load_orders_from_url()

def clear_orders():
    st.session_state.orders = []
    persist_orders()

with st.sidebar:
    st.header("新增订单")
                        "end_time": end_time,
                    }
                )
                persist_orders()
    st.button("清空全部订单", on_click=clear_orders, type="secondary")

orders = st.session_state.orders
                )
            if delete_order:
                st.session_state.orders.pop(idx)
                persist_orders()
                st.rerun()

            st.caption(
                            "order_time": order_time_edit,
                            "end_time": end_time_edit,
                        }
                        persist_orders()
                        st.success("订单已更新。页面刷新后会显示最新进度。")
                        st.rerun()
