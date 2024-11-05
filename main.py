import streamlit as st
import streamlit_oauth
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from models import Question, Response, User, db
import json

st.set_page_config(
    page_title="Cloud Security Roadmap Guide",
    page_icon="🛡️",
    layout="wide",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': 'Cloud Security Roadmap Guide'
    }
)

def validate_answer(selected_initiatives):
    """Validate the selected initiatives"""
    if not selected_initiatives:
        return False, "Please select at least one option"
    if len(selected_initiatives) > 3:
        return False, "Please select no more than 3 options"
    return True, None

def calculate_progress():
    """Calculate user's progress through the questionnaire"""
    if 'answers' not in st.session_state:
        return 0
    total_questions = 1  # Currently we only have one question
    answered_questions = 1 if st.session_state.answers else 0
    return (answered_questions / total_questions) * 100

def save_answer(selected_initiatives):
    """Save the answer to session state and database"""
    if 'answers' not in st.session_state:
        st.session_state.answers = {}
    st.session_state.answers['initiatives'] = selected_initiatives
    
    if 'user_id' in st.session_state:
        try:
            response = Response.query.filter_by(
                user_id=st.session_state.user_id,
                question_id=1  # First question
            ).first()
            
            if response:
                response.answer = json.dumps(selected_initiatives)
            else:
                response = Response(
                    user_id=st.session_state.user_id,
                    question_id=1,
                    answer=json.dumps(selected_initiatives),
                    is_valid=True
                )
                db.session.add(response)
            
            db.session.commit()
        except Exception as e:
            st.error(f"Failed to save answer: {str(e)}")

def show_questionnaire():
    st.header('Strategic Assessment Questionnaire')
    
    # Get previously saved answers
    current_selections = st.session_state.answers.get('initiatives', []) if 'answers' in st.session_state else []
    
    # Create multiselect for initiatives
    selected_initiatives = st.multiselect(
        'Please select your top Business Initiatives in Cloud Security (select 1-3)',
        options=[
            'Cloud Adoption and Business Alignment',
            'Achieving Key Business Outcomes',
            'Maximizing ROI for Cloud Security',
            'Integration of Cloud Security with Business Strategy',
            'Driving Innovation and Value Delivery',
            'Supporting Digital Transformation',
            'Balancing Rapid Adoption with Compliance'
        ],
        default=current_selections,
        max_selections=3
    )
    
    # Validate and save answer
    is_valid, message = validate_answer(selected_initiatives)
    if selected_initiatives:
        if is_valid:
            save_answer(selected_initiatives)
            progress = calculate_progress()
            st.progress(progress / 100)
            st.success(f'Selected {len(selected_initiatives)} of 3 maximum options')
        else:
            st.error(message)
    else:
        st.error('Please select at least one option')

    # Show current progress
    progress = calculate_progress()
    st.sidebar.header('Progress')
    st.sidebar.progress(progress / 100)
    st.sidebar.write(f'{progress:.0f}% Complete')

def main():
    st.title('Cloud Security Roadmap Guide')
    
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        
    if not st.session_state.authenticated:
        oauth_button = st.button('Sign in with Google')
        if oauth_button:
            # Handle OAuth flow
            st.session_state.authenticated = True
            st.session_state.user_id = 1  # For testing, we'll use a fixed user ID
    else:
        show_questionnaire()

if __name__ == '__main__':
    # Set Streamlit to run on port 5000
    import sys
    if len(sys.argv) == 1:
        sys.argv.extend(["run", "--server.port=5000", "--server.address=0.0.0.0"])
    main()
