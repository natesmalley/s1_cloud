import streamlit as st
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from models import Question, Response, User, db
import json
from app import create_app
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        </style>
    ''', unsafe_allow_html=True)

def validate_setup_form(recorder_name, recorder_email, customer_company, 
                       customer_name, customer_title, customer_email):
    """Validate the setup form inputs"""
    if not all([recorder_name, recorder_email, customer_company, 
                customer_name, customer_title, customer_email]):
        return False, "All fields are required"
    
    # Basic email validation
    if not '@' in recorder_email or not '@' in customer_email:
        return False, "Please enter valid email addresses"
        
    return True, None

def show_setup():
    st.header('Setup Information')
    
    with st.form("setup_form"):
        st.subheader("Recorder Information")
        recorder_name = st.text_input("Name *", key="recorder_name")
        recorder_email = st.text_input("Email *", key="recorder_email")
        
        st.subheader("Customer Information")
        customer_company = st.text_input("Company *", key="customer_company")
        customer_name = st.text_input("Name *", key="customer_name")
        customer_title = st.text_input("Title *", key="customer_title")
        customer_email = st.text_input("Email *", key="customer_email")
        
        submitted = st.form_submit_button("Save and Continue")
        
        if submitted:
            is_valid, error_message = validate_setup_form(
                recorder_name, recorder_email, customer_company,
                customer_name, customer_title, customer_email
            )
            
            if is_valid:
                with flask_app.app_context():
                    try:
                        user = User.query.get(st.session_state.user_id)
                        if user:
                            user.recorder_name = recorder_name
                            user.recorder_email = recorder_email
                            user.customer_company = customer_company
                            user.customer_name = customer_name
                            user.customer_title = customer_title
                            user.customer_email = customer_email
                            user.setup_completed = True
                            db.session.commit()
                            st.session_state.setup_completed = True
                            st.success("Setup completed successfully!")
                            st.rerun()
                        else:
                            st.error("User not found. Please try logging in again.")
                    except Exception as e:
                        logger.error(f"Error saving setup information: {str(e)}")
                        st.error(f"Error saving setup information: {str(e)}")
            else:
                st.error(error_message)

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
            logger.error(f"Error calculating progress: {str(e)}")
            return 0

def validate_answer(selected_initiatives):
    """Validate the selected initiatives"""
    if not selected_initiatives:
        return False, "Please select at least one option"
    if len(selected_initiatives) > 3:
        return False, "Please select no more than 3 options"
    return True, None

def save_answer(selected_initiatives):
    """Save the answer to database with validation"""
    with flask_app.app_context():
        try:
            # First validate the answer
            is_valid, validation_message = validate_answer(selected_initiatives)
            if not is_valid:
                return False, validation_message

            # Verify user exists
            user = User.query.get(st.session_state.user_id)
            if not user:
                return False, "User not found"

            # Save the response
            response = Response.query.filter_by(
                user_id=st.session_state.user_id,
                question_id=1
            ).first()
            
            if response:
                response.answer = json.dumps(selected_initiatives)
                response.is_valid = is_valid
                response.validation_message = validation_message
            else:
                response = Response(
                    user_id=st.session_state.user_id,
                    question_id=1,
                    answer=json.dumps(selected_initiatives),
                    is_valid=is_valid,
                    validation_message=validation_message
                )
                db.session.add(response)
            
            db.session.commit()
            
            # Update progress in session
            progress = calculate_progress()
            st.session_state.progress = progress
            
            return True, None
        except Exception as e:
            logger.error(f"Error saving answer: {str(e)}")
            db.session.rollback()
            return False, f"Failed to save answer: {str(e)}"

def show_questionnaire():
    st.header('Strategic Assessment Questionnaire')
    
    st.write('### Please select your top Business Initiatives in Cloud Security (select 1-3)')
    
    initiatives = [
        {
            'title': 'Cloud Adoption and Business Alignment',
            'description': 'Ensure cloud adoption supports overall business objectives by leveraging SentinelOne\'s Unified Visibility and Secrets Scanning.',
            'icon': '☁️'
        },
        {
            'title': 'Achieving Key Business Outcomes',
            'description': 'Use SentinelOne\'s Offensive Security Engine to drive business outcomes by proactively identifying and mitigating risks.',
            'icon': '🎯'
        },
        {
            'title': 'Maximizing ROI for Cloud Security',
            'description': 'Optimize return on investment with SentinelOne\'s AI-Powered Threat Detection and Response.',
            'icon': '💰'
        },
        {
            'title': 'Integration of Cloud Security with Business Strategy',
            'description': 'Align cloud security goals with broader IT and business strategies using SentinelOne\'s Unified Platform.',
            'icon': '🔄'
        },
        {
            'title': 'Driving Innovation and Value Delivery',
            'description': 'Leverage SentinelOne\'s Offensive Security Engine to enable innovation while reducing vulnerabilities.',
            'icon': '💡'
        },
        {
            'title': 'Supporting Digital Transformation',
            'description': 'Enhance digital transformation initiatives using SentinelOne\'s Agentless and Agent-Based Capabilities.',
            'icon': '🚀'
        },
        {
            'title': 'Balancing Rapid Adoption with Compliance',
            'description': 'Maintain security compliance using SentinelOne\'s Secrets Scanning and Cloud Workload Security.',
            'icon': '⚖️'
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
            if st.checkbox(
                label="",
                value=is_selected,
                disabled=is_disabled,
                key=f"cb_{initiative['title']}"
            ):
                selected_initiatives.append(initiative['title'])
        with col2:
            st.markdown(f'''
                <div style="padding: 10px; border-radius: 5px; background-color: rgba(80, 70, 228, 0.1);">
                    <div style="display: flex; align-items: center;">
                        <span style="font-size: 24px; margin-right: 10px;">{initiative['icon']}</span>
                        <div>
                            <strong style="color: white;">{initiative['title']}</strong>
                            <p style="margin: 5px 0 0 0; color: #aaa; font-size: 0.9em;">
                                {initiative['description']}
                            </p>
                        </div>
                    </div>
                </div>
            ''', unsafe_allow_html=True)
    
    if selected_initiatives:
        is_valid, validation_message = validate_answer(selected_initiatives)
        if is_valid:
            st.success(f'Selected {len(selected_initiatives)} of 3 maximum options')
            save_success, save_error = save_answer(selected_initiatives)
            if not save_success:
                st.error(save_error)
        else:
            st.warning(validation_message)
    else:
        st.warning('Please select at least one option')
    
    # Show progress
    progress = calculate_progress()
    st.sidebar.header('Progress')
    st.sidebar.progress(progress / 100)
    st.sidebar.write(f'{progress:.0f}% Complete')

def main():
    apply_custom_css()
    
    col1, col2 = st.columns([0.1, 0.9])
    with col1:
        try:
            st.image('paladin _inPixio.png', width=80)
        except Exception:
            st.write("S1")
    with col2:
        st.title('Cloud Security Roadmap Guide')
    
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        
    if not st.session_state.authenticated:
        if st.button('Sign in with Google'):
            st.session_state.authenticated = True
            st.session_state.user_id = 1  # For testing
            st.rerun()
    else:
        # Check if setup is completed
        if 'setup_completed' not in st.session_state:
            with flask_app.app_context():
                user = User.query.get(st.session_state.user_id)
                st.session_state.setup_completed = user.setup_completed if user else False
        
        if not st.session_state.setup_completed:
            show_setup()
        else:
            show_questionnaire()

if __name__ == '__main__':
    # Set Streamlit to run on port 5000
    import sys
    if len(sys.argv) == 1:
        sys.argv.extend(["run", "--server.port=5000", "--server.address=0.0.0.0"])
    main()
