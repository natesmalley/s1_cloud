import streamlit as st
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from models import Question, Response, User, db
import json
from app import create_app

# Create Flask app instance
flask_app = create_app()

def apply_custom_css():
    st.markdown('''
        <style>
        /* SentinelOne Colors */
        :root {
            --s1-purple: #5046E4;
            --s1-dark-blue: #1B1B27;
            --s1-light-gray: #F5F5F7;
        }
        
        /* Main elements */
        .stApp {
            background-color: var(--s1-dark-blue);
        }
        
        .stTitle {
            color: white !important;
        }
        
        /* Buttons */
        .stButton > button {
            background-color: var(--s1-purple);
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
        }
        
        .stButton > button:hover {
            background-color: #6357FF;
        }
        
        /* Checkboxes */
        .stCheckbox > label {
            color: white !important;
        }
        
        .stCheckbox > div[role="checkbox"] {
            border-color: var(--s1-purple) !important;
        }
        
        .stCheckbox > div[role="checkbox"][aria-checked="true"] {
            background-color: var(--s1-purple) !important;
        }
        
        /* Progress bar */
        .stProgress > div > div > div {
            background-color: var(--s1-purple);
        }
        
        /* Messages */
        .stAlert {
            background-color: rgba(80, 70, 228, 0.1);
            border-color: var(--s1-purple);
        }

        /* Description text */
        small {
            color: var(--bs-gray-400);
        }
        </style>
    ''', unsafe_allow_html=True)

st.set_page_config(
    page_title="Cloud Security Roadmap Guide",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
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
    with flask_app.app_context():
        try:
            if 'user_id' not in st.session_state:
                return 0
            
            total_questions = Question.query.count()
            if total_questions == 0:
                return 0
                
            answered_questions = Response.query.filter_by(
                user_id=st.session_state.user_id,
                is_valid=True
            ).count()
            
            return (answered_questions / total_questions) * 100
        except Exception as e:
            st.error(f"Error calculating progress: {str(e)}")
            return 0

def save_answer(selected_initiatives):
    """Save the answer to database"""
    with flask_app.app_context():
        try:
            # First verify user exists
            user = User.query.get(st.session_state.user_id)
            if not user:
                return False, "User not found"

            # Now save the response
            response = Response.query.filter_by(
                user_id=st.session_state.user_id,
                question_id=1
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
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to save answer: {str(e)}"

def show_questionnaire():
    st.header('Strategic Assessment Questionnaire')
    st.markdown('---')  # Divider
    
    st.write('### Please select your top Business Initiatives in Cloud Security (select 1-3)')
    
    initiatives = [
        {
            'title': 'Cloud Adoption and Business Alignment',
            'description': 'Ensure cloud adoption supports overall business objectives by leveraging SentinelOne\'s Unified Visibility and Secrets Scanning.'
        },
        {
            'title': 'Achieving Key Business Outcomes',
            'description': 'Use SentinelOne\'s Offensive Security Engine to drive business outcomes by proactively identifying and mitigating risks.'
        },
        {
            'title': 'Maximizing ROI for Cloud Security',
            'description': 'Optimize return on investment with SentinelOne\'s AI-Powered Threat Detection and Response.'
        },
        {
            'title': 'Integration of Cloud Security with Business Strategy',
            'description': 'Align cloud security goals with broader IT and business strategies using SentinelOne\'s Unified Platform.'
        },
        {
            'title': 'Driving Innovation and Value Delivery',
            'description': 'Leverage SentinelOne\'s Offensive Security Engine to enable innovation while reducing vulnerabilities.'
        },
        {
            'title': 'Supporting Digital Transformation',
            'description': 'Enhance digital transformation initiatives using SentinelOne\'s Agentless and Agent-Based Capabilities.'
        },
        {
            'title': 'Balancing Rapid Adoption with Compliance',
            'description': 'Maintain security compliance using SentinelOne\'s Secrets Scanning and Cloud Workload Security.'
        }
    ]
    
    selected_initiatives = []
    
    # Get previously selected initiatives from the database
    with flask_app.app_context():
        try:
            response = Response.query.filter_by(
                user_id=st.session_state.user_id,
                question_id=1
            ).first()
            saved_initiatives = json.loads(response.answer) if response else []
        except Exception:
            saved_initiatives = []

    for initiative in initiatives:
        is_selected = initiative['title'] in saved_initiatives
        is_disabled = len(selected_initiatives) >= 3 and not is_selected
        
        col1, col2 = st.columns([0.1, 0.9])
        with col1:
            # Fix: Remove the empty string and use only the label parameter
            if st.checkbox(label=initiative['title'], 
                         value=is_selected,
                         disabled=is_disabled,
                         key=f"cb_{initiative['title']}"):
                selected_initiatives.append(initiative['title'])
        with col2:
            st.markdown(f"**{initiative['title']}**")
            st.markdown(f"<small>{initiative['description']}</small>", unsafe_allow_html=True)
    
    # Add a container for the selection count
    if len(selected_initiatives) > 0:
        st.success(f'Selected {len(selected_initiatives)} of 3 maximum options')
    else:
        st.warning('Please select at least one option')
    
    # Save answers when changes occur
    if selected_initiatives:
        save_success, save_error = save_answer(selected_initiatives)
        if not save_success:
            st.error(save_error)

    # Show current progress
    progress = calculate_progress()
    st.sidebar.header('Progress')
    st.sidebar.progress(progress / 100)
    st.sidebar.write(f'{progress:.0f}% Complete')

def main():
    apply_custom_css()
    
    # Update logo handling
    col1, col2 = st.columns([0.1, 0.9])
    with col1:
        try:
            st.image('paladin _inPixio.png', width=80)
        except Exception as e:
            st.write("S1")  # Fallback text if image fails to load
    with col2:
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
