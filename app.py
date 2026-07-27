import streamlit as st


st.set_page_config(
    page_title="产品报价计算器",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
    <style>
        .stApp {
            background: linear-gradient(135deg, #f7f9fc 0%, #eef4ff 100%);
        }
        .block-container {
            max-width: 1180px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        .app-title {
            font-size: clamp(2rem, 5vw, 3.1rem);
            font-weight: 800;
            letter-spacing: -0.04em;
            color: #17233c;
            margin-bottom: 0.25rem;
        }
        .app-subtitle {
            color: #667085;
            font-size: 1.05rem;
            margin-bottom: 1.5rem;
        }
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid #e5eaf2;
            border-radius: 16px;
            padding: 1rem 1.1rem;
            box-shadow: 0 8px 24px rgba(30, 58, 95, 0.06);
        }
        div[data-testid="stButton"] > button {
            min-height: 3rem;
            border-radius: 12px;
            font-size: 1.05rem;
            font-weight: 700;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 255, 0.78);
            border-radius: 18px;
        }
        @media (max-width: 640px) {
            .block-container { padding: 1.2rem 0.9rem 2rem; }
            .app-subtitle { font-size: 0.95rem; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def invalidate_result() -> None:
    """Hide a previous quote whenever any input changes."""
    st.session_state.quote_result = None


def money_rmb(value: float) -> str:
    return f"¥{value:,.2f}"


def money_usd(value: float) -> str:
    return f"${value:,.2f}"


if "quote_result" not in st.session_state:
    st.session_state.quote_result = None


st.markdown('<div class="app-title">产品报价计算器</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">一次填写产品、包装与物流信息，快速生成 RMB / USD 报价。</div>',
    unsafe_allow_html=True,
)


left, right = st.columns([1, 1], gap="large")

with left:
    with st.container(border=True):
        st.subheader("📦 产品信息")
        product_name = st.text_input(
            "产品名称",
            placeholder="例如：折叠桌",
            on_change=invalidate_result,
        )

        cbm_input_mode = st.radio(
            "CBM 录入方式",
            ["根据长宽高自动计算", "直接填写 CBM"],
            horizontal=True,
            on_change=invalidate_result,
        )

        if cbm_input_mode == "根据长宽高自动计算":
            size_cols = st.columns(3)
            with size_cols[0]:
                length_cm = st.number_input(
                    "长（cm）", min_value=0.0, value=0.0, step=1.0,
                    on_change=invalidate_result,
                )
            with size_cols[1]:
                width_cm = st.number_input(
                    "宽（cm）", min_value=0.0, value=0.0, step=1.0,
                    on_change=invalidate_result,
                )
            with size_cols[2]:
                height_cm = st.number_input(
                    "高（cm）", min_value=0.0, value=0.0, step=1.0,
                    on_change=invalidate_result,
                )
            manual_cbm = 0.0
        else:
            manual_cbm = st.number_input(
                "产品 CBM（m³）",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.4f",
                on_change=invalidate_result,
                help="该数值同时用于包装费，以及选择按 CBM 计算的国内、国际运费。",
            )
            length_cm = 0.0
            width_cm = 0.0
            height_cm = 0.0

        product_weight = st.number_input(
            "重量（kg）",
            min_value=0.0,
            value=0.0,
            step=0.1,
            on_change=invalidate_result,
        )
        packaging = st.selectbox(
            "包装方式",
            ["纸袋", "纸箱", "木架", "木箱"],
            on_change=invalidate_result,
        )
        manual_cbm_expansion_pct = 0
        if (
            cbm_input_mode == "直接填写 CBM"
            and packaging in ("木架", "木箱")
        ):
            manual_cbm_expansion_pct = st.selectbox(
                "木包装国际体积放大比例",
                [20, 30, 40],
                format_func=lambda value: f"{value}%",
                on_change=invalidate_result,
                help="只放大国际计费 CBM；包装费和国内运费仍使用原始 CBM。",
            )
            st.caption(
                "系统会按所选比例放大国际计费 CBM；原始 CBM 保持不变。"
            )

    with st.container(border=True):
        st.subheader("💰 产品报价")
        quote_mode = st.radio(
            "报价模式",
            ["直接报人民币价格", "成本 + 利润"],
            horizontal=True,
            on_change=invalidate_result,
        )

        if quote_mode == "直接报人民币价格":
            direct_quote = st.number_input(
                "含利润 RMB 报价（元）",
                min_value=0.0,
                value=0.0,
                step=10.0,
                on_change=invalidate_result,
            )
            cost_price = 0.0
            profit_margin = 0.0
        else:
            quote_cols = st.columns(2)
            with quote_cols[0]:
                cost_price = st.number_input(
                    "成本价（元）",
                    min_value=0.0,
                    value=0.0,
                    step=10.0,
                    on_change=invalidate_result,
                )
            with quote_cols[1]:
                profit_margin = st.number_input(
                    "利润点（%）",
                    min_value=0.0,
                    max_value=99.9,
                    value=20.0,
                    step=1.0,
                    on_change=invalidate_result,
                    help="报价 = 成本价 ÷（1 - 利润点%）",
                )
            direct_quote = 0.0

with right:
    with st.container(border=True):
        st.subheader("🚚 包装与国内运输")
        rate_cols = st.columns(2)
        with rate_cols[0]:
            wood_rack_rate = st.number_input(
                "木架单价（元/CBM）",
                min_value=0.0,
                value=300.0,
                step=10.0,
                on_change=invalidate_result,
                disabled=packaging != "木架",
            )
            if packaging != "木架":
                wood_rack_rate = 300.0
        with rate_cols[1]:
            wood_box_rate = st.number_input(
                "木箱单价（元/CBM）",
                min_value=0.0,
                value=400.0,
                step=10.0,
                on_change=invalidate_result,
                disabled=packaging != "木箱",
            )
            if packaging != "木箱":
                wood_box_rate = 400.0

        domestic_freight_mode = st.radio(
            "国内运费计算方式",
            ["按 CBM 计算", "直接填写人民币运费"],
            horizontal=True,
            on_change=invalidate_result,
        )
        if domestic_freight_mode == "按 CBM 计算":
            domestic_rate = st.number_input(
                "国内运费单价（元/CBM）",
                min_value=0.0,
                value=350.0,
                step=10.0,
                on_change=invalidate_result,
                help="厂家包邮时可填写 0",
            )
            direct_domestic_freight_rmb = 0.0
        else:
            direct_domestic_freight_rmb = st.number_input(
                "国内运费总价（RMB）",
                min_value=0.0,
                value=0.0,
                step=10.0,
                on_change=invalidate_result,
                help="厂家包邮时可填写 0",
            )
            domestic_rate = 0.0

    with st.container(border=True):
        st.subheader("✈️ 国际运输")
        exchange_rate = st.number_input(
            "汇率（USD/CNY）",
            min_value=0.0001,
            value=6.70,
            step=0.01,
            format="%.4f",
            on_change=invalidate_result,
            help="1 USD 可兑换的人民币金额。修改后重新计算，所有美元结果会同步更新。",
        )

        international_freight_mode = st.radio(
            "国际运费录入方式",
            ["按计费重量计算", "按 CBM 计算", "直接填写人民币运费"],
            horizontal=True,
            on_change=invalidate_result,
        )

        international_unit_rate = 0.0
        international_cbm_rate = 0.0
        charge_mode = "自动取实重/体积重较大值"
        manual_charge_weight = 0.0
        direct_international_freight_rmb = 0.0
        last_mile_usd = 0.0
        last_mile_rmb = 0.0

        if international_freight_mode == "按计费重量计算":
            freight_cols = st.columns(2)
            with freight_cols[0]:
                international_unit_rate = st.number_input(
                    "国际运费单价（元/kg）",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    on_change=invalidate_result,
                )
            with freight_cols[1]:
                charge_mode = st.selectbox(
                    "计费重量",
                    ["自动取实重/体积重较大值", "手动输入"],
                    on_change=invalidate_result,
                )

            manual_charge_weight = 0.0
            if charge_mode == "手动输入":
                manual_charge_weight = st.number_input(
                    "手动计费重量（kg）",
                    min_value=0.0,
                    value=0.0,
                    step=0.1,
                    on_change=invalidate_result,
                    help="仍会在结果中展示自动计算的实重和体积重，便于核对。",
                )
        elif international_freight_mode == "按 CBM 计算":
            international_cbm_rate = st.number_input(
                "国际运费单价（元/CBM）",
                min_value=0.0,
                value=0.0,
                step=10.0,
                on_change=invalidate_result,
                help="国际基础运费 = 产品 CBM × 国际运费单价",
            )

        if international_freight_mode != "直接填写人民币运费":
            st.caption("尾程派送费可由两种币种组成；没有对应币种费用时填 0。")
            delivery_cols = st.columns(2)
            with delivery_cols[0]:
                last_mile_usd = st.number_input(
                    "尾程派送费（USD）",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    on_change=invalidate_result,
                )
            with delivery_cols[1]:
                last_mile_rmb = st.number_input(
                    "尾程派送费（RMB）",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    on_change=invalidate_result,
                )
        else:
            direct_international_freight_rmb = st.number_input(
                "国际运费总价（RMB）",
                min_value=0.0,
                value=0.0,
                step=10.0,
                on_change=invalidate_result,
                help="填写包含国际运输及尾程派送在内的人民币总运费。",
            )
            st.caption("计算后会根据上方汇率自动换算为美元金额。")


calculate = st.button("计算报价", type="primary", use_container_width=True)

if calculate:
    if not product_name.strip():
        st.error("请输入产品名称。")
    elif (
        cbm_input_mode == "根据长宽高自动计算"
        and (length_cm <= 0 or width_cm <= 0 or height_cm <= 0)
    ):
        st.error("产品的长、宽、高都必须大于 0。")
    elif cbm_input_mode == "直接填写 CBM" and manual_cbm <= 0:
        st.error("请输入大于 0 的产品 CBM。")
    elif (
        international_freight_mode == "按计费重量计算"
        and charge_mode == "自动取实重/体积重较大值"
        and product_weight <= 0
    ):
        st.error("按计费重量计算国际运费时，产品重量必须大于 0。")
    elif quote_mode == "直接报人民币价格" and direct_quote <= 0:
        st.error("请输入大于 0 的含利润 RMB 报价。")
    elif quote_mode == "成本 + 利润" and cost_price <= 0:
        st.error("请输入大于 0 的成本价。")
    elif (
        international_freight_mode == "按计费重量计算"
        and charge_mode == "手动输入"
        and manual_charge_weight <= 0
    ):
        st.error("请输入大于 0 的手动计费重量。")
    elif (
        international_freight_mode == "直接填写人民币运费"
        and direct_international_freight_rmb <= 0
    ):
        st.error("请输入大于 0 的人民币国际运费总价。")
    else:
        if cbm_input_mode == "直接填写 CBM":
            cbm = manual_cbm
        else:
            cbm = length_cm * width_cm * height_cm / 1_000_000

        if packaging == "木架":
            packaging_fee = wood_rack_rate * cbm
        elif packaging == "木箱":
            packaging_fee = wood_box_rate * cbm
        else:
            packaging_fee = 0.0

        if domestic_freight_mode == "直接填写人民币运费":
            domestic_freight = direct_domestic_freight_rmb
        else:
            domestic_freight = domestic_rate * cbm

        if cbm_input_mode == "根据长宽高自动计算":
            # 木制包装为国际体积重预留空间，三边分别增加 15 cm。
            volume_extra_cm = 15.0 if packaging in ("木架", "木箱") else 0.0
            freight_length_m = (length_cm + volume_extra_cm) / 100
            freight_width_m = (width_cm + volume_extra_cm) / 100
            freight_height_m = (height_cm + volume_extra_cm) / 100
            international_cbm = (
                freight_length_m * freight_width_m * freight_height_m
            )
            volumetric_weight = international_cbm * 167
        else:
            # 手动 CBM 无法还原三边，木制包装按选择的百分比放大。
            volume_extra_cm = 0.0
            international_cbm = cbm * (1 + manual_cbm_expansion_pct / 100)
            volumetric_weight = international_cbm * 167
        auto_charge_weight = max(product_weight, volumetric_weight)
        charge_weight = (
            manual_charge_weight if charge_mode == "手动输入" else auto_charge_weight
        )

        last_mile_total_rmb = last_mile_rmb + last_mile_usd * exchange_rate
        if international_freight_mode == "直接填写人民币运费":
            international_freight_rmb = direct_international_freight_rmb
        elif international_freight_mode == "按 CBM 计算":
            international_freight_rmb = (
                international_cbm_rate * international_cbm + last_mile_total_rmb
            )
        else:
            international_freight_rmb = (
                international_unit_rate * charge_weight + last_mile_total_rmb
            )
        international_freight_usd = international_freight_rmb / exchange_rate

        if quote_mode == "直接报人民币价格":
            product_quote = direct_quote
        else:
            product_quote = cost_price / (1 - profit_margin / 100)

        final_total_rmb = (
            product_quote
            + packaging_fee
            + domestic_freight
            + international_freight_rmb
        )
        final_total_usd = final_total_rmb / exchange_rate

        if international_freight_mode == "直接填写人民币运费":
            weight_message = (
                f"本次使用直接填写的国际运费；计费重量不参与运费计算。"
                f"参考自动计费重量为 **{auto_charge_weight:,.2f} kg**"
                f"（实重 {product_weight:,.2f} kg，体积重 {volumetric_weight:,.2f} kg）。"
            )
        elif international_freight_mode == "按 CBM 计算":
            weight_message = (
                f"本次国际基础运费按 **{international_cbm:.4f} CBM** 计费，"
                f"单价为 **{money_rmb(international_cbm_rate)}/CBM**；"
                "实重和体积重不参与国际运费计算。"
            )
        elif charge_mode == "手动输入":
            weight_message = (
                f"本次使用手动计费重量 **{charge_weight:,.2f} kg**。"
                f"自动核算结果为 {auto_charge_weight:,.2f} kg。"
            )
        elif volumetric_weight > product_weight:
            weight_message = (
                f"体积重 **{volumetric_weight:,.2f} kg** 大于实重 "
                f"**{product_weight:,.2f} kg**，本次按体积重计费。"
            )
        elif product_weight > volumetric_weight:
            weight_message = (
                f"实重 **{product_weight:,.2f} kg** 大于体积重 "
                f"**{volumetric_weight:,.2f} kg**，本次按实重计费。"
            )
        else:
            weight_message = (
                f"实重与体积重相同，均为 **{product_weight:,.2f} kg**。"
            )

        st.session_state.quote_result = {
            "product_name": product_name.strip(),
            "length_cm": length_cm,
            "width_cm": width_cm,
            "height_cm": height_cm,
            "product_weight": product_weight,
            "packaging": packaging,
            "cbm": cbm,
            "international_cbm": international_cbm,
            "manual_cbm_expansion_pct": manual_cbm_expansion_pct,
            "packaging_fee": packaging_fee,
            "domestic_freight": domestic_freight,
            "volumetric_weight": volumetric_weight,
            "charge_weight": charge_weight,
            "weight_message": weight_message,
            "volume_extra_cm": volume_extra_cm,
            "last_mile_total_rmb": last_mile_total_rmb,
            "international_freight_rmb": international_freight_rmb,
            "international_freight_usd": international_freight_usd,
            "product_quote": product_quote,
            "final_total_rmb": final_total_rmb,
            "final_total_usd": final_total_usd,
            "exchange_rate": exchange_rate,
            "international_freight_mode": international_freight_mode,
            "domestic_freight_mode": domestic_freight_mode,
            "cbm_input_mode": cbm_input_mode,
        }


result = st.session_state.quote_result
if result:
    st.divider()
    st.subheader("报价结果")

    if result["cbm_input_mode"] == "根据长宽高自动计算":
        product_volume_summary = (
            f"{result['length_cm']:g} × {result['width_cm']:g} × "
            f"{result['height_cm']:g} cm"
        )
    else:
        product_volume_summary = f"直接填写 {result['cbm']:.4f} CBM"
    product_weight_summary = (
        f" · {result['product_weight']:g} kg"
        if result["product_weight"] > 0
        else ""
    )
    st.info(
        f"**{result['product_name']}** · "
        f"{product_volume_summary}{product_weight_summary} · {result['packaging']}包装"
    )

    total_cols = st.columns(2)
    with total_cols[0]:
        st.metric("最终总价（RMB）", money_rmb(result["final_total_rmb"]))
    with total_cols[1]:
        st.metric("最终总价（USD）", money_usd(result["final_total_usd"]))

    detail_cols = st.columns(5)
    with detail_cols[0]:
        st.metric("产品报价", money_rmb(result["product_quote"]))
    with detail_cols[1]:
        st.metric("原始 CBM", f"{result['cbm']:.4f} m³")
    with detail_cols[2]:
        st.metric("国际计费 CBM", f"{result['international_cbm']:.4f} m³")
    with detail_cols[3]:
        st.metric("包装费", money_rmb(result["packaging_fee"]))
    with detail_cols[4]:
        st.metric("国内运费", money_rmb(result["domestic_freight"]))

    freight_result_cols = st.columns(2)
    with freight_result_cols[0]:
        st.metric(
            "国际运费（RMB）",
            money_rmb(result["international_freight_rmb"]),
        )
    with freight_result_cols[1]:
        st.metric(
            "国际运费（USD）",
            money_usd(result["international_freight_usd"]),
        )

    st.success(result["weight_message"])
    if result["manual_cbm_expansion_pct"]:
        st.caption(
            f"木制包装的国际计费 CBM 已在原始 CBM 基础上放大 "
            f"{result['manual_cbm_expansion_pct']}%："
            f"{result['cbm']:.4f} → {result['international_cbm']:.4f} m³。"
            "包装费和国内运费仍按原始 CBM 计算。"
        )
    elif result["volume_extra_cm"]:
        st.caption(
            "木制包装体积重已按产品长、宽、高分别增加 15 cm 后计算；"
            "国际 CBM 运费也使用放大后的体积。包装费和国内运费仍按原始尺寸计算。"
        )
    result_caption = f"本次汇率：1 USD = {result['exchange_rate']:.4f} CNY"
    if result["international_freight_mode"] != "直接填写人民币运费":
        result_caption += (
            f" · 尾程派送费折合：{money_rmb(result['last_mile_total_rmb'])}"
        )
    else:
        result_caption += " · 国际运费采用直接填写的人民币总价"
    st.caption(result_caption)
