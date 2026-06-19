import streamlit as st

def load_theme():

    st.markdown("""
    <style>
[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stToolbar"] {
    visibility: hidden;
}                



    .block-container {
        padding-top: 2rem !important;
    }
        .main {
        background-color: #FFF8F2;
    }

    .stApp {
        background: linear-gradient(
            135deg,
            #fff7ed 0%,
            #fffbeb 100%
        );
    }

    h1 {
        color: #ea580c !important;
        text-align: center;
        font-weight: 800;
    }

    h2,h3 {
        color: #c2410c !important;
    }

    .hero-box {
        background: white;
        padding: 25px;
        border-radius: 20px;
        text-align: center;
        box-shadow: 0px 4px 20px rgba(0,0,0,0.08);
        margin-bottom: 20px;
    }

    .feature-card {
        background: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.06);
        margin-bottom: 15px;
    }

    .stButton>button {
        width: 100%;
        border-radius: 12px;
        font-weight: bold;
        border: none;
    }

    .stTabs [data-baseweb="tab"] {
        font-size: 16px;
        font-weight: bold;
    }

    </style>
    """, unsafe_allow_html=True)