"""
Streamlit UI Components Template for AI Extraction Pipeline

This template provides upload, review, and save components.
Customize the review form fields for your extraction schema.
"""

import streamlit as st
from pathlib import Path
import tempfile

# Import your extraction engine
# from ai_engine import extract_from_file, process_extracted_data, ExtractionResult


# =============================================================================
# CONFIGURATION
# =============================================================================

ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "gif", "pdf", "mp3", "wav", "m4a"]
MAX_FILE_SIZE_MB = 10


# =============================================================================
# FILE UPLOAD COMPONENT
# =============================================================================

def render_file_uploader(key: str = "file_upload") -> tuple[str, str] | tuple[None, None]:
    """
    Render file upload component.

    Returns:
        Tuple of (temp_file_path, original_filename) or (None, None) if no file.
    """
    uploaded_file = st.file_uploader(
        "Upload file",
        type=ALLOWED_EXTENSIONS,
        help=f"Supported: {', '.join(ALLOWED_EXTENSIONS)}. Max {MAX_FILE_SIZE_MB}MB.",
        key=key
    )

    if uploaded_file is None:
        return None, None

    # Check file size
    if uploaded_file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
        st.error(f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB.")
        return None, None

    # Save to temp file
    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        return tmp.name, uploaded_file.name


# =============================================================================
# EXTRACTION WITH PROGRESS
# =============================================================================

def run_extraction_with_progress(file_path: str, extract_func):
    """
    Run extraction with a progress spinner.

    Args:
        file_path: Path to the file to extract from
        extract_func: The extraction function to call

    Returns:
        ExtractionResult
    """
    with st.spinner("Analyzing file with AI..."):
        result = extract_func(file_path)
    return result


# =============================================================================
# REVIEW FORM COMPONENT
# =============================================================================

def render_review_form(
    extracted_data: dict,
    on_save: callable,
    on_cancel: callable = None,
    form_key: str = "review_form"
):
    """
    Render the review form with pre-populated extracted data.

    CUSTOMIZE THIS FOR YOUR SCHEMA.

    Args:
        extracted_data: Dictionary of extracted fields
        on_save: Callback function when user saves (receives form_data dict)
        on_cancel: Optional callback when user cancels
        form_key: Unique key for the form
    """
    st.subheader("Review Extracted Data")
    st.caption("Please verify and correct any errors before saving.")

    with st.form(form_key):
        # =================================================================
        # CUSTOMIZE THESE FIELDS FOR YOUR SCHEMA
        # =================================================================

        # Example: Text field
        field1 = st.text_input(
            "Field 1 *",
            value=extracted_data.get("field1", ""),
            help="Description of field 1"
        )

        # Example: Number field
        field2 = st.number_input(
            "Field 2",
            value=float(extracted_data.get("field2", 0) or 0),
            min_value=0.0,
            format="%.2f"
        )

        # Example: Date field
        field3_value = extracted_data.get("field3")
        if field3_value:
            from datetime import datetime
            try:
                field3_default = datetime.strptime(field3_value, "%Y-%m-%d").date()
            except:
                field3_default = None
        else:
            field3_default = None

        field3 = st.date_input(
            "Field 3 (Date)",
            value=field3_default
        )

        # Example: Select/Enum field
        category_options = ["Option1", "Option2", "Option3", "Other"]
        category_default = extracted_data.get("category", "Other")
        if category_default not in category_options:
            category_default = "Other"

        category = st.selectbox(
            "Category",
            options=category_options,
            index=category_options.index(category_default)
        )

        # Example: Text area for notes
        notes = st.text_area(
            "Notes",
            value=extracted_data.get("notes", ""),
            height=100
        )

        # =================================================================
        # END CUSTOMIZATION
        # =================================================================

        # Form buttons
        col1, col2 = st.columns(2)

        with col1:
            submitted = st.form_submit_button("Save", type="primary", use_container_width=True)

        with col2:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

        if submitted:
            # Validate required fields
            if not field1:
                st.error("Field 1 is required")
            else:
                # Build form data
                form_data = {
                    "field1": field1,
                    "field2": field2,
                    "field3": field3,
                    "category": category,
                    "notes": notes,
                }
                on_save(form_data)

        if cancelled and on_cancel:
            on_cancel()


# =============================================================================
# ERROR DISPLAY
# =============================================================================

def render_extraction_error(error_message: str, file_path: str = None):
    """Display extraction error with helpful guidance."""
    st.error(f"Extraction failed: {error_message}")

    with st.expander("What can I do?"):
        st.markdown("""
        **Common solutions:**
        - Ensure the file is not corrupted
        - For images: ensure text is clearly visible
        - For audio: ensure speech is clear and audible
        - Try a different file format
        - If the problem persists, use manual entry
        """)

    # Offer manual entry
    if st.button("Enter manually instead"):
        st.session_state["manual_entry"] = True
        st.rerun()


# =============================================================================
# EXTRACTION METADATA DISPLAY
# =============================================================================

def render_extraction_metadata(result, show_details: bool = False):
    """Display extraction metadata (tokens, cost, time)."""
    if show_details:
        col1, col2, col3 = st.columns(3)
        col1.caption(f"Time: {result.extraction_time_ms:.0f}ms")
        col2.caption(f"Tokens: {result.input_tokens} in / {result.output_tokens} out")
        col3.caption(f"Cost: ${result.cost_usd:.4f}")
    else:
        st.caption(f"Extracted in {result.extraction_time_ms:.0f}ms")


# =============================================================================
# RATE LIMIT DISPLAY
# =============================================================================

def render_rate_limit_status(remaining: int, limit: int):
    """Display rate limit status."""
    if remaining <= 0:
        st.warning(f"Daily extraction limit reached ({limit}/{limit}). Use manual entry or try again tomorrow.")
    elif remaining <= 5:
        st.info(f"Extractions remaining today: {remaining}/{limit}")
    else:
        st.caption(f"AI extractions: {limit - remaining}/{limit} used today")


# =============================================================================
# COMPLETE EXTRACTION FLOW
# =============================================================================

def render_extraction_flow(
    extract_func: callable,
    save_func: callable,
    can_extract_func: callable,
    increment_func: callable,
    user_id: str
):
    """
    Render the complete extraction flow: upload → extract → review → save.

    Args:
        extract_func: Function to extract data from file
        save_func: Function to save form data to database
        can_extract_func: Function to check rate limit (returns tuple[bool, int])
        increment_func: Function to increment extraction count
        user_id: Current user identifier
    """
    # Check rate limit
    allowed, remaining = can_extract_func(user_id)

    if not allowed:
        render_rate_limit_status(0, remaining)
        st.info("You can still add items manually.")
        # Show manual form here if desired
        return

    render_rate_limit_status(remaining, remaining + (20 - remaining))  # Adjust for your limit

    # File upload
    file_path, filename = render_file_uploader()

    if file_path:
        st.success(f"Uploaded: {filename}")

        # Extract button
        if st.button("Extract with AI", type="primary"):
            # Increment usage first
            if not increment_func(user_id):
                st.error("Rate limit reached")
                return

            # Run extraction
            result = run_extraction_with_progress(file_path, extract_func)

            if result.error:
                render_extraction_error(result.error, file_path)
            else:
                # Store result in session state
                st.session_state["extraction_result"] = result
                st.session_state["extracted_data"] = result.data
                st.rerun()

    # Show review form if we have extracted data
    if "extracted_data" in st.session_state:
        result = st.session_state.get("extraction_result")
        if result:
            render_extraction_metadata(result)

        def on_save(form_data):
            save_func(form_data)
            # Clear session state
            del st.session_state["extracted_data"]
            if "extraction_result" in st.session_state:
                del st.session_state["extraction_result"]
            st.success("Saved successfully!")
            st.rerun()

        def on_cancel():
            del st.session_state["extracted_data"]
            if "extraction_result" in st.session_state:
                del st.session_state["extraction_result"]
            st.rerun()

        render_review_form(
            st.session_state["extracted_data"],
            on_save=on_save,
            on_cancel=on_cancel
        )
