import streamlit as st

def apply_premium_ui():
    """
    Injects custom CSS to transform the Streamlit app layout into a card-based premium UI,
    while utilizing Streamlit's native CSS variables to flawlessly support the original color palette
    (Light/Dark mode compatible).
    """
    custom_css = """
    <style>
        /* Import Google Font */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        /* Global Typography tied to native Streamlit colors */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif !important;
            font-size: 1.25rem !important;
        }

        /* Glassmorphic Top Header using native background color with opacity */
        [data-testid="stHeader"] {
            background: rgba(var(--background-color-rgb), 0.7) !important;
            backdrop-filter: blur(10px) !important;
            -webkit-backdrop-filter: blur(10px) !important;
        }

        /* Remove default Streamlit top padding */
        .block-container, [data-testid="stAppViewBlockContainer"] {
            padding-top: 1rem !important;
        }

        /* Subtle Sidebar enhancement - keeping original colors but adding depth */
        [data-testid="stSidebar"] {
            border-right: 1px solid var(--secondary-background-color);
            box-shadow: 2px 0 10px rgba(0, 0, 0, 0.05);
        }

        /* Card-Based UI Classes utilizing native colors */
        .medical-card {
            background: var(--secondary-background-color);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
            border: 1px solid rgba(128, 128, 128, 0.1);
            margin-bottom: 1rem;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            color: var(--text-color);
        }
        
        .medical-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
        }
        
        .medical-card-title {
            color: var(--text-color);
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1rem;
            border-bottom: 1px solid rgba(128, 128, 128, 0.2);
            padding-bottom: 0.5rem;
        }
        
        /* Button Micro-animations - inheriting from Streamlit's primary buttons */
        div.stButton > button {
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        
        div.stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 10px rgba(var(--primary-color-rgb), 0.15);
        }

        /* DataFrame Structural Customization */
        [data-testid="stDataFrame"] > div {
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid rgba(128, 128, 128, 0.2);
        }
        
        /* Custom Divider adapting to background */
        hr {
            margin: 1.5rem 0 !important;
            border: 0;
            height: 1px;
            background: linear-gradient(to right, transparent, rgba(128, 128, 128, 0.2), transparent);
        }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)
