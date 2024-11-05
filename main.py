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
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    ''', unsafe_allow_html=True)

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
            return True, None
        except Exception as e:
            logger.error(f"Error saving answer: {str(e)}")
            db.session.rollback()
            return False, f"Failed to save answer: {str(e)}"

def calculate_progress():
    """Calculate user's progress through the questionnaire"""
    with flask_app.app_context():
        try:
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
        
        if st.form_submit_button("Save and Continue"):
            if not all([recorder_name, recorder_email, customer_company, 
                       customer_name, customer_title, customer_email]):
                st.error("All fields are required")
                return
                
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

def show_questionnaire():
    st.header('Strategic Assessment Questionnaire')
    st.markdown('---')
    
    st.write('### Please select your top Business Initiatives in Cloud Security (select 1-3)')
    
    initiatives = [
        {
            'title': 'Cloud Adoption and Business Alignment',
            'description': 'Ensure cloud adoption is in line with the organization\'s overarching business objectives, providing a secure and compliant foundation for business activities.',
        },
        {
            'title': 'Achieving Key Business Outcomes',
            'description': 'Drive security practices that directly support business outcomes, ensuring risk mitigation efforts contribute positively to overall business performance.',
        },
        {
            'title': 'Maximizing ROI for Cloud Security',
            'description': 'Evaluate cloud security investments to maximize return on investment, ensuring that security measures are both effective and financially sustainable.',
        },
        {
            'title': 'Integration of Cloud Security with Business Strategy',
            'description': 'Integrate cloud security practices within the broader IT and business strategies to ensure cohesive growth, operational efficiency, and security posture.',
        },
        {
            'title': 'Driving Innovation and Value Delivery',
            'description': 'Facilitate secure innovation by embedding proactive risk management into cloud projects, enabling business opportunities while minimizing risk.',
        },
        {
            'title': 'Supporting Digital Transformation',
            'description': 'Leverage cloud security to support digital transformation initiatives, ensuring that new technologies and processes are securely adopted.',
        },
        {
            'title': 'Balancing Rapid Adoption with Compliance',
            'description': 'Achieve a balance between rapidly adopting cloud technologies and maintaining compliance, ensuring security does not hinder business agility.',
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
            if response and response.answer:
                saved_initiatives = json.loads(response.answer)
            else:
                saved_initiatives = []
        except Exception as e:
            logger.error(f"Error loading saved initiatives: {str(e)}")
            saved_initiatives = []

    for initiative in initiatives:
        is_selected = initiative['title'] in saved_initiatives
        is_disabled = len(selected_initiatives) >= 3 and not is_selected
        
        col1, col2, col3 = st.columns([0.1, 0.8, 0.1])
        with col1:
            if st.checkbox(
                label=initiative['title'],
                key=f"cb_{initiative['title']}",
                label_visibility="collapsed"
            ):
                selected_initiatives.append(initiative['title'])
        with col2:
            st.markdown(f'''
                <div style="display: flex; align-items: center;">
                    <strong>{initiative['title']}</strong>
                </div>
            ''', unsafe_allow_html=True)
        with col3:
            st.markdown(f'''
                <div class="tooltip">
                    <i class="fas fa-info-circle"></i>
                    <span class="tooltiptext">{initiative['description']}</span>
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
            st.image('paladin_inPixio.png', width=80)
        except Exception:
            st.write("S1")
    with col2:
        st.title('Cloud Security Roadmap Guide')
    
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        
    if not st.session_state.authenticated:
        if st.button('Sign in with Google'):
            with flask_app.app_context():
                # Create or get user
                user = User.query.filter_by(email="test@example.com").first()
                if not user:
                    user = User(
                        username="Test User",
                        email="test@example.com"
                    )
                    db.session.add(user)
                    db.session.commit()
                
                st.session_state.authenticated = True
                st.session_state.user_id = user.id
                st.rerun()
    else:
        # Check if setup is completed
        if 'setup_completed' not in st.session_state:
            with flask_app.app_context():
                user = User.query.filter_by(id=st.session_state.user_id).first()
                st.session_state.setup_completed = user.setup_completed if user else False
        
        if not st.session_state.setup_completed:
            show_setup()
        else:
            show_questionnaire()

if __name__ == '__main__':
    import sys
    from init_db import clear_and_init_db
    
    app = create_app()
    with app.app_context():
        # Initialize database first
        clear_and_init_db()
        
    # Then start Streamlit
    if len(sys.argv) == 1:
        sys.argv.extend(['run', '--server.port=5000', '--server.address=0.0.0.0'])
    main()
