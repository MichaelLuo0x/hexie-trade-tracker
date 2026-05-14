from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

MARKET_SESSIONS = {
    "港股": [
        (time(9, 30), time(12, 0)),
        (time(13, 0), time(16, 0)),
    ],
    "A股": [
        (time(9, 30), time(11, 30)),
        (time(13, 0), time(15, 0)),
    ],
}


def combine_today(t: time) -> datetime:
    return datetime.combine(date.today(), t)


def market_close_time(market: str) -> time:
    return MARKET_SESSIONS[market][-1][1]


def parse_quantity(value: str) -> int | None:
    cleaned = str(value).replace(",", "").strip()
    if not cleaned.isdigit():
        return None
    quantity = int(cleaned)
    return quantity if quantity > 0 else None


def truncate_decimal(value: float, decimals: int = 4) -> float:
    factor = 10**decimals
    return int(value * factor) / factor


def build_trading_minutes(order_time: time, end_time: time, market: str):
    order_dt = combine_today(order_time)
    end_dt = combine_today(end_time)
    minutes = []
    for start, end in MARKET_SESSIONS[market]:
        session_start = combine_today(start)
        session_end = combine_today(end)
        if order_dt >= session_end or end_dt <= session_start:
            continue
        current = max(order_dt, session_start)
        stop = min(end_dt, session_end)
        if current >= stop:
            continue
        delta_minutes = int((stop - current).total_seconds() // 60)
        for i in range(delta_minutes):
            minutes.append(current + timedelta(minutes=i))
    return minutes


def hourly_anchors(start_dt: datetime, end_time: time):
    end_dt = combine_today(end_time)
    anchors = []
    hour_mark = start_dt.replace(minute=0, second=0, microsecond=0)
    if hour_mark < start_dt:
        hour_mark += timedelta(hours=1)
    while hour_mark <= end_dt:
        anchors.append(hour_mark)
        hour_mark += timedelta(hours=1)
    if not anchors or anchors[-1] != end_dt:
        anchors.append(end_dt)
    return anchors


def calculate_schedule(order_time: time, end_time: time, quantity: int, market: str):
    minutes = build_trading_minutes(order_time, end_time, market)
    total_minutes = len(minutes)
    if total_minutes == 0:
        return None, None, None

    df_minutes = pd.DataFrame({"time": minutes})
    cumulative_ratio = (df_minutes.index + 1) / total_minutes
    df_minutes["cumulative_pct"] = ((cumulative_ratio * 100 * 10000).astype(int) / 10000)
    df_minutes["target_qty"] = (cumulative_ratio * quantity).astype(int)
    df_minutes["remaining_qty"] = quantity - df_minutes["target_qty"]

    anchors = hourly_anchors(minutes[0], end_time)
    anchor_rows = []
    for anchor in anchors:
        elapsed = sum(1 for m in minutes if m < anchor)
        pct = elapsed / total_minutes
        anchor_rows.append(
            {
                "time": anchor.time().strftime("%H:%M"),
                "cumulative_pct": truncate_decimal(pct * 100),
                "target_qty": int(pct * quantity),
                "remaining_qty": quantity - int(pct * quantity),
            }
        )
    anchor_df = pd.DataFrame(anchor_rows)
    return df_minutes, anchor_df, total_minutes


def calculate_current_progress(order_time: time, end_time: time, quantity: int, market: str):
    minutes = build_trading_minutes(order_time, end_time, market)
    total_minutes = len(minutes)
    if total_minutes == 0:
        return None

    now_dt = datetime.now().replace(second=0, microsecond=0)
    elapsed_minutes = sum(1 for minute in minutes if minute < now_dt)
    elapsed_minutes = min(max(elapsed_minutes, 0), total_minutes)
    pct = elapsed_minutes / total_minutes
    target_qty = int(pct * quantity)
    remaining_qty = quantity - target_qty
    remaining_minutes = total_minutes - elapsed_minutes

    return {
        "elapsed_minutes": elapsed_minutes,
        "remaining_minutes": remaining_minutes,
        "cumulative_pct": pct,
        "target_qty": target_qty,
        "remaining_qty": remaining_qty,
    }


st.set_page_config(page_title="交易进度跟踪", page_icon="📈", layout="wide")
st.title("交易进度跟踪")
st.caption(
    "按所选市场的连续交易时段线性分配交易进度。"
    "港股: 09:30–12:00，13:00–16:00；A股: 09:30–11:30，13:00–15:00。午休时间不计入可交易时间。"
)

if "orders" not in st.session_state:
    st.session_state.orders = []

def clear_orders():
    st.session_state.orders = []

with st.sidebar:
    st.header("新增订单")
    market = st.selectbox("市场", ["港股", "A股"], key="add_market")
    with st.form("order_form", clear_on_submit=True):
        stock = st.text_input("股票代码 / 名称", value="HK0267 中信股份")
        direction = st.selectbox("交易方向", ["买入", "卖出"])
        limit_price = st.number_input("限价", min_value=0.0, value=12.0, format="%.3f")
        quantity_text = st.text_input("订单数量", value="1,000,000")
        order_time = st.time_input("收到订单时间 (HH:MM)", value=time(9, 30), step=60)
        end_time = st.time_input(
            "订单结束时间 (HH:MM)", value=market_close_time(market), step=60
        )
        submitted = st.form_submit_button("添加订单")
        if submitted:
            quantity = parse_quantity(quantity_text)
            if quantity is None:
                st.error("订单数量请输入大于 0 的整数，例如 1,000,000。")
            else:
                st.session_state.orders.append(
                    {
                        "stock": stock,
                        "market": market,
                        "direction": direction,
                        "limit_price": limit_price,
                        "quantity": quantity,
                        "order_time": order_time,
                        "end_time": end_time,
                    }
                )
    st.button("清空全部订单", on_click=clear_orders, type="secondary")

orders = st.session_state.orders
for order in orders:
    order.setdefault("market", "港股")
    order.setdefault("end_time", market_close_time(order["market"]))
    if order.get("direction") == "Buy":
        order["direction"] = "买入"
    elif order.get("direction") == "Sell":
        order["direction"] = "卖出"

if not orders:
    st.info("请先在左侧栏添加订单，添加后会显示对应的交易进度表。")
else:
    now_display = datetime.now().strftime("%H:%M")
    st.markdown(f"**订单总览（当前时间 {now_display}）**")
    st.button("刷新当前时间", type="secondary")

    overview_rows = []
    for order in orders:
        current_progress = calculate_current_progress(
            order["order_time"], order["end_time"], order["quantity"], order["market"]
        )
        if current_progress is None:
            overview_rows.append(
                {
                    "股票": order.get("stock", ""),
                    "市场": order["market"],
                    "方向": order["direction"],
                    "限价": order["limit_price"],
                    "订单数量": order["quantity"],
                    "当前理论进度": 0.0,
                    "当前目标数量": 0,
                    "剩余数量": order["quantity"],
                    "剩余可交易分钟": 0,
                    "结束时间": order["end_time"].strftime("%H:%M"),
                }
            )
            continue

        overview_rows.append(
            {
                "股票": order.get("stock", ""),
                "市场": order["market"],
                "方向": order["direction"],
                "限价": order["limit_price"],
                "订单数量": order["quantity"],
                "当前理论进度": truncate_decimal(current_progress["cumulative_pct"] * 100),
                "当前目标数量": current_progress["target_qty"],
                "剩余数量": current_progress["remaining_qty"],
                "剩余可交易分钟": current_progress["remaining_minutes"],
                "结束时间": order["end_time"].strftime("%H:%M"),
            }
        )

    st.dataframe(
        pd.DataFrame(overview_rows),
        use_container_width=True,
        column_config={
            "限价": st.column_config.NumberColumn("限价", format="%.3f"),
            "订单数量": st.column_config.NumberColumn("订单数量", format="%,d"),
            "当前理论进度": st.column_config.ProgressColumn(
                "当前理论进度",
                format="%.4f%%",
                min_value=0.0,
                max_value=100.0,
            ),
            "当前目标数量": st.column_config.NumberColumn("当前目标数量", format="%,d"),
            "剩余数量": st.column_config.NumberColumn("剩余数量", format="%,d"),
            "剩余可交易分钟": st.column_config.NumberColumn("剩余可交易分钟", format="%d"),
        },
        hide_index=True,
    )

    expand_all = st.checkbox("展开全部订单", value=False)
    for idx, order in enumerate(orders):
        minute_df, anchor_df, total_minutes = calculate_schedule(
            order["order_time"], order["end_time"], order["quantity"], order["market"]
        )

        label = f"{order.get('stock', '')} - {order['market']} - {order['direction']} @ {order['limit_price']:.3f}"
        with st.expander(label, expanded=expand_all):
            delete_col, info_col = st.columns([1, 5])
            with delete_col:
                delete_order = st.button(
                    "删除该订单",
                    key=f"delete_order_{idx}",
                    type="secondary",
                )
            if delete_order:
                st.session_state.orders.pop(idx)
                st.rerun()

            st.caption(
                f"市场 {order['market']} | 收到时间 {order['order_time'].strftime('%H:%M')} | 结束时间 {order['end_time'].strftime('%H:%M')} | 订单数量 {order['quantity']:,}"
            )

            with st.form(f"edit_form_{idx}"):
                st.markdown("**修改订单**")
                market_edit = st.selectbox(
                    "市场",
                    ["港股", "A股"],
                    index=0 if order["market"] == "港股" else 1,
                )
                stock_edit = st.text_input("股票代码 / 名称", value=order["stock"])
                direction_edit = st.selectbox(
                    "交易方向",
                    ["买入", "卖出"],
                    index=0 if order["direction"] == "买入" else 1,
                )
                limit_price_edit = st.number_input(
                    "限价",
                    min_value=0.0,
                    value=float(order["limit_price"]),
                    format="%.3f",
                )
                quantity_text_edit = st.text_input(
                    "订单数量", value=f"{int(order['quantity']):,}"
                )
                order_time_edit = st.time_input(
                    "收到订单时间 (HH:MM)", value=order["order_time"], step=60
                )
                end_time_edit = st.time_input(
                    "订单结束时间 (HH:MM)", value=order["end_time"], step=60
                )
                if st.form_submit_button("保存修改"):
                    if (
                        market_edit != order["market"]
                        and end_time_edit == market_close_time(order["market"])
                    ):
                        end_time_edit = market_close_time(market_edit)
                    quantity_edit = parse_quantity(quantity_text_edit)
                    if quantity_edit is None:
                        st.error("订单数量请输入大于 0 的整数，例如 1,000,000。")
                    else:
                        st.session_state.orders[idx] = {
                            "stock": stock_edit,
                            "market": market_edit,
                            "direction": direction_edit,
                            "limit_price": limit_price_edit,
                            "quantity": quantity_edit,
                            "order_time": order_time_edit,
                            "end_time": end_time_edit,
                        }
                        st.success("订单已更新。页面刷新后会显示最新进度。")
                        st.rerun()

            if total_minutes is None:
                st.error("该订单在收到时间和结束时间之间没有剩余可交易时间，请检查时间设置。")
                continue

            total_hours = total_minutes / 60
            pace_per_hour = order["quantity"] / total_hours if total_hours else 0
            current_progress = calculate_current_progress(
                order["order_time"], order["end_time"], order["quantity"], order["market"]
            )

            col1, col2, col3 = st.columns(3)
            col1.metric("剩余可交易分钟", total_minutes)
            col2.metric("剩余可交易小时", f"{total_hours:.2f}")
            col3.metric("平均每小时目标", f"{pace_per_hour:,.0f} 股/小时")

            if current_progress:
                progress_col1, progress_col2, progress_col3 = st.columns(3)
                progress_col1.metric(
                    "当前理论进度",
                    f"{truncate_decimal(current_progress['cumulative_pct'] * 100):.4f}%",
                )
                progress_col2.metric(
                    "当前目标数量",
                    f"{current_progress['target_qty']:,} 股",
                )
                progress_col3.metric(
                    "当前剩余数量",
                    f"{current_progress['remaining_qty']:,} 股",
                )

            st.markdown("**整点目标进度**")
            st.dataframe(
                anchor_df,
                use_container_width=True,
                column_config={
                    "time": "时间",
                    "cumulative_pct": st.column_config.ProgressColumn(
                        "累计进度 %",
                        format="%.4f%%",
                        min_value=0.0,
                        max_value=100.0,
                    ),
                    "target_qty": st.column_config.NumberColumn("目标完成数量", format="%,d"),
                    "remaining_qty": st.column_config.NumberColumn(
                        "剩余数量", format="%,d"
                    ),
                },
                hide_index=True,
            )

            show_minutes = st.checkbox(
                "显示分钟级进度表", value=False, key=f"minutes_{idx}"
            )
            if show_minutes:
                st.dataframe(
                    minute_df,
                    use_container_width=True,
                    column_config={
                        "time": "时间",
                        "cumulative_pct": st.column_config.ProgressColumn(
                            "累计进度 %",
                            format="%.4f%%",
                            min_value=0.0,
                            max_value=100.0,
                        ),
                        "target_qty": st.column_config.NumberColumn("目标完成数量", format="%,d"),
                        "remaining_qty": st.column_config.NumberColumn(
                            "剩余数量", format="%,d"
                        ),
                    },
                    hide_index=True,
                )
                csv = minute_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "下载分钟级进度表 (CSV)",
                    data=csv,
                    file_name=f"schedule_{idx+1}.csv",
                    mime="text/csv",
                    key=f"download_{idx}",
                )
