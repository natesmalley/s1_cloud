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

def show_strategic_goals():
    """Show the initial strategic goals question"""
    st.write('### Please select your top Business Initiatives in Cloud Security (select 1-3)')
    
    initiatives = [
        {
            'title': 'Cloud Adoption and Business Alignment',
            'description': 'Ensure cloud adoption supports overall business objectives.',
        },
        {
            'title': 'Achieving Key Business Outcomes',
            'description': 'Drive security practices that directly support business outcomes.',
        },
        {
            'title': 'Maximizing ROI for Cloud Security',
            'description': 'Evaluate cloud security investments to maximize return on investment.',
        },
        {
            'title': 'Integration of Cloud Security with Business Strategy',
            'description': 'Integrate cloud security practices within broader IT strategies.',
        },
        {
            'title': 'Driving Innovation and Value Delivery',
            'description': 'Facilitate secure innovation and risk management.',
        },
        {
            'title': 'Supporting Digital Transformation',
            'description': 'Support digital transformation initiatives securely.',
        },
        {
            'title': 'Balancing Rapid Adoption with Compliance',
            'description': 'Balance rapid cloud adoption with compliance requirements.',
        }
    ]
    
    selected_initiatives = []
    
    for initiative in initiatives:
        if st.checkbox(initiative['title'], help=initiative['description']):
            selected_initiatives.append(initiative['title'])
    
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

def show_questionnaire():
    st.header('Strategic Assessment Questionnaire')
    st.markdown('---')
    
    # Get user's response for strategic goals
    with flask_app.app_context():
        strategic_response = Response.query.filter_by(
            user_id=st.session_state.user_id,
            question_id=1
        ).first()
        
        if not strategic_response:
            show_strategic_goals()
        else:
            selected_goals = json.loads(strategic_response.answer)
            # Get questions for selected goals
            questions = Question.query.filter(
                Question.parent_answer.in_(selected_goals)
            ).order_by(Question.order).all()
            
            for question in questions:
                st.subheader(question.text)
                for option in question.options:
                    st.checkbox(
                        option['title'],
                        help=option['description']
                    )
    
    # Show progress
    progress = calculate_progress()
    st.sidebar.header('Progress')
    st.sidebar.progress(progress / 100)
    st.sidebar.write(f'{progress:.0f}% Complete')

def main():
    # Initialize session state for user authentication
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        # Create or get test user for development
        with flask_app.app_context():
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
