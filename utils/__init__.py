# utils/__init__.py
"""Utility functions for ResearchAI"""
import streamlit as st


def safe_link_button(label: str, url: str, **kwargs):
    """
    Wrapper for st.link_button that strips unsupported kwargs.
    Compatible across Streamlit versions.
    """
    kwargs.pop("key", None)
    return st.link_button(label, url, **kwargs)
