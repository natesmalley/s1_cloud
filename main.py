import streamlit as st
from models import Question, Response, User, db
import json
from app import create_app
from init_db import clear_and_init_db
import logging
import sys
from flask import session

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
                logger.info("Creating a test user for session")
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

        # Show options as checkboxes
        selected_initiatives = []
        for option in question.options:
            if st.checkbox(
                option['title'],
                help=option['description'],
                key=f"strategic_opt_{option['title']}"
            ):
                selected_initiatives.append(option['title'])

        # Validate and save response
        if selected_initiatives:
            is_valid, message = validate_answer(selected_initiatives)
            if is_valid:
                success, error = save_answer(selected_initiatives)
                if success:
                    st.success("Your response has been saved successfully!")
                else:
                    st.error(f"Failed to save answer: {error}")
            else:
                st.warning(message)

def show_questionnaire():
    st.header('Strategic Assessment Questionnaire')
    st.markdown('---')

    with flask_app.app_context():
        # Retrieve user's response for the strategic goals
        strategic_response = Response.query.filter_by(
            user_id=st.session_state.user_id,
            question_id=1
        ).first()

        # Show the strategic goals question if not answered
        if not strategic_response:
            show_strategic_goals()
        else:
            # Display previously selected business initiatives
            selected_goals = json.loads(strategic_response.answer)
            st.write("### Selected Business Initiatives:")
            for goal in selected_goals:
                st.write(f"- {goal}")
            st.markdown("---")

            # Show follow-up questions based on the selected goals
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
                selected_options = []

                # Display each option as a checkbox
                for i, option in enumerate(question.options):
                    key = f"q{question.id}_opt{i}"
                    if st.checkbox(
                        option['title'],
                        value=option['title'] in current_answer,
                        help=option['description'],
                        key=key
                    ):
                        selected_options.append(option['title'])

                # Save follow-up question responses
                if selected_options:
                    success, error = save_answer(selected_options)
                    if success:
                        st.success(f"Your response for '{question.text}' has been saved.")
                    else:
                        st.error(f"Failed to save answer: {error}")

def main():
    # Initialize session state for user ID
    if 'user_id' not in st.session_state:
        st.session_state.user_id = 1  # This should be dynamically assigned in a real app

    # Show the questionnaire
    show_questionnaire()

if __name__ == '__main__':
    # Initialize the database
    with flask_app.app_context():
        try:
            clear_and_init_db()  # Clear and reinitialize the database
            logger.info("Database initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            st.error("Failed to initialize database. Please refresh the page.")

    # Start the Streamlit app
    if len(sys.argv) == 1:
        sys.argv.extend(['run', '--server.port=8080', '--server.address=0.0.0.0'])
    main()
