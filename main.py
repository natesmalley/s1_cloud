import streamlit as st
from models import Question, Response, User, db
import json
from app import create_app
from init_db import clear_and_init_db
import logging
import sys

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
            # Verify the question exists
            question = Question.query.get(1)
            if not question:
                return False, "Question not found"
            
            # Create test user if needed
            user = User.query.get(st.session_state.user_id)
            if not user:
                user = User(
                    id=st.session_state.user_id,
                    username="Test User",
                    email="test@example.com"
                )
                db.session.add(user)
                db.session.commit()
            
            # Save response
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
                    answer=json.dumps(selected_initiatives)
                )
                db.session.add(response)
            
            db.session.commit()
            return True, None
            
        except Exception as e:
            logger.error(f"Error saving answer: {str(e)}")
            db.session.rollback()
            return False, str(e)

def show_strategic_goals():
    st.write('### Please select your top Business Initiatives in Cloud Security (select 1-3)')
    
    with flask_app.app_context():
        question = Question.query.get(1)
        if not question:
            st.error("Failed to load strategic goals question")
            return
            
        response = Response.query.filter_by(
            user_id=st.session_state.user_id,
            question_id=1
        ).first()
        
        selected_initiatives = []
        for option in question.options:
            if st.checkbox(
                option['title'],
                help=option['description'],
                key=f"strategic_opt_{option['title']}"
            ):
                selected_initiatives.append(option['title'])
        
        if selected_initiatives:
            is_valid, message = validate_answer(selected_initiatives)
            if is_valid:
                success, error = save_answer(selected_initiatives)
                if not success:
                    st.error(f"Failed to save answer: {error}")
            else:
                st.warning(message)

def show_questionnaire():
    st.header('Strategic Assessment Questionnaire')
    st.markdown('---')
    
    with flask_app.app_context():
        strategic_response = Response.query.filter_by(
            user_id=st.session_state.user_id,
            question_id=1
        ).first()
        
        if not strategic_response:
            show_strategic_goals()
        else:
            selected_goals = json.loads(strategic_response.answer)
            st.write("### Selected Business Initiatives:")
            for goal in selected_goals:
                st.write(f"- {goal}")
            st.markdown("---")
            
            questions = Question.query.filter(
                Question.parent_answer.in_(selected_goals)
            ).order_by(Question.order).all()
            
            for question in questions:
                st.subheader(question.text)
                response = Response.query.filter_by(
                    user_id=st.session_state.user_id,
                    question_id=question.id
                ).first()
                
                current_answer = json.loads(response.answer) if response and response.answer else []
                
                for i, option in enumerate(question.options):
                    key = f"q{question.id}_opt{i}"
                    if st.checkbox(
                        option['title'],
                        value=option['title'] in current_answer,
                        help=option['description'],
                        key=key
                    ):
                        if question.id not in [r.question_id for r in Response.query.filter_by(user_id=st.session_state.user_id).all()]:
                            save_answer([option['title']])

def main():
    # Initialize session state
    if 'user_id' not in st.session_state:
        st.session_state.user_id = 1  # Using a default user ID for testing
    
    # Show questionnaire
    show_questionnaire()

if __name__ == '__main__':
    with flask_app.app_context():
        try:
            clear_and_init_db()  # Clear and reinitialize database
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            st.error("Failed to initialize database. Please refresh the page.")
    
    # Start Streamlit on port 8080 to match Flask
    if len(sys.argv) == 1:
        sys.argv.extend(['run', '--server.port=8080', '--server.address=0.0.0.0'])
    main()
