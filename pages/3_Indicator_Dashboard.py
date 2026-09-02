from pathlib import Path

indicator_page = Path(
    "/content/predictive_monitoring_app/"
    "pages/3_Indicator_Dashboard.py"
)

page_code = indicator_page.read_text(
    encoding="utf-8"
)

start_marker = (
    "# --------------------------------------------------\n"
    "# ACTUAL, TARGET, AND FORECAST TREND\n"
    "# --------------------------------------------------"
)

end_marker = (
    "# --------------------------------------------------\n"
    "# PERFORMANCE GAP VISUAL\n"
    "# --------------------------------------------------"
)

if start_marker not in page_code:
    raise ValueError(
        "The beginning of the old trend section "
        "was not found."
    )

if end_marker not in page_code:
    raise ValueError(
        "The end of the old trend section "
        "was not found."
    )

before_section = page_code.split(
    start_marker,
    1
)[0]

after_section = page_code.split(
    end_marker,
    1
)[1]

new_trend_section = '''
# --------------------------------------------------
# THREE PERFORMANCE TREND CHARTS
# --------------------------------------------------

st.divider()

st.subheader("Performance and Forecast Trend Analysis")

st.caption(
    "The following charts show how quarterly performance, "
    "annual outlook, and life-of-project outlook have "
    "changed up to the selected reporting period."
)


# Use only records available up to the selected period

trend_history = history.copy()

trend_history = trend_history.sort_values(
    "PeriodIndex"
).reset_index(drop=True)


# --------------------------------------------------
# CHART 1: QUARTERLY ACTUAL VS TARGET
# --------------------------------------------------

st.markdown("### 1. Quarterly Actual vs Target")


quarter_chart = go.Figure()


quarter_chart.add_trace(
    go.Scatter(
        x=trend_history["PeriodLabel"],
        y=trend_history["QuarterTarget"],
        mode="lines+markers",
        name="Quarter Target",
        line=dict(
            color="#2E7D32",
            width=3
        ),
        marker=dict(
            size=8
        )
    )
)


quarter_chart.add_trace(
    go.Scatter(
        x=trend_history["PeriodLabel"],
        y=trend_history["QuarterActual"],
        mode="lines+markers",
        name="Quarter Actual",
        line=dict(
            color="#1F77B4",
            width=3
        ),
        marker=dict(
            size=8
        )
    )
)


quarter_chart.add_vline(
    x=len(trend_history) - 1,
    line_width=2,
    line_dash="dot",
    line_color="#6B7280"
)


quarter_chart.update_layout(
    xaxis_title="Project Reporting Period",
    yaxis_title=str(
        current_record.get(
            "Unit",
            "Indicator value"
        )
    ),
    legend_title="Series",
    hovermode="x unified",
    margin=dict(
        l=20,
        r=20,
        t=20,
        b=20
    )
)


st.plotly_chart(
    quarter_chart,
    use_container_width=True
)


st.caption(
    "The blue line shows reported quarterly actuals. "
    "The green line shows planned quarterly targets. "
    "The vertical dotted line marks the selected "
    "reporting period."
)


# --------------------------------------------------
# SHARED FORECAST-INDEX CHART FUNCTION
# --------------------------------------------------

def create_forecast_index_chart(
    dataframe,
    value_column,
    chart_title,
    line_color
):

    chart_data = dataframe[
        [
            "PeriodIndex",
            "PeriodLabel",
            value_column
        ]
    ].copy()

    chart_data = chart_data.dropna(
        subset=[value_column]
    )

    chart = go.Figure()


    # Off Track background: below 80%

    chart.add_hrect(
        y0=0,
        y1=0.80,
        fillcolor="#FDECEC",
        opacity=0.45,
        line_width=0,
        annotation_text="Off Track",
        annotation_position="top left"
    )


    # At Risk background: 80% to below 100%

    chart.add_hrect(
        y0=0.80,
        y1=1.00,
        fillcolor="#FFF8E1",
        opacity=0.50,
        line_width=0,
        annotation_text="At Risk",
        annotation_position="top left"
    )


    # On Track background: 100% and above

    upper_limit = 1.20

    if not chart_data.empty:

        observed_maximum = (
            chart_data[value_column]
            .replace(
                [np.inf, -np.inf],
                np.nan
            )
            .dropna()
            .max()
        )

        if not pd.isna(observed_maximum):

            upper_limit = max(
                1.20,
                float(observed_maximum) * 1.10
            )


    chart.add_hrect(
        y0=1.00,
        y1=upper_limit,
        fillcolor="#EFF8F0",
        opacity=0.40,
        line_width=0,
        annotation_text="On Track",
        annotation_position="top left"
    )


    chart.add_trace(
        go.Scatter(
            x=chart_data["PeriodLabel"],
            y=chart_data[value_column],
            mode="lines+markers",
            name=chart_title,
            line=dict(
                color=line_color,
                width=3
            ),
            marker=dict(
                size=8
            )
        )
    )


    # 100% target line

    chart.add_hline(
        y=1.00,
        line_width=2,
        line_dash="dash",
        line_color="#2E7D32",
        annotation_text="100% target",
        annotation_position="top right"
    )


    # 80% risk threshold

    chart.add_hline(
        y=0.80,
        line_width=2,
        line_dash="dot",
        line_color="#C62828",
        annotation_text="80% threshold",
        annotation_position="bottom right"
    )


    chart.update_layout(
        xaxis_title="Project Reporting Period",
        yaxis_title="Forecast Achievement Index",
        hovermode="x unified",
        showlegend=False,
        margin=dict(
            l=20,
            r=20,
            t=25,
            b=20
        )
    )


    chart.update_yaxes(
        tickformat=".0%",
        range=[
            0,
            upper_limit
        ]
    )


    return chart, chart_data


# --------------------------------------------------
# CHART 2: ANNUAL FORECAST INDEX TREND
# --------------------------------------------------

st.markdown("### 2. Annual Forecast Index Trend")


if "AnnualForecastRatio" in trend_history.columns:

    annual_forecast_chart, annual_chart_data = (
        create_forecast_index_chart(
            dataframe=trend_history,
            value_column="AnnualForecastRatio",
            chart_title="Annual Forecast Index",
            line_color="#F28E2B"
        )
    )


    if annual_chart_data.empty:

        st.info(
            "Annual forecast-index values are not "
            "available for this indicator."
        )

    else:

        st.plotly_chart(
            annual_forecast_chart,
            use_container_width=True
        )


        first_annual_value = (
            annual_chart_data[
                "AnnualForecastRatio"
            ].iloc[0]
        )

        latest_annual_value = (
            annual_chart_data[
                "AnnualForecastRatio"
            ].iloc[-1]
        )

        annual_change = (
            latest_annual_value
            - first_annual_value
        )


        st.caption(
            "The annual forecast index estimates the "
            "share of the annual target likely to be "
            "achieved if the observed annual pace "
            "continues."
        )


        if annual_change > 0.02:

            st.success(
                "Annual outlook improved by "
                f"{annual_change * 100:,.1f} percentage "
                "points across the displayed history."
            )

        elif annual_change < -0.02:

            st.warning(
                "Annual outlook declined by "
                f"{abs(annual_change) * 100:,.1f} "
                "percentage points across the displayed "
                "history."
            )

        else:

            st.info(
                "Annual outlook remained broadly stable "
                "across the displayed history."
            )

else:

    st.info(
        "AnnualForecastRatio is not available "
        "in the monitoring dataset."
    )


# --------------------------------------------------
# CHART 3: LOP FORECAST INDEX TREND
# --------------------------------------------------

st.markdown(
    "### 3. Life-of-Project Forecast Index Trend"
)


if "LoPForecastRatio" in trend_history.columns:

    lop_forecast_chart, lop_chart_data = (
        create_forecast_index_chart(
            dataframe=trend_history,
            value_column="LoPForecastRatio",
            chart_title="LoP Forecast Index",
            line_color="#7030A0"
        )
    )


    if lop_chart_data.empty:

        st.info(
            "LoP forecast-index values are not "
            "available for this indicator."
        )

    else:

        st.plotly_chart(
            lop_forecast_chart,
            use_container_width=True
        )


        first_lop_value = (
            lop_chart_data[
                "LoPForecastRatio"
            ].iloc[0]
        )

        latest_lop_value = (
            lop_chart_data[
                "LoPForecastRatio"
            ].iloc[-1]
        )

        lop_change = (
            latest_lop_value
            - first_lop_value
        )


        st.caption(
            "The LoP forecast index estimates the share "
            "of the life-of-project target likely to be "
            "achieved if the observed cumulative pace "
            "continues."
        )


        if lop_change > 0.02:

            st.success(
                "Life-of-project outlook improved by "
                f"{lop_change * 100:,.1f} percentage "
                "points across the displayed history."
            )

        elif lop_change < -0.02:

            st.warning(
                "Life-of-project outlook declined by "
                f"{abs(lop_change) * 100:,.1f} "
                "percentage points across the displayed "
                "history."
            )

        else:

            st.info(
                "Life-of-project outlook remained "
                "broadly stable across the displayed "
                "history."
            )

else:

    st.info(
        "LoPForecastRatio is not available "
        "in the monitoring dataset."
    )


st.markdown(
    """
    <div class="method-note">
    <strong>How to read the forecast-index charts:</strong><br>
    A value of 100% indicates the current pace is aligned
    with full target achievement. Values from 80% to below
    100% are classified as At Risk. Values below 80% are
    classified as Off Track. These are pace-based
    monitoring indices and require contextual review.
    </div>
    """,
    unsafe_allow_html=True
)

'''

updated_code = (
    before_section
    + new_trend_section
    + end_marker
    + after_section
)

indicator_page.write_text(
    updated_code,
    encoding="utf-8"
)

print(
    "Indicator Dashboard trend section replaced."
)
