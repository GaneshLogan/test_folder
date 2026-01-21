import pathlib

import altair as alt
import pandas as pd
import streamlit as st

try:
    from wordcloud import STOPWORDS, WordCloud
except ImportError:  # pragma: no cover - runtime install for local envs
    import subprocess
    import sys

    subprocess.check_call([sys.executable, "-m", "pip", "install", "wordcloud"])
    from wordcloud import STOPWORDS, WordCloud

st.set_page_config(page_title="SIA Review Pulse", layout="wide")


DATA_PATH = pathlib.Path(__file__).parent / "data" / "singapore_airlines_reviews.csv"


@st.cache_data(show_spinner=False)
def load_reviews(path: pathlib.Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["published_date"] = (
        pd.to_datetime(df["published_date"], errors="coerce", utc=True)
        .dt.tz_convert(None)
    )
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df["helpful_votes"] = pd.to_numeric(df["helpful_votes"], errors="coerce").fillna(0)
    df["published_platform"] = df["published_platform"].fillna("Unknown")
    df["type"] = df["type"].fillna("Unknown")
    return df


st.title("SIA Review Pulse")
st.markdown("Explore Singapore Airlines reviews with filters, summary stats, and trends.")

data = load_reviews(DATA_PATH)

with st.sidebar:
    st.header("Filters")
    min_date = data["published_date"].min()
    max_date = data["published_date"].max()
    default_start = max_date - pd.DateOffset(months=12)
    start_default = max(min_date, default_start).date()
    start_date_input = st.date_input(
        "Start date",
        value=start_default,
        min_value=min_date.date(),
        max_value=max_date.date(),
    )
    end_date_input = st.date_input(
        "End date",
        value=max_date.date(),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )
    platforms = sorted(data["published_platform"].dropna().unique().tolist())
    selected_platforms = st.multiselect(
        "Platform",
        options=platforms,
        default=platforms,
    )
    review_types = sorted(data["type"].dropna().unique().tolist())
    selected_types = st.multiselect(
        "Review type",
        options=review_types,
        default=review_types,
    )
    rating_min, rating_max = int(data["rating"].min()), int(data["rating"].max())
    rating_range = st.slider(
        "Rating range",
        min_value=rating_min,
        max_value=rating_max,
        value=(rating_min, rating_max),
    )

start_date, end_date = pd.to_datetime(start_date_input), pd.to_datetime(end_date_input)
if start_date > end_date:
    start_date, end_date = end_date, start_date
    with st.sidebar:
        st.caption("Swapped dates so Start is before End.")
filtered = data[
    (data["published_date"] >= start_date)
    & (data["published_date"] <= end_date)
    & (data["published_platform"].isin(selected_platforms))
    & (data["type"].isin(selected_types))
    & (data["rating"].between(rating_range[0], rating_range[1]))
].copy()

total_reviews = len(filtered)
avg_rating = filtered["rating"].mean()
median_helpful = filtered["helpful_votes"].median()
positive_share = (
    filtered[filtered["rating"].isin([4, 5])].shape[0] / total_reviews * 100
    if total_reviews
    else 0
)
negative_share = (
    filtered[filtered["rating"].isin([1, 2])].shape[0] / total_reviews * 100
    if total_reviews
    else 0
)

summary_text = (
    f"Filtered summary: {total_reviews:,} reviews, "
    f"average rating {avg_rating:.2f}. "
    f"Positive reviews (4-5): {positive_share:.1f}%, "
    f"negative reviews (1-2): {negative_share:.1f}%."
    if total_reviews
    else "Filtered summary: 0 reviews for the selected filters."
)
st.markdown(
    f"""
<div style="
    display:inline-block;
    padding:0.35rem 0.6rem;
    border-radius:999px;
    background-color:#6d28d9;
    color:#ffffff;
    font-size:0.9rem;
    font-weight:600;">
  {summary_text}
</div>
""",
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
col1.metric("Reviews", f"{total_reviews:,}")
col2.metric("Average rating", f"{avg_rating:.2f}" if total_reviews else "N/A")
col3.metric("Median helpful votes", f"{median_helpful:.0f}" if total_reviews else "N/A")

left, right = st.columns((2, 1))

with left:
    rating_counts = (
        filtered.groupby("rating", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("rating")
    )
    rating_chart = (
        alt.Chart(rating_counts)
        .mark_bar(color="#2F6690")
        .encode(
            x=alt.X("rating:O", title="Rating"),
            y=alt.Y("count:Q", title="Number of reviews"),
            tooltip=["rating:O", "count:Q"],
        )
        .properties(title="Rating distribution")
    )
    st.altair_chart(rating_chart, use_container_width=True)

with right:
    platform_counts = (
        filtered.groupby("published_platform", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    platform_chart = (
        alt.Chart(platform_counts)
        .mark_bar(color="#F6AE2D")
        .encode(
            y=alt.Y("published_platform:N", sort="-x", title=None),
            x=alt.X("count:Q", title="Reviews"),
            tooltip=["published_platform:N", "count:Q"],
        )
        .properties(title="Reviews by platform")
    )
    st.altair_chart(platform_chart, use_container_width=True)

trend = (
    filtered.dropna(subset=["published_date"])
    .set_index("published_date")
    .resample("M")
    .size()
    .reset_index(name="count")
)
trend_chart = (
    alt.Chart(trend)
    .mark_line(point=True, color="#1B998B")
    .encode(
        x=alt.X("published_date:T", title="Month"),
        y=alt.Y("count:Q", title="Reviews"),
        tooltip=[
            alt.Tooltip("published_date:T", title="Month"),
            alt.Tooltip("count:Q", title="Reviews"),
        ],
    )
    .properties(title="Review volume over time")
)
st.altair_chart(trend_chart, use_container_width=True)

st.subheader("Sample reviews")
st.dataframe(
    filtered[
        ["published_date", "rating", "title", "text", "type", "published_platform"]
    ].sort_values("published_date", ascending=False),
    use_container_width=True,
    height=320,
)

st.subheader("Positive review keywords (ratings 4-5)")
positive_text = " ".join(
    filtered[filtered["rating"].isin([4, 5])]["text"].dropna().astype(str).tolist()
)
stopwords = set(STOPWORDS).union(
    {
        "airline",
        "flight",
        "flights",
        "plane",
        "airlines",
        "seat",
        "seats",
        "crew",
        "singapore",
        "air",
        "sia",
        "singaporeairlines",
    }
)
positive_wc = WordCloud(
    width=900, height=450, background_color="white", stopwords=stopwords
).generate(positive_text or "No data")
st.image(positive_wc.to_array(), use_container_width=True)

st.subheader("Negative review keywords (ratings 1-2)")
negative_text = " ".join(
    filtered[filtered["rating"].isin([1, 2])]["text"].dropna().astype(str).tolist()
)
negative_wc = WordCloud(
    width=900, height=450, background_color="white", stopwords=stopwords
).generate(negative_text or "No data")
st.image(negative_wc.to_array(), use_container_width=True)
