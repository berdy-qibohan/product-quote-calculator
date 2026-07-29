import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="多产品报价计算器",
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
            max-width: 1240px;
            padding-top: 1.7rem;
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
            margin-bottom: 1.35rem;
        }
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid #e5eaf2;
            border-radius: 16px;
            padding: 1rem 1.1rem;
            box-shadow: 0 8px 24px rgba(30, 58, 95, 0.06);
        }
        div[data-testid="stButton"] > button {
            min-height: 2.75rem;
            border-radius: 12px;
            font-weight: 700;
        }
        div[data-testid="stVerticalBlockBorderWrapper"],
        details[data-testid="stExpander"] {
            background: rgba(255, 255, 255, 0.82);
            border-radius: 18px;
        }
        .logic-note {
            padding: 0.8rem 1rem;
            background: #eef6ff;
            border: 1px solid #d6e9ff;
            border-radius: 12px;
            color: #31547a;
            margin: 0.35rem 0 1rem;
        }
        @media (max-width: 640px) {
            .block-container { padding: 1.1rem 0.8rem 2rem; }
            .app-subtitle { font-size: 0.95rem; }
            [data-testid="stMetric"] { padding: 0.8rem; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


CBM_MODES = [
    "方式A：输入单个长宽高",
    "方式B：输入多个长宽高",
    "方式C：直接填写总CBM",
]
PACKAGING_OPTIONS = ["纸袋", "纸箱", "木架", "木箱"]
RESULT_SCHEMA_VERSION = 3


def invalidate_result() -> None:
    """任何输入变化后清除旧结果。"""
    st.session_state.quote_result = None
    st.session_state.individual_results = {}
    st.session_state.show_update_preview = False
    st.session_state.update_success = False


def open_update_preview() -> None:
    """打开本次布局与体积重规则的可视化预览。"""
    st.session_state.show_update_preview = True
    st.session_state.update_success = False


def confirm_update() -> None:
    """确认已查看并接受本次更新。"""
    st.session_state.show_update_preview = False
    st.session_state.update_success = True


def cancel_update() -> None:
    """关闭预览，不影响正常报价输入与计算。"""
    st.session_state.show_update_preview = False
    st.session_state.update_success = False


def add_size_row(product_index: int) -> None:
    key = f"p{product_index}_size_rows"
    rows = list(st.session_state.get(key, [0]))
    rows.append(max(rows, default=-1) + 1)
    st.session_state[key] = rows
    invalidate_result()


def delete_size_row(product_index: int, row_id: int) -> None:
    key = f"p{product_index}_size_rows"
    rows = list(st.session_state.get(key, [0]))
    if len(rows) > 1 and row_id in rows:
        rows.remove(row_id)
        st.session_state[key] = rows
    invalidate_result()


def chinese_number(number: int) -> str:
    names = [
        "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
        "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
    ]
    return names[number - 1] if 1 <= number <= len(names) else str(number)


def money_rmb(value: float) -> str:
    return f"¥{value:,.2f}"


def money_usd(value: float) -> str:
    return f"${value:,.2f}"


def distribute_total(total: float, weights: list[float]) -> list[float]:
    """按计费占比分摊整票费用；全部为零时平均分摊。"""
    if not weights:
        return []
    weight_sum = sum(weights)
    if weight_sum > 0:
        return [total * weight / weight_sum for weight in weights]
    return [total / len(weights)] * len(weights)


def validate_product(product: dict, settings: dict) -> list[str]:
    errors = []
    label = product["label"]

    if not product["name"].strip():
        errors.append(f"{label}：请输入产品名称。")

    if product["cbm_mode"] in CBM_MODES[:2]:
        if not product["dimensions"]:
            errors.append(f"{label}：请至少保留一组尺寸。")
        for row_number, dimension in enumerate(product["dimensions"], start=1):
            if any(value <= 0 for value in dimension):
                errors.append(f"{label}：第 {row_number} 组长、宽、高都必须大于 0。")
                break
    elif product["manual_cbm"] <= 0:
        errors.append(f"{label}：请输入大于 0 的总 CBM。")

    if product["quote_mode"] == "直接报人民币价格" and product["direct_quote"] <= 0:
        errors.append(f"{label}：请输入大于 0 的含利润 RMB 报价。")
    if product["quote_mode"] == "成本 + 利润" and product["cost_price"] <= 0:
        errors.append(f"{label}：请输入大于 0 的成本价。")

    if (
        settings["international_mode"] == "按计费重量计算"
        and settings["charge_mode"] == "自动：各产品分别取实重/体积重较大值"
        and product["weight"] <= 0
    ):
        errors.append(f"{label}：按自动计费重量计算时，产品重量必须大于 0。")

    return errors


def prepare_product(
    product: dict,
    settings: dict,
    apply_new_volume_rule: bool = True,
) -> dict:
    """计算产品体积、体积重、包装费和产品报价。

    关键规则：
    1. 原始 CBM 始终用于包装费。
    2. 输入尺寸时，木架/木箱的每组长宽高各增加 15 cm，得到国际计费 CBM。
    3. 直接输入 CBM 时，木架/木箱按用户选择的 30%/35%/40%/50% 放大。
    4. 木包装的国内计费 CBM 和国际计费 CBM 都使用包装后体积；
       纸袋/纸箱的国内、国际计费 CBM 均使用原始体积。
    5. 体积重 = 国际计费 CBM × 167 kg。
    6. apply_new_volume_rule=False 仅供“修改前 vs 修改后”预览使用：
       国内运费使用原始 CBM，直接输入 CBM 的木包装不做百分比放大。
    """
    if product["cbm_mode"] == CBM_MODES[2]:
        cbm = product["manual_cbm"]
        international_cbm = cbm
        if (
            apply_new_volume_rule
            and product["packaging"] in ("木架", "木箱")
        ):
            international_cbm *= 1 + product["manual_expansion_pct"] / 100
        dimension_summary = f"直接填写 {cbm:.4f} CBM"
    else:
        cbm_values = [length * width * height / 1_000_000 for length, width, height in product["dimensions"]]
        cbm = sum(cbm_values)
        extra_cm = 15.0 if product["packaging"] in ("木架", "木箱") else 0.0
        international_cbm_values = [
            (length + extra_cm) * (width + extra_cm) * (height + extra_cm) / 1_000_000
            for length, width, height in product["dimensions"]
        ]
        international_cbm = sum(international_cbm_values)
        if product["cbm_mode"] == CBM_MODES[0]:
            length, width, height = product["dimensions"][0]
            dimension_summary = f"{length:g} × {width:g} × {height:g} cm"
        else:
            dimension_summary = f"{len(product['dimensions'])} 个包裹，合计 {cbm:.4f} CBM"

    # 木包装在国内运输前已经完成，因此国内运费也必须按包装后体积计费。
    # 预览“修改前”时仍使用原始 CBM，以便清楚显示本次规则变化。
    domestic_cbm = (
        international_cbm
        if apply_new_volume_rule and product["packaging"] in ("木架", "木箱")
        else cbm
    )

    volumetric_weight = international_cbm * 167
    auto_charge_weight = max(product["weight"], volumetric_weight)

    if product["packaging"] == "木架":
        packaging_fee = settings["wood_rack_rate"] * cbm
    elif product["packaging"] == "木箱":
        packaging_fee = settings["wood_box_rate"] * cbm
    else:
        packaging_fee = 0.0

    if product["quote_mode"] == "直接报人民币价格":
        product_quote = product["direct_quote"]
    else:
        product_quote = product["cost_price"] / (1 - product["profit_margin"] / 100)

    return {
        **product,
        "name": product["name"].strip(),
        "cbm": cbm,
        "domestic_cbm": domestic_cbm,
        "international_cbm": international_cbm,
        "volumetric_weight": volumetric_weight,
        "auto_charge_weight": auto_charge_weight,
        "charge_weight": auto_charge_weight,
        "packaging_fee": packaging_fee,
        "product_quote": product_quote,
        "dimension_summary": dimension_summary,
        "domestic_freight": 0.0,
        "international_freight_rmb": 0.0,
        "international_freight_usd": 0.0,
        "extra_service_share_rmb": 0.0,
    }


def calculate_products(
    products: list[dict],
    settings: dict,
    apply_new_volume_rule: bool = True,
) -> dict:
    prepared = [
        prepare_product(product, settings, apply_new_volume_rule)
        for product in products
    ]

    if settings["domestic_mode"] == "按 CBM 计算":
        domestic_values = [
            settings["domestic_rate"] * item["domestic_cbm"]
            for item in prepared
        ]
    else:
        domestic_values = distribute_total(
            settings["direct_domestic_rmb"],
            [item["domestic_cbm"] for item in prepared],
        )

    if (
        settings["international_mode"] == "按计费重量计算"
        and settings["charge_mode"] == "手动输入整票计费重量"
    ):
        manual_weights = distribute_total(
            settings["manual_total_charge_weight"],
            [item["auto_charge_weight"] for item in prepared],
        )
        for item, weight in zip(prepared, manual_weights):
            item["charge_weight"] = weight

    # 尾程派送费支持人民币和美元同时录入，美元按当前汇率折算。
    last_mile_total_rmb = (
        settings["last_mile_rmb"]
        + settings["last_mile_usd"] * settings["exchange_rate"]
    )
    inspection_fee_rmb = (
        settings["inspection_fee_rmb"]
        if settings["inspection_required"] == "需要"
        else 0.0
    )
    customs_fee_rmb = (
        settings["customs_fee_rmb"]
        if settings["customs_required"] == "需要"
        else 0.0
    )
    shipment_extra_total_rmb = (
        last_mile_total_rmb + inspection_fee_rmb + customs_fee_rmb
    )

    if settings["international_mode"] == "直接填写人民币总运费":
        allocation_weights = [item["international_cbm"] for item in prepared]
        base_values = distribute_total(
            settings["direct_international_rmb"],
            allocation_weights,
        )
    elif settings["international_mode"] == "按 CBM 计算":
        allocation_weights = [item["international_cbm"] for item in prepared]
        base_values = [
            settings["international_cbm_rate"] * item["international_cbm"]
            for item in prepared
        ]
    else:
        allocation_weights = [item["charge_weight"] for item in prepared]
        base_values = [
            settings["international_unit_rate"] * item["charge_weight"]
            for item in prepared
        ]

    extra_service_shares = distribute_total(
        shipment_extra_total_rmb,
        allocation_weights,
    )
    international_values = [
        base + extra
        for base, extra in zip(base_values, extra_service_shares)
    ]

    for item, domestic, international, extra_share in zip(
        prepared, domestic_values, international_values, extra_service_shares
    ):
        item["domestic_freight"] = domestic
        item["international_freight_rmb"] = international
        item["international_freight_usd"] = international / settings["exchange_rate"]
        item["extra_service_share_rmb"] = extra_share
        item["final_total_rmb"] = (
            item["product_quote"]
            + item["packaging_fee"]
            + domestic
            + international
        )
        item["final_total_usd"] = item["final_total_rmb"] / settings["exchange_rate"]

        if settings["international_mode"] == "直接填写人民币总运费":
            item["weight_message"] = (
                f"国际基础运费采用直接填写的整票人民币总价；"
                f"尾程、商检和报关费用另行加入并按国际计费 CBM 分摊。"
                f"本产品参考实重 {item['weight']:.2f} kg、体积重 {item['volumetric_weight']:.2f} kg。"
            )
        elif settings["international_mode"] == "按 CBM 计算":
            item["weight_message"] = (
                f"国际基础运费按 {item['international_cbm']:.4f} CBM 计算；"
                "体积重和实重仅供核对，不参与本模式运费计算。"
            )
        elif settings["charge_mode"] == "手动输入整票计费重量":
            item["weight_message"] = (
                f"整票手动计费重量已按各产品自动计费重量占比分摊；"
                f"本产品分摊 {item['charge_weight']:.2f} kg。"
            )
        elif item["volumetric_weight"] > item["weight"]:
            item["weight_message"] = (
                f"本产品多个包裹的体积重相加为 {item['volumetric_weight']:.2f} kg，"
                f"大于实重 {item['weight']:.2f} kg，本产品按体积重计费。"
            )
        elif item["weight"] > item["volumetric_weight"]:
            item["weight_message"] = (
                f"本产品实重 {item['weight']:.2f} kg 大于多个包裹合计体积重 "
                f"{item['volumetric_weight']:.2f} kg，本产品按实重计费。"
            )
        else:
            item["weight_message"] = f"本产品实重与体积重相同，均为 {item['weight']:.2f} kg。"

    totals = {
        "product_quote": sum(item["product_quote"] for item in prepared),
        "cbm": sum(item["cbm"] for item in prepared),
        "domestic_cbm": sum(item["domestic_cbm"] for item in prepared),
        "international_cbm": sum(item["international_cbm"] for item in prepared),
        "packaging_fee": sum(item["packaging_fee"] for item in prepared),
        "domestic_freight": sum(item["domestic_freight"] for item in prepared),
        "international_freight_rmb": sum(item["international_freight_rmb"] for item in prepared),
        "last_mile_total_rmb": last_mile_total_rmb,
        "inspection_fee_rmb": inspection_fee_rmb,
        "customs_fee_rmb": customs_fee_rmb,
        "shipment_extra_total_rmb": shipment_extra_total_rmb,
        "volumetric_weight": sum(item["volumetric_weight"] for item in prepared),
        "charge_weight": sum(item["charge_weight"] for item in prepared),
        "final_total_rmb": sum(item["final_total_rmb"] for item in prepared),
    }
    totals["international_freight_usd"] = totals["international_freight_rmb"] / settings["exchange_rate"]
    totals["final_total_usd"] = totals["final_total_rmb"] / settings["exchange_rate"]

    return {"products": prepared, "totals": totals, "settings": settings}


def render_compact_result(result: dict, exchange_rate: float) -> None:
    total_cols = st.columns(2)
    with total_cols[0]:
        st.metric("本产品总价（RMB）", money_rmb(result["final_total_rmb"]))
    with total_cols[1]:
        st.metric("本产品总价（USD）", money_usd(result["final_total_rmb"] / exchange_rate))

    detail_cols = st.columns(5)
    detail_cols[0].metric("原始 CBM", f"{result['cbm']:.4f}")
    detail_cols[1].metric("国内计费 CBM", f"{result['domestic_cbm']:.4f}")
    detail_cols[2].metric("包装费", money_rmb(result["packaging_fee"]))
    detail_cols[3].metric("国内运费", money_rmb(result["domestic_freight"]))
    detail_cols[4].metric("国际运费", money_rmb(result["international_freight_rmb"]))
    st.info(result["weight_message"])


def signed_money_change(value: float, currency: str) -> str:
    if abs(value) < 0.005:
        return "-"
    sign = "+" if value > 0 else "-"
    symbol = "¥" if currency == "RMB" else "$"
    return f"{sign}{symbol}{abs(value):,.2f}"


def percent_change(old_value: float, new_value: float) -> str:
    if abs(new_value - old_value) < 1e-9:
        return "-"
    if old_value <= 0:
        return "新增"
    change = (new_value - old_value) / old_value * 100
    return f"{change:+.2f}%"


def build_update_preview(products: list[dict], settings: dict) -> pd.DataFrame:
    """用当前输入数据对比直接 CBM 木包装规则修改前后的结果。"""
    old_result = calculate_products(
        products,
        settings,
        apply_new_volume_rule=False,
    )
    new_result = calculate_products(
        products,
        settings,
        apply_new_volume_rule=True,
    )
    old = old_result["totals"]
    new = new_result["totals"]

    rows = [
        {
            "项目": "产品CBM",
            "修改前结果": f"{old['cbm']:.4f} m³",
            "修改后结果": f"{new['cbm']:.4f} m³（不变）",
            "变化": "-",
        },
        {
            "项目": "国内计费CBM",
            "修改前结果": f"{old['domestic_cbm']:.4f} m³",
            "修改后结果": f"{new['domestic_cbm']:.4f} m³（包装后）",
            "变化": percent_change(old["domestic_cbm"], new["domestic_cbm"]),
        },
        {
            "项目": "体积重",
            "修改前结果": f"{old['volumetric_weight']:.2f} kg（原始）",
            "修改后结果": f"{new['volumetric_weight']:.2f} kg（放大后）",
            "变化": percent_change(old["volumetric_weight"], new["volumetric_weight"]),
        },
        {
            "项目": "国内运费",
            "修改前结果": money_rmb(old["domestic_freight"]),
            "修改后结果": money_rmb(new["domestic_freight"]),
            "变化": signed_money_change(
                new["domestic_freight"] - old["domestic_freight"],
                "RMB",
            ),
        },
        {
            "项目": "国际运费",
            "修改前结果": money_rmb(old["international_freight_rmb"]),
            "修改后结果": money_rmb(new["international_freight_rmb"]),
            "变化": signed_money_change(
                new["international_freight_rmb"] - old["international_freight_rmb"],
                "RMB",
            ),
        },
        {
            "项目": "最终总价(RMB)",
            "修改前结果": money_rmb(old["final_total_rmb"]),
            "修改后结果": money_rmb(new["final_total_rmb"]),
            "变化": signed_money_change(
                new["final_total_rmb"] - old["final_total_rmb"],
                "RMB",
            ),
        },
        {
            "项目": "最终总价(USD)",
            "修改前结果": money_usd(old["final_total_usd"]),
            "修改后结果": money_usd(new["final_total_usd"]),
            "变化": signed_money_change(
                new["final_total_usd"] - old["final_total_usd"],
                "USD",
            ),
        },
    ]
    return pd.DataFrame(rows)


if "quote_result" not in st.session_state:
    st.session_state.quote_result = None
if "individual_results" not in st.session_state:
    st.session_state.individual_results = {}
if "show_update_preview" not in st.session_state:
    st.session_state.show_update_preview = False
if "update_success" not in st.session_state:
    st.session_state.update_success = False

# 计算结果字段发生升级时自动清除旧缓存，避免热更新后读取旧结构报错。
if st.session_state.get("result_schema_version") != RESULT_SCHEMA_VERSION:
    st.session_state.quote_result = None
    st.session_state.individual_results = {}
    st.session_state.result_schema_version = RESULT_SCHEMA_VERSION


st.markdown('<div class="app-title">多产品报价计算器</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">支持多个产品、多个包裹尺寸，以及统一的包装和物流计费设置。</div>',
    unsafe_allow_html=True,
)

if st.session_state.update_success:
    st.success("✅ 更新成功，新规则已生效")


top_cols = st.columns([1, 2.2])
with top_cols[0]:
    product_count = int(
        st.number_input(
            "产品数量",
            min_value=1,
            max_value=20,
            value=1,
            step=1,
            key="product_count",
            on_change=invalidate_result,
            help="修改数量后，页面会自动增加或减少产品区块。",
        )
    )
with top_cols[1]:
    st.markdown(
        '<div class="logic-note">计费规则：木架/木箱的国内和国际运输均按包装后体积；包装费仍按原始 CBM。同一产品的多个包裹体积重相加，尾程派送费按整票只计一次。</div>',
        unsafe_allow_html=True,
    )

# 先创建产品信息容器。虽然全局设置变量在代码中先完成采集，
# 产品内容会写入这个预留容器，因此视觉顺序始终是“产品在上、运费在下”。
products_section = st.container()

with st.expander("⚙️ 全局价格与物流设置（所有产品共用）", expanded=True):
    global_left, global_right = st.columns(2, gap="large")

    with global_left:
        st.markdown("#### 汇率与包装单价")
        exchange_rate = st.number_input(
            "汇率（USD/CNY）",
            min_value=0.0001,
            value=6.70,
            step=0.01,
            format="%.4f",
            key="exchange_rate",
            on_change=invalidate_result,
            help="1 USD 可兑换的人民币金额。",
        )
        package_rate_cols = st.columns(2)
        with package_rate_cols[0]:
            wood_rack_rate = st.number_input(
                "木架单价（元/CBM）",
                min_value=0.0,
                value=300.0,
                step=10.0,
                key="wood_rack_rate",
                on_change=invalidate_result,
            )
        with package_rate_cols[1]:
            wood_box_rate = st.number_input(
                "木箱单价（元/CBM）",
                min_value=0.0,
                value=400.0,
                step=10.0,
                key="wood_box_rate",
                on_change=invalidate_result,
            )

        st.markdown("#### 国内运输")
        domestic_mode = st.radio(
            "国内运费计算方式",
            ["按 CBM 计算", "直接填写整票人民币运费"],
            horizontal=True,
            key="domestic_mode",
            on_change=invalidate_result,
        )
        if domestic_mode == "按 CBM 计算":
            domestic_rate = st.number_input(
                "国内运费单价（元/CBM）",
                min_value=0.0,
                value=350.0,
                step=10.0,
                key="domestic_rate",
                on_change=invalidate_result,
                help="厂家包邮时可以填写 0。",
            )
            direct_domestic_rmb = 0.0
        else:
            direct_domestic_rmb = st.number_input(
                "国内运费整票总价（RMB）",
                min_value=0.0,
                value=0.0,
                step=10.0,
                key="direct_domestic_rmb",
                on_change=invalidate_result,
                help="汇总时按各产品国内计费 CBM 占比分摊，整票只计一次。",
            )
            domestic_rate = 0.0

    with global_right:
        st.markdown("#### 国际运输")
        international_mode = st.radio(
            "国际运费计算方式",
            ["按计费重量计算", "按 CBM 计算", "直接填写人民币总运费"],
            horizontal=True,
            key="international_mode",
            on_change=invalidate_result,
        )

        international_unit_rate = 0.0
        international_cbm_rate = 0.0
        manual_total_charge_weight = 0.0
        charge_mode = "自动：各产品分别取实重/体积重较大值"
        direct_international_rmb = 0.0
        tail_fee_mode = "人民币（RMB）"
        last_mile_usd = 0.0
        last_mile_rmb = 0.0
        inspection_required = "不需要"
        inspection_fee_rmb = 0.0
        customs_required = "不需要"
        customs_fee_rmb = 0.0

        if international_mode == "按计费重量计算":
            freight_cols = st.columns(2)
            with freight_cols[0]:
                international_unit_rate = st.number_input(
                    "国际运费单价（元/kg）",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    key="international_unit_rate",
                    on_change=invalidate_result,
                )
            with freight_cols[1]:
                charge_mode = st.selectbox(
                    "计费重量模式",
                    ["自动：各产品分别取实重/体积重较大值", "手动输入整票计费重量"],
                    key="charge_mode",
                    on_change=invalidate_result,
                )
            if charge_mode == "手动输入整票计费重量":
                manual_total_charge_weight = st.number_input(
                    "整票手动计费重量（kg）",
                    min_value=0.0,
                    value=0.0,
                    step=0.1,
                    key="manual_total_charge_weight",
                    on_change=invalidate_result,
                    help="按各产品自动计费重量占比分摊到产品明细。",
                )
        elif international_mode == "按 CBM 计算":
            international_cbm_rate = st.number_input(
                "国际运费单价（元/CBM）",
                min_value=0.0,
                value=0.0,
                step=10.0,
                key="international_cbm_rate",
                on_change=invalidate_result,
            )
        else:
            direct_international_rmb = st.number_input(
                "国际运费整票总价（RMB）",
                min_value=0.0,
                value=0.0,
                step=10.0,
                key="direct_international_rmb",
                on_change=invalidate_result,
                help="这里填写基础国际运费；尾程、商检和报关费用由下方另行添加。",
            )

        st.markdown("##### 尾程派送费")
        tail_fee_mode = st.radio(
            "尾程派送费录入币种",
            ["人民币（RMB）", "美元（USD）", "人民币 + 美元"],
            horizontal=True,
            key="tail_fee_mode",
            on_change=invalidate_result,
            help="选择任意一种币种，或同时录入两种币种；美元会按当前汇率换算。",
        )
        st.caption("尾程派送费是整票费用，只计一次，再按各产品计费占比分摊。")
        if tail_fee_mode == "人民币 + 美元":
            tail_cols = st.columns(2)
            with tail_cols[0]:
                last_mile_rmb = st.number_input(
                    "尾程派送费（RMB）",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    key="last_mile_rmb",
                    on_change=invalidate_result,
                )
            with tail_cols[1]:
                last_mile_usd = st.number_input(
                    "尾程派送费（USD）",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    key="last_mile_usd",
                    on_change=invalidate_result,
                )
        elif tail_fee_mode == "美元（USD）":
            last_mile_usd = st.number_input(
                "尾程派送费（USD）",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key="last_mile_usd",
                on_change=invalidate_result,
            )
        else:
            last_mile_rmb = st.number_input(
                "尾程派送费（RMB）",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key="last_mile_rmb",
                on_change=invalidate_result,
            )

        st.markdown("##### 商检与报关")
        service_cols = st.columns(2)
        with service_cols[0]:
            inspection_required = st.radio(
                "是否需要商检",
                ["不需要", "需要"],
                horizontal=True,
                key="inspection_required",
                on_change=invalidate_result,
            )
            if inspection_required == "需要":
                inspection_fee_rmb = st.number_input(
                    "商检费用（RMB）",
                    min_value=0.0,
                    value=0.0,
                    step=10.0,
                    key="inspection_fee_rmb",
                    on_change=invalidate_result,
                    help="整票只收取一次。",
                )
        with service_cols[1]:
            customs_required = st.radio(
                "是否需要报关",
                ["不需要", "需要"],
                horizontal=True,
                key="customs_required",
                on_change=invalidate_result,
            )
            if customs_required == "需要":
                customs_fee_rmb = st.number_input(
                    "报关费用（RMB）",
                    min_value=0.0,
                    value=0.0,
                    step=10.0,
                    key="customs_fee_rmb",
                    on_change=invalidate_result,
                    help="整票只收取一次。",
                )


settings = {
    "exchange_rate": exchange_rate,
    "wood_rack_rate": wood_rack_rate,
    "wood_box_rate": wood_box_rate,
    "domestic_mode": domestic_mode,
    "domestic_rate": domestic_rate,
    "direct_domestic_rmb": direct_domestic_rmb,
    "international_mode": international_mode,
    "international_unit_rate": international_unit_rate,
    "international_cbm_rate": international_cbm_rate,
    "charge_mode": charge_mode,
    "manual_total_charge_weight": manual_total_charge_weight,
    "direct_international_rmb": direct_international_rmb,
    "tail_fee_mode": tail_fee_mode,
    "last_mile_usd": last_mile_usd,
    "last_mile_rmb": last_mile_rmb,
    "inspection_required": inspection_required,
    "inspection_fee_rmb": inspection_fee_rmb,
    "customs_required": customs_required,
    "customs_fee_rmb": customs_fee_rmb,
}


products_section.subheader("📦 产品信息")
products = []

for product_index in range(product_count):
    product_number = product_index + 1
    product_label = f"产品{chinese_number(product_number)}"
    saved_name = st.session_state.get(f"p{product_index}_name", "").strip()
    expander_title = f"{product_label}：{saved_name or '未命名产品'}"

    with products_section.expander(expander_title, expanded=product_index == 0):
        info_left, info_right = st.columns(2, gap="large")

        with info_left:
            product_name = st.text_input(
                "产品名称",
                placeholder="例如：折叠桌",
                key=f"p{product_index}_name",
                on_change=invalidate_result,
            )
            cbm_mode = st.radio(
                "CBM 录入方式",
                CBM_MODES,
                key=f"p{product_index}_cbm_mode",
                on_change=invalidate_result,
            )

            dimensions = []
            manual_cbm = 0.0
            if cbm_mode == CBM_MODES[0]:
                size_cols = st.columns(3)
                length = size_cols[0].number_input(
                    "长（cm）", min_value=0.0, value=0.0, step=1.0,
                    key=f"p{product_index}_single_length", on_change=invalidate_result,
                )
                width = size_cols[1].number_input(
                    "宽（cm）", min_value=0.0, value=0.0, step=1.0,
                    key=f"p{product_index}_single_width", on_change=invalidate_result,
                )
                height = size_cols[2].number_input(
                    "高（cm）", min_value=0.0, value=0.0, step=1.0,
                    key=f"p{product_index}_single_height", on_change=invalidate_result,
                )
                dimensions = [(length, width, height)]
            elif cbm_mode == CBM_MODES[1]:
                row_key = f"p{product_index}_size_rows"
                if row_key not in st.session_state:
                    st.session_state[row_key] = [0]
                row_ids = list(st.session_state[row_key])

                for visible_row, row_id in enumerate(row_ids, start=1):
                    st.caption(f"第 {visible_row} 组包装尺寸")
                    row_cols = st.columns([1, 1, 1, 0.48])
                    length = row_cols[0].number_input(
                        "长（cm）", min_value=0.0, value=0.0, step=1.0,
                        key=f"p{product_index}_r{row_id}_length", on_change=invalidate_result,
                    )
                    width = row_cols[1].number_input(
                        "宽（cm）", min_value=0.0, value=0.0, step=1.0,
                        key=f"p{product_index}_r{row_id}_width", on_change=invalidate_result,
                    )
                    height = row_cols[2].number_input(
                        "高（cm）", min_value=0.0, value=0.0, step=1.0,
                        key=f"p{product_index}_r{row_id}_height", on_change=invalidate_result,
                    )
                    row_cols[3].button(
                        "删除",
                        key=f"p{product_index}_r{row_id}_delete",
                        on_click=delete_size_row,
                        args=(product_index, row_id),
                        disabled=len(row_ids) == 1,
                        width="stretch",
                    )
                    dimensions.append((length, width, height))

                st.button(
                    "➕ 添加一组尺寸",
                    key=f"p{product_index}_add_size",
                    on_click=add_size_row,
                    args=(product_index,),
                    width="stretch",
                )
                entered_cbm = sum(length * width * height / 1_000_000 for length, width, height in dimensions)
                st.caption(f"当前多组尺寸合计：{entered_cbm:.4f} CBM（计算按钮点击后写入报价结果）")
            else:
                manual_cbm = st.number_input(
                    "总 CBM（m³）",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.4f",
                    key=f"p{product_index}_manual_cbm",
                    on_change=invalidate_result,
                )

            product_weight = st.number_input(
                "产品总重量（kg）",
                min_value=0.0,
                value=0.0,
                step=0.1,
                key=f"p{product_index}_weight",
                on_change=invalidate_result,
                help="多个包裹时填写该产品所有包裹的总实重。",
            )

        with info_right:
            packaging = st.selectbox(
                "包装方式",
                PACKAGING_OPTIONS,
                key=f"p{product_index}_packaging",
                on_change=invalidate_result,
            )
            manual_expansion_pct = 0
            if cbm_mode == CBM_MODES[2] and packaging in ("木架", "木箱"):
                manual_expansion_pct = st.selectbox(
                    "木包装国际体积放大比例",
                    [30, 35, 40, 50],
                    format_func=lambda value: f"{value}%",
                    key=f"p{product_index}_manual_expansion_v2",
                    on_change=invalidate_result,
                    help="国内和国际运输均使用放大后的 CBM；包装费仍使用原始 CBM。",
                )
            elif cbm_mode in CBM_MODES[:2] and packaging in ("木架", "木箱"):
                st.caption("国内和国际计费体积会将每组包装的长、宽、高分别增加 15 cm；包装费仍按原始 CBM。")

            quote_mode = st.radio(
                "报价模式",
                ["直接报人民币价格", "成本 + 利润"],
                horizontal=True,
                key=f"p{product_index}_quote_mode",
                on_change=invalidate_result,
            )
            direct_quote = 0.0
            cost_price = 0.0
            profit_margin = 0.0
            if quote_mode == "直接报人民币价格":
                direct_quote = st.number_input(
                    "含利润 RMB 报价（元）",
                    min_value=0.0,
                    value=0.0,
                    step=10.0,
                    key=f"p{product_index}_direct_quote",
                    on_change=invalidate_result,
                )
            else:
                quote_cols = st.columns(2)
                cost_price = quote_cols[0].number_input(
                    "成本价（元）",
                    min_value=0.0,
                    value=0.0,
                    step=10.0,
                    key=f"p{product_index}_cost_price",
                    on_change=invalidate_result,
                )
                profit_margin = quote_cols[1].number_input(
                    "利润点（%）",
                    min_value=0.0,
                    max_value=99.9,
                    value=20.0,
                    step=1.0,
                    key=f"p{product_index}_profit_margin",
                    on_change=invalidate_result,
                    help="报价 = 成本价 ÷（1 - 利润点%）",
                )

        product = {
            "index": product_index,
            "label": product_label,
            "name": product_name,
            "cbm_mode": cbm_mode,
            "dimensions": dimensions,
            "manual_cbm": manual_cbm,
            "weight": product_weight,
            "packaging": packaging,
            "manual_expansion_pct": manual_expansion_pct,
            "quote_mode": quote_mode,
            "direct_quote": direct_quote,
            "cost_price": cost_price,
            "profit_margin": profit_margin,
        }
        products.append(product)

        if st.button(
            f"单独计算{product_label}",
            key=f"p{product_index}_calculate",
            type="secondary",
            width="stretch",
        ):
            product_errors = validate_product(product, settings)
            if (
                settings["international_mode"] == "按计费重量计算"
                and settings["charge_mode"] == "手动输入整票计费重量"
                and settings["manual_total_charge_weight"] <= 0
            ):
                product_errors.append("请输入大于 0 的整票手动计费重量。")
            if product_errors:
                for error in product_errors:
                    st.error(error)
            else:
                individual = calculate_products([product], settings)["products"][0]
                st.session_state.individual_results[product_index] = individual

        if product_index in st.session_state.individual_results:
            render_compact_result(
                st.session_state.individual_results[product_index],
                settings["exchange_rate"],
            )


st.button(
    "🔎 预览修改",
    key="preview_update_button",
    type="secondary",
    width="stretch",
    on_click=open_update_preview,
)

if st.session_state.show_update_preview:
    with st.expander("本次修改预览与确认", expanded=True):
        st.markdown(
            """
            **本次修改摘要**

            - 修改一：页面布局调整为“产品信息在上、运费设置在下”，计算按钮位于最底部。
            - 修改二：体积重规则优化。输入尺寸的木包装每边加 15 cm；直接输入 CBM 的木包装按 30% / 35% / 40% / 50% 放大。
            - 包装费仍按原始 CBM；木包装的国内运费和国际运输均按包装后体积计算。
            """
        )
        st.dataframe(
            build_update_preview(products, settings),
            width="stretch",
            hide_index=True,
        )
        confirm_col, cancel_col = st.columns(2)
        confirm_col.button(
            "✅ 确认更新",
            key="confirm_update_button",
            type="primary",
            width="stretch",
            on_click=confirm_update,
        )
        cancel_col.button(
            "取消",
            key="cancel_update_button",
            type="secondary",
            width="stretch",
            on_click=cancel_update,
        )


calculate_all = st.button(
    "计算全部产品并生成汇总",
    type="primary",
    width="stretch",
)

if calculate_all:
    all_errors = []
    for product in products:
        all_errors.extend(validate_product(product, settings))

    if (
        settings["international_mode"] == "按计费重量计算"
        and settings["charge_mode"] == "手动输入整票计费重量"
        and settings["manual_total_charge_weight"] <= 0
    ):
        all_errors.append("请输入大于 0 的整票手动计费重量。")

    if all_errors:
        st.session_state.quote_result = None
        for error in all_errors:
            st.error(error)
    else:
        st.session_state.quote_result = calculate_products(products, settings)


result = st.session_state.quote_result
if result:
    totals = result["totals"]
    result_settings = result["settings"]

    st.divider()
    st.subheader("📊 全部产品汇总")

    total_cols = st.columns(2)
    total_cols[0].metric("所有产品最终总价（RMB）", money_rmb(totals["final_total_rmb"]))
    total_cols[1].metric("所有产品最终总价（USD）", money_usd(totals["final_total_usd"]))

    summary_cols = st.columns(6)
    summary_cols[0].metric("产品报价总和", money_rmb(totals["product_quote"]))
    summary_cols[1].metric("原始总 CBM", f"{totals['cbm']:.4f} m³")
    summary_cols[2].metric("国内计费总 CBM", f"{totals['domestic_cbm']:.4f} m³")
    summary_cols[3].metric("包装费总和", money_rmb(totals["packaging_fee"]))
    summary_cols[4].metric("国内运费总和", money_rmb(totals["domestic_freight"]))
    summary_cols[5].metric("国际运费总和", money_rmb(totals["international_freight_rmb"]))

    extra_cols = st.columns(4)
    extra_cols[0].metric("尾程派送费（折合RMB）", money_rmb(totals["last_mile_total_rmb"]))
    extra_cols[1].metric("商检费用", money_rmb(totals["inspection_fee_rmb"]))
    extra_cols[2].metric("报关费用", money_rmb(totals["customs_fee_rmb"]))
    extra_cols[3].metric("国际附加费合计", money_rmb(totals["shipment_extra_total_rmb"]))

    table_rows = []
    for item in result["products"]:
        table_rows.append(
            {
                "产品": item["name"],
                "包装": item["packaging"],
                "原始CBM": f"{item['cbm']:.4f}",
                "国内计费CBM": f"{item['domestic_cbm']:.4f}",
                "产品报价(RMB)": f"{item['product_quote']:,.2f}",
                "包装费(RMB)": f"{item['packaging_fee']:,.2f}",
                "国内运费(RMB)": f"{item['domestic_freight']:,.2f}",
                "国际运费(RMB)": f"{item['international_freight_rmb']:,.2f}",
                "最终总价(RMB)": f"{item['final_total_rmb']:,.2f}",
                "最终总价(USD)": f"{item['final_total_usd']:,.2f}",
            }
        )
    st.dataframe(pd.DataFrame(table_rows), width="stretch", hide_index=True)

    st.markdown("#### 各产品报价明细")
    for item in result["products"]:
        with st.expander(f"{item['label']}：{item['name']}"):
            st.info(
                f"**{item['name']}** · {item['dimension_summary']} · "
                f"{item['weight']:g} kg · {item['packaging']}包装"
            )
            render_compact_result(item, result_settings["exchange_rate"])
            reference_cols = st.columns(3)
            reference_cols[0].metric("国际计费 CBM", f"{item['international_cbm']:.4f} m³")
            reference_cols[1].metric("体积重", f"{item['volumetric_weight']:.2f} kg")
            reference_cols[2].metric("计费重量", f"{item['charge_weight']:.2f} kg")

    st.success(
        f"多个包裹的体积重已按各包裹分别计算后相加；多个产品的计费重量合计为 "
        f"{totals['charge_weight']:.2f} kg。"
    )
    st.caption(
        f"本次汇率：1 USD = {result_settings['exchange_rate']:.4f} CNY · "
        f"国际运费合计：{money_rmb(totals['international_freight_rmb'])} / "
        f"{money_usd(totals['international_freight_usd'])} · "
        f"其中尾程、商检和报关合计：{money_rmb(totals['shipment_extra_total_rmb'])}"
    )
